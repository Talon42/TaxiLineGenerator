import bpy


_TLG_RIBBON_MESH_NODEGROUP_NAME = "TLG_RibbonMesh"
_TLG_RIBBON_MESH_MODIFIER_NAME = "TLG_RibbonMesh"


def _ensure_ribbon_mesh_nodegroup():
    ng = bpy.data.node_groups.get(_TLG_RIBBON_MESH_NODEGROUP_NAME)
    if ng is not None:
        return ng

    ng = bpy.data.node_groups.new(_TLG_RIBBON_MESH_NODEGROUP_NAME, "GeometryNodeTree")

    # Blender 3.6 (legacy) group sockets API.
    ng.inputs.new("NodeSocketGeometry", "Geometry")
    ng.inputs.new("NodeSocketObject", "Source Curve")
    ng.inputs.new("NodeSocketFloat", "Width")
    ng.inputs["Width"].default_value = 0.15
    ng.outputs.new("NodeSocketGeometry", "Geometry")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-500, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (500, 0)

    n_obj_info = nodes.new("GeometryNodeObjectInfo")
    n_obj_info.location = (-250, 0)
    n_obj_info.transform_space = "RELATIVE"

    n_curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
    n_curve_to_mesh.location = (200, 0)

    n_curve_line = nodes.new("GeometryNodeCurvePrimitiveLine")
    n_curve_line.location = (-100, -220)

    n_mul_half = nodes.new("ShaderNodeMath")
    n_mul_half.operation = "MULTIPLY"
    n_mul_half.inputs[1].default_value = 0.5
    n_mul_half.location = (-320, -210)

    n_mul_neg_half = nodes.new("ShaderNodeMath")
    n_mul_neg_half.operation = "MULTIPLY"
    n_mul_neg_half.inputs[1].default_value = -0.5
    n_mul_neg_half.location = (-320, -330)

    n_combine_start = nodes.new("ShaderNodeCombineXYZ")
    n_combine_start.location = (-120, -330)

    n_combine_end = nodes.new("ShaderNodeCombineXYZ")
    n_combine_end.location = (-120, -210)

    # Width -> +/- half width
    links.new(n_in.outputs["Width"], n_mul_half.inputs[0])
    links.new(n_in.outputs["Width"], n_mul_neg_half.inputs[0])

    links.new(n_mul_neg_half.outputs[0], n_combine_start.inputs["X"])
    links.new(n_mul_half.outputs[0], n_combine_end.inputs["X"])

    # Profile curve from (-w/2,0,0) to (+w/2,0,0)
    links.new(n_combine_start.outputs[0], n_curve_line.inputs["Start"])
    links.new(n_combine_end.outputs[0], n_curve_line.inputs["End"])

    # Input curve -> Curve to Mesh with profile curve -> Output
    links.new(n_in.outputs["Source Curve"], n_obj_info.inputs["Object"])
    links.new(n_obj_info.outputs["Geometry"], n_curve_to_mesh.inputs["Curve"])
    links.new(n_curve_line.outputs["Curve"], n_curve_to_mesh.inputs["Profile Curve"])
    links.new(n_curve_to_mesh.outputs["Mesh"], n_out.inputs["Geometry"])

    return ng


def _ensure_ribbon_mesh_modifier(mesh_obj):
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


def apply_width_to_taxi_mesh(context, mesh_obj, width_m):
    if not mesh_obj or mesh_obj.type != "MESH":
        return

    mod = _ensure_ribbon_mesh_modifier(mesh_obj)
    _set_modifier_input(mod, "Width", float(width_m))

    mesh_obj.update_tag()
    if context and context.view_layer:
        context.view_layer.update()


def tlg_line_width_update(scene, context):
    width_m = scene.tlg_line_width

    for obj in context.selected_objects:
        apply_width_to_taxi_mesh(context, obj, width_m)


def register_properties():
    bpy.types.Scene.tlg_line_width = bpy.props.FloatProperty(
        name="Line Width",
        description="Taxi line width (meters). Applies live to selected curve objects",
        default=0.15,
        min=0.001,
        soft_max=2.0,
        subtype="DISTANCE",
        update=tlg_line_width_update,
    )


def unregister_properties():
    try:
        del bpy.types.Scene.tlg_line_width
    except Exception:
        pass


__all__ = (
    "apply_width_to_taxi_mesh",
    "_ensure_ribbon_mesh_modifier",
    "_set_modifier_input",
)
