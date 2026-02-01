import bpy
from bpy_extras import view3d_utils

from ..properties import _ensure_ribbon_mesh_modifier, _set_modifier_input


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
    _spline = None
    _has_first_point = False
    _mesh_obj = None

    def _ensure_collection(self, context, name):
        col = bpy.data.collections.get(name)
        if col is None:
            col = bpy.data.collections.new(name)
            context.scene.collection.children.link(col)
        return col

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

        # Create first spline
        spline = curve_data.splines.new(type="BEZIER")
        spline.bezier_points.add(count=0)

        bp = spline.bezier_points[0]
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"

        self._curve_obj = curve_obj
        self._mesh_obj = mesh_obj
        self._spline = spline
        self._has_first_point = False

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

            return {"FINISHED"}

        # Finish (Enter)
        if event.type in {"RET", "NUMPAD_ENTER"} and event.value == "PRESS":
            if self._curve_obj:
                context.view_layer.objects.active = self._curve_obj
                self._curve_obj.select_set(True)

            return {"FINISHED"}

        # Add point (Left Click)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            origin, direction = _get_mouse_ray(context, event)
            hit = _intersect_ray_with_plane(origin, direction, plane_z=0.0)

            if hit is None:
                self.report({"WARNING"}, "Could not place point.")
                return {"RUNNING_MODAL"}

            spline = self._spline
            if spline is None:
                return {"CANCELLED"}

            points = spline.bezier_points

            # First point: set object origin to the first click, store point at local (0,0,0)
            if not self._has_first_point:
                self._curve_obj.location = hit

                points[0].co = (0.0, 0.0, 0.0)
                points[0].handle_left_type = "AUTO"
                points[0].handle_right_type = "AUTO"
                self._has_first_point = True

            # Add new point
            else:
                spline.bezier_points.add(count=1)

                new_pt = spline.bezier_points[-1]
                local_hit = self._curve_obj.matrix_world.inverted() @ hit
                new_pt.co = local_hit
                new_pt.handle_left_type = "AUTO"
                new_pt.handle_right_type = "AUTO"

            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}
