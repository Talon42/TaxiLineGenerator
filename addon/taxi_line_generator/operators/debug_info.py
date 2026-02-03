import bpy  # pyright: ignore[reportMissingImports]

from ..properties import get_baked_mesh_for_curve, is_taxi_curve


def _uv_bbox(mesh, uv_layer):
    if mesh is None or uv_layer is None:
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


def _append_mesh_uv_debug(lines, mesh_obj, label):
    if mesh_obj is None or mesh_obj.type != "MESH":
        return
    mesh = getattr(mesh_obj, "data", None)
    if mesh is None or not hasattr(mesh, "uv_layers"):
        lines.append(f"  {label}: (no mesh/uv_layers)")
        return

    try:
        active = mesh.uv_layers.active
        active_name = getattr(active, "name", None)
    except Exception:
        active_name = None

    try:
        layers = list(mesh.uv_layers)
    except Exception:
        layers = []

    lines.append(f"  {label}: uv_layers={len(layers)} active={active_name!r}")
    for uv_layer in layers:
        try:
            name = uv_layer.name
        except Exception:
            name = "?"
        bbox = None
        try:
            bbox = _uv_bbox(mesh, uv_layer)
        except Exception:
            bbox = None
        if bbox is None:
            lines.append(f"    - {name}: bbox=None")
        else:
            u0, v0, u1, v1 = bbox
            lines.append(f"    - {name}: bbox=({u0:.6g}, {v0:.6g}, {u1:.6g}, {v1:.6g})")


class TAXILINES_OT_debug_active(bpy.types.Operator):
    bl_idname = "taxilines.debug_active"
    bl_label = "Debug Active Taxi Line"
    bl_description = "Print active Taxi Line debug info to the system console"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        obj = context.view_layer.objects.active
        if obj is None:
            self.report({"ERROR"}, "No active object.")
            return {"CANCELLED"}

        lines = []
        lines.append(f"Active: {obj.name} type={obj.type} mode={context.mode}")
        try:
            lines.append(
                f"  hide_viewport={obj.hide_viewport} hide_select={obj.hide_select} display_type={getattr(obj, 'display_type', '?')}"
            )
        except Exception:
            pass

        if obj.type == "MESH":
            try:
                lines.append(f"  tlg_source_curve={obj.get('tlg_source_curve')!r}")
            except Exception:
                pass
            _append_mesh_uv_debug(lines, obj, label="mesh_uv")

        if obj.type == "CURVE" and obj.data is not None:
            try:
                sx = float(obj.scale.x)
                sy = float(obj.scale.y)
                sz = float(obj.scale.z)
                lines.append(f"  scale=({sx:.6g}, {sy:.6g}, {sz:.6g})")
            except Exception:
                pass
            try:
                lines.append(f"  tlg_export_uv_bbox={obj.get('tlg_export_uv_bbox')!r}")
            except Exception:
                pass
            try:
                width_m = float(getattr(obj, "tlg_line_width", 0.15))
                auto_handles = bool(getattr(obj, "tlg_auto_smooth_handles", True))
                lines.append(f"  tlg_line_width={width_m:.6g} tlg_auto_smooth_handles={auto_handles}")
            except Exception:
                pass
            try:
                splines = obj.data.splines
                lines.append(f"  splines={len(splines)}")
                for i, s in enumerate(splines):
                    if s.type == "BEZIER":
                        lines.append(f"    spline[{i}] type=BEZIER points={len(s.bezier_points)}")
                        try:
                            radii = [float(getattr(bp, "radius", 1.0)) for bp in s.bezier_points]
                            if radii:
                                lines.append(
                                    "      point_radius(min/avg/max)="
                                    + f"{min(radii):.6g}/{(sum(radii)/len(radii)):.6g}/{max(radii):.6g}"
                                )
                        except Exception:
                            pass
                    else:
                        lines.append(f"    spline[{i}] type={s.type}")
            except Exception:
                pass

        baked = get_baked_mesh_for_curve(obj) if obj.type == "CURVE" else None
        if baked is not None:
            lines.append(f"  baked_mesh={baked.name} hide_viewport={baked.hide_viewport} in_collections={len(baked.users_collection)}")
            _append_mesh_uv_debug(lines, baked, label="baked_mesh_uv")

        lines.append(f"  is_taxi_curve={is_taxi_curve(obj)}")
        lines.append(f"  scene.tlg_view_mode={getattr(context.scene, 'tlg_view_mode', '?')}")

        try:
            mod = obj.modifiers.get("TLG_TaxiLinePreview")
            if mod is None:
                lines.append("  modifier=TLG_TaxiLinePreview (missing)")
            else:
                ng = getattr(mod, "node_group", None)
                lines.append(
                    "  modifier=TLG_TaxiLinePreview "
                    + f"show_viewport={getattr(mod, 'show_viewport', '?')} "
                    + f"show_in_editmode={getattr(mod, 'show_in_editmode', '?')} "
                    + f"show_on_cage={getattr(mod, 'show_on_cage', '?')}"
                )
                if ng is None:
                    lines.append("    node_group=None")
                else:
                    lines.append(
                        f"    node_group={ng.name} tlg_version={ng.get('tlg_version')} inputs={len(getattr(ng, 'inputs', []))} nodes={len(getattr(ng, 'nodes', []))}"
                    )
        except Exception:
            pass

        msg = "\n".join(lines)
        print("\n[TaxiLineGenerator Debug]\n" + msg + "\n")
        self.report({"INFO"}, "Wrote debug info to console.")
        return {"FINISHED"}
