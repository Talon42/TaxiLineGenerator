from math import acos, degrees

from mathutils import Vector


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _norm_or(v, fallback):
    if v.length <= 1e-9:
        return fallback
    return v.normalized()


def _dir(a, b, fallback):
    return _norm_or(Vector(b) - Vector(a), fallback)


def apply_taxi_handles_to_spline(spline):
    pts = spline.bezier_points
    n = len(pts)
    if n < 2:
        return

    # Fixed "taxi line" handle behavior (no user slider):
    # - Default: smooth tangent (bisector) for rounded corners.
    # - Special-case ~90° corners for a cleaner fillet-like turn.
    # - Straighten approach/departure on moderate turns to avoid "snaking".
    handle_scale = 0.34

    # Explicit handles reduce overshoot and keep corners predictable.
    for bp in pts:
        bp.handle_left_type = "FREE"
        bp.handle_right_type = "FREE"

    for i, bp in enumerate(pts):
        p = Vector(bp.co)

        if i == 0:
            p1 = Vector(pts[1].co)
            v = p1 - p
            dist = v.length
            if dist > 1e-6:
                d = v.normalized()
                bp.handle_left = p
                bp.handle_right = p + d * (dist * handle_scale)
            continue

        if i == n - 1:
            p0 = Vector(pts[i - 1].co)
            v = p0 - p
            dist = v.length
            if dist > 1e-6:
                d = v.normalized()
                bp.handle_left = p + d * (dist * handle_scale)
                bp.handle_right = p
            continue

        prev = Vector(pts[i - 1].co)
        nxt = Vector(pts[i + 1].co)
        v_in = prev - p
        v_out = nxt - p
        dist_in = v_in.length
        dist_out = v_out.length
        if dist_in <= 1e-6 or dist_out <= 1e-6:
            continue

        t_in = _norm_or(p - prev, Vector((1.0, 0.0, 0.0)))
        t_out = _norm_or(nxt - p, Vector((1.0, 0.0, 0.0)))
        deflection = degrees(acos(_clamp(t_in.dot(t_out), -1.0, 1.0)))  # 0 straight, 180 reverse

        # For near-right angles, prefer segment-aligned handles (fillet-like) so the
        # path stays straight up to the corner and the outside edge rounds cleanly.
        if 70.0 <= deflection <= 110.0:
            vL = -t_in
            vR = t_out
            local_scale = 0.42
        else:
            # Default: smooth tangent (colinear handles) for a rounded corner.
            t = t_in + t_out
            if t.length <= 1e-9:
                t = t_out
            t = _norm_or(t, t_out)
            vL = -t
            vR = t
            local_scale = handle_scale

        base = min(dist_in, dist_out)
        length = base * local_scale

        # Reduce length for extremely sharp corners (prevents loops/overshoot) but keep rounding.
        if deflection < 20.0:
            length *= 0.55
        elif deflection < 45.0:
            length *= 0.75

        bp.handle_left = p + vL * length
        bp.handle_right = p + vR * length

    # Second pass: straighten approach/departure handles before/after significant turns
    # to avoid "snaking" where the curve initially bends the wrong way.
    # Only apply to moderate turns; for right angles we handle the corner point directly.
    turn_min_deg = 25.0
    turn_max_deg = 70.0
    approach_scale = 0.08

    for i in range(1, n - 1):
        p_prev = Vector(pts[i - 1].co)
        p = Vector(pts[i].co)
        p_next = Vector(pts[i + 1].co)

        a = _dir(p_prev, p, Vector((1.0, 0.0, 0.0)))
        b = _dir(p, p_next, Vector((1.0, 0.0, 0.0)))
        deflection = degrees(acos(_clamp(a.dot(b), -1.0, 1.0)))  # 0 straight, 90 right angle

        if deflection < turn_min_deg or deflection > turn_max_deg:
            continue

        # Straighten the segment BEFORE the turn: force previous point's outgoing handle
        # to lie on the segment direction (no sideways component).
        dist_prev = (p - p_prev).length
        if dist_prev > 1e-6 and i - 1 >= 0:
            d = (p - p_prev).normalized()
            pts[i - 1].handle_right_type = "FREE"
            pts[i - 1].handle_right = p_prev + d * (dist_prev * approach_scale)

        # Straighten the segment AFTER the turn: force next point's incoming handle similarly.
        dist_next = (p_next - p).length
        if dist_next > 1e-6 and i + 1 < n:
            d = (p - p_next).normalized()
            pts[i + 1].handle_left_type = "FREE"
            pts[i + 1].handle_left = p_next + d * (dist_next * approach_scale)


def apply_taxi_handles_to_curve(curve_obj, corner_tightness=0.5):
    if curve_obj is None or curve_obj.type != "CURVE" or curve_obj.data is None:
        return
    for spline in curve_obj.data.splines:
        if spline.type != "BEZIER":
            continue
        apply_taxi_handles_to_spline(spline)
