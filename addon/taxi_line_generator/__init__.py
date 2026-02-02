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

from .operators.create_ribbon_mesh import TAXILINES_OT_create_ribbon_mesh
from .operators.draw_line_modal import TAXILINES_OT_draw_taxi_line
from .operators.edit_path import TAXILINES_OT_edit_path, TAXILINES_OT_finish_editing
from .operators.normalize_curve import TAXILINES_OT_normalize_curve
from .properties import register_properties, unregister_properties
from .ui import TAXILINES_OT_reload_addon, TAXILINES_PT_main


classes = (
    TAXILINES_OT_reload_addon,
    TAXILINES_OT_draw_taxi_line,
    TAXILINES_OT_create_ribbon_mesh,
    TAXILINES_OT_edit_path,
    TAXILINES_OT_finish_editing,
    TAXILINES_OT_normalize_curve,
    TAXILINES_PT_main,
)


def register():
    register_properties()

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    unregister_properties()
