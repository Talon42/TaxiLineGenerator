import bpy  # pyright: ignore[reportMissingImports]
import addon_utils  # pyright: ignore[reportMissingImports]
import importlib
import sys
from datetime import datetime, timezone

from .properties import get_baked_mesh_for_curve, is_taxi_curve


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

        active = context.view_layer.objects.active
        if active and active.type == "CURVE" and is_taxi_curve(active):
            layout.prop(active, "tlg_line_width", text="Line Width")
            layout.prop(active, "tlg_auto_smooth_handles", text="Auto Smooth Handles")
            layout.label(text="Curve is authoritative; mesh is for export.")
            layout.operator("taxilines.finish_editing", text="Edit Mesh", icon="MESH_GRID")
            layout.separator()
        elif active and active.type == "MESH" and active.get("tlg_source_curve"):
            layout.label(text=f"Source Curve: {active.get('tlg_source_curve')}")
            layout.operator("taxilines.edit_path", text="Edit Curve", icon="CURVE_BEZCURVE")
            layout.separator()
        else:
            layout.prop(context.scene, "tlg_default_width", text="Default Line Width")
            layout.operator("taxilines.create_ribbon_mesh", text="Attach GN Preview", icon="GEOMETRY_NODES")
            layout.separator()

        layout.operator("taxilines.draw_taxi_line", text="Create Taxi Line", icon="GREASEPENCIL")
        layout.operator("taxilines.normalize_curve", icon="MOD_CURVE")
        layout.operator("taxilines.recompute_handles", icon="HANDLE_AUTO")
        layout.operator("taxilines.debug_active", icon="CONSOLE")
        layout.separator()
        layout.label(text="Edit Mesh regenerates the export mesh.")
        layout.label(text="Left-click = add point on Z=0")
        layout.label(text="Enter/Right-click = finish")
