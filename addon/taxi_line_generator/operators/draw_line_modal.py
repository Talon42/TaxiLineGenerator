import bpy
from bpy_extras import view3d_utils

from ..properties import _ensure_ribbon_mesh_modifier, _set_modifier_input
from ..curve_utils import apply_taxi_handles_to_spline


def _set_point_handles_smooth(_bp):
    # Backward-compat shim: older modal code called this for the first point.
    # Kept as a no-op so stale registrations don't crash Blender.
    return


def _get_mouse_ray(context, event):
    region = context.region
    rv3d = context.region_data
    coord = (event.mouse_region_x, event.mouse_region_y)

    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    return origin, direction


def _intersect_ray_with_plane(origin, direction, plane_z=0.0):
    # Intersect ray with plane Z = plane_z
    if abs(direction.z) < 1e-8:
        return None

    t = (plane_z - origin.z) / direction.z

    if t < 0:
        return None

    return origin + direction * t


class TAXILINES_OT_draw_taxi_line(bpy.types.Operator):
    bl_idname = "taxilines.draw_taxi_line"
    bl_label = "Draw Taxi Line (Click Points)"
    bl_description = "Click to place points on Z=0 plane. Enter/Right-click to finish."
    bl_options = {"REGISTER", "UNDO"}

    _curve_obj = None
    _spline_index = 0
    _has_first_point = False
    _mesh_obj = None

    def _ensure_collection(self, context, name):
        col = bpy.data.collections.get(name)
        if col is None:
            col = bpy.data.collections.new(name)
            context.scene.collection.children.link(col)
        return col

    def _safe_mode_set(self, context, obj, mode):
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

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            self.report({"ERROR"}, "Run this in the 3D View.")
            return {"CANCELLED"}

        # Create curve data
        curve_data = bpy.data.curves.new("TaxiLineCurve", type="CURVE")
        curve_data.dimensions = "3D"

        # Create object
        curve_obj = bpy.data.objects.new("TaxiLineCurve_SRC", curve_data)

        # Main taxi lines collection (curve is the primary editable object).
        col = self._ensure_collection(context, "TAXI_LINES")

        col.objects.link(curve_obj)
        curve_obj.hide_viewport = False
        curve_obj.hide_select = False
        curve_obj.hide_render = True
        curve_obj.display_type = "WIRE"
        curve_obj.show_in_front = True

        mesh_data = bpy.data.meshes.new("TaxiLineRibbon")
        mesh_obj = bpy.data.objects.new("TaxiLineRibbon", mesh_data)
        col.objects.link(mesh_obj)
        mesh_obj.hide_select = True

        mod = _ensure_ribbon_mesh_modifier(mesh_obj)
        _set_modifier_input(mod, "Source Curve", curve_obj)

        width_m = getattr(context.scene, "tlg_default_width", 0.15)
        curve_obj.tlg_line_width = float(width_m)
        _set_modifier_input(mod, "Width", float(curve_obj.tlg_line_width))

        mesh_obj["taxilines_source_curve"] = curve_obj.name
        curve_obj["taxilines_mesh"] = mesh_obj.name

        # Make active
        context.view_layer.objects.active = curve_obj
        curve_obj.select_set(True)
        self._safe_mode_set(context, curve_obj, "OBJECT")

        # Create first spline
        spline = curve_data.splines.new(type="BEZIER")
        spline.bezier_points.add(count=0)
        self._spline_index = len(curve_data.splines) - 1

        self._curve_obj = curve_obj
        self._mesh_obj = mesh_obj
        self._has_first_point = False

        # Keep the curve in Edit Mode so control points are visible while drawing and after finishing.
        self._safe_mode_set(context, curve_obj, "EDIT")

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        # Allow viewport navigation while drawing (MMB orbit/pan, wheel zoom, trackpad, NDOF, etc).
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

        # Support "Alt + LMB" (emulate 3-button mouse / alt-nav) without placing points.
        if event.alt and event.type == "LEFTMOUSE":
            return {"PASS_THROUGH"}

        # Don't treat Alt+RMB as "finish" if the user uses it for navigation.
        if event.alt and event.type == "RIGHTMOUSE":
            return {"PASS_THROUGH"}

        # Finish (Right Click / Esc)
        if event.type in {"RIGHTMOUSE", "ESC"} and event.value == "PRESS":
            if self._curve_obj:
                context.view_layer.objects.active = self._curve_obj
                self._curve_obj.select_set(True)
                self._safe_mode_set(context, self._curve_obj, "EDIT")

            return {"FINISHED"}

        # Finish (Enter)
        if event.type in {"RET", "NUMPAD_ENTER"} and event.value == "PRESS":
            if self._curve_obj:
                context.view_layer.objects.active = self._curve_obj
                self._curve_obj.select_set(True)
                self._safe_mode_set(context, self._curve_obj, "EDIT")

            return {"FINISHED"}

        # Add point (Left Click)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            # We mutate curve data directly. If we're currently in Edit Mode, Blender keeps an
            # internal edit cache that won't reflect these changes until we leave/re-enter Edit Mode.
            # Toggling ensures all created points are visible while drawing.
            if self._curve_obj:
                self._safe_mode_set(context, self._curve_obj, "OBJECT")

            origin, direction = _get_mouse_ray(context, event)
            hit = _intersect_ray_with_plane(origin, direction, plane_z=0.0)

            if hit is None:
                self.report({"WARNING"}, "Could not place point.")
                return {"RUNNING_MODAL"}

            spline = None
            if self._curve_obj and self._curve_obj.data and len(self._curve_obj.data.splines) > self._spline_index:
                spline = self._curve_obj.data.splines[self._spline_index]
            if spline is None:
                return {"CANCELLED"}

            points = spline.bezier_points
            if len(points) == 0:
                spline.bezier_points.add(count=1)
                points = spline.bezier_points

            # First point: set object origin to the first click, store point at local (0,0,0)
            if not self._has_first_point:
                self._curve_obj.location = hit

                points[0].co = (0.0, 0.0, 0.0)
                self._has_first_point = True

            # Add new point
            else:
                spline.bezier_points.add(count=1)

                new_pt = spline.bezier_points[-1]
                local_hit = self._curve_obj.matrix_world.inverted() @ hit
                new_pt.co = local_hit

            apply_taxi_handles_to_spline(spline)

            if self._curve_obj:
                self._curve_obj.data.update_tag()
                self._curve_obj.update_tag()
                self._safe_mode_set(context, self._curve_obj, "EDIT")

            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}
