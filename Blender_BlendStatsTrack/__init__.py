bl_info = {
    "name": "[JavStud] .blend Stats Tracker",
    "author": "'Javelin' Jérôme Noël",
    "version": (1, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Time Tracker Tab",
    "description": "Track time spent working on blend files with idle detection, save statistics, and exportable metrics",
    "category": "Development",
}

import bpy
import os

# Register and Unregister
def register():
    
    from . import blendTimeTrack
    blendTimeTrack.register()

def unregister():
    
    from . import blendTimeTrack
    blendTimeTrack.unregister()

if __name__ == "__main__":
    register()