import bpy
from bpy_extras import view3d_utils
from mathutils import Vector


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

    def invoke(self, context, event):
        if context.area.type != "VIEW_3D":
            self.report({"ERROR"}, "Run this in the 3D View.")
            return {"CANCELLED"}

        # Create curve data
        curve_data = bpy.data.curves.new("TaxiLineCurve", type="CURVE")
        curve_data.dimensions = "3D"

        # Create object
        obj = bpy.data.objects.new("TaxiLineCurve", curve_data)

        # Ensure TAXI_LINES collection exists
        col_name = "TAXI_LINES"
        col = bpy.data.collections.get(col_name)

        if col is None:
            col = bpy.data.collections.new(col_name)
            context.scene.collection.children.link(col)

        col.objects.link(obj)

        # Make active
        context.view_layer.objects.active = obj
        obj.select_set(True)

        # Create first spline
        spline = curve_data.splines.new(type="BEZIER")
        spline.bezier_points.add(count=0)

        bp = spline.bezier_points[0]
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"

        self._curve_obj = obj
        self._spline = spline

        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):

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

            # First point
            if len(points) == 1 and points[0].co.length < 1e-6:

                points[0].co = hit
                points[0].handle_left_type = "AUTO"
                points[0].handle_right_type = "AUTO"

            # Add new point
            else:

                spline.bezier_points.add(count=1)

                new_pt = spline.bezier_points[-1]
                new_pt.co = hit
                new_pt.handle_left_type = "AUTO"
                new_pt.handle_right_type = "AUTO"

            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        return {"RUNNING_MODAL"}
