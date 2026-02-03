import bpy  # pyright: ignore[reportMissingImports]

from ..properties import get_baked_mesh_for_curve, is_taxi_curve


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

        if obj.type == "CURVE" and obj.data is not None:
            try:
                sx = float(obj.scale.x)
                sy = float(obj.scale.y)
                sz = float(obj.scale.z)
                lines.append(f"  scale=({sx:.6g}, {sy:.6g}, {sz:.6g})")
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
