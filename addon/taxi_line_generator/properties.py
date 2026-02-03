import bpy  # pyright: ignore[reportMissingImports]

_TLG_RIBBON_MESH_NODEGROUP_NAME = "TLG_RibbonMesh"
_TLG_RIBBON_MESH_MODIFIER_NAME = "TLG_RibbonMesh"
_TLG_RIBBON_MESH_NODEGROUP_VERSION = 4


def _ensure_ribbon_mesh_nodegroup():
    # During add-on enable/disable Blender may restrict access to bpy.data to prevent
    # add-ons from mutating the current file. Create node groups lazily from operators.
    if not hasattr(bpy.data, "node_groups"):
        return None

    ng = bpy.data.node_groups.get(_TLG_RIBBON_MESH_NODEGROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(_TLG_RIBBON_MESH_NODEGROUP_NAME, "GeometryNodeTree")

    if ng.get("tlg_version") == _TLG_RIBBON_MESH_NODEGROUP_VERSION:
        return ng

    # Blender 3.6 (legacy) group sockets API.
    while len(ng.inputs):
        ng.inputs.remove(ng.inputs[0])
    while len(ng.outputs):
        ng.outputs.remove(ng.outputs[0])

    ng.inputs.new("NodeSocketGeometry", "Geometry")
    ng.inputs.new("NodeSocketObject", "Source Curve")
    ng.inputs.new("NodeSocketFloat", "Width")  # Base width in meters
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

    n_set_curve_radius = nodes.new("GeometryNodeSetCurveRadius")
    n_set_curve_radius.location = (-20, 0)

    # Densify the curve before converting to mesh so corners have more "bevel"/rounding
    # in the generated ribbon (prevents visibly faceted turns on low-resolution curves).
    n_resample = nodes.new("GeometryNodeResampleCurve")
    n_resample.location = (90, 0)
    try:
        n_resample.mode = "LENGTH"
    except Exception:
        pass

    n_curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
    n_curve_to_mesh.location = (320, 0)

    n_curve_line = nodes.new("GeometryNodeCurvePrimitiveLine")
    n_curve_line.location = (-50, -220)

    # Unit-width profile curve from (-0.5,0,0) to (+0.5,0,0).
    n_curve_line.inputs["Start"].default_value = (-0.5, 0.0, 0.0)
    n_curve_line.inputs["End"].default_value = (0.5, 0.0, 0.0)

    # Per-point curve radius (from the source curve): explicit node if available; else fall back to named attribute "radius".
    try:
        n_radius = nodes.new("GeometryNodeInputRadius")
        radius_out = n_radius.outputs[0]
    except Exception:
        n_radius = nodes.new("GeometryNodeInputNamedAttribute")
        if hasattr(n_radius, "data_type"):
            n_radius.data_type = "FLOAT"
        if "Name" in n_radius.inputs:
            n_radius.inputs["Name"].default_value = "radius"
        if "Default" in n_radius.inputs:
            n_radius.inputs["Default"].default_value = 1.0
        radius_out = n_radius.outputs[0]
    n_radius.location = (-250, -260)

    n_mul_width = nodes.new("ShaderNodeMath")
    n_mul_width.operation = "MULTIPLY"
    n_mul_width.location = (-20, -340)

    links.new(n_in.outputs["Width"], n_mul_width.inputs[0])
    links.new(radius_out, n_mul_width.inputs[1])

    # Resample length is derived from width: smaller segment length => smoother corners.
    # Keep a small minimum to avoid extremely dense meshes on tiny widths.
    n_seg_len_mul = nodes.new("ShaderNodeMath")
    n_seg_len_mul.operation = "MULTIPLY"
    n_seg_len_mul.location = (90, -220)
    n_seg_len_mul.inputs[1].default_value = 0.25

    n_seg_len_max = nodes.new("ShaderNodeMath")
    n_seg_len_max.operation = "MAXIMUM"
    n_seg_len_max.location = (240, -220)
    n_seg_len_max.inputs[1].default_value = 0.02

    links.new(n_in.outputs["Width"], n_seg_len_mul.inputs[0])
    links.new(n_seg_len_mul.outputs[0], n_seg_len_max.inputs[0])
    if "Length" in n_resample.inputs:
        links.new(n_seg_len_max.outputs[0], n_resample.inputs["Length"])

    # Input curve -> set curve radius (base width * per-point radius) -> Curve to Mesh with profile curve -> Output
    links.new(n_in.outputs["Source Curve"], n_obj_info.inputs["Object"])
    links.new(n_obj_info.outputs["Geometry"], n_set_curve_radius.inputs["Curve"])
    links.new(n_mul_width.outputs[0], n_set_curve_radius.inputs["Radius"])
    links.new(n_set_curve_radius.outputs["Curve"], n_resample.inputs["Curve"])
    links.new(n_resample.outputs["Curve"], n_curve_to_mesh.inputs["Curve"])
    links.new(n_curve_line.outputs["Curve"], n_curve_to_mesh.inputs["Profile Curve"])

    links.new(n_curve_to_mesh.outputs["Mesh"], n_out.inputs["Geometry"])

    ng["tlg_version"] = _TLG_RIBBON_MESH_NODEGROUP_VERSION
    return ng


def _ensure_ribbon_mesh_modifier(mesh_obj):
    mod = mesh_obj.modifiers.get(_TLG_RIBBON_MESH_MODIFIER_NAME)
    if mod and mod.type == "NODES":
        if mod.node_group is None:
            ng = _ensure_ribbon_mesh_nodegroup()
            if ng is not None:
                mod.node_group = ng
        return mod

    mod = mesh_obj.modifiers.new(_TLG_RIBBON_MESH_MODIFIER_NAME, "NODES")
    ng = _ensure_ribbon_mesh_nodegroup()
    if ng is not None:
        mod.node_group = ng
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


def _find_linked_mesh_for_curve(curve_obj):
    mesh_name = curve_obj.get("taxilines_mesh") if curve_obj else None
    if mesh_name:
        mesh_obj = bpy.data.objects.get(mesh_name)
        if mesh_obj and mesh_obj.type == "MESH":
            return mesh_obj

    if curve_obj:
        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            if obj.get("taxilines_source_curve") == curve_obj.name:
                return obj

    return None


def _tlg_curve_width_update(obj, context):
    if not obj or obj.type != "CURVE":
        return

    mesh_obj = _find_linked_mesh_for_curve(obj)
    if mesh_obj is None:
        return

    apply_width_to_taxi_mesh(context, mesh_obj, obj.tlg_line_width)

    if context and context.area:
        context.area.tag_redraw()


def register_properties():
    bpy.types.Scene.tlg_default_width = bpy.props.FloatProperty(
        name="Default Line Width",
        description="Default taxi line width (meters) for newly created lines",
        default=0.15,
        min=0.01,
        soft_min=0.01,
        soft_max=10.0,
        subtype="DISTANCE",
    )

    bpy.types.Object.tlg_line_width = bpy.props.FloatProperty(
        name="Line Width",
        description="Taxi line width (meters) for this line",
        default=0.15,
        min=0.01,
        soft_min=0.01,
        soft_max=10.0,
        subtype="DISTANCE",
        update=_tlg_curve_width_update,
    )


def unregister_properties():
    try:
        del bpy.types.Scene.tlg_default_width
    except Exception:
        pass
    try:
        del bpy.types.Object.tlg_line_width
    except Exception:
        pass


__all__ = (
    "apply_width_to_taxi_mesh",
    "_ensure_ribbon_mesh_modifier",
    "_set_modifier_input",
)
