bl_info = {
    "name": "Taxi Line Generator",
    "author": "Fox Two Models",
    "version": (0, 2, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Taxi Lines",
    "description": "Create airport taxi line markings (in development).",
    "category": "3D View",
}

import bpy

from .operators.bake_export_mesh import TAXILINES_OT_bake_export_mesh
from .operators.debug_info import TAXILINES_OT_debug_active
from .operators.draw_line_modal import TAXILINES_OT_draw_taxi_line
from .operators.edit_path import TAXILINES_OT_edit_path, TAXILINES_OT_finish_editing
from .operators.insert_point import TAXILINES_OT_insert_point_at_mouse, draw_insert_point_menu
from .operators.normalize_curve import TAXILINES_OT_normalize_curve
from .operators.recompute_handles import TAXILINES_OT_recompute_handles
from .operators.resume_line_modal import TAXILINES_OT_resume_taxi_line
from .name_sync import register_handlers as _register_handlers
from .name_sync import unregister_handlers as _unregister_handlers
from .properties import register_properties, unregister_properties
from .ui import TAXILINES_OT_reload_addon, TAXILINES_PT_main

_addon_keymaps = []

classes = (
    TAXILINES_OT_reload_addon,
    TAXILINES_OT_draw_taxi_line,
    TAXILINES_OT_resume_taxi_line,
    TAXILINES_OT_bake_export_mesh,
    TAXILINES_OT_debug_active,
    TAXILINES_OT_edit_path,
    TAXILINES_OT_finish_editing,
    TAXILINES_OT_insert_point_at_mouse,
    TAXILINES_OT_normalize_curve,
    TAXILINES_OT_recompute_handles,
    TAXILINES_PT_main,
)


def register():
    register_properties()

    for cls in classes:
        bpy.utils.register_class(cls)

    # Add "Insert Taxi Point Here" to the Edit Curve right-click context menu.
    bpy.types.VIEW3D_MT_edit_curve_context_menu.append(draw_insert_point_menu)

    # IMPORTANT: Menu operators receive the mouse position from the click on the menu item,
    # not the original right-click that opened the menu. Provide a direct hotkey so the
    # operator can use the true click location.
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="Curve", space_type="EMPTY")
        kmi = km.keymap_items.new("taxilines.insert_point", type="RIGHTMOUSE", value="PRESS", shift=True)
        _addon_keymaps.append((km, kmi))

    _register_handlers()


def unregister():
    _unregister_handlers()

    for km, kmi in _addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _addon_keymaps.clear()

    try:
        bpy.types.VIEW3D_MT_edit_curve_context_menu.remove(draw_insert_point_menu)
    except Exception:
        pass

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    unregister_properties()
