bl_info = {
    "name": "Taxi Line Generator",
    "author": "Fox Two Models",
    "version": (0, 0, 1),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Taxi Lines",
    "description": "Create airport taxi line markings (in development).",
    "category": "3D View",
}

import bpy
from .ui import TAXILINES_PT_main, TAXILINES_OT_reload_addon


classes = (
    TAXILINES_OT_reload_addon,
    TAXILINES_PT_main,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
