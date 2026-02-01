import bpy

from ..properties import _ensure_ribbon_mesh_modifier, _set_modifier_input


class TAXILINES_OT_create_ribbon_mesh(bpy.types.Operator):
    bl_idname = "taxilines.create_ribbon_mesh"
    bl_label = "Create Ribbon Mesh (GN)"
    bl_description = "Create a mesh object driven by Geometry Nodes from the selected curve"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        curves = [o for o in context.selected_objects if o.type == "CURVE"]
        if not curves:
            self.report({"ERROR"}, "Select at least one curve object.")
            return {"CANCELLED"}

        width_m = getattr(context.scene, "tlg_line_width", 0.15)

        created = 0
        for curve_obj in curves:
            mesh_data = bpy.data.meshes.new(f"{curve_obj.name}_RibbonMesh")
            mesh_obj = bpy.data.objects.new(f"{curve_obj.name}_Ribbon", mesh_data)

            # Link next to the curve (same collection when possible).
            if curve_obj.users_collection:
                curve_obj.users_collection[0].objects.link(mesh_obj)
            else:
                context.scene.collection.objects.link(mesh_obj)

            mod = _ensure_ribbon_mesh_modifier(mesh_obj)
            _set_modifier_input(mod, "Source Curve", curve_obj)
            _set_modifier_input(mod, "Width", float(width_m))

            created += 1

        self.report({"INFO"}, f"Created {created} ribbon mesh object(s).")
        return {"FINISHED"}
