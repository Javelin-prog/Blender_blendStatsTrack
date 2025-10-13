import bpy
import time
import json
import os
from pathlib import Path
from bpy.app.handlers import persistent

# Global tracking variables
tracking_data = {
    "is_tracking": False,
    "last_activity_time": 0,
    "session_start_time": 0,
    "idle_threshold": 60,  # 1 minute in seconds
}


def get_stats_file_path():
    """Get the path to the stats file for the current blend file"""
    blend_file = bpy.data.filepath
    if not blend_file:
        return None
    
    stats_file = blend_file.replace(".blend", "_stats.json")
    return stats_file


def load_stats():
    """Load statistics from the stats file"""
    stats_file = get_stats_file_path()
    if not stats_file or not os.path.exists(stats_file):
        return {
            "total_time": 0,
            "save_count": 0,
            "first_opened": time.time(),
            "last_opened": time.time(),
            "sessions": []
        }
    
    try:
        with open(stats_file, 'r') as f:
            return json.load(f)
    except:
        return {
            "total_time": 0,
            "save_count": 0,
            "first_opened": time.time(),
            "last_opened": time.time(),
            "sessions": []
        }


def save_stats(stats):
    """Save statistics to the stats file"""
    stats_file = get_stats_file_path()
    if not stats_file:
        return
    
    try:
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        print(f"Error saving stats: {e}")


def format_time(seconds):
    """Format seconds into days, hours, minutes"""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "0m"


def update_tracking():
    """Update tracking based on activity"""
    if not tracking_data["is_tracking"]:
        return 1.0
    
    current_time = time.time()
    last_activity = tracking_data["last_activity_time"]
    
    # Check if idle
    if current_time - last_activity > tracking_data["idle_threshold"]:
        # Still tracking but idle, don't add time
        return 1.0
    
    # Add time since last check
    if hasattr(bpy.context.scene, "time_tracker_props"):
        props = bpy.context.scene.time_tracker_props
        props.session_time += 1.0
    
    return 1.0


def register_activity():
    """Register user activity"""
    tracking_data["last_activity_time"] = time.time()


@persistent
def on_load_post(dummy):
    """Handler for when a file is loaded"""
    stats = load_stats()
    stats["last_opened"] = time.time()
    save_stats(stats)
    
    # Start tracking
    tracking_data["is_tracking"] = True
    tracking_data["session_start_time"] = time.time()
    tracking_data["last_activity_time"] = time.time()
    
    # Initialize session time
    if hasattr(bpy.context.scene, "time_tracker_props"):
        bpy.context.scene.time_tracker_props.session_time = 0


@persistent
def on_save_post(dummy):
    """Handler for when a file is saved"""
    stats = load_stats()
    stats["save_count"] += 1
    
    # Add current session time to total
    if hasattr(bpy.context.scene, "time_tracker_props"):
        props = bpy.context.scene.time_tracker_props
        stats["total_time"] += props.session_time
        props.session_time = 0
        tracking_data["session_start_time"] = time.time()
    
    # Record session
    stats["sessions"].append({
        "timestamp": time.time(),
        "duration": props.session_time if hasattr(bpy.context.scene, "time_tracker_props") else 0
    })
    
    save_stats(stats)
    register_activity()


class TimeTrackerProperties(bpy.types.PropertyGroup):
    session_time: bpy.props.FloatProperty(
        name="Session Time",
        default=0.0
    )


class TIME_TRACKER_PT_panel(bpy.types.Panel):
    bl_label = "Time Tracker"
    bl_idname = "TIME_TRACKER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Time Tracker'

    def draw(self, context):
        layout = self.layout
        
        if not bpy.data.filepath:
            layout.label(text="Save file to track time", icon='ERROR')
            return
        
        stats = load_stats()
        props = context.scene.time_tracker_props
        
        # Current session
        box = layout.box()
        box.label(text="Current Session:", icon='TIME')
        current_session = props.session_time
        box.label(text=f"  {format_time(current_session)}")
        
        # Show idle status
        current_time = time.time()
        if tracking_data["is_tracking"]:
            idle_time = current_time - tracking_data["last_activity_time"]
            if idle_time > tracking_data["idle_threshold"]:
                box.label(text="  Status: IDLE", icon='PAUSE')
            else:
                box.label(text="  Status: Active", icon='PLAY')
        
        # Total time
        box = layout.box()
        box.label(text="Total Time Worked:", icon='PREVIEW_RANGE')
        total = stats["total_time"] + current_session
        box.label(text=f"  {format_time(total)}")
        
        # Save statistics
        box = layout.box()
        box.label(text="Save Statistics:", icon='FILE_TICK')
        box.label(text=f"  Times Saved: {stats['save_count']}")
        
        if stats['save_count'] > 0:
            avg_time = total / stats['save_count']
            box.label(text=f"  Avg Time/Save: {format_time(avg_time)}")
        
        # Project info
        box = layout.box()
        box.label(text="Project Info:", icon='INFO')
        first_opened = time.strftime('%Y-%m-%d', time.localtime(stats['first_opened']))
        box.label(text=f"  First Opened: {first_opened}")
        
        project_age = time.time() - stats['first_opened']
        box.label(text=f"  Project Age: {format_time(project_age)}")
        
        # Additional metrics
        if stats['save_count'] > 0:
            box = layout.box()
            box.label(text="Productivity:", icon='GRAPH')
            
            # Work efficiency (time worked vs project age)
            efficiency = (total / project_age) * 100 if project_age > 0 else 0
            box.label(text=f"  Work Ratio: {efficiency:.1f}%")
            
            # Average session length
            if len(stats.get('sessions', [])) > 0:
                avg_session = sum(s.get('duration', 0) for s in stats['sessions']) / len(stats['sessions'])
                box.label(text=f"  Avg Session: {format_time(avg_session)}")
        
        # Action buttons
        layout.separator()
        row = layout.row(align=True)
        row.operator("time_tracker.export_stats", icon='EXPORT', text="Export")
        row.operator("time_tracker.import_stats", icon='IMPORT', text="Import")
        layout.operator("time_tracker.reset_stats", icon='X', text="Reset Stats")


class TIME_TRACKER_OT_export_stats(bpy.types.Operator):
    bl_idname = "time_tracker.export_stats"
    bl_label = "Export Statistics"
    bl_description = "Export time tracking statistics to share with others"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filename: bpy.props.StringProperty(default="time_stats")
    
    def execute(self, context):
        stats = load_stats()
        
        if not stats:
            self.report({'ERROR'}, "No statistics to export")
            return {'CANCELLED'}
        
        # Add blend file name for reference
        stats['blend_file_name'] = os.path.basename(bpy.data.filepath)
        stats['export_date'] = time.time()
        
        try:
            # Ensure .json extension
            filepath = self.filepath
            if not filepath.endswith('.json'):
                filepath += '.json'
            
            with open(filepath, 'w') as f:
                json.dump(stats, f, indent=2)
            
            self.report({'INFO'}, f"Statistics exported to {filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        # Set default filename based on blend file
        if bpy.data.filepath:
            blend_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            self.filename = f"{blend_name}_time_stats"
        
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class TIME_TRACKER_OT_import_stats(bpy.types.Operator):
    bl_idname = "time_tracker.import_stats"
    bl_label = "Import Statistics"
    bl_description = "Import time tracking statistics from another file"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})
    
    merge_mode: bpy.props.EnumProperty(
        name="Import Mode",
        items=[
            ('REPLACE', "Replace", "Replace current statistics"),
            ('MERGE', "Merge", "Add imported time to current statistics"),
        ],
        default='MERGE'
    )
    
    def execute(self, context):
        try:
            with open(self.filepath, 'r') as f:
                imported_stats = json.load(f)
            
            current_stats = load_stats()
            
            if self.merge_mode == 'REPLACE':
                # Keep current session time but replace everything else
                session_time = context.scene.time_tracker_props.session_time
                save_stats(imported_stats)
                context.scene.time_tracker_props.session_time = session_time
                self.report({'INFO'}, "Statistics replaced")
            else:  # MERGE
                # Merge statistics
                current_stats['total_time'] += imported_stats.get('total_time', 0)
                current_stats['save_count'] += imported_stats.get('save_count', 0)
                
                # Keep earliest first_opened date
                if 'first_opened' in imported_stats:
                    if imported_stats['first_opened'] < current_stats['first_opened']:
                        current_stats['first_opened'] = imported_stats['first_opened']
                
                # Merge sessions
                if 'sessions' in imported_stats:
                    current_stats['sessions'].extend(imported_stats['sessions'])
                    # Sort by timestamp
                    current_stats['sessions'].sort(key=lambda x: x.get('timestamp', 0))
                
                save_stats(current_stats)
                self.report({'INFO'}, "Statistics merged")
            
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "merge_mode")


class TIME_TRACKER_OT_reset_stats(bpy.types.Operator):
    bl_idname = "time_tracker.reset_stats"
    bl_label = "Reset Statistics"
    bl_description = "Reset all time tracking statistics for this file"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        stats_file = get_stats_file_path()
        if stats_file and os.path.exists(stats_file):
            os.remove(stats_file)
        
        context.scene.time_tracker_props.session_time = 0
        tracking_data["session_start_time"] = time.time()
        
        self.report({'INFO'}, "Statistics reset")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


# Activity detection through modal operator
class TIME_TRACKER_OT_modal(bpy.types.Operator):
    bl_idname = "time_tracker.modal"
    bl_label = "Time Tracker Modal"
    
    _timer = None
    
    def modal(self, context, event):
        if event.type == 'TIMER':
            update_tracking()
        
        # Register activity on mouse/keyboard events
        if event.type in {'MOUSEMOVE', 'LEFTMOUSE', 'RIGHTMOUSE', 'MIDDLEMOUSE', 
                         'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'KEY_PRESS'}:
            register_activity()
        
        return {'PASS_THROUGH'}
    
    def execute(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(1.0, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)


classes = (
    TimeTrackerProperties,
    TIME_TRACKER_PT_panel,
    TIME_TRACKER_OT_export_stats,
    TIME_TRACKER_OT_import_stats,
    TIME_TRACKER_OT_reset_stats,
    TIME_TRACKER_OT_modal,
)


@persistent
def start_modal_timer(dummy):
    """Start the modal operator after Blender is fully loaded"""
    if not any(timer for timer in bpy.app.timers if hasattr(timer, '__name__') and 'time_tracker' in str(timer)):
        try:
            bpy.ops.time_tracker.modal()
        except:
            # If it fails, try again in 1 second
            bpy.app.timers.register(lambda: bpy.ops.time_tracker.modal(), first_interval=1.0)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.time_tracker_props = bpy.props.PointerProperty(type=TimeTrackerProperties)
    
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.handlers.save_post.append(on_save_post)
    bpy.app.handlers.load_post.append(start_modal_timer)
    
    # Delay modal operator start to avoid context issues
    bpy.app.timers.register(lambda: bpy.ops.time_tracker.modal(), first_interval=0.1)


def unregister():
    # Remove timer
    if bpy.app.timers.is_registered(start_modal_timer):
        bpy.app.timers.unregister(start_modal_timer)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.time_tracker_props
    
    bpy.app.handlers.load_post.remove(on_load_post)
    bpy.app.handlers.save_post.remove(on_save_post)
    if start_modal_timer in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(start_modal_timer)