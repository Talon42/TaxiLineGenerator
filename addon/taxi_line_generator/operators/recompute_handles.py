import bpy

from ..curve_utils import apply_taxi_handles_to_spline
from ..properties import is_taxi_curve


def _safe_mode_set(context, obj, mode):
    if context is None or obj is None:
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


def _iter_target_curves(context):
    selected = [o for o in context.selected_objects if is_taxi_curve(o)]
    if selected:
        return selected
    active = context.view_layer.objects.active
    if is_taxi_curve(active):
        return [active]
    return []


class TAXILINES_OT_recompute_handles(bpy.types.Operator):
    bl_idname = "taxilines.recompute_handles"
    bl_label = "Recompute Taxi Handles"
    bl_description = "Recompute curve handles using Taxi Line Generator's smoothing rules (fixes sharp corner kinks)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        curves = _iter_target_curves(context)
        if not curves:
            self.report({"ERROR"}, "Select a Taxi Line curve.")
            return {"CANCELLED"}

        active_before = context.view_layer.objects.active
        was_edit = context.mode == "EDIT_CURVE" and is_taxi_curve(active_before)
        if was_edit:
            _safe_mode_set(context, active_before, "OBJECT")

        changed = 0
        for curve_obj in curves:
            curve_data = getattr(curve_obj, "data", None)
            if curve_data is None:
                continue

            for spline in curve_data.splines:
                if spline.type != "BEZIER":
                    continue
                apply_taxi_handles_to_spline(spline)
                changed += 1

            try:
                curve_obj.data.update_tag()
                curve_obj.update_tag()
            except Exception:
                pass

        if was_edit:
            _safe_mode_set(context, active_before, "EDIT")

        self.report({"INFO"}, f"Recomputed handles on {changed} spline(s).")
        return {"FINISHED"}

