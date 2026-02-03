import bpy  # pyright: ignore[reportMissingImports]
import addon_utils  # pyright: ignore[reportMissingImports]
import importlib
import sys
from datetime import datetime, timezone

from .properties import get_baked_mesh_for_curve, get_source_curve_for_mesh, is_taxi_curve


_LAST_RELOAD_STATUS = None
_LAST_RELOAD_AT_UTC = None


class TAXILINES_OT_reload_addon(bpy.types.Operator):
    bl_idname = "taxilines.reload_addon"
    bl_label = "Reload Taxi Line Generator"
    bl_description = "Reload the Taxi Line Generator addon (dev helper)"
    bl_options = {"INTERNAL"}

    _reload_pending = False

    @staticmethod
    def _deferred_reload(addon_name):
        global _LAST_RELOAD_STATUS, _LAST_RELOAD_AT_UTC
        try:
            addon_utils.disable(addon_name, default_set=False)
            importlib.invalidate_caches()

            # Ensure the next enable imports fresh code from disk (Blender may otherwise
            # reuse cached modules from sys.modules).
            prefix = addon_name + "."
            for key in list(sys.modules.keys()):
                if key == addon_name or key.startswith(prefix):
                    del sys.modules[key]

            addon_utils.enable(addon_name, default_set=False)
            _LAST_RELOAD_STATUS = "OK"
            _LAST_RELOAD_AT_UTC = datetime.now(timezone.utc)

            def _draw(self, _context):
                self.layout.label(text="Taxi Line Generator reloaded.")

            try:
                bpy.context.window_manager.popup_menu(_draw, title="Reload", icon="CHECKMARK")
            except Exception:
                pass
        except Exception:
            import traceback

            traceback.print_exc()
            _LAST_RELOAD_STATUS = "ERROR (see console)"
            _LAST_RELOAD_AT_UTC = datetime.now(timezone.utc)
        finally:
            TAXILINES_OT_reload_addon._reload_pending = False

        return None

    def execute(self, context):
        addon_name = __package__  # "taxi_line_generator"
        if not addon_name:
            self.report({"ERROR"}, "Could not determine addon package name.")
            return {"CANCELLED"}

        # Disabling the add-on while an operator defined by that same add-on is still executing
        # can crash Blender. Defer the reload to a timer so this operator can finish safely.
        if TAXILINES_OT_reload_addon._reload_pending:
            self.report({"WARNING"}, "Reload already in progress.")
            return {"CANCELLED"}

        TAXILINES_OT_reload_addon._reload_pending = True
        bpy.app.timers.register(lambda: TAXILINES_OT_reload_addon._deferred_reload(addon_name), first_interval=0.1)

        self.report({"INFO"}, "Taxi Line Generator reload scheduled.")
        return {"FINISHED"}


class TAXILINES_PT_main(bpy.types.Panel):
    bl_label = "Taxi Line Generator"
    bl_idname = "TAXILINES_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Taxi Lines"

    def draw(self, context):
        layout = self.layout

        layout.row().operator("taxilines.reload_addon", icon="FILE_REFRESH")
        if _LAST_RELOAD_STATUS is not None:
            when = _LAST_RELOAD_AT_UTC.astimezone().strftime("%Y-%m-%d %H:%M:%S") if _LAST_RELOAD_AT_UTC else "?"
            layout.label(text=f"Reload: {_LAST_RELOAD_STATUS} @ {when}")
        layout.separator()

        wm = context.window_manager
        is_drawing = bool(getattr(wm, "tlg_ui_is_drawing_line", False))
        is_resuming = bool(getattr(wm, "tlg_ui_is_resuming_line", False))

        active = context.view_layer.objects.active
        active_taxi_curve = bool(active and active.type == "CURVE" and is_taxi_curve(active))

        active_mesh_source_curve = None
        if active and active.type == "MESH":
            active_mesh_source_curve = get_source_curve_for_mesh(active)
        active_mesh_has_taxi_curve = bool(active_mesh_source_curve and is_taxi_curve(active_mesh_source_curve))
        is_edit_mesh_mode = bool(active and active.type == "MESH" and active_mesh_has_taxi_curve)

        target_curve = active if active_taxi_curve else (active_mesh_source_curve if active_mesh_has_taxi_curve else None)

        create_box = layout.box()
        create_box.label(text="Create")

        create_box.operator(
            "taxilines.draw_taxi_line",
            text="DRAWING LINE" if is_drawing else "Create Taxi Line",
            icon="GREASEPENCIL",
            depress=is_drawing,
        )
        if not is_edit_mesh_mode:
            create_box.operator(
                "taxilines.resume_taxi_line",
                text="RESUMING LINE" if is_resuming else "Resume",
                icon="PLAY",
                depress=is_resuming,
            )

        if active_taxi_curve:
            create_box.operator("taxilines.finish_editing", text="Edit Mesh", icon="MESH_GRID")
        elif active_mesh_has_taxi_curve:
            if not is_edit_mesh_mode:
                create_box.label(text=f"Source Curve: {active_mesh_source_curve.name}")
            create_box.operator("taxilines.edit_path", text="Edit Curve", icon="CURVE_BEZCURVE")

        modifiers_box = layout.box()
        modifiers_box.label(text="Modifiers")

        if target_curve is None:
            modifiers_box.prop(context.scene, "tlg_default_width", text="Default Line Width")
            modifiers_box.separator()

        if target_curve is not None:
            modifiers_box.prop(target_curve, "tlg_line_width", text="Line Width")
            modifiers_box.prop(target_curve, "tlg_segments_mult", text="Segments")
            if not is_edit_mesh_mode:
                modifiers_box.operator("taxilines.normalize_curve", text="Normalize Curve", icon="MOD_CURVE")
                modifiers_box.operator("taxilines.recompute_handles", text="Recompute Taxi Handles", icon="HANDLE_AUTO")
            if not is_edit_mesh_mode:
                modifiers_box.prop(target_curve, "tlg_auto_smooth_handles", text="Auto Smooth Handles")
            modifiers_box.separator()
        elif not is_edit_mesh_mode:
            modifiers_box.operator("taxilines.normalize_curve", text="Normalize Curve", icon="MOD_CURVE")
            modifiers_box.operator("taxilines.recompute_handles", text="Recompute Taxi Handles", icon="HANDLE_AUTO")

        layout.operator("taxilines.debug_active", icon="CONSOLE")
        layout.separator()
        layout.label(text="Edit Mesh regenerates the export mesh.")
        layout.label(text="Left-click = add point on Z=0")
        layout.label(text="Enter/Right-click = finish")
        layout.label(text="Resume: select end point in Edit Curve mode")
