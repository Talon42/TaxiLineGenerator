import bpy
from bpy_extras import view3d_utils

from ..curve_utils import apply_taxi_handles_to_spline
from ..properties import ensure_taxi_preview, is_taxi_curve


def _get_mouse_ray(context, event):
    region = context.region
    rv3d = context.region_data
    coord = (event.mouse_region_x, event.mouse_region_y)

    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    return origin, direction


def _intersect_ray_with_plane(origin, direction, plane_z=0.0):
    if abs(direction.z) < 1e-8:
        return None

    t = (plane_z - origin.z) / direction.z
    if t < 0:
        return None

    return origin + direction * t


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


def _copy_spline_settings(src, dst):
    for name in (
        "resolution_u",
        "resolution_v",
        "tilt_interpolation",
        "radius_interpolation",
        "use_cyclic_u",
        "use_endpoint_u",
        "use_smooth",
    ):
        if hasattr(src, name) and hasattr(dst, name):
            try:
                setattr(dst, name, getattr(src, name))
            except Exception:
                pass


def _copy_bezier_point(src, dst):
    dst.co = src.co.copy()
    dst.handle_left = src.handle_left.copy()
    dst.handle_right = src.handle_right.copy()
    dst.handle_left_type = src.handle_left_type
    dst.handle_right_type = src.handle_right_type
    if hasattr(src, "radius") and hasattr(dst, "radius"):
        dst.radius = float(src.radius)
    if hasattr(src, "tilt") and hasattr(dst, "tilt"):
        dst.tilt = float(src.tilt)


def _prepend_bezier_point(curve_data, spline, local_co):
    bps = spline.bezier_points
    n = len(bps)

    new_spline = curve_data.splines.new(type="BEZIER")
    new_spline.bezier_points.add(count=n)  # adds n + the initial = n+1 total
    _copy_spline_settings(spline, new_spline)

    new_bps = new_spline.bezier_points
    new_bps[0].co = local_co

    for i in range(n):
        _copy_bezier_point(bps[i], new_bps[i + 1])

    curve_data.splines.remove(spline)
    return new_spline


def _get_single_selected_endpoint(curve_obj):
    if curve_obj is None or curve_obj.type != "CURVE" or curve_obj.data is None:
        return None

    selected = []
    for spline_index, spline in enumerate(curve_obj.data.splines):
        if spline.type != "BEZIER":
            continue
        bps = spline.bezier_points
        for point_index, bp in enumerate(bps):
            if getattr(bp, "select_control_point", False):
                selected.append((spline_index, point_index))

    if len(selected) != 1:
        return None

    spline_index, point_index = selected[0]
    spline = curve_obj.data.splines[spline_index]
    if getattr(spline, "use_cyclic_u", False):
        return None

    bps = spline.bezier_points
    n = len(bps)
    if n == 0:
        return None
    if n == 1:
        return (spline_index, point_index, False)

    if point_index == 0:
        return (spline_index, point_index, True)
    if point_index == n - 1:
        return (spline_index, point_index, False)
    return None


class TAXILINES_OT_resume_taxi_line(bpy.types.Operator):
    bl_idname = "taxilines.resume_taxi_line"
    bl_label = "Resume Taxi Line"
    bl_description = (
        "Extend the active Taxi Line curve from a selected end point (Edit Curve mode). "
        "Left-click to add points on the Z=0 plane. Enter/Right-click to finish."
    )
    bl_options = {"REGISTER", "UNDO"}

    _curve_obj = None
    _spline_index = 0
    _extend_at_start = False
    _initial_points_count = 0

    def _set_ui_state(self, context, *, active):
        wm = getattr(context, "window_manager", None)
        if wm is None:
            return

        try:
            if hasattr(wm, "tlg_ui_is_resuming_line"):
                wm.tlg_ui_is_resuming_line = bool(active)
            if active and hasattr(wm, "tlg_ui_is_drawing_line"):
                wm.tlg_ui_is_drawing_line = False
        except Exception:
            pass

        if getattr(context, "area", None) is not None:
            try:
                context.area.tag_redraw()
            except Exception:
                pass

    @classmethod
    def poll(cls, context):
        obj = getattr(context, "active_object", None)
        if obj is None or getattr(obj, "type", None) != "CURVE":
            return False
        if getattr(context, "mode", None) != "EDIT_CURVE":
            return False
        if not is_taxi_curve(obj):
            return False
        try:
            return _get_single_selected_endpoint(obj) is not None
        except Exception:
            return False

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"ERROR"}, "Run this in the 3D View.")
            return {"CANCELLED"}

        if context.mode != "EDIT_CURVE":
            self.report({"ERROR"}, "Switch to Edit Curve mode to resume a line.")
            return {"CANCELLED"}

        obj = context.active_object
        if obj is None or obj.type != "CURVE" or obj.data is None:
            self.report({"ERROR"}, "Active object must be a curve.")
            return {"CANCELLED"}

        if not is_taxi_curve(obj):
            self.report({"ERROR"}, "Active curve is not a Taxi Line curve.")
            return {"CANCELLED"}

        try:
            context.view_layer.objects.active = obj
            obj.select_set(True)
        except Exception:
            pass

        picked = _get_single_selected_endpoint(obj)
        if picked is None:
            self.report({"ERROR"}, "Select exactly one non-cyclic end point on the curve.")
            return {"CANCELLED"}

        spline_index, _point_index, extend_at_start = picked
        spline = obj.data.splines[spline_index]
        bps = spline.bezier_points

        _safe_mode_set(context, obj, "OBJECT")
        ensure_taxi_preview(obj, context=context)
        _safe_mode_set(context, obj, "EDIT")

        self._curve_obj = obj
        self._spline_index = int(spline_index)
        self._extend_at_start = bool(extend_at_start)
        self._initial_points_count = int(len(bps))

        self._set_ui_state(context, active=True)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        nav_event_types = {
            "MIDDLEMOUSE",
            "WHEELUPMOUSE",
            "WHEELDOWNMOUSE",
            "WHEELINMOUSE",
            "WHEELOUTMOUSE",
            "MOUSEPAN",
            "TRACKPADPAN",
            "TRACKPADZOOM",
            "NDOF_MOTION",
            "NDOF_BUTTON_MENU",
            "NDOF_BUTTON_FIT",
            "NDOF_BUTTON_TOP",
            "NDOF_BUTTON_BOTTOM",
            "NDOF_BUTTON_LEFT",
            "NDOF_BUTTON_RIGHT",
            "NDOF_BUTTON_FRONT",
            "NDOF_BUTTON_BACK",
            "NDOF_BUTTON_ISO1",
            "NDOF_BUTTON_ISO2",
        }
        if event.type in nav_event_types:
            return {"PASS_THROUGH"}

        if event.alt and event.type in {"LEFTMOUSE", "RIGHTMOUSE"}:
            return {"PASS_THROUGH"}

        if self._curve_obj is None or self._curve_obj.data is None:
            self._set_ui_state(context, active=False)
            return {"CANCELLED"}

        # Finish (Right Click / Esc)
        if event.type in {"RIGHTMOUSE", "ESC"} and event.value == "PRESS":
            _safe_mode_set(context, self._curve_obj, "EDIT")
            self._set_ui_state(context, active=False)
            return {"FINISHED"}

        # Finish (Enter)
        if event.type in {"RET", "NUMPAD_ENTER"} and event.value == "PRESS":
            _safe_mode_set(context, self._curve_obj, "EDIT")
            self._set_ui_state(context, active=False)
            return {"FINISHED"}

        # Undo last placed point (keep resuming).
        if event.type == "Z" and event.value == "PRESS" and (event.ctrl or event.oskey):
            curve_data = self._curve_obj.data
            if len(curve_data.splines) <= self._spline_index:
                return {"RUNNING_MODAL"}

            spline = curve_data.splines[self._spline_index]
            if spline.type != "BEZIER":
                return {"RUNNING_MODAL"}

            points = spline.bezier_points
            if len(points) <= max(1, self._initial_points_count):
                return {"RUNNING_MODAL"}

            _safe_mode_set(context, self._curve_obj, "EDIT")
            try:
                for bp in points:
                    bp.select_control_point = False
                    if hasattr(bp, "select_left_handle"):
                        bp.select_left_handle = False
                    if hasattr(bp, "select_right_handle"):
                        bp.select_right_handle = False

                target = points[0] if self._extend_at_start else points[-1]
                target.select_control_point = True
                with context.temp_override(
                    object=self._curve_obj,
                    active_object=self._curve_obj,
                    selected_objects=[self._curve_obj],
                    selected_editable_objects=[self._curve_obj],
                ):
                    bpy.ops.curve.delete(type="VERT")
            except Exception:
                return {"RUNNING_MODAL"}

            _safe_mode_set(context, self._curve_obj, "OBJECT")
            try:
                apply_taxi_handles_to_spline(spline)
                self._curve_obj.data.update_tag()
                self._curve_obj.update_tag()
            except Exception:
                pass

            _safe_mode_set(context, self._curve_obj, "EDIT")
            if context.area is not None:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        # Add point (Left Click)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            _safe_mode_set(context, self._curve_obj, "OBJECT")

            origin, direction = _get_mouse_ray(context, event)
            hit = _intersect_ray_with_plane(origin, direction, plane_z=0.0)
            if hit is None:
                self.report({"WARNING"}, "Could not place point.")
                _safe_mode_set(context, self._curve_obj, "EDIT")
                return {"RUNNING_MODAL"}

            curve_data = self._curve_obj.data
            if len(curve_data.splines) <= self._spline_index:
                _safe_mode_set(context, self._curve_obj, "EDIT")
                self._set_ui_state(context, active=False)
                return {"CANCELLED"}

            spline = curve_data.splines[self._spline_index]
            if spline.type != "BEZIER":
                _safe_mode_set(context, self._curve_obj, "EDIT")
                self._set_ui_state(context, active=False)
                return {"CANCELLED"}

            local_hit = self._curve_obj.matrix_world.inverted() @ hit

            if self._extend_at_start:
                spline = _prepend_bezier_point(curve_data, spline, local_hit)
                self._spline_index = len(curve_data.splines) - 1
            else:
                spline.bezier_points.add(count=1)
                spline.bezier_points[-1].co = local_hit

            try:
                apply_taxi_handles_to_spline(spline)
            except Exception:
                pass

            try:
                for bp in spline.bezier_points:
                    bp.select_control_point = False
                endpoint = spline.bezier_points[0] if self._extend_at_start else spline.bezier_points[-1]
                endpoint.select_control_point = True
            except Exception:
                pass

            try:
                self._curve_obj.data.update_tag()
                self._curve_obj.update_tag()
            except Exception:
                pass

            _safe_mode_set(context, self._curve_obj, "EDIT")
            if context.area is not None:
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}
