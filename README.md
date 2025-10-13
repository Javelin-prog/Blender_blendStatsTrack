# Blender - Time Tracker

A productivity and project time-tracking add-on for Blender.  
This tool automatically monitors how long you spend working on each `.blend` file, tracking **total time**, **session duration**, and **save counts**, all stored locally in a lightweight JSON file.

## Features

- Automatically tracks **time spent** on each project file  
- Detects **idle time** (no keyboard or mouse activity for over 1 minute)  
- Records **save events**, **first opened date**, and **session history**  
- Displays total time, current session duration, and productivity metrics  
- Exports and imports tracking data in `.json` format  
- Provides a clean, organized UI panel in the 3D Viewport sidebar  
- Automatically starts tracking when a file is loaded  
- Can **reset** tracking data per project when needed  

## Installation

1. Download or save the `time_tracker.py` script.
2. Open Blender.
3. Go to `Edit` → `Preferences` → `Add-ons` → click the drop-down arrow.
4. Click `Install...` and select the `time_tracker.py` file.
5. Enable the add-on by checking the box next to **Time Tracker**.

::: primary
Alternatively, drag and drop the `Blender_TimeTrackBlend.zip` file directly into the Blender window.
:::

## Location

`3D Viewport` → `Sidebar (N)` → **Time Tracker** tab

## Usage

1. Open or save your `.blend` file to begin tracking.
2. Open the **Time Tracker** panel (`N` → *Time Tracker* tab).
3. The panel shows:
   - **Current Session** time (updates as you work)
   - **Idle Status** (Active or Idle)
   - **Total Time Worked** across sessions
   - **Save Statistics** (total saves and average time per save)
   - **Project Info** (first opened date and project age)
   - **Productivity Metrics** (work ratio and average session length)
4. Use the bottom action buttons to:
   - **Export**: Save your stats as a `.json` file  
   - **Import**: Load or merge stats from another file  
   - **Reset Stats**: Clear all data for this project  

## File Storage

Each `.blend` file stores its statistics in a companion JSON file:
These files are created and updated automatically when you open, save, or close the project.

## Notes

- Time is **not tracked** when Blender is idle for more than 60 seconds.
- Statistics are **per project**, allowing independent tracking across multiple files.
- The add-on works entirely offline; no external data is sent or received.
- Resetting stats only affects the current blend file’s tracking data.

## License

MIT License

