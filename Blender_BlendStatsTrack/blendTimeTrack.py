import bpy
import time
import json
import os
import sys
from bpy.app.handlers import persistent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RECENT_SESSIONS_LIMIT   = 20     # max individual session records to keep
RECENT_SESSION_MIN_SECS = 300    # 5 min — shorter saves are only added to daily totals

# ---------------------------------------------------------------------------
# OS focus detection
# ---------------------------------------------------------------------------

def is_blender_focused():
    """Return True if the Blender window is the current foreground application."""
    try:
        if sys.platform == "win32":
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if hwnd == 0:
                return False
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return "blender" in buf.value.lower()

        elif sys.platform == "darwin":
            try:
                from AppKit import NSWorkspace
                active = NSWorkspace.sharedWorkspace().activeApplication()
                return "blender" in active.get("NSApplicationName", "").lower()
            except ImportError:
                return True

        else:  # Linux
            try:
                import subprocess
                r = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=0.5
                )
                if r.returncode == 0:
                    return "blender" in r.stdout.lower()
            except Exception:
                pass
            try:
                import gi
                gi.require_version('Wnck', '3.0')
                from gi.repository import Wnck
                screen = Wnck.Screen.get_default()
                screen.force_update()
                win = screen.get_active_window()
                if win:
                    return "blender" in win.get_name().lower()
            except Exception:
                pass
            return True

    except Exception:
        return True


# ---------------------------------------------------------------------------
# Global in-memory tracking state
# ---------------------------------------------------------------------------
tracking_data = {
    "is_tracking":            False,
    "last_activity_time":     0,
    "session_start_time":     0,
    "last_update_time":       0,
    "idle_threshold":         60,   # seconds before counting as idle
    "modal_running":          False,
    # per-save-cycle accumulators
    "session_active_time":    0.0,
    "session_idle_time":      0.0,
    "session_unfocused_time": 0.0,
}

# ---------------------------------------------------------------------------
# Stats schema — stored as JSON inside the .blend file's StringProperty
# ---------------------------------------------------------------------------
EMPTY_STATS = {
    "total_time":           0,
    "total_idle_time":      0,
    "total_unfocused_time": 0,
    "save_count":           0,
    "first_opened":         0,
    "last_opened":          0,
    # daily[YYYY-MM-DD] = {active, idle, unfocused, saves}  — max 365 entries/year
    "daily":                {},
    # last N sessions with duration >= RECENT_SESSION_MIN_SECS
    "recent_sessions":      [],
}


def _empty_stats():
    s = dict(EMPTY_STATS)
    s["first_opened"] = time.time()
    s["last_opened"]  = time.time()
    s["daily"]        = {}
    s["recent_sessions"] = []
    return s


# ---------------------------------------------------------------------------
# Load / save  (blend file StringProperty, no external file)
# ---------------------------------------------------------------------------

def load_stats(scene=None):
    if scene is None:
        try:
            scene = bpy.context.scene
        except Exception:
            return _empty_stats()
    try:
        raw = scene.time_tracker_props.stats_json
        if raw:
            data = json.loads(raw)
            for k, v in EMPTY_STATS.items():
                data.setdefault(k, v if not isinstance(v, (dict, list)) else type(v)())
            return data
    except Exception:
        pass
    return _empty_stats()


def save_stats(stats, scene=None):
    if scene is None:
        try:
            scene = bpy.context.scene
        except Exception:
            return
    try:
        scene.time_tracker_props.stats_json = json.dumps(stats, separators=(',', ':'))
    except Exception as e:
        print(f"Stat Tracker: save_stats error – {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_time(seconds):
    seconds = max(0, int(seconds))
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    return " ".join(parts) if parts else "0m"


def _reset_session_counters():
    tracking_data["session_active_time"]    = 0.0
    tracking_data["session_idle_time"]      = 0.0
    tracking_data["session_unfocused_time"] = 0.0
    tracking_data["session_start_time"]     = time.time()
    tracking_data["last_update_time"]       = time.time()


def _migrate_old_json():
    """One-time: if an old _stats.json exists beside the blend, import it and rename it."""
    try:
        blend = bpy.data.filepath
        if not blend:
            return
        old_path = blend.replace(".blend", "_stats.json")
        if not os.path.exists(old_path):
            return
        stats = load_stats()
        if stats["save_count"] > 0:
            return  # already have data — don't overwrite
        with open(old_path, 'r') as f:
            old = json.load(f)
        stats["total_time"]   = old.get("total_time", 0)
        stats["save_count"]   = old.get("save_count", 0)
        stats["first_opened"] = old.get("first_opened", time.time())
        stats["last_opened"]  = old.get("last_opened",  time.time())
        for s in old.get("sessions", []):
            dur = s.get("duration", 0)
            ts  = s.get("timestamp", time.time())
            day = time.strftime('%Y-%m-%d', time.localtime(ts))
            d   = stats["daily"].setdefault(day, {"active":0,"idle":0,"unfocused":0,"saves":0})
            d["active"] += dur
            d["saves"]  += 1
            if dur >= RECENT_SESSION_MIN_SECS:
                stats["recent_sessions"].append({
                    "timestamp": ts, "date": day,
                    "duration": dur, "idle": 0, "unfocused": 0
                })
        stats["recent_sessions"] = sorted(
            stats["recent_sessions"], key=lambda x: x["timestamp"]
        )[-RECENT_SESSIONS_LIMIT:]
        save_stats(stats)
        os.rename(old_path, old_path + ".migrated")
        print("Stat Tracker: migrated old _stats.json into .blend file")
    except Exception as e:
        print(f"Stat Tracker: migration error – {e}")


# ---------------------------------------------------------------------------
# Core tick
# ---------------------------------------------------------------------------

def update_tracking():
    if not tracking_data["is_tracking"]:
        return
    try:
        now     = time.time()
        elapsed = now - tracking_data["last_update_time"]
        focused = is_blender_focused()
        is_idle = (now - tracking_data["last_activity_time"]) > tracking_data["idle_threshold"]

        if not focused:
            tracking_data["session_unfocused_time"] += elapsed
        elif is_idle:
            tracking_data["session_idle_time"] += elapsed
        else:
            tracking_data["session_active_time"] += elapsed
            try:
                bpy.context.scene.time_tracker_props.session_time += elapsed
            except Exception:
                pass

        tracking_data["last_update_time"] = now
    except Exception:
        pass


def register_activity():
    tracking_data["last_activity_time"] = time.time()
    if not tracking_data["is_tracking"]:
        tracking_data["is_tracking"]      = True
        tracking_data["last_update_time"] = time.time()


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@persistent
def on_load_post(dummy):
    try:
        stats = load_stats()
        if stats["first_opened"] == 0:
            stats["first_opened"] = time.time()
        stats["last_opened"] = time.time()
        save_stats(stats)

        tracking_data["is_tracking"]        = True
        tracking_data["last_activity_time"] = time.time()
        _reset_session_counters()

        try:
            bpy.context.scene.time_tracker_props.session_time = 0
        except Exception:
            pass

        if not tracking_data["modal_running"]:
            bpy.app.timers.register(start_modal_delayed, first_interval=1.0)

        bpy.app.timers.register(_migrate_old_json, first_interval=2.0)
    except Exception as e:
        print(f"Stat Tracker: on_load_post error – {e}")


@persistent
def on_save_post(dummy):
    try:
        update_tracking()

        scene = bpy.context.scene
        props = scene.time_tracker_props
        session_duration = props.session_time

        stats = load_stats(scene)
        stats["save_count"]           += 1
        stats["total_time"]           += session_duration
        stats["total_idle_time"]      += tracking_data["session_idle_time"]
        stats["total_unfocused_time"] += tracking_data["session_unfocused_time"]

        # ── Roll into daily bucket ────────────────────────────────────
        today = time.strftime('%Y-%m-%d')
        day   = stats["daily"].setdefault(today, {"active":0,"idle":0,"unfocused":0,"saves":0})
        day["active"]    += session_duration
        day["idle"]      += tracking_data["session_idle_time"]
        day["unfocused"] += tracking_data["session_unfocused_time"]
        day["saves"]     += 1

        # ── Keep recent notable sessions only ─────────────────────────
        if session_duration >= RECENT_SESSION_MIN_SECS:
            stats["recent_sessions"].append({
                "timestamp": time.time(),
                "date":      today,
                "duration":  session_duration,
                "idle":      tracking_data["session_idle_time"],
                "unfocused": tracking_data["session_unfocused_time"],
            })
            stats["recent_sessions"] = sorted(
                stats["recent_sessions"], key=lambda x: x["timestamp"]
            )[-RECENT_SESSIONS_LIMIT:]

        save_stats(stats, scene)
        props.session_time = 0
        _reset_session_counters()
        register_activity()

    except Exception as e:
        print(f"Stat Tracker: on_save_post error – {e}")


# ---------------------------------------------------------------------------
# Property group
# ---------------------------------------------------------------------------

class TimeTrackerProperties(bpy.types.PropertyGroup):
    session_time: bpy.props.FloatProperty(name="Session Time", default=0.0)
    # The entire stats dict lives here — travels with the .blend, no sidecar file
    stats_json:   bpy.props.StringProperty(name="Stats JSON", default="")


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class TIME_TRACKER_PT_panel(bpy.types.Panel):
    bl_label       = "Stat Tracker"
    bl_idname      = "TIME_TRACKER_PT_panel"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'Stat Tracker'

    def draw(self, context):
        layout = self.layout

        if not bpy.data.filepath:
            layout.label(text="Save file to start tracking", icon='ERROR')
            return

        stats          = load_stats()
        props          = context.scene.time_tracker_props
        current_active = props.session_time
        cur_idle       = tracking_data["session_idle_time"]
        cur_unfocused  = tracking_data["session_unfocused_time"]
        now            = time.time()
        total          = stats["total_time"] + current_active
        today_str      = time.strftime('%Y-%m-%d')
        daily          = stats.get("daily", {})
        recent         = stats.get("recent_sessions", [])

        # ── Current Session ───────────────────────────────────────────
        box = layout.box()
        box.label(text="Current Session:", icon='TIME')
        box.label(text=f"  Active:       {format_time(current_active)}")
        box.label(text=f"  Idle:         {format_time(cur_idle)}")
        box.label(text=f"  Unfocused:    {format_time(cur_unfocused)}")
        sess_elapsed = current_active + cur_idle + cur_unfocused
        if sess_elapsed > 0:
            box.label(text=f"  Focus Score:  {current_active / sess_elapsed * 100:.0f}%")

        focused  = is_blender_focused()
        idle_sec = now - tracking_data["last_activity_time"]
        if tracking_data["is_tracking"]:
            if not focused:
                box.label(text="  Status: Unfocused", icon='HIDE_ON')
            elif idle_sec > tracking_data["idle_threshold"]:
                box.label(text="  Status: Idle", icon='PAUSE')
            else:
                box.label(text="  Status: Active", icon='PLAY')
        else:
            box.label(text="  Status: Not Tracking", icon='CANCEL')

        if not tracking_data["modal_running"]:
            box.label(text="  Tracker: Stopped", icon='ERROR')
            box.operator("time_tracker.start_modal", text="Restart Tracker")

        # ── Today ─────────────────────────────────────────────────────
        today_data   = daily.get(today_str, {"active":0,"idle":0,"unfocused":0,"saves":0})
        today_active = today_data["active"] + current_active
        today_saves  = today_data["saves"]

        box = layout.box()
        box.label(text="Today:", icon='SORTTIME')
        box.label(text=f"  Active Time:  {format_time(today_active)}")
        box.label(text=f"  Saves:        {today_saves}")

        # Work streak
        streak     = 0
        prev_date  = time.strptime(today_str, '%Y-%m-%d')
        for d in sorted(daily.keys(), reverse=True):
            d_struct  = time.strptime(d, '%Y-%m-%d')
            days_diff = (time.mktime(prev_date) - time.mktime(d_struct)) / 86400
            if days_diff <= streak + 0.6 and daily[d].get("active", 0) > 0:
                streak    += 1
                prev_date  = d_struct
            elif days_diff > streak + 0.6:
                break
        box.label(text=f"  Work Streak:  {streak} day{'s' if streak != 1 else ''}")

        # ── Lifetime Totals ───────────────────────────────────────────
        t_idle      = stats.get("total_idle_time", 0)      + cur_idle
        t_unfocused = stats.get("total_unfocused_time", 0) + cur_unfocused

        box = layout.box()
        box.label(text="Lifetime Totals:", icon='PREVIEW_RANGE')
        box.label(text=f"  Active:       {format_time(total)}")
        box.label(text=f"  Idle:         {format_time(t_idle)}")
        box.label(text=f"  Unfocused:    {format_time(t_unfocused)}")
        box.label(text=f"  Total Saves:  {stats['save_count']}")

        # ── Productivity ──────────────────────────────────────────────
        box = layout.box()
        box.label(text="Productivity:", icon='GRAPH')

        total_clocked = total + t_idle + t_unfocused
        if total_clocked > 0:
            box.label(text=f"  Focus Ratio:  {total / total_clocked * 100:.1f}%")

        in_blender = total + t_idle
        if in_blender > 0:
            box.label(text=f"  Idle Ratio:   {t_idle / in_blender * 100:.1f}%")

        if stats["save_count"] > 1 and total > 0:
            box.label(text=f"  Avg/Save:     {format_time(total / stats['save_count'])}")

        days_worked = len([d for d, v in daily.items() if v.get("active", 0) > 0])
        if today_active > 0 and today_str not in daily:
            days_worked += 1

        if days_worked > 0:
            box.label(text=f"  Days Worked:  {days_worked}")
            box.label(text=f"  Avg/Day:      {format_time(total / days_worked)}")

        if daily:
            best_day, best_val = max(daily.items(), key=lambda x: x[1].get("active", 0))
            box.label(text=f"  Best Day:     {best_day} ({format_time(best_val['active'])})")

        last_7 = sum(
            v.get("active", 0) for d, v in daily.items()
            if (now - time.mktime(time.strptime(d, '%Y-%m-%d'))) < 7 * 86400
        ) + current_active
        box.label(text=f"  Last 7 Days:  {format_time(last_7)}")

        if recent:
            durations = [s["duration"] for s in recent]
            box.label(text=f"  Avg Session:  {format_time(sum(durations) / len(durations))}")
            box.label(text=f"  Best Session: {format_time(max(durations))}")

        # ── Recent Sessions ───────────────────────────────────────────
        if recent:
            box = layout.box()
            box.label(text=f"Recent Sessions (top {len(recent)}):", icon='RECOVER_LAST')
            for s in reversed(recent[-5:]):
                dur     = s["duration"]
                elapsed = dur + s.get("idle", 0) + s.get("unfocused", 0)
                focus   = dur / elapsed * 100 if elapsed > 0 else 0
                box.label(text=f"  {s['date']}  {format_time(dur)}  ({focus:.0f}% focus)")

        # ── Project Info ──────────────────────────────────────────────
        box = layout.box()
        box.label(text="Project Info:", icon='INFO')
        if stats["first_opened"]:
            box.label(text=f"  First Opened: {time.strftime('%Y-%m-%d', time.localtime(stats['first_opened']))}")
        if stats["last_opened"]:
            box.label(text=f"  Last Opened:  {time.strftime('%Y-%m-%d', time.localtime(stats['last_opened']))}")
        if stats["first_opened"]:
            box.label(text=f"  Project Age:  {format_time(now - stats['first_opened'])}")
        box.label(text="  Storage: inside .blend", icon='CHECKMARK')

        # ── Actions ───────────────────────────────────────────────────
        layout.separator()
        row = layout.row(align=True)
        row.operator("time_tracker.export_stats", icon='EXPORT', text="Export JSON")
        row.operator("time_tracker.import_stats", icon='IMPORT', text="Import JSON")
        layout.operator("time_tracker.reset_stats", icon='X', text="Reset All Stats")


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class TIME_TRACKER_OT_start_modal(bpy.types.Operator):
    bl_idname      = "time_tracker.start_modal"
    bl_label       = "Start Time Tracking"
    bl_description = "Manually start the time tracking modal"

    def execute(self, context):
        if not tracking_data["modal_running"]:
            try:
                bpy.ops.time_tracker.modal()
                self.report({'INFO'}, "Time tracking started")
            except Exception as e:
                self.report({'ERROR'}, f"Failed: {e}")
                return {'CANCELLED'}
        else:
            self.report({'INFO'}, "Already running")
        return {'FINISHED'}


class TIME_TRACKER_OT_export_stats(bpy.types.Operator):
    bl_idname      = "time_tracker.export_stats"
    bl_label       = "Export Statistics"
    bl_description = "Export stats to a JSON file"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filename: bpy.props.StringProperty(default="time_stats")

    def execute(self, context):
        stats = load_stats()
        stats['blend_file_name'] = os.path.basename(bpy.data.filepath or "unknown")
        stats['export_date']     = time.time()
        try:
            fp = self.filepath if self.filepath.endswith('.json') else self.filepath + '.json'
            with open(fp, 'w') as f:
                json.dump(stats, f, indent=2)
            self.report({'INFO'}, f"Exported to {fp}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        if bpy.data.filepath:
            self.filename = os.path.splitext(os.path.basename(bpy.data.filepath))[0] + "_time_stats"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class TIME_TRACKER_OT_import_stats(bpy.types.Operator):
    bl_idname      = "time_tracker.import_stats"
    bl_label       = "Import Statistics"
    bl_description = "Import stats from a JSON file"
    bl_options     = {'REGISTER', 'UNDO'}

    filepath:    bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})
    merge_mode:  bpy.props.EnumProperty(
        name="Mode",
        items=[('REPLACE', "Replace", "Replace all stats"),
               ('MERGE',   "Merge",   "Add imported time to current stats")],
        default='MERGE'
    )

    def execute(self, context):
        try:
            with open(self.filepath, 'r') as f:
                imported = json.load(f)
            current = load_stats()
            if self.merge_mode == 'REPLACE':
                session_time = context.scene.time_tracker_props.session_time
                save_stats(imported)
                context.scene.time_tracker_props.session_time = session_time
                self.report({'INFO'}, "Stats replaced")
            else:
                current['total_time']           += imported.get('total_time', 0)
                current['total_idle_time']       += imported.get('total_idle_time', 0)
                current['total_unfocused_time']  += imported.get('total_unfocused_time', 0)
                current['save_count']            += imported.get('save_count', 0)
                fo = imported.get('first_opened', 0)
                if fo and fo < current['first_opened']:
                    current['first_opened'] = fo
                for day, val in imported.get('daily', {}).items():
                    d = current['daily'].setdefault(day, {"active":0,"idle":0,"unfocused":0,"saves":0})
                    for k in ('active','idle','unfocused','saves'):
                        d[k] = d.get(k, 0) + val.get(k, 0)
                combined = current['recent_sessions'] + imported.get('recent_sessions', [])
                current['recent_sessions'] = sorted(
                    combined, key=lambda x: x['timestamp']
                )[-RECENT_SESSIONS_LIMIT:]
                save_stats(current)
                self.report({'INFO'}, "Stats merged")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        self.layout.prop(self, "merge_mode")


class TIME_TRACKER_OT_reset_stats(bpy.types.Operator):
    bl_idname      = "time_tracker.reset_stats"
    bl_label       = "Reset Statistics"
    bl_description = "Wipe all tracking data for this file"
    bl_options     = {'REGISTER', 'UNDO'}

    def execute(self, context):
        save_stats(_empty_stats())
        context.scene.time_tracker_props.session_time = 0
        _reset_session_counters()
        self.report({'INFO'}, "Stats reset")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


# ---------------------------------------------------------------------------
# Modal operator  (1-second tick)
# ---------------------------------------------------------------------------

class TIME_TRACKER_OT_modal(bpy.types.Operator):
    bl_idname = "time_tracker.modal"
    bl_label  = "Stat Tracker Modal"
    _timer    = None

    def modal(self, context, event):
        if event.type == 'TIMER':
            update_tracking()
            try:
                for area in context.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
            except Exception:
                pass

        if event.type in {'MOUSEMOVE', 'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE',
                          'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'RET', 'ESC', 'TAB',
                          'SPACE'} or event.value == 'PRESS':
            register_activity()

        return {'PASS_THROUGH'}

    def execute(self, context):
        if tracking_data["modal_running"]:
            return {'CANCELLED'}
        wm            = context.window_manager
        self._timer   = wm.event_timer_add(1.0, window=context.window)
        wm.modal_handler_add(self)
        tracking_data["modal_running"]      = True
        tracking_data["is_tracking"]        = True
        tracking_data["last_activity_time"] = time.time()
        tracking_data["last_update_time"]   = time.time()
        print("Stat Tracker: modal started")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        tracking_data["modal_running"] = False
        print("Stat Tracker: modal stopped")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    TimeTrackerProperties,
    TIME_TRACKER_PT_panel,
    TIME_TRACKER_OT_start_modal,
    TIME_TRACKER_OT_export_stats,
    TIME_TRACKER_OT_import_stats,
    TIME_TRACKER_OT_reset_stats,
    TIME_TRACKER_OT_modal,
)


def start_modal_delayed():
    try:
        if not tracking_data["modal_running"] and bpy.data.filepath:
            bpy.ops.time_tracker.modal()
            print("Stat Tracker: started via timer")
    except Exception as e:
        print(f"Stat Tracker: failed to start – {e}")
    return None


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.time_tracker_props = bpy.props.PointerProperty(type=TimeTrackerProperties)
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.handlers.save_post.append(on_save_post)
    try:
        bpy.app.timers.register(start_modal_delayed, first_interval=2.0)
    except Exception:
        pass
    print("Stat Tracker: registered")


def unregister():
    tracking_data["modal_running"] = False
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.time_tracker_props
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)
    if on_save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_save_post)
    print("Stat Tracker: unregistered")
