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
from .operators.insert_point import TAXILINES_OT_insert_point_at_mouse, draw_insert_point_menu
from .operators.normalize_curve import TAXILINES_OT_normalize_curve
from .properties import register_properties, unregister_properties
from .ui import TAXILINES_OT_reload_addon, TAXILINES_PT_main

_addon_keymaps = []

classes = (
    TAXILINES_OT_reload_addon,
    TAXILINES_OT_draw_taxi_line,
    TAXILINES_OT_create_ribbon_mesh,
    TAXILINES_OT_edit_path,
    TAXILINES_OT_finish_editing,
    TAXILINES_OT_insert_point_at_mouse,
    TAXILINES_OT_normalize_curve,
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


def unregister():
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
