import bpy


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
    return bpy.data.collections.get("_TAXI_LINES_SRC")


def _get_source_curve_from_mesh(mesh_obj):
    if not mesh_obj or mesh_obj.type != "MESH":
        return None
    curve_name = mesh_obj.get("taxilines_source_curve")
    if not curve_name:
        return None
    curve_obj = bpy.data.objects.get(curve_name)
    if not curve_obj or curve_obj.type != "CURVE":
        return None
    return curve_obj


def _get_mesh_from_curve(curve_obj):
    if not curve_obj or curve_obj.type != "CURVE":
        return None
    mesh_name = curve_obj.get("taxilines_mesh")
    if not mesh_name:
        return None
    mesh_obj = bpy.data.objects.get(mesh_name)
    if not mesh_obj or mesh_obj.type != "MESH":
        return None
    return mesh_obj


class TAXILINES_OT_edit_path(bpy.types.Operator):
    bl_idname = "taxilines.edit_path"
    bl_label = "Edit Path"
    bl_description = "Reveal and select the hidden curve path for the active taxi line mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.view_layer.objects.active
        if active is None:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        if active.type == "MESH":
            mesh_obj = active
            curve_obj = _get_source_curve_from_mesh(mesh_obj)
        elif active.type == "CURVE":
            curve_obj = active
            mesh_obj = _get_mesh_from_curve(curve_obj)
        else:
            self.report({"ERROR"}, "Active object must be a taxi mesh or its source curve.")
            return {"CANCELLED"}

        if curve_obj is None:
            self.report({"ERROR"}, "Could not find source curve for the active taxi mesh.")
            return {"CANCELLED"}

        src_col = _get_src_collection()
        if src_col is not None:
            src_col.hide_viewport = False
            src_col.hide_select = False

        curve_obj.hide_viewport = False
        curve_obj.hide_select = False
        curve_obj.hide_render = True

        # Make curve active before any mode switching.
        _deselect_all(context)
        curve_obj.select_set(True)
        context.view_layer.objects.active = curve_obj

        _safe_mode_set(context, curve_obj, "OBJECT")

        if mesh_obj is not None:
            mesh_obj.hide_viewport = True
            mesh_obj.hide_select = True

        _safe_mode_set(context, curve_obj, "EDIT")

        return {"FINISHED"}


class TAXILINES_OT_finish_editing(bpy.types.Operator):
    bl_idname = "taxilines.finish_editing"
    bl_label = "Finish Editing"
    bl_description = "Hide the source curve and reselect the taxi mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.view_layer.objects.active
        if active is None:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        if active.type == "CURVE":
            curve_obj = active
            mesh_obj = _get_mesh_from_curve(curve_obj)
        elif active.type == "MESH":
            mesh_obj = active
            curve_obj = _get_source_curve_from_mesh(mesh_obj)
        else:
            self.report({"ERROR"}, "Active object must be a taxi mesh or its source curve.")
            return {"CANCELLED"}

        if curve_obj is not None:
            _safe_mode_set(context, curve_obj, "OBJECT")
            curve_obj.hide_viewport = True
            curve_obj.hide_select = True
            curve_obj.hide_render = True

        src_col = _get_src_collection()
        if src_col is not None:
            src_col.hide_viewport = True
            src_col.hide_select = True

        if mesh_obj is None:
            self.report({"WARNING"}, "Could not find taxi mesh to reselect.")
            return {"FINISHED"}

        mesh_obj.hide_viewport = False
        mesh_obj.hide_select = False

        _deselect_all(context)
        mesh_obj.select_set(True)
        context.view_layer.objects.active = mesh_obj

        return {"FINISHED"}
