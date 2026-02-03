import bpy

from ..properties import ensure_taxi_preview, get_baked_mesh_for_curve, is_taxi_curve


def _deselect_all(context):
    for obj in list(context.selected_objects):
        obj.select_set(False)


def _safe_mode_set(context, obj, mode):
    if obj is None:
        return
    try:
        with context.temp_override(
            object=obj,
            active_object=obj,
            selected_objects=[obj],
            selected_editable_objects=[obj],
        ):
            bpy.ops.object.mode_set(mode=mode)
    except Exception:
        pass


def _get_src_collection():
    # Legacy collection (old workflow). Kept for compatibility with existing files.
    return bpy.data.collections.get("_TAXI_LINES_SRC")


def _get_source_curve_from_mesh(mesh_obj):
    if not mesh_obj or mesh_obj.type != "MESH":
        return None
    curve_name = mesh_obj.get("tlg_source_curve") or mesh_obj.get("taxilines_source_curve")
    if not curve_name:
        return None
    curve_obj = bpy.data.objects.get(curve_name)
    if not curve_obj or curve_obj.type != "CURVE":
        return None
    return curve_obj


def _get_mesh_from_curve(curve_obj):
    return get_baked_mesh_for_curve(curve_obj)


class TAXILINES_OT_edit_path(bpy.types.Operator):
    bl_idname = "taxilines.edit_path"
    bl_label = "Edit Mode (Curve)"
    bl_description = "Show the editable curve with live GN preview (hide baked export mesh)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.view_layer.objects.active
        if active is None:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        if active.type == "CURVE":
            curve_obj = active
        elif active.type == "MESH":
            curve_obj = _get_source_curve_from_mesh(active)
        else:
            curve_obj = None

        if curve_obj is None:
            self.report({"ERROR"}, "Active object must be a Taxi Line curve or its baked mesh.")
            return {"CANCELLED"}

        if not is_taxi_curve(curve_obj):
            curve_obj["tlg_is_taxi_line"] = True

        try:
            context.scene.tlg_view_mode = "EDIT"
        except Exception:
            pass
        ensure_taxi_preview(curve_obj, context=context)

        # Make curve active before any mode switching.
        _deselect_all(context)
        curve_obj.select_set(True)
        context.view_layer.objects.active = curve_obj

        _safe_mode_set(context, curve_obj, "OBJECT")

        _safe_mode_set(context, curve_obj, "EDIT")

        return {"FINISHED"}


class TAXILINES_OT_finish_editing(bpy.types.Operator):
    bl_idname = "taxilines.finish_editing"
    bl_label = "Export Mode (Baked)"
    bl_description = "Show the baked export mesh (curve hidden/locked)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.view_layer.objects.active
        if active is None:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        if active.type == "CURVE":
            curve_obj = active
        elif active.type == "MESH":
            curve_obj = _get_source_curve_from_mesh(active)
        else:
            curve_obj = None

        if curve_obj is None:
            self.report({"ERROR"}, "Active object must be a Taxi Line curve or its baked mesh.")
            return {"CANCELLED"}

        mesh_obj = _get_mesh_from_curve(curve_obj)
        if mesh_obj is None:
            self.report({"WARNING"}, "No baked mesh found for this curve. Use Bake first.")
            return {"CANCELLED"}

        try:
            context.scene.tlg_view_mode = "EXPORT"
        except Exception:
            pass

        _deselect_all(context)
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj
        return {"FINISHED"}
