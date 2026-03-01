# Blender - Time Tracker

A productivity and project time-tracking add-on for Blender.  
Automatically monitors how long you actively spend working on each `.blend` file — tracking **active time**, **idle time**, **focus state**, **daily breakdowns**, and **session history**, all stored directly inside the `.blend` file itself.

## Features

- Automatically tracks **active working time** per project file
- Detects **idle time** (no keyboard or mouse activity for over 1 minute)
- Detects **window focus** — time is **not counted** when you switch to another application
- Stores all data **inside the `.blend` file** — no sidecar files, travels with your project
- Tracks **active**, **idle**, and **unfocused** time separately for full transparency
- Displays a **Focus Score** per session (active ÷ total elapsed)
- Shows **daily breakdowns**, **work streak**, **best day**, and **last 7 days** totals
- Keeps a **rolling log of the last 20 notable sessions** (5+ minutes) to avoid data bloat
- All other saves are **compressed into daily buckets** — storage stays bounded forever
- Exports and imports tracking data as `.json` for backup or sharing
- Automatic **one-time migration** from old `_stats.json` sidecar files
- Provides a clean, organized UI panel in the 3D Viewport sidebar
- Automatically starts tracking when a file is loaded

## Installation

1. Download or save the `Blender_TimeTrackBlend.zip` file.
2. Open Blender.
3. Go to `Edit` → `Preferences` → `Add-ons` → click the drop-down arrow.
4. Click `Install...` and select the `Blender_TimeTrackBlend.zip` file.
5. Enable the add-on by checking the box next to **Time Tracker**.

> **Tip:** You can also drag and drop the `.zip` file directly into the Blender window.

## Location

`3D Viewport` → `Sidebar (N)` → **Time Tracker** tab

## Usage

1. Open or save your `.blend` file to begin tracking.
2. Open the **Time Tracker** panel (`N` → *Time Tracker* tab).
3. Work normally — the add-on tracks everything automatically in the background.
4. Save (`Ctrl+S`) at any point to commit the current session to your stats.

## Panel Overview

### Current Session
Shows a live breakdown of the current unsaved session:
- **Active** — time you were in Blender and actively using it
- **Idle** — time in Blender with no keyboard or mouse input
- **Unfocused** — time Blender was open but you were in another application
- **Focus Score** — percentage of elapsed time that was genuinely active
- **Status** — live indicator: Active / Idle / Unfocused / Not Tracking

### Today
- Total **active time** accumulated today (including the current unsaved session)
- **Number of saves** made today
- **Work Streak** — how many consecutive days you've worked on this project

### Lifetime Totals
- Cumulative **active**, **idle**, and **unfocused** time across all sessions
- **Total saves** since the project began

### Productivity
Meaningful metrics derived from your history:
- **Focus Ratio** — active time ÷ all clocked time (the real measure of productive time)
- **Idle Ratio** — how much of your in-Blender time was idle
- **Avg/Save** — average active time between saves
- **Days Worked** and **Avg/Day** — across actual working days only
- **Best Day** — your most productive single day and its active time
- **Last 7 Days** — rolling weekly total
- **Avg Session** and **Best Session** — derived from recent notable sessions

### Recent Sessions
A log of the last 5 most recent sessions that lasted 5 minutes or more, showing date, duration, and focus percentage.

### Project Info
- First and last opened dates
- Project age
- Confirmation that stats are stored inside the `.blend` file

## Data Storage

All statistics are stored **directly inside the `.blend` file** as scene data. This means:

- Stats are saved and versioned alongside your project automatically
- No companion files to lose, move, or forget
- Stats are included in Blender's backup files (`.blend1`, `.blend2`, etc.)
- Renaming or copying the `.blend` file keeps the stats intact
- No risk of stats/project mismatch

### Storage Efficiency

To keep data size bounded regardless of how long a project runs:

- Every save is **aggregated into a daily bucket** (at most ~365 entries per year)
- Individual session records are only kept if the session was **5 minutes or longer**
- The individual session log is capped at the **last 20 notable sessions**

### Migration from Previous Versions

If your project has an existing `_stats.json` file from an older version of this add-on, the migration is automatic: on first load, the old data is imported into the `.blend` file and the JSON file is renamed to `_stats.json.migrated` so nothing is lost.

## Action Buttons

| Button | Description |
|--------|-------------|
| **Export JSON** | Save a full copy of your stats to a `.json` file for backup or sharing |
| **Import JSON** | Load stats from a `.json` file, with choice to Replace or Merge |
| **Reset All Stats** | Wipe all tracking data for this project (asks for confirmation) |

## Notes

- Time is **not tracked** when Blender is idle for more than 60 seconds.
- Time is **not tracked** when Blender is not the active foreground window.
- Statistics are **per project** — each `.blend` file maintains its own independent history.
- The add-on works entirely **offline**; no external data is sent or received.
- Resetting stats only affects the currently open file.

## Platform Support

Window focus detection is supported on:
- **Windows** — via built-in `ctypes` (no extra dependencies)
- **macOS** — via `AppKit` (available by default on macOS)
- **Linux** — via `xdotool` or `gi/Wnck` if installed; falls back to always-active if neither is available

## License

MIT License
