import bpy


_TLG_RIBBON_MESH_NODEGROUP_NAME = "TLG_RibbonMesh"
_TLG_RIBBON_MESH_MODIFIER_NAME = "TLG_RibbonMesh"


def _ensure_ribbon_mesh_nodegroup():
    ng = bpy.data.node_groups.get(_TLG_RIBBON_MESH_NODEGROUP_NAME)
    if ng is not None:
        return ng

    ng = bpy.data.node_groups.new(_TLG_RIBBON_MESH_NODEGROUP_NAME, "GeometryNodeTree")

    ng.inputs.new("NodeSocketGeometry", "Geometry")
    ng.inputs.new("NodeSocketObject", "Source Curve")
    ng.inputs.new("NodeSocketFloat", "Width")
    ng.inputs["Width"].default_value = 0.15
    ng.outputs.new("NodeSocketGeometry", "Geometry")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-700, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (650, 0)

    n_obj_info = nodes.new("GeometryNodeObjectInfo")
    n_obj_info.location = (-450, 0)
    n_obj_info.transform_space = "RELATIVE"

    n_curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
    n_curve_to_mesh.location = (350, 0)

    n_curve_line = nodes.new("GeometryNodeCurvePrimitiveLine")
    n_curve_line.location = (-100, -220)

    n_mul_half = nodes.new("ShaderNodeMath")
    n_mul_half.operation = "MULTIPLY"
    n_mul_half.inputs[1].default_value = 0.5
    n_mul_half.location = (-520, -210)

    n_mul_neg_half = nodes.new("ShaderNodeMath")
    n_mul_neg_half.operation = "MULTIPLY"
    n_mul_neg_half.inputs[1].default_value = -0.5
    n_mul_neg_half.location = (-520, -330)

    n_combine_start = nodes.new("ShaderNodeCombineXYZ")
    n_combine_start.location = (-300, -330)

    n_combine_end = nodes.new("ShaderNodeCombineXYZ")
    n_combine_end.location = (-300, -210)

    # Inputs -> Object Info
    links.new(n_in.outputs["Source Curve"], n_obj_info.inputs["Object"])

    # Width -> +/- half width
    links.new(n_in.outputs["Width"], n_mul_half.inputs[0])
    links.new(n_in.outputs["Width"], n_mul_neg_half.inputs[0])

    links.new(n_mul_neg_half.outputs[0], n_combine_start.inputs["X"])
    links.new(n_mul_half.outputs[0], n_combine_end.inputs["X"])

    # Profile curve from (-w/2,0,0) to (+w/2,0,0)
    links.new(n_combine_start.outputs[0], n_curve_line.inputs["Start"])
    links.new(n_combine_end.outputs[0], n_curve_line.inputs["End"])

    # Curve -> Curve to Mesh with profile
    links.new(n_obj_info.outputs["Geometry"], n_curve_to_mesh.inputs["Curve"])
    links.new(n_curve_line.outputs["Curve"], n_curve_to_mesh.inputs["Profile Curve"])

    links.new(n_curve_to_mesh.outputs["Mesh"], n_out.inputs["Geometry"])

    return ng


def _ensure_modifier(mesh_obj):
    mod = mesh_obj.modifiers.get(_TLG_RIBBON_MESH_MODIFIER_NAME)
    if mod and mod.type == "NODES":
        if mod.node_group is None:
            mod.node_group = _ensure_ribbon_mesh_nodegroup()
        return mod

    mod = mesh_obj.modifiers.new(_TLG_RIBBON_MESH_MODIFIER_NAME, "NODES")
    mod.node_group = _ensure_ribbon_mesh_nodegroup()
    return mod


def _set_modifier_input(mod, socket_name, value):
    if mod.node_group is None:
        return False
    socket = mod.node_group.inputs.get(socket_name)
    if socket is None:
        return False
    mod[socket.identifier] = value
    return True


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

            mod = _ensure_modifier(mesh_obj)
            _set_modifier_input(mod, "Source Curve", curve_obj)
            _set_modifier_input(mod, "Width", float(width_m))

            created += 1

        self.report({"INFO"}, f"Created {created} ribbon mesh object(s).")
        return {"FINISHED"}

