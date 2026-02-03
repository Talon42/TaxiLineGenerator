import bpy
import bmesh

from ..properties import (
    ensure_taxi_preview,
    get_base_mesh_for_curve,
    get_baked_mesh_for_curve,
    get_source_curve_for_mesh,
    tlg_parse_base_name,
    tlg_sync_linked_object_names,
    get_taxi_curves_collection,
    get_taxi_export_collection,
    get_taxi_internal_collection,
    is_taxi_curve,
)


def _debug_uv(context, msg):
    try:
        scene = getattr(context, "scene", None) if context else None
        enabled = bool(scene and scene.get("tlg_debug_uv"))
    except Exception:
        enabled = False
    if not enabled:
        return
    try:
        print("[TLG UV DEBUG] " + str(msg))
    except Exception:
        pass


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
    return get_source_curve_for_mesh(mesh_obj)


def _get_mesh_from_curve(curve_obj):
    return get_baked_mesh_for_curve(curve_obj)


def _iter_target_curves(context):
    curves = []
    seen = set()

    for obj in list(getattr(context, "selected_objects", []) or []):
        curve_obj = None
        if getattr(obj, "type", None) == "CURVE":
            curve_obj = obj
        elif getattr(obj, "type", None) == "MESH":
            curve_obj = _get_source_curve_from_mesh(obj)
            # If the user renamed the export mesh (or base) manually, treat that as authoritative
            # and sync the linked trio right away (prevents Edit Curve from "reverting" the mesh name).
            if curve_obj is not None:
                try:
                    ensure_taxi_preview(curve_obj, context=context)
                    line_id = curve_obj.get("tlg_line_id")
                    if line_id:
                        try:
                            obj["tlg_line_id"] = line_id
                        except Exception:
                            pass
                        try:
                            role = obj.get("tlg_line_role")
                        except Exception:
                            role = None
                        if not role:
                            try:
                                if str(getattr(obj, "name", "")).endswith("_BASE") or (
                                    bool(getattr(obj, "hide_select", False))
                                    and bool(getattr(obj, "hide_viewport", False))
                                ):
                                    role = "BASE"
                                else:
                                    role = "MESH"
                            except Exception:
                                role = "MESH"
                        try:
                            obj["tlg_line_role"] = role
                        except Exception:
                            pass

                    base = tlg_parse_base_name(getattr(obj, "name", "") or "")
                    if base:
                        tlg_sync_linked_object_names(curve_obj, base)
                except Exception:
                    pass

        if curve_obj is None:
            continue
        if not is_taxi_curve(curve_obj):
            continue
        if curve_obj.name in seen:
            continue
        seen.add(curve_obj.name)
        curves.append(curve_obj)

    if curves:
        return curves

    active = context.view_layer.objects.active if context and context.view_layer else None
    if active is None:
        return []
    if active.type == "CURVE" and is_taxi_curve(active):
        return [active]
    if active.type == "MESH":
        curve_obj = _get_source_curve_from_mesh(active)
        if curve_obj and is_taxi_curve(curve_obj):
            return [curve_obj]
    return []


def _link_obj_to_collection(obj, col):
    if obj is None or col is None:
        return
    try:
        if col not in obj.users_collection:
            col.objects.link(obj)
    except Exception:
        pass


def _unlink_obj_from_collection_by_name(obj, names):
    if obj is None:
        return
    for col in list(getattr(obj, "users_collection", [])):
        try:
            if col and col.name in names:
                col.objects.unlink(obj)
        except Exception:
            pass


def _ensure_export_and_base_mesh_objs(context, curve_obj):
    # Ensure this curve has persistent linkage metadata (safe under renames).
    ensure_taxi_preview(curve_obj, context=context)

    scene = getattr(context, "scene", None)
    export_col = get_taxi_export_collection(scene)
    curves_col = get_taxi_curves_collection(scene)
    internal_col = get_taxi_internal_collection(scene)

    # Ensure curve is linked into the authoring collection (helps keep Outliner clean).
    _link_obj_to_collection(curve_obj, curves_col)

    export_obj = get_baked_mesh_for_curve(curve_obj)
    # Treat an existing export/base name as authoritative (prevents name revert if user renamed mesh/base).
    try:
        if export_obj is not None:
            base_from_export = tlg_parse_base_name(export_obj.name)
            if base_from_export:
                curve_obj["tlg_line_name"] = base_from_export
    except Exception:
        pass
    if export_obj is None:
        base = curve_obj.get("tlg_line_name") or tlg_parse_base_name(curve_obj.name)
        name = f"{base}_MESH"
        mesh = bpy.data.meshes.new(name)
        export_obj = bpy.data.objects.new(name, mesh)
        curve_obj["tlg_baked_mesh"] = export_obj.name
        export_obj["tlg_source_curve"] = curve_obj.name
        export_obj["tlg_line_id"] = curve_obj.get("tlg_line_id")
        export_obj["tlg_line_role"] = "MESH"
        _link_obj_to_collection(export_obj, export_col)
    else:
        _link_obj_to_collection(export_obj, export_col)
        try:
            export_obj["tlg_source_curve"] = curve_obj.name
        except Exception:
            pass
        try:
            export_obj["tlg_line_id"] = curve_obj.get("tlg_line_id")
            export_obj["tlg_line_role"] = "MESH"
        except Exception:
            pass

    base_obj = get_base_mesh_for_curve(curve_obj)
    try:
        if base_obj is not None:
            base_from_base = tlg_parse_base_name(base_obj.name)
            if base_from_base:
                curve_obj["tlg_line_name"] = base_from_base
    except Exception:
        pass
    if base_obj is None:
        base = curve_obj.get("tlg_line_name") or tlg_parse_base_name(curve_obj.name)
        name = f"{base}_BASE"
        mesh = bpy.data.meshes.new(name)
        base_obj = bpy.data.objects.new(name, mesh)
        curve_obj["tlg_base_mesh"] = base_obj.name
        base_obj["tlg_source_curve"] = curve_obj.name
        base_obj["tlg_line_id"] = curve_obj.get("tlg_line_id")
        base_obj["tlg_line_role"] = "BASE"
        _link_obj_to_collection(base_obj, internal_col)
    else:
        _link_obj_to_collection(base_obj, internal_col)
        try:
            base_obj["tlg_source_curve"] = curve_obj.name
        except Exception:
            pass
        try:
            base_obj["tlg_line_id"] = curve_obj.get("tlg_line_id")
            base_obj["tlg_line_role"] = "BASE"
        except Exception:
            pass

    # Migrate out of legacy add-on collections if present (keeps Outliner tidy).
    _unlink_obj_from_collection_by_name(curve_obj, {"TAXI_LINES"})
    _unlink_obj_from_collection_by_name(export_obj, {"TLG_Baked"})

    # Base mesh is internal: never selectable/visible.
    try:
        base_obj.hide_viewport = True
        base_obj.hide_select = True
        base_obj.hide_render = True
    except Exception:
        pass

    # Normalize names to <BASE>_SRC / <BASE>_MESH / <BASE>_BASE (no "_SRC_" in mesh/base).
    try:
        base_name = curve_obj.get("tlg_line_name") or tlg_parse_base_name(curve_obj.name)
        if base_name:
            tlg_sync_linked_object_names(curve_obj, base_name)
    except Exception:
        pass

    return export_obj, base_obj


def _replace_mesh_data(obj, new_mesh):
    old_mesh = getattr(obj, "data", None)
    obj.data = new_mesh
    if old_mesh is not None:
        try:
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
        except Exception:
            pass


def _mesh_new_from_curve(context, curve_obj):
    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = curve_obj.evaluated_get(depsgraph)
    return bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True, depsgraph=depsgraph)


def _uv_bbox(mesh, uv_layer_name="UVMap"):
    if mesh is None:
        return None
    uv_layer = None
    try:
        uv_layer = mesh.uv_layers.get(uv_layer_name) if hasattr(mesh, "uv_layers") else None
    except Exception:
        uv_layer = None
    if uv_layer is None:
        return None
    data = getattr(uv_layer, "data", None)
    if not data:
        return None
    min_u = 1e30
    min_v = 1e30
    max_u = -1e30
    max_v = -1e30
    for uv in data:
        try:
            u = float(uv.uv.x)
            v = float(uv.uv.y)
        except Exception:
            continue
        if u < min_u:
            min_u = u
        if v < min_v:
            min_v = v
        if u > max_u:
            max_u = u
        if v > max_v:
            max_v = v
    if min_u > max_u or min_v > max_v:
        return None
    return (min_u, min_v, max_u, max_v)


def _sanitize_uv_bbox(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            return (
                float(value[0]),
                float(value[1]),
                float(value[2]),
                float(value[3]),
            )
        except Exception:
            return None
    return None


def _active_uv_layer_name(mesh_obj):
    if mesh_obj is None or getattr(mesh_obj, "type", None) != "MESH":
        return None
    mesh = getattr(mesh_obj, "data", None)
    if mesh is None or not hasattr(mesh, "uv_layers"):
        return None
    try:
        uv_layer = mesh.uv_layers.active
        if uv_layer is None:
            return None
        return str(getattr(uv_layer, "name", None) or "") or None
    except Exception:
        return None


def _copy_uv_layer_by_index(src_mesh, dst_mesh, uv_layer_name):
    if src_mesh is None or dst_mesh is None or not uv_layer_name:
        return False
    if not hasattr(src_mesh, "uv_layers") or not hasattr(dst_mesh, "uv_layers"):
        return False

    try:
        src_layer = src_mesh.uv_layers.get(uv_layer_name)
    except Exception:
        src_layer = None
    if src_layer is None:
        return False

    try:
        dst_layer = dst_mesh.uv_layers.get(uv_layer_name) or dst_mesh.uv_layers.new(name=uv_layer_name)
        dst_mesh.uv_layers.active = dst_layer
    except Exception:
        return False

    try:
        src_polys = list(src_mesh.polygons)
        dst_polys = list(dst_mesh.polygons)
    except Exception:
        return False
    if len(src_polys) != len(dst_polys):
        return False
    try:
        for sp, dp in zip(src_polys, dst_polys):
            if int(getattr(sp, "loop_total", -1)) != int(getattr(dp, "loop_total", -1)):
                return False
    except Exception:
        return False

    try:
        src_data = src_layer.data
        dst_data = dst_layer.data
        if len(src_data) != len(dst_data):
            return False
        for i in range(len(dst_data)):
            dst_data[i].uv = src_data[i].uv
    except Exception:
        return False

    return True


def _get_curve_saved_uv_bbox(curve_obj):
    if curve_obj is None:
        return None
    try:
        return _sanitize_uv_bbox(curve_obj.get("tlg_export_uv_bbox"))
    except Exception:
        return None


def _get_curve_saved_uv_layer_name(curve_obj):
    if curve_obj is None:
        return None
    try:
        v = curve_obj.get("tlg_export_uv_layer")
    except Exception:
        v = None
    if not v:
        return None
    try:
        v = str(v)
    except Exception:
        return None
    return v or None


def _set_curve_saved_uv_bbox(curve_obj, bbox):
    if curve_obj is None or bbox is None:
        return False
    bbox = _sanitize_uv_bbox(bbox)
    if bbox is None:
        return False
    try:
        curve_obj["tlg_export_uv_bbox"] = [bbox[0], bbox[1], bbox[2], bbox[3]]
        return True
    except Exception:
        return False


def _set_curve_saved_uv_layer_name(curve_obj, name):
    if curve_obj is None or not name:
        return False
    try:
        curve_obj["tlg_export_uv_layer"] = str(name)
        return True
    except Exception:
        return False


def _fit_uv_to_bbox(mesh, target_bbox, uv_layer_name="UVMap"):
    if mesh is None or target_bbox is None:
        return False
    uv_layer = None
    try:
        uv_layer = mesh.uv_layers.get(uv_layer_name) if hasattr(mesh, "uv_layers") else None
    except Exception:
        uv_layer = None
    if uv_layer is None:
        return False

    current_bbox = _uv_bbox(mesh, uv_layer_name=uv_layer_name)
    if current_bbox is None:
        return False

    cmin_u, cmin_v, cmax_u, cmax_v = current_bbox
    tmin_u, tmin_v, tmax_u, tmax_v = target_bbox

    csize_u = cmax_u - cmin_u
    csize_v = cmax_v - cmin_v
    tsize_u = tmax_u - tmin_u
    tsize_v = tmax_v - tmin_v
    eps = 1e-12
    if abs(csize_u) <= eps or abs(csize_v) <= eps:
        return False

    su = tsize_u / csize_u
    sv = tsize_v / csize_v

    for uv in uv_layer.data:
        uv.uv.x = (uv.uv.x - cmin_u) * su + tmin_u
        uv.uv.y = (uv.uv.y - cmin_v) * sv + tmin_v
    return True


def _follow_active_quads_unwrap(context, mesh_obj, uv_layer_name="UVMap"):
    if context is None or mesh_obj is None or mesh_obj.type != "MESH":
        return False

    mesh = mesh_obj.data
    if mesh is None or not hasattr(mesh, "uv_layers"):
        return False

    try:
        uv_layer = mesh.uv_layers.get(uv_layer_name) or mesh.uv_layers.new(name=uv_layer_name)
        mesh.uv_layers.active = uv_layer
    except Exception:
        pass

    _deselect_all(context)
    mesh_obj.select_set(True)
    context.view_layer.objects.active = mesh_obj

    _safe_mode_set(context, mesh_obj, "OBJECT")
    _safe_mode_set(context, mesh_obj, "EDIT")

    try:
        with context.temp_override(
            object=mesh_obj,
            active_object=mesh_obj,
            selected_objects=[mesh_obj],
            selected_editable_objects=[mesh_obj],
        ):
            bm = bmesh.from_edit_mesh(mesh)
            if not bm.faces:
                return False

            # Follow Active Quads uses the "active" face as the reference. Ensure the mesh has
            # a valid active face in selection history (last selected), otherwise Blender can
            # fall back to producing stacked UVs.
            best_face = None
            best_boundary_edges = -1
            for f in bm.faces:
                boundary_edges = 0
                for e in f.edges:
                    try:
                        if e.is_boundary:
                            boundary_edges += 1
                    except Exception:
                        pass
                if boundary_edges > best_boundary_edges:
                    best_boundary_edges = boundary_edges
                    best_face = f
            if best_face is None:
                best_face = bm.faces[0]

            bpy.ops.mesh.select_all(action="DESELECT")
            for f in bm.faces:
                f.select_set(False)
            best_face.select_set(True)
            bm.faces.active = best_face
            try:
                bm.select_history.clear()
                bm.select_history.add(best_face)
            except Exception:
                pass
            bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

            # Seed the active face UVs so Follow Active Quads has a well-defined reference.
            try:
                bpy.ops.uv.reset()
            except Exception:
                pass

            bpy.ops.mesh.select_all(action="SELECT")
            bm = bmesh.from_edit_mesh(mesh)
            try:
                bm.faces.active = best_face
            except Exception:
                try:
                    bm.faces.active = bm.faces[0]
                except Exception:
                    pass
            try:
                bm.select_history.clear()
                bm.select_history.add(bm.faces.active)
            except Exception:
                pass
            bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)

            try:
                bpy.ops.uv.follow_active_quads(mode="LENGTH_AVERAGE")
            except Exception:
                try:
                    bpy.ops.uv.follow_active_quads(mode="EVEN")
                except Exception:
                    bpy.ops.uv.follow_active_quads()
    except Exception:
        return False

    return True


class TAXILINES_OT_edit_path(bpy.types.Operator):
    bl_idname = "taxilines.edit_path"
    bl_label = "Edit Curve"
    bl_description = "Edit the source curve (hide/lock the export mesh)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # If we're leaving a mesh Edit Mode session, force a flush of BMesh edits (including UVs)
        # before we hide/lock the export mesh. Without this, UV changes can appear to "reset"
        # when switching back to Edit Mesh later.
        active = context.view_layer.objects.active if context and context.view_layer else None
        invoked_from_mesh = bool(active and getattr(active, "type", None) == "MESH")
        if invoked_from_mesh:
            _debug_uv(context, f"edit_path: invoked_from_mesh active={active.name if active else None} mode={getattr(context, 'mode', '?')}")
            _safe_mode_set(context, active, "OBJECT")

        curves = _iter_target_curves(context)
        if not curves:
            self.report({"ERROR"}, "Select a Taxi Line curve or its export mesh.")
            return {"CANCELLED"}

        # Determine the active curve to enter Edit Mode on.
        active_curve = None
        if active is not None:
            if active.type == "CURVE":
                active_curve = active
            elif active.type == "MESH":
                active_curve = _get_source_curve_from_mesh(active)
        if active_curve is None or not is_taxi_curve(active_curve):
            active_curve = curves[0]

        for curve_obj in curves:
            ensure_taxi_preview(curve_obj, context=context)
            export_obj, base_obj = _ensure_export_and_base_mesh_objs(context, curve_obj)

            if invoked_from_mesh:
                uv_name = _active_uv_layer_name(export_obj) or "UVMap"
                try:
                    bbox = _uv_bbox(getattr(export_obj, "data", None), uv_layer_name=uv_name)
                except Exception:
                    bbox = None
                if bbox is not None:
                    _debug_uv(
                        context, f"edit_path: save curve={curve_obj.name} export={export_obj.name} uv={uv_name} bbox={bbox}"
                    )
                    _set_curve_saved_uv_layer_name(curve_obj, uv_name)
                    _set_curve_saved_uv_bbox(curve_obj, bbox)
                else:
                    _debug_uv(
                        context, f"edit_path: save curve={curve_obj.name} export={export_obj.name} uv={uv_name} bbox=None"
                    )

            # Curve mode: curve is visible/selectable; meshes are hidden/locked.
            try:
                curve_obj.hide_viewport = False
                curve_obj.hide_select = False
                curve_obj.hide_render = True
                curve_obj.display_type = "WIRE"
                curve_obj.show_in_front = True
            except Exception:
                pass
            try:
                export_obj.hide_viewport = True
                export_obj.hide_select = True
            except Exception:
                pass
            try:
                base_obj.hide_viewport = True
                base_obj.hide_select = True
            except Exception:
                pass

        _deselect_all(context)
        for curve_obj in curves:
            try:
                curve_obj.select_set(True)
            except Exception:
                pass
        context.view_layer.objects.active = active_curve

        _safe_mode_set(context, active_curve, "OBJECT")
        _safe_mode_set(context, active_curve, "EDIT")
        return {"FINISHED"}


class TAXILINES_OT_finish_editing(bpy.types.Operator):
    bl_idname = "taxilines.finish_editing"
    bl_label = "Edit Mesh"
    bl_description = "Generate/update the export mesh from the curve, unwrap UVs, then edit the mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        curves = _iter_target_curves(context)
        if not curves:
            self.report({"ERROR"}, "Select a Taxi Line curve or its export mesh.")
            return {"CANCELLED"}

        active = context.view_layer.objects.active
        active_curve = None
        if active is not None:
            if active.type == "CURVE":
                active_curve = active
            elif active.type == "MESH":
                active_curve = _get_source_curve_from_mesh(active)
        if active_curve is None or not is_taxi_curve(active_curve):
            active_curve = curves[0]

        export_objs = []
        any_failed = False
        any_unwrap_failed = False

        for curve_obj in curves:
            ensure_taxi_preview(curve_obj, context=context)
            export_obj, base_obj = _ensure_export_and_base_mesh_objs(context, curve_obj)

            old_export_mesh = getattr(export_obj, "data", None)
            old_base_mesh = getattr(base_obj, "data", None)

            uv_layer_name = _get_curve_saved_uv_layer_name(curve_obj)
            if not uv_layer_name and old_export_mesh is not None and hasattr(old_export_mesh, "uv_layers"):
                try:
                    uv_layer_name = getattr(old_export_mesh.uv_layers.active, "name", None)
                except Exception:
                    uv_layer_name = None
            uv_layer_name = uv_layer_name or "UVMap"

            saved_uv_bbox = _get_curve_saved_uv_bbox(curve_obj)
            old_uv_bbox = _uv_bbox(old_export_mesh, uv_layer_name=uv_layer_name)
            target_uv_bbox = saved_uv_bbox or old_uv_bbox
            _debug_uv(
                context,
                f"finish_editing: curve={curve_obj.name} export={export_obj.name} uv={uv_layer_name} saved={saved_uv_bbox} old={old_uv_bbox} target={target_uv_bbox}",
            )
            old_materials = []
            try:
                if old_export_mesh is not None and hasattr(old_export_mesh, "materials"):
                    old_materials = list(old_export_mesh.materials)
            except Exception:
                old_materials = []

            _safe_mode_set(context, curve_obj, "OBJECT")

            try:
                new_base_mesh = _mesh_new_from_curve(context, curve_obj)
            except Exception:
                any_failed = True
                continue

            new_export_mesh = new_base_mesh.copy()

            try:
                can_apply_deltas = (
                    old_export_mesh is not None
                    and old_base_mesh is not None
                    and len(old_export_mesh.vertices) == len(old_base_mesh.vertices)
                    and len(new_export_mesh.vertices) == len(old_base_mesh.vertices)
                )
            except Exception:
                can_apply_deltas = False

            if can_apply_deltas:
                try:
                    for i, v in enumerate(new_export_mesh.vertices):
                        v.co = v.co + (old_export_mesh.vertices[i].co - old_base_mesh.vertices[i].co)
                except Exception:
                    pass

            try:
                new_export_mesh.materials.clear()
            except Exception:
                pass
            for mat in old_materials:
                if mat is None:
                    continue
                try:
                    new_export_mesh.materials.append(mat)
                except Exception:
                    pass

            # Preserve UVs exactly when topology matches (most common when toggling Curve <-> Mesh
            # without changing curve point counts). This avoids any unwrap/fit churn.
            uv_copied = False
            try:
                uv_copied = _copy_uv_layer_by_index(old_export_mesh, new_export_mesh, uv_layer_name)
            except Exception:
                uv_copied = False
            _debug_uv(context, f"finish_editing: uv_copied={uv_copied}")

            _replace_mesh_data(base_obj, new_base_mesh)
            _replace_mesh_data(export_obj, new_export_mesh)

            try:
                export_obj.matrix_world = curve_obj.matrix_world
                base_obj.matrix_world = curve_obj.matrix_world
            except Exception:
                pass

            try:
                curve_obj.hide_viewport = True
                curve_obj.hide_select = True
            except Exception:
                pass
            try:
                export_obj.hide_viewport = False
                export_obj.hide_select = False
                export_obj.hide_render = False
            except Exception:
                pass
            try:
                base_obj.hide_viewport = True
                base_obj.hide_select = True
                base_obj.hide_render = True
            except Exception:
                pass

            ok_unwrap = True
            if not uv_copied:
                ok_unwrap = _follow_active_quads_unwrap(context, export_obj, uv_layer_name=uv_layer_name)
                if not ok_unwrap:
                    any_unwrap_failed = True

                # UV ops run in Edit Mode (BMesh). Switch back to Object Mode to flush results
                # onto the Mesh datablock before applying bbox fitting.
                _safe_mode_set(context, export_obj, "OBJECT")

            # Preserve the user's last UV scale/offset across regenerations.
            # Prefer the bbox saved when leaving Edit Mesh, then fall back to the previous mesh bbox.
            applied = False
            if target_uv_bbox is not None:
                try:
                    applied = _fit_uv_to_bbox(export_obj.data, target_uv_bbox, uv_layer_name=uv_layer_name)
                except Exception:
                    applied = False
            _debug_uv(
                context,
                f"finish_editing: unwrap_ok={ok_unwrap} fit_applied={applied} new_bbox={_uv_bbox(getattr(export_obj, 'data', None), uv_layer_name=uv_layer_name)}",
            )
            if applied and target_uv_bbox is not None:
                _set_curve_saved_uv_layer_name(curve_obj, uv_layer_name)
                _set_curve_saved_uv_bbox(curve_obj, target_uv_bbox)
            elif uv_copied:
                # If we copied UVs exactly, treat the copied bbox as authoritative.
                try:
                    copied_bbox = _uv_bbox(getattr(export_obj, "data", None), uv_layer_name=uv_layer_name)
                except Exception:
                    copied_bbox = None
                if copied_bbox is not None:
                    _set_curve_saved_uv_layer_name(curve_obj, uv_layer_name)
                    _set_curve_saved_uv_bbox(curve_obj, copied_bbox)

            export_objs.append(export_obj)

        if not export_objs:
            self.report({"ERROR"}, "No export meshes were generated.")
            return {"CANCELLED"}

        # Select results and make the active one match the previously active curve (if possible).
        _deselect_all(context)
        active_export = export_objs[0]
        for export_obj in export_objs:
            try:
                export_obj.select_set(True)
            except Exception:
                pass
            try:
                if export_obj.get("tlg_line_id") and export_obj.get("tlg_line_id") == active_curve.get("tlg_line_id"):
                    active_export = export_obj
            except Exception:
                if export_obj.get("tlg_source_curve") == getattr(active_curve, "name", None):
                    active_export = export_obj
        context.view_layer.objects.active = active_export

        # For single-object workflows, drop into Edit Mode on the export mesh.
        _safe_mode_set(context, active_export, "OBJECT")
        if len(export_objs) == 1:
            _safe_mode_set(context, active_export, "EDIT")

        if any_failed:
            self.report({"WARNING"}, "Some selected taxi lines failed to generate.")
        elif any_unwrap_failed:
            self.report({"WARNING"}, "Export mesh updated, but UV unwrap failed on one or more lines.")
        else:
            self.report({"INFO"}, "Export mesh updated from curve.")
        return {"FINISHED"}
