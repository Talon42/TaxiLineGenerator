import bpy  # pyright: ignore[reportMissingImports]

from ..properties import (
    ensure_taxi_preview,
    get_baked_collection,
    get_baked_mesh_for_curve,
    is_taxi_curve,
)


def _iter_target_curves(context):
    selected = [o for o in context.selected_objects if is_taxi_curve(o)]
    if selected:
        return selected
    active = context.view_layer.objects.active
    if is_taxi_curve(active):
        return [active]
    return []


def _copy_material_slots_from_curve(curve_obj, mesh_data):
    try:
        mesh_data.materials.clear()
    except Exception:
        pass

    src_mats = []
    try:
        if curve_obj.data and hasattr(curve_obj.data, "materials"):
            src_mats = list(curve_obj.data.materials)
    except Exception:
        src_mats = []

    for mat in src_mats:
        if mat is None:
            continue
        try:
            mesh_data.materials.append(mat)
        except Exception:
            pass


def _find_or_create_baked_obj(context, curve_obj, baked_col):
    baked_obj = get_baked_mesh_for_curve(curve_obj)
    if baked_obj is not None:
        try:
            if baked_col not in baked_obj.users_collection:
                baked_col.objects.link(baked_obj)
        except Exception:
            pass
        return baked_obj

    # Fallback: search baked collection for an object pointing at this curve.
    matches = []
    for obj in list(getattr(baked_col, "objects", [])):
        try:
            if obj.type == "MESH" and obj.get("tlg_source_curve") == curve_obj.name:
                matches.append(obj)
        except Exception:
            continue

    if matches:
        keep = matches[0]
        curve_obj["tlg_baked_mesh"] = keep.name
        for extra in matches[1:]:
            try:
                mesh = getattr(extra, "data", None)
                bpy.data.objects.remove(extra, do_unlink=True)
                if mesh is not None and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            except Exception:
                pass
        return keep

    name = f"{curve_obj.name}_BAKED"
    mesh = bpy.data.meshes.new(name)
    baked_obj = bpy.data.objects.new(name, mesh)
    baked_col.objects.link(baked_obj)
    curve_obj["tlg_baked_mesh"] = baked_obj.name
    baked_obj["tlg_source_curve"] = curve_obj.name
    return baked_obj


def _replace_mesh_data(obj, new_mesh):
    old_mesh = getattr(obj, "data", None)
    obj.data = new_mesh
    if old_mesh is not None:
        try:
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
        except Exception:
            pass


class TAXILINES_OT_bake_export_mesh(bpy.types.Operator):
    bl_idname = "taxilines.bake_export_mesh"
    bl_label = "Bake Export Mesh"
    bl_description = "Bake the live GN ribbon preview to a real mesh in a dedicated baked collection"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        curves = _iter_target_curves(context)
        if not curves:
            self.report({"ERROR"}, "Select a Taxi Line curve to bake.")
            return {"CANCELLED"}

        baked_col = get_baked_collection(context.scene)
        depsgraph = context.evaluated_depsgraph_get()

        baked_count = 0
        last_baked_obj = None
        for curve_obj in curves:
            ensure_taxi_preview(curve_obj, context=context)

            baked_obj = _find_or_create_baked_obj(context, curve_obj, baked_col)

            overlay_before = bool(getattr(curve_obj, "tlg_show_curve_overlay", True))
            try:
                curve_obj.tlg_show_curve_overlay = False
            except Exception:
                overlay_before = None

            try:
                eval_obj = curve_obj.evaluated_get(depsgraph)
                new_mesh = bpy.data.meshes.new_from_object(
                    eval_obj, preserve_all_data_layers=True, depsgraph=depsgraph
                )
            finally:
                if overlay_before is not None:
                    try:
                        curve_obj.tlg_show_curve_overlay = overlay_before
                    except Exception:
                        pass

            _replace_mesh_data(baked_obj, new_mesh)
            baked_obj.matrix_world = curve_obj.matrix_world
            baked_obj["tlg_source_curve"] = curve_obj.name
            curve_obj["tlg_baked_mesh"] = baked_obj.name

            _copy_material_slots_from_curve(curve_obj, baked_obj.data)

            try:
                # In the new workflow the export mesh is meant to be editable/selectable.
                baked_obj.hide_select = False
                baked_obj.hide_render = False
            except Exception:
                pass

            # Keep baked meshes hidden by default; "Edit Mesh" will show/select them.
            try:
                baked_obj.hide_viewport = True
            except Exception:
                pass

            baked_count += 1
            last_baked_obj = baked_obj

        # Keep selection unchanged; "Edit Mesh" controls mode switching.

        self.report({"INFO"}, f"Baked {baked_count} export mesh(es).")
        return {"FINISHED"}
