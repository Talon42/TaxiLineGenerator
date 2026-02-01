import bpy
import importlib


class TAXILINES_OT_reload_addon(bpy.types.Operator):
    bl_idname = "taxilines.reload_addon"
    bl_label = "Reload Taxi Line Generator"
    bl_description = "Reload the Taxi Line Generator addon (dev helper)"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        addon_name = __package__  # "taxi_line_generator"
        if not addon_name:
            self.report({"ERROR"}, "Could not determine addon package name.")
            return {"CANCELLED"}

        # Reload submodules first (simple approach: just ui for now)
        try:
            import taxi_line_generator.ui as ui_mod
            importlib.reload(ui_mod)
        except Exception as e:
            self.report({"ERROR"}, f"Reload failed: {e}")
            raise

        # Full addon reload via disabling/enabling
        try:
            bpy.ops.preferences.addon_disable(module=addon_name)
            bpy.ops.preferences.addon_enable(module=addon_name)
        except Exception as e:
            self.report({"ERROR"}, f"Addon re-enable failed: {e}")
            raise

        self.report({"INFO"}, "Taxi Line Generator reloaded.")
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
        layout.separator()

        layout.label(text="Addon loaded ✅")
