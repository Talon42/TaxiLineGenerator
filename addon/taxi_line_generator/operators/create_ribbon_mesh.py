import bpy

from ..properties import ensure_taxi_preview


class TAXILINES_OT_create_ribbon_mesh(bpy.types.Operator):
    bl_idname = "taxilines.create_ribbon_mesh"
    bl_label = "Attach GN Preview to Curve"
    bl_description = "Attach the Taxi Line Generator Geometry Nodes preview to the selected curve(s)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        curves = [o for o in context.selected_objects if o.type == "CURVE"]
        if not curves:
            self.report({"ERROR"}, "Select at least one curve object.")
            return {"CANCELLED"}

        width_m = getattr(context.scene, "tlg_default_width", 0.15)

        created = 0
        for curve_obj in curves:
            curve_obj.tlg_line_width = float(width_m)
            ensure_taxi_preview(curve_obj, context=context)

            created += 1

        self.report({"INFO"}, f"Attached GN preview to {created} curve(s).")
        return {"FINISHED"}
