import bpy  # pyright: ignore[reportMissingImports]

from .properties import ensure_taxi_preview, get_source_curve_for_mesh, tlg_parse_base_name, tlg_sync_linked_object_names

_IS_SYNCING = False
_PENDING_BY_LINE_ID = {}
_TIMER_ARMED = False
_LAST_ROLES_BY_LINE_ID = None

_TLG_ROOT_COLLECTION_NAME = "Taxi Lines"
_TLG_CHILD_COLLECTION_NAMES = (
    "EDIT - Curves",
    "EXPORT - Meshes",
    "_INTERNAL - Base",
)


def _infer_role(obj):
    if obj is None:
        return None
    try:
        t = getattr(obj, "type", None)
    except Exception:
        t = None
    if t == "CURVE":
        return "SRC"
    if t != "MESH":
        return None

    try:
        name = str(getattr(obj, "name", "") or "")
    except Exception:
        name = ""

    if name.endswith("_BASE"):
        return "BASE"
    if name.endswith("_MESH"):
        return "MESH"

    # BASE meshes are internal/hidden; use that as a heuristic when suffix isn't present.
    try:
        if bool(getattr(obj, "hide_select", False)) and bool(getattr(obj, "hide_viewport", False)):
            return "BASE"
    except Exception:
        pass

    return "MESH"


def _iter_possible_tlg_objects():
    try:
        objects = getattr(bpy.data, "objects", None)
    except Exception:
        objects = None
    if not objects:
        return []

    out = []
    for obj in list(objects):
        try:
            t = getattr(obj, "type", None)
        except Exception:
            continue
        if t not in {"CURVE", "MESH"}:
            continue
        try:
            if obj.get("tlg_line_id"):
                out.append(obj)
                continue
        except Exception:
            pass
        if t == "CURVE":
            try:
                if obj.get("tlg_is_taxi_line") or ("taxilines_mesh" in obj):
                    out.append(obj)
                    continue
            except Exception:
                continue
        else:
            try:
                if obj.get("tlg_source_curve") or obj.get("taxilines_source_curve"):
                    out.append(obj)
                    continue
            except Exception:
                continue
    return out


def _build_line_state():
    roles_by_line_id = {}
    objs_by_line_id = {}

    for obj in _iter_possible_tlg_objects():
        line_id = None
        role = None

        try:
            line_id = obj.get("tlg_line_id")
        except Exception:
            line_id = None
        try:
            role = obj.get("tlg_line_role")
        except Exception:
            role = None

        if obj.type == "CURVE":
            ensure_taxi_preview(obj)
            try:
                line_id = obj.get("tlg_line_id")
            except Exception:
                line_id = None
            role = "SRC"
        else:
            curve_obj = get_source_curve_for_mesh(obj)
            if curve_obj is not None:
                ensure_taxi_preview(curve_obj)
                try:
                    line_id = curve_obj.get("tlg_line_id")
                except Exception:
                    line_id = None
                if line_id:
                    try:
                        obj["tlg_line_id"] = line_id
                    except Exception:
                        pass

            if not role:
                role = _infer_role(obj)
                if role:
                    try:
                        obj["tlg_line_role"] = role
                    except Exception:
                        pass

        if not line_id or not role:
            continue

        line_id = str(line_id)
        roles_by_line_id.setdefault(line_id, set()).add(str(role))
        objs_by_line_id.setdefault(line_id, []).append(obj)

    return roles_by_line_id, objs_by_line_id


def _remove_object_and_data(obj):
    if obj is None:
        return
    data = getattr(obj, "data", None)
    data_type = getattr(data, "bl_rna", None).name if data is not None and hasattr(data, "bl_rna") else None
    try:
        bpy.data.objects.remove(obj, do_unlink=True)
    except Exception:
        return

    if data is None:
        return
    try:
        if getattr(data, "users", 0) != 0:
            return
    except Exception:
        return

    try:
        if data_type == "Mesh":
            bpy.data.meshes.remove(data)
        elif data_type == "Curve":
            bpy.data.curves.remove(data)
    except Exception:
        pass


def _is_collection_empty(col):
    if col is None:
        return True
    try:
        if len(getattr(col, "objects", [])) != 0:
            return False
    except Exception:
        return False
    try:
        if len(getattr(col, "children", [])) != 0:
            return False
    except Exception:
        return False
    return True


def _remove_collection_if_empty(col):
    if col is None:
        return False
    if not _is_collection_empty(col):
        return False
    try:
        bpy.data.collections.remove(col, do_unlink=True)
        return True
    except Exception:
        try:
            bpy.data.collections.remove(col)
            return True
        except Exception:
            return False


def _cleanup_empty_taxi_collections():
    root = bpy.data.collections.get(_TLG_ROOT_COLLECTION_NAME)
    if root is None:
        return

    # Remove empty children under Taxi Lines (only if they are actually linked there).
    try:
        root_children = set(list(getattr(root, "children", [])))
    except Exception:
        root_children = set()

    for name in _TLG_CHILD_COLLECTION_NAMES:
        col = bpy.data.collections.get(name)
        if col is None:
            continue
        if root_children and col not in root_children:
            continue
        _remove_collection_if_empty(col)

    # Remove Taxi Lines itself if it becomes empty after pruning children.
    root = bpy.data.collections.get(_TLG_ROOT_COLLECTION_NAME)
    if root is None:
        return
    _remove_collection_if_empty(root)


def _find_curve_by_line_id(line_id: str):
    if not line_id:
        return None
    try:
        objects = getattr(bpy.data, "objects", None)
    except Exception:
        objects = None
    if not objects:
        return None
    for obj in list(objects):
        try:
            if obj.type != "CURVE":
                continue
            if obj.get("tlg_line_id") != line_id:
                continue
            if obj.get("tlg_line_role") != "SRC":
                continue
            return obj
        except Exception:
            continue
    return None


def _depsgraph_update_post(scene, depsgraph):
    global _IS_SYNCING
    if _IS_SYNCING:
        return

    base_by_line_id = {}
    try:
        updates = getattr(depsgraph, "updates", None)
    except Exception:
        updates = None
    if not updates:
        return

    for update in list(updates):
        obj = getattr(update, "id", None)
        if obj is None or getattr(obj, "type", None) not in {"CURVE", "MESH"}:
            continue

        try:
            last = obj.get("tlg_last_seen_name")
        except Exception:
            last = None
        if last == getattr(obj, "name", None):
            continue

        curve_obj = None
        line_id = None
        if obj.type == "CURVE":
            curve_obj = obj
        else:
            curve_obj = get_source_curve_for_mesh(obj)

        if curve_obj is None:
            # Can't safely sync without knowing which line this belongs to.
            continue

        ensure_taxi_preview(curve_obj)
        try:
            line_id = curve_obj.get("tlg_line_id")
        except Exception:
            line_id = None

        # Stamp metadata onto the renamed mesh so future lookups are rename-safe.
        if obj.type == "MESH" and line_id:
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
                        bool(getattr(obj, "hide_select", False)) and bool(getattr(obj, "hide_viewport", False))
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
            try:
                obj["tlg_source_curve"] = curve_obj.name
            except Exception:
                pass

        base = tlg_parse_base_name(getattr(obj, "name", "") or "")
        if not base:
            continue
        if line_id:
            base_by_line_id[str(line_id)] = base

    if not base_by_line_id:
        # Still schedule a state check (captures deletions).
        _queue_name_sync({})
        return

    _queue_name_sync(base_by_line_id)


def _apply_pending_sync():
    global _IS_SYNCING, _TIMER_ARMED, _PENDING_BY_LINE_ID, _LAST_ROLES_BY_LINE_ID
    _TIMER_ARMED = False

    pending = dict(_PENDING_BY_LINE_ID)
    _PENDING_BY_LINE_ID.clear()

    _IS_SYNCING = True
    try:
        # Apply queued renames (if any).
        for line_id, base in pending.items():
            curve_obj = _find_curve_by_line_id(line_id)
            if curve_obj is None:
                continue
            tlg_sync_linked_object_names(curve_obj, base)

        # Sync-delete: if any one of the trio is deleted, delete the other two.
        roles_by_line_id, objs_by_line_id = _build_line_state()
        if _LAST_ROLES_BY_LINE_ID is None:
            _LAST_ROLES_BY_LINE_ID = {k: set(v) for k, v in roles_by_line_id.items()}
            return None

        deleted_any = False
        required = {"SRC", "MESH", "BASE"}
        for line_id, prev_roles in list(_LAST_ROLES_BY_LINE_ID.items()):
            if not prev_roles or not required.issubset(prev_roles):
                continue

            cur_roles = roles_by_line_id.get(line_id, set())
            if not cur_roles:
                continue
            if required.issubset(cur_roles):
                continue

            for obj in list(objs_by_line_id.get(line_id, [])):
                _remove_object_and_data(obj)
            deleted_any = True

        if deleted_any:
            roles_by_line_id, _objs_by_line_id = _build_line_state()
            _cleanup_empty_taxi_collections()

        _LAST_ROLES_BY_LINE_ID = {k: set(v) for k, v in roles_by_line_id.items()}
    finally:
        _IS_SYNCING = False

    # If more were queued during application, schedule another pass.
    if _PENDING_BY_LINE_ID:
        _queue_name_sync({})
    return None


def _queue_name_sync(base_by_line_id):
    global _PENDING_BY_LINE_ID, _TIMER_ARMED
    for line_id, base in (base_by_line_id or {}).items():
        if not line_id or not base:
            continue
        _PENDING_BY_LINE_ID[str(line_id)] = base

    if _TIMER_ARMED:
        return
    _TIMER_ARMED = True
    try:
        bpy.app.timers.register(_apply_pending_sync, first_interval=0.0)
    except Exception:
        _TIMER_ARMED = False


def register_handlers():
    handlers = bpy.app.handlers.depsgraph_update_post
    if _depsgraph_update_post not in handlers:
        handlers.append(_depsgraph_update_post)


def unregister_handlers():
    handlers = bpy.app.handlers.depsgraph_update_post
    try:
        handlers.remove(_depsgraph_update_post)
    except ValueError:
        pass
