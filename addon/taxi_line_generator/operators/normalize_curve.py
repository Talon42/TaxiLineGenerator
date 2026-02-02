import bpy
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


def _sample_spline_segment_points(bezier_points, i0, i1, resolution=24):
    pts = []
    for i in range(i0, i1):
        a = bezier_points[i]
        b = bezier_points[i + 1]
        seg = geometry.interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, resolution)
        if i != i0:
            seg = seg[1:]
        pts.extend(seg)
    return pts


def _resample_polyline_evenly(points, count):
    if count <= 1:
        return points[:1]
    if len(points) < 2:
        return points

    cumulative = [0.0]
    for i in range(1, len(points)):
        cumulative.append(cumulative[-1] + (points[i] - points[i - 1]).length)
    total = cumulative[-1]
    if total <= 1e-9:
        return [points[0].copy() for _ in range(count)]

    out = []
    for k in range(count):
        d = total * (k / (count - 1))
        j = 1
        while j < len(cumulative) and cumulative[j] < d:
            j += 1
        if j >= len(cumulative):
            out.append(points[-1].copy())
            continue
        d0 = cumulative[j - 1]
        d1 = cumulative[j]
        if d1 - d0 <= 1e-12:
            out.append(points[j].copy())
            continue
        t = (d - d0) / (d1 - d0)
        out.append(points[j - 1].lerp(points[j], t))
    return out


def _normalize_segment_preserve_shape(bps, i0, i1, resolution):
    n = len(bps)
    if n < 2 or i1 <= i0:
        return False

    count = i1 - i0 + 1

    # Snapshot old control points + handles so we can preserve local curve shape
    # by moving handles along with their points (and scaling to match new spacing).
    old = []
    for idx in range(i0, i1 + 1):
        bp = bps[idx]
        old.append(
            (
                bp.co.copy(),
                bp.handle_left.copy(),
                bp.handle_right.copy(),
            )
        )

    start = old[0][0].copy()
    end = old[-1][0].copy()

    sampled = _sample_spline_segment_points(bps, i0, i1, resolution=resolution)
    if len(sampled) < 2:
        return False

    targets = _resample_polyline_evenly(sampled, count)
    if len(targets) != count:
        return False

    targets[0] = start
    targets[-1] = end

    eps = 1e-9

    # Apply points + translated/scaled handles.
    for local_i, idx in enumerate(range(i0, i1 + 1)):
        bp = bps[idx]
        old_co, old_hl, old_hr = old[local_i]
        new_co = targets[local_i]

        delta = new_co - old_co
        left_vec = old_hl - old_co
        right_vec = old_hr - old_co

        # Scale handle lengths relative to the new spacing to avoid loops/overshoot.
        # Keep boundary handles that affect the unselected outside segments unchanged
        # (only translated), so normalization doesn't disturb the rest of the spline.
        left_scale = 1.0
        right_scale = 1.0

        if local_i > 0:
            old_prev_len = (old_co - old[local_i - 1][0]).length
            new_prev_len = (new_co - targets[local_i - 1]).length
            if old_prev_len > eps:
                left_scale = new_prev_len / old_prev_len

        if local_i < count - 1:
            old_next_len = (old[local_i + 1][0] - old_co).length
            new_next_len = (targets[local_i + 1] - new_co).length
            if old_next_len > eps:
                right_scale = new_next_len / old_next_len

        bp.co = new_co
        bp.handle_left_type = "FREE"
        bp.handle_right_type = "FREE"

        # Left handle: preserve outside continuity on the start boundary.
        if idx == i0 and i0 > 0:
            bp.handle_left = old_hl + delta
        else:
            bp.handle_left = new_co + (left_vec * left_scale)

        # Right handle: preserve outside continuity on the end boundary.
        if idx == i1 and i1 < n - 1:
            bp.handle_right = old_hr + delta
        else:
            bp.handle_right = new_co + (right_vec * right_scale)

    # After normalization, switch the affected span to Blender's AUTO handles to
    # remove small curvature "humps" at each control point and produce a smoother,
    # more taxi-line-like arc across many points.
    #
    # Preserve the boundary handle on the OUTSIDE of the selection so we don't
    # disturb the unselected parts of the spline.
    if i0 > 0:
        keep_left = (
            bps[i0].handle_left.copy(),
            bps[i0].handle_left_type,
        )
    else:
        keep_left = None

    if i1 < n - 1:
        keep_right = (
            bps[i1].handle_right.copy(),
            bps[i1].handle_right_type,
        )
    else:
        keep_right = None

    for idx in range(i0, i1 + 1):
        bp = bps[idx]
        # Blender 3.6 supports: FREE, VECTOR, ALIGNED, AUTO (no AUTO_CLAMPED).
        # Use AUTO for smoothness; later versions will also accept AUTO_CLAMPED.
        try:
            bp.handle_left_type = "AUTO_CLAMPED"
            bp.handle_right_type = "AUTO_CLAMPED"
        except Exception:
            bp.handle_left_type = "AUTO"
            bp.handle_right_type = "AUTO"

    if keep_left is not None:
        bps[i0].handle_left_type = "FREE"
        bps[i0].handle_left = keep_left[0]
        bps[i0].handle_left_type = keep_left[1]

    if keep_right is not None:
        bps[i1].handle_right_type = "FREE"
        bps[i1].handle_right = keep_right[0]
        bps[i1].handle_right_type = keep_right[1]

    return True


class TAXILINES_OT_normalize_curve(bpy.types.Operator):
    bl_idname = "taxilines.normalize_curve"
    bl_label = "Normalize Curve"
    bl_description = "Evenly redistribute points between the first and last selected Bezier point"
    bl_options = {"REGISTER", "UNDO"}

    resolution: bpy.props.IntProperty(
        name="Sampling Resolution",
        description="Higher = more accurate normalization, slower",
        default=24,
        min=8,
        soft_max=64,
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != "CURVE" or obj.data is None:
            self.report({"ERROR"}, "Active object must be a curve.")
            return {"CANCELLED"}

        # Work on the underlying data in Object Mode, then return to Edit Mode.
        was_edit = context.mode == "EDIT_CURVE"
        _safe_mode_set(context, obj, "OBJECT")

        curve_data = obj.data
        changed = 0

        for spline in curve_data.splines:
            if spline.type != "BEZIER":
                continue

            bps = spline.bezier_points
            selected = [i for i, bp in enumerate(bps) if getattr(bp, "select_control_point", False)]
            if len(selected) < 2:
                continue

            i0 = min(selected)
            i1 = max(selected)
            if i1 - i0 < 1:
                continue

            # Sample the existing curve segment (including its current shape/curvature),
            # redistribute points evenly along that path, and preserve the local curve
            # by moving/scaling handles with their points.
            ok = _normalize_segment_preserve_shape(
                bps,
                i0,
                i1,
                resolution=max(32, int(self.resolution)),
            )
            if ok:
                changed += 1

        if changed == 0:
            self.report({"WARNING"}, "Select 2+ Bezier points on a spline to normalize.")
        else:
            obj.data.update_tag()
            obj.update_tag()
            if context.view_layer:
                context.view_layer.update()

        if was_edit:
            _safe_mode_set(context, obj, "EDIT")

        return {"FINISHED"}
