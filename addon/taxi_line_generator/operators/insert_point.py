import bpy
from bpy_extras import view3d_utils
from mathutils import geometry
from mathutils import Vector


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


def _get_mouse_ray(context, mouse_xy):
    region = context.region
    rv3d = context.region_data
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse_xy)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse_xy)
    return origin, direction


def _intersect_ray_with_plane_z(origin, direction, plane_z=0.0):
    if abs(direction.z) < 1e-8:
        return None
    t = (plane_z - origin.z) / direction.z
    if t < 0:
        return None
    return origin + direction * t


def _iter_bezier_splines(curve_data):
    for spline in curve_data.splines:
        if spline.type != "BEZIER":
            continue
        if len(spline.bezier_points) < 2:
            continue
        yield spline


def _find_nearest_segment_at_mouse(context, curve_obj, mouse_xy, resolution=40):
    region = context.region
    rv3d = context.region_data
    if region is None or rv3d is None:
        return None

    def closest_on_seg_2d(a2, b2, p2):
        v = b2 - a2
        denom = v.dot(v)
        if denom <= 1e-12:
            return (p2 - a2).length, 0.0
        u = (p2 - a2).dot(v) / denom
        u = 0.0 if u < 0.0 else 1.0 if u > 1.0 else u
        c = a2 + v * u
        return (p2 - c).length, u

    best = None
    best_dist = 1e18

    world = curve_obj.matrix_world
    curve_data = curve_obj.data

    for spline in _iter_bezier_splines(curve_data):
        bps = spline.bezier_points
        for i in range(len(bps) - 1):
            a = bps[i]
            b = bps[i + 1]

            samples = geometry.interpolate_bezier(
                Vector(a.co),
                Vector(a.handle_right),
                Vector(b.handle_left),
                Vector(b.co),
                resolution,
            )

            pts2d = []
            for p in samples:
                p2d = view3d_utils.location_3d_to_region_2d(region, rv3d, world @ p)
                pts2d.append(Vector(p2d) if p2d is not None else None)

            # Measure distance to the polyline formed by the sampled points (more robust than
            # checking only sample-point distances).
            denom = (len(samples) - 1)
            for j in range(len(samples) - 1):
                a2 = pts2d[j]
                b2 = pts2d[j + 1]
                if a2 is None or b2 is None:
                    continue
                d, u = closest_on_seg_2d(a2, b2, mouse_xy)
                if d < best_dist:
                    best_dist = d
                    t = (j + u) / denom if denom > 0 else 0.0
                    best = (spline, i, t)

    return best, best_dist


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
    if hasattr(dst, "select_control_point"):
        dst.select_control_point = bool(getattr(src, "select_control_point", False))


def _rebuild_spline_insert_through(curve_data, spline, seg_index, local_co):
    bps = spline.bezier_points
    n = len(bps)
    if seg_index < 0 or seg_index >= n - 1:
        return None

    # Create a new spline with one extra point, then delete the old spline.
    new_spline = curve_data.splines.new(type="BEZIER")
    new_spline.bezier_points.add(count=n)  # adds n points + the initial = n+1 total
    _copy_spline_settings(spline, new_spline)

    new_bps = new_spline.bezier_points
    insert_at = seg_index + 1

    # Copy points before insertion.
    for i in range(insert_at):
        _copy_bezier_point(bps[i], new_bps[i])

    # Inserted point: force the curve to pass through the clicked position by
    # creating two straight Bezier segments (left->mid->right).
    mid = new_bps[insert_at]
    mid.co = Vector(local_co)
    if hasattr(mid, "radius"):
        left_r = float(getattr(bps[seg_index], "radius", 1.0))
        right_r = float(getattr(bps[seg_index + 1], "radius", 1.0))
        mid.radius = (left_r + right_r) * 0.5
    if hasattr(mid, "tilt"):
        left_t = float(getattr(bps[seg_index], "tilt", 0.0))
        right_t = float(getattr(bps[seg_index + 1], "tilt", 0.0))
        mid.tilt = (left_t + right_t) * 0.5
    if hasattr(mid, "select_control_point"):
        mid.select_control_point = True

    # Copy points after insertion.
    for i in range(insert_at, n):
        _copy_bezier_point(bps[i], new_bps[i + 1])

    # Force straight segments into / out of the inserted point (no automatic handle solver).
    left = new_bps[seg_index]
    right = new_bps[seg_index + 2]

    pL = Vector(left.co)
    pM = Vector(mid.co)
    pR = Vector(right.co)

    left.handle_right_type = "FREE"
    mid.handle_left_type = "FREE"
    mid.handle_right_type = "FREE"
    right.handle_left_type = "FREE"

    left.handle_right = pL + (pM - pL) / 3.0
    mid.handle_left = pM - (pM - pL) / 3.0

    mid.handle_right = pM + (pR - pM) / 3.0
    right.handle_left = pR - (pR - pM) / 3.0

    # Remove old spline.
    curve_data.splines.remove(spline)
    return new_spline


class TAXILINES_OT_insert_point_at_mouse(bpy.types.Operator):
    bl_idname = "taxilines.insert_point"
    bl_label = "Insert Taxi Point Here"
    bl_description = "Insert a Bezier point at the clicked location on the active curve (preserves curve shape)"
    bl_options = {"REGISTER", "UNDO"}

    search_radius_px: bpy.props.IntProperty(
        name="Search Radius (px)",
        description="Legacy: kept for debugging; insert no longer requires clicking close to the curve",
        default=120,
        min=5,
        soft_max=200,
    )

    sample_resolution: bpy.props.IntProperty(
        name="Sampling Resolution",
        description="Higher = more accurate hit location, slower",
        default=40,
        min=12,
        soft_max=120,
    )

    _mouse_xy = None

    def invoke(self, context, event):
        self._mouse_xy = Vector((event.mouse_region_x, event.mouse_region_y))
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != "CURVE" or obj.data is None:
            self.report({"ERROR"}, "Active object must be a curve.")
            return {"CANCELLED"}

        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"ERROR"}, "Run this in the 3D View.")
            return {"CANCELLED"}

        mouse_xy = self._mouse_xy
        if mouse_xy is None:
            self.report({"ERROR"}, "No mouse position.")
            return {"CANCELLED"}

        was_edit = context.mode == "EDIT_CURVE"
        _safe_mode_set(context, obj, "OBJECT")

        # Taxi lines are created on Z=0; interpret the click in 3D by intersecting the view ray with Z=0.
        origin, direction = _get_mouse_ray(context, mouse_xy)
        hit_world = _intersect_ray_with_plane_z(origin, direction, plane_z=0.0)
        if hit_world is None:
            if was_edit:
                _safe_mode_set(context, obj, "EDIT")
            self.report({"WARNING"}, "Could not project click to Z=0 plane.")
            return {"CANCELLED"}

        best, dist = _find_nearest_segment_at_mouse(
            context,
            obj,
            mouse_xy,
            resolution=int(self.sample_resolution),
        )
        if best is None:
            if was_edit:
                _safe_mode_set(context, obj, "EDIT")
            self.report({"WARNING"}, "Could not find a curve segment under this view to insert into.")
            return {"CANCELLED"}

        spline, seg_index, t = best
        local_hit = obj.matrix_world.inverted() @ hit_world
        _rebuild_spline_insert_through(obj.data, spline, seg_index, local_hit)

        obj.data.update_tag()
        obj.update_tag()
        if context.view_layer:
            context.view_layer.update()

        if was_edit:
            _safe_mode_set(context, obj, "EDIT")

        return {"FINISHED"}


def draw_insert_point_menu(self, context):
    obj = context.active_object
    if obj is None or obj.type != "CURVE":
        return
    self.layout.separator()
    prev = self.layout.operator_context
    try:
        # We need the mouse position from the click that opened the context menu,
        # so run this operator as INVOKE (not EXEC) to receive the event.
        self.layout.operator_context = "INVOKE_DEFAULT"
        self.layout.operator("taxilines.insert_point", icon="IPO_BEZIER")
    finally:
        self.layout.operator_context = prev


__all__ = ("TAXILINES_OT_insert_point_at_mouse", "draw_insert_point_menu")
