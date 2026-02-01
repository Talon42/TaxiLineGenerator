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
from .operators.draw_line_modal import TAXILINES_OT_draw_taxi_line




classes = (
    TAXILINES_OT_reload_addon,
    TAXILINES_OT_draw_taxi_line,
    TAXILINES_PT_main,
)



def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
