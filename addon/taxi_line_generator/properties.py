import bpy  # pyright: ignore[reportMissingImports]

from .curve_utils import apply_taxi_handles_to_curve

_TLG_PREVIEW_NODEGROUP_NAME = "TLG_TaxiLinePreview"
_TLG_PREVIEW_MODIFIER_NAME = "TLG_TaxiLinePreview"
_TLG_PREVIEW_NODEGROUP_VERSION = 9

_TLG_COLLECTION_ROOT_NAME = "Taxi Lines"
_TLG_COLLECTION_CURVES_NAME = "EDIT - Curves"
_TLG_COLLECTION_EXPORT_NAME = "EXPORT - Meshes"
_TLG_COLLECTION_INTERNAL_NAME = "_INTERNAL - Base"

# Legacy collection names (kept for migrating older files).
_TLG_LEGACY_CURVES_COLLECTION_NAME = "TAXI_LINES"
_TLG_LEGACY_BAKED_COLLECTION_NAME = "TLG_Baked"


def _nodes_new_first_available(nodes, type_names):
    for t in type_names:
        try:
            return nodes.new(t)
        except Exception:
            continue
    raise RuntimeError(f"Could not create node from any of: {type_names}")


def _sock(col, name, index=0):
    try:
        s = col.get(name)
        if s is not None:
            return s
    except Exception:
        pass
    try:
        return col[index]
    except Exception:
        return None


def _ensure_preview_nodegroup():
    # During add-on enable/disable Blender may restrict access to bpy.data to prevent
    # add-ons from mutating the current file. Create node groups lazily from operators.
    if not hasattr(bpy.data, "node_groups"):
        return None

    ng = bpy.data.node_groups.get(_TLG_PREVIEW_NODEGROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(_TLG_PREVIEW_NODEGROUP_NAME, "GeometryNodeTree")

    if ng.get("tlg_version") == _TLG_PREVIEW_NODEGROUP_VERSION:
        return ng

    while len(ng.inputs):
        ng.inputs.remove(ng.inputs[0])
    while len(ng.outputs):
        ng.outputs.remove(ng.outputs[0])

    ng.inputs.new("NodeSocketGeometry", "Geometry")
    ng.inputs.new("NodeSocketFloat", "Width (m)")
    ng.inputs["Width (m)"].default_value = 0.15
    ng.inputs.new("NodeSocketFloat", "UV U (m/tile)")
    ng.inputs["UV U (m/tile)"].default_value = 1.0
    ng.inputs.new("NodeSocketFloat", "UV V (m/tile)")
    ng.inputs["UV V (m/tile)"].default_value = 1.0
    ng.inputs.new("NodeSocketMaterial", "Material")
    ng.outputs.new("NodeSocketGeometry", "Geometry")

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    n_in = nodes.new("NodeGroupInput")
    n_in.location = (-900, 0)

    n_out = nodes.new("NodeGroupOutput")
    n_out.location = (900, 0)

    n_set_curve_radius = nodes.new("GeometryNodeSetCurveRadius")
    n_set_curve_radius.location = (-560, 0)

    # Bevel/fillet corners before turning the curve into a ribbon mesh.
    # This prevents self-overlap on inside corners when the line is wide relative to turn radius.
    try:
        n_fillet = nodes.new("GeometryNodeFilletCurve")
    except Exception:
        n_fillet = None
    if n_fillet is not None:
        n_fillet.location = (-420, 40)

        n_fillet_r_mul = nodes.new("ShaderNodeMath")
        n_fillet_r_mul.operation = "MULTIPLY"
        n_fillet_r_mul.location = (-560, 80)
        # Larger than 0.5*width so the inside offset stays well-behaved.
        n_fillet_r_mul.inputs[1].default_value = 0.75
        links.new(n_in.outputs["Width (m)"], n_fillet_r_mul.inputs[0])

        # Minimum radius (in meters) so small widths still get a visible bevel.
        n_fillet_r_max = nodes.new("ShaderNodeMath")
        n_fillet_r_max.operation = "MAXIMUM"
        n_fillet_r_max.location = (-420, 80)
        n_fillet_r_max.inputs[1].default_value = 0.02
        links.new(n_fillet_r_mul.outputs[0], n_fillet_r_max.inputs[0])

        fillet_radius_in = _sock(n_fillet.inputs, "Radius", 1)
        if fillet_radius_in is not None:
            links.new(n_fillet_r_max.outputs[0], fillet_radius_in)

        # Keep the bevel reasonably smooth without adding too much geometry.
        fillet_count_in = _sock(n_fillet.inputs, "Count", 2) or _sock(n_fillet.inputs, "Resolution", 2)
        if fillet_count_in is not None:
            try:
                fillet_count_in.default_value = 8
            except Exception:
                pass

    n_resample = nodes.new("GeometryNodeResampleCurve")
    n_resample.location = (-360, 0)
    try:
        n_resample.mode = "LENGTH"
    except Exception:
        pass

    # Profile curve (unit width) from (-0.5,0,0) to (+0.5,0,0).
    n_profile_line = nodes.new("GeometryNodeCurvePrimitiveLine")
    n_profile_line.location = (-560, -360)
    _sock(n_profile_line.inputs, "Start", 0).default_value = (-0.5, 0.0, 0.0)
    _sock(n_profile_line.inputs, "End", 1).default_value = (0.5, 0.0, 0.0)

    # Per-point curve radius (from the curve): explicit node if available; else fall back to named attribute "radius".
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
    n_radius.location = (-760, -200)

    n_mul_width = nodes.new("ShaderNodeMath")
    n_mul_width.operation = "MULTIPLY"
    n_mul_width.location = (-560, -200)
    links.new(n_in.outputs["Width (m)"], n_mul_width.inputs[0])
    links.new(radius_out, n_mul_width.inputs[1])

    # Resample length is derived from width: smaller segment length => smoother corners.
    n_seg_len_mul = nodes.new("ShaderNodeMath")
    n_seg_len_mul.operation = "MULTIPLY"
    n_seg_len_mul.location = (-360, -260)
    n_seg_len_mul.inputs[1].default_value = 0.10

    n_seg_len_max = nodes.new("ShaderNodeMath")
    n_seg_len_max.operation = "MAXIMUM"
    n_seg_len_max.location = (-200, -260)
    n_seg_len_max.inputs[1].default_value = 0.5

    # Cap segment length so wide lines still get enough bevel at corners.
    n_seg_len_min = nodes.new("ShaderNodeMath")
    n_seg_len_min.operation = "MINIMUM"
    n_seg_len_min.location = (-40, -260)
    n_seg_len_min.inputs[1].default_value = 0.5

    links.new(n_in.outputs["Width (m)"], n_seg_len_mul.inputs[0])
    links.new(n_seg_len_mul.outputs[0], n_seg_len_max.inputs[0])
    links.new(n_seg_len_max.outputs[0], n_seg_len_min.inputs[0])
    if "Length" in n_resample.inputs:
        links.new(n_seg_len_min.outputs[0], n_resample.inputs["Length"])

    # Curve parameterization for UV U: store length along spline to a named attribute on the curve.
    n_spline_param_curve = _nodes_new_first_available(
        nodes, ("GeometryNodeSplineParameter", "GeometryNodeCurveParameter")
    )
    n_spline_param_curve.location = (-560, 220)

    n_store_u = nodes.new("GeometryNodeStoreNamedAttribute")
    n_store_u.location = (-360, 220)
    try:
        n_store_u.data_type = "FLOAT"
    except Exception:
        pass
    try:
        n_store_u.domain = "POINT"
    except Exception:
        pass
    if "Name" in n_store_u.inputs:
        n_store_u.inputs["Name"].default_value = "tlg_u_len"
    resample_curve_out = n_resample.outputs.get("Curve") or n_resample.outputs[0]
    spline_len_out = n_spline_param_curve.outputs.get("Length") or n_spline_param_curve.outputs[0]
    links.new(resample_curve_out, n_store_u.inputs["Geometry"])
    links.new(spline_len_out, n_store_u.inputs["Value"])

    # Profile parameterization for UV V: store factor (0..1) along profile to a named attribute on the profile curve.
    n_spline_param_profile = _nodes_new_first_available(
        nodes, ("GeometryNodeSplineParameter", "GeometryNodeCurveParameter")
    )
    n_spline_param_profile.location = (-360, -520)

    n_store_v = nodes.new("GeometryNodeStoreNamedAttribute")
    n_store_v.location = (-200, -520)
    try:
        n_store_v.data_type = "FLOAT"
    except Exception:
        pass
    try:
        n_store_v.domain = "POINT"
    except Exception:
        pass
    if "Name" in n_store_v.inputs:
        n_store_v.inputs["Name"].default_value = "tlg_v_fac"
    profile_curve_out = n_profile_line.outputs.get("Curve") or n_profile_line.outputs[0]
    spline_factor_out = n_spline_param_profile.outputs.get("Factor") or n_spline_param_profile.outputs[0]
    links.new(profile_curve_out, n_store_v.inputs["Geometry"])
    links.new(spline_factor_out, n_store_v.inputs["Value"])

    n_curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
    n_curve_to_mesh.location = (0, 0)

    # Geometry in -> set curve radius (base width * per-point radius) -> fillet corners -> resample -> store U -> curve to mesh with profile -> ...
    links.new(_sock(n_in.outputs, "Geometry", 0), _sock(n_set_curve_radius.inputs, "Curve", 0))
    links.new(n_mul_width.outputs[0], _sock(n_set_curve_radius.inputs, "Radius", 1))

    curve_for_resample = _sock(n_set_curve_radius.outputs, "Curve", 0)
    if n_fillet is not None:
        try:
            links.new(curve_for_resample, _sock(n_fillet.inputs, "Curve", 0))
            curve_for_resample = _sock(n_fillet.outputs, "Curve", 0) or n_fillet.outputs[0]
        except Exception:
            curve_for_resample = _sock(n_set_curve_radius.outputs, "Curve", 0)

    links.new(curve_for_resample, _sock(n_resample.inputs, "Curve", 0))
    links.new(_sock(n_store_u.outputs, "Geometry", 0), _sock(n_curve_to_mesh.inputs, "Curve", 0))
    links.new(_sock(n_store_v.outputs, "Geometry", 0), _sock(n_curve_to_mesh.inputs, "Profile Curve", 1))

    n_set_material = nodes.new("GeometryNodeSetMaterial")
    n_set_material.location = (210, 0)
    curve_to_mesh_out = _sock(n_curve_to_mesh.outputs, "Mesh", 0)
    links.new(curve_to_mesh_out, _sock(n_set_material.inputs, "Geometry", 0))
    links.new(_sock(n_in.outputs, "Material", 4), _sock(n_set_material.inputs, "Material", 1))

    # Build UVMap from the stored U and V factors.
    n_u_attr = nodes.new("GeometryNodeInputNamedAttribute")
    n_u_attr.location = (210, 220)
    if hasattr(n_u_attr, "data_type"):
        n_u_attr.data_type = "FLOAT"
    if "Name" in n_u_attr.inputs:
        n_u_attr.inputs["Name"].default_value = "tlg_u_len"

    n_v_attr = nodes.new("GeometryNodeInputNamedAttribute")
    n_v_attr.location = (210, 160)
    if hasattr(n_v_attr, "data_type"):
        n_v_attr.data_type = "FLOAT"
    if "Name" in n_v_attr.inputs:
        n_v_attr.inputs["Name"].default_value = "tlg_v_fac"

    n_u_div = nodes.new("ShaderNodeMath")
    n_u_div.operation = "DIVIDE"
    n_u_div.location = (430, 220)
    links.new(n_u_attr.outputs[0], n_u_div.inputs[0])
    links.new(n_in.outputs["UV U (m/tile)"], n_u_div.inputs[1])

    n_v_sub = nodes.new("ShaderNodeMath")
    n_v_sub.operation = "SUBTRACT"
    n_v_sub.location = (430, 160)
    n_v_sub.inputs[1].default_value = 0.5
    links.new(n_v_attr.outputs[0], n_v_sub.inputs[0])

    n_v_mul_width = nodes.new("ShaderNodeMath")
    n_v_mul_width.operation = "MULTIPLY"
    n_v_mul_width.location = (610, 160)
    links.new(n_v_sub.outputs[0], n_v_mul_width.inputs[0])
    links.new(n_in.outputs["Width (m)"], n_v_mul_width.inputs[1])

    n_v_div = nodes.new("ShaderNodeMath")
    n_v_div.operation = "DIVIDE"
    n_v_div.location = (790, 160)
    links.new(n_v_mul_width.outputs[0], n_v_div.inputs[0])
    links.new(n_in.outputs["UV V (m/tile)"], n_v_div.inputs[1])

    n_combine = nodes.new("ShaderNodeCombineXYZ")
    n_combine.location = (610, 220)
    links.new(n_u_div.outputs[0], n_combine.inputs["X"])
    links.new(n_v_div.outputs[0], n_combine.inputs["Y"])

    n_store_uv = nodes.new("GeometryNodeStoreNamedAttribute")
    n_store_uv.location = (430, 0)
    try:
        n_store_uv.data_type = "FLOAT_VECTOR"
    except Exception:
        pass
    try:
        n_store_uv.domain = "CORNER"
    except Exception:
        pass
    if "Name" in n_store_uv.inputs:
        n_store_uv.inputs["Name"].default_value = "UVMap"
    links.new(_sock(n_set_material.outputs, "Geometry", 0), _sock(n_store_uv.inputs, "Geometry", 0))
    links.new(n_combine.outputs[0], _sock(n_store_uv.inputs, "Value", 3))

    store_uv_geom_out = n_store_uv.outputs.get("Geometry") or n_store_uv.outputs[0]
    links.new(store_uv_geom_out, n_out.inputs["Geometry"])

    ng["tlg_version"] = _TLG_PREVIEW_NODEGROUP_VERSION
    return ng


def _ensure_ribbon_mesh_modifier(curve_obj):
    if not curve_obj or curve_obj.type != "CURVE":
        return None

    mod = curve_obj.modifiers.get(_TLG_PREVIEW_MODIFIER_NAME)
    if mod and mod.type == "NODES":
        if mod.node_group is None:
            ng = _ensure_preview_nodegroup()
            if ng is not None:
                mod.node_group = ng
        try:
            mod.show_in_editmode = False
        except Exception:
            pass
        try:
            mod.show_on_cage = False
        except Exception:
            pass
        return mod

    mod = curve_obj.modifiers.new(_TLG_PREVIEW_MODIFIER_NAME, "NODES")
    ng = _ensure_preview_nodegroup()
    if ng is not None:
        mod.node_group = ng
    try:
        mod.show_in_editmode = False
    except Exception:
        pass
    try:
        mod.show_on_cage = False
    except Exception:
        pass
    try:
        mod.show_viewport = True
    except Exception:
        pass
    curve_obj["tlg_is_taxi_line"] = True
    return mod


def _set_modifier_input(mod, socket_name, value):
    if mod.node_group is None:
        return False
    socket = mod.node_group.inputs.get(socket_name)
    if socket is None:
        return False
    mod[socket.identifier] = value
    return True


def is_taxi_curve(obj):
    if not obj or obj.type != "CURVE":
        return False
    return bool(obj.get("tlg_is_taxi_line") or ("taxilines_mesh" in obj))


def ensure_taxi_preview(curve_obj, context=None):
    mod = _ensure_ribbon_mesh_modifier(curve_obj)
    if mod is None:
        return None

    if bool(getattr(curve_obj, "tlg_auto_smooth_handles", True)):
        try:
            apply_taxi_handles_to_curve(curve_obj)
        except Exception:
            pass

    # Inputs are evaluated in the object's local space. Compensate for object scale so
    # the user-facing width/UV values remain in world meters (avoids surprise "fat" lines
    # and corner overlap on scaled objects).
    try:
        sx = abs(float(curve_obj.scale.x))
        sy = abs(float(curve_obj.scale.y))
        scale_xy = (sx + sy) * 0.5
    except Exception:
        scale_xy = 1.0
    if scale_xy <= 1e-6:
        scale_xy = 1.0

    width_m = float(getattr(curve_obj, "tlg_line_width", 0.15))

    _set_modifier_input(mod, "Width (m)", width_m / scale_xy)
    _set_modifier_input(
        mod, "UV U (m/tile)", float(getattr(curve_obj, "tlg_uv_u_m_per_tile", 1.0)) / scale_xy
    )
    _set_modifier_input(
        mod, "UV V (m/tile)", float(getattr(curve_obj, "tlg_uv_v_m_per_tile", 1.0)) / scale_xy
    )
    # Note: we intentionally avoid mixing a curve component into the GN output on Blender 3.6
    # because combined curve+mesh outputs on Curve objects can fail to display reliably.

    # Best-effort material sync for preview (bake will copy all material slots).
    mat = getattr(curve_obj, "active_material", None)
    if mat is None and curve_obj.data and hasattr(curve_obj.data, "materials") and curve_obj.data.materials:
        mat = curve_obj.data.materials[0]
    if mat is not None:
        _set_modifier_input(mod, "Material", mat)

    # Display defaults: keep the curve as the editable/authoritative object.
    try:
        curve_obj.hide_select = False
        curve_obj.hide_viewport = False
        curve_obj.hide_render = True
        curve_obj.display_type = "WIRE"
        curve_obj.show_in_front = True
    except Exception:
        pass

    curve_obj.update_tag()
    if context and context.view_layer:
        context.view_layer.update()
    if context and context.area:
        context.area.tag_redraw()

    return mod


def get_baked_collection(scene):
    # Backward-compatible name: "baked" now means the export mesh collection under Taxi Lines.
    return get_taxi_export_collection(scene)


def _ensure_child_collection(parent, name):
    if parent is None:
        return None
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    try:
        if col.name not in [c.name for c in parent.children]:
            parent.children.link(col)
    except Exception:
        # Blender may throw if already linked or during restricted contexts.
        pass
    return col


def get_taxi_root_collection(scene):
    if scene is None:
        return None
    root = bpy.data.collections.get(_TLG_COLLECTION_ROOT_NAME)
    if root is None:
        root = bpy.data.collections.new(_TLG_COLLECTION_ROOT_NAME)
    try:
        if root.name not in [c.name for c in scene.collection.children]:
            scene.collection.children.link(root)
    except Exception:
        pass
    return root


def get_taxi_curves_collection(scene):
    root = get_taxi_root_collection(scene)
    return _ensure_child_collection(root, _TLG_COLLECTION_CURVES_NAME)


def get_taxi_export_collection(scene):
    root = get_taxi_root_collection(scene)
    return _ensure_child_collection(root, _TLG_COLLECTION_EXPORT_NAME)


def get_taxi_internal_collection(scene):
    root = get_taxi_root_collection(scene)
    return _ensure_child_collection(root, _TLG_COLLECTION_INTERNAL_NAME)


def get_baked_mesh_for_curve(curve_obj):
    if not curve_obj:
        return None
    baked_name = curve_obj.get("tlg_baked_mesh")
    if baked_name:
        obj = bpy.data.objects.get(baked_name)
        if obj and obj.type == "MESH":
            return obj
    return None


def get_base_mesh_for_curve(curve_obj):
    if not curve_obj:
        return None
    base_name = curve_obj.get("tlg_base_mesh")
    if base_name:
        obj = bpy.data.objects.get(base_name)
        if obj and obj.type == "MESH":
            return obj
    return None


def _tlg_curve_settings_update(obj, context):
    if not obj or obj.type != "CURVE":
        return
    if not is_taxi_curve(obj):
        return
    ensure_taxi_preview(obj, context=context)


def _tlg_view_mode_update(scene, context):
    # Legacy: older versions had a scene-level view mode toggle that hid/shows all taxi lines.
    # The current workflow is per-line via "Edit Curve" / "Edit Mesh" operators, so this is a no-op.
    return


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
        update=_tlg_curve_settings_update,
    )

    bpy.types.Object.tlg_auto_smooth_handles = bpy.props.BoolProperty(
        name="Auto Smooth Handles",
        description="Automatically recompute curve handles for clean, beveled corners (recommended)",
        default=True,
        update=_tlg_curve_settings_update,
    )

    bpy.types.Object.tlg_uv_u_m_per_tile = bpy.props.FloatProperty(
        name="UV U (m/tile)",
        description="Meters per texture tile along the line (U axis)",
        default=1.0,
        min=0.001,
        soft_min=0.05,
        soft_max=50.0,
        update=_tlg_curve_settings_update,
    )

    bpy.types.Object.tlg_uv_v_m_per_tile = bpy.props.FloatProperty(
        name="UV V (m/tile)",
        description="Meters per texture tile across the line (V axis)",
        default=1.0,
        min=0.001,
        soft_min=0.01,
        soft_max=10.0,
        update=_tlg_curve_settings_update,
    )

    bpy.types.Object.tlg_show_curve_overlay = bpy.props.BoolProperty(
        name="Show Curve Overlay",
        description="Include the curve component in the GN output (may hide mesh preview on some Blender versions)",
        default=False,
        update=_tlg_curve_settings_update,
    )

    bpy.types.Scene.tlg_view_mode = bpy.props.EnumProperty(
        name="View Mode",
        description="Switch visibility between editable curves (preview) and baked export meshes",
        items=(
            ("EDIT", "Edit Mode", "Show curves + live GN preview"),
            ("EXPORT", "Export Mode", "Show baked meshes (curves hidden)"),
        ),
        default="EDIT",
        update=_tlg_view_mode_update,
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
    try:
        del bpy.types.Object.tlg_auto_smooth_handles
    except Exception:
        pass
    try:
        del bpy.types.Object.tlg_uv_u_m_per_tile
    except Exception:
        pass
    try:
        del bpy.types.Object.tlg_uv_v_m_per_tile
    except Exception:
        pass
    try:
        del bpy.types.Object.tlg_show_curve_overlay
    except Exception:
        pass
    try:
        del bpy.types.Scene.tlg_view_mode
    except Exception:
        pass


__all__ = (
    "_ensure_ribbon_mesh_modifier",
    "_set_modifier_input",
    "ensure_taxi_preview",
    "get_baked_collection",
    "get_baked_mesh_for_curve",
    "get_base_mesh_for_curve",
    "get_taxi_root_collection",
    "get_taxi_curves_collection",
    "get_taxi_export_collection",
    "get_taxi_internal_collection",
    "is_taxi_curve",
)
