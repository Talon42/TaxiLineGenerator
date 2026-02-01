import bpy


class TAXILINES_PT_main(bpy.types.Panel):
    bl_label = "Taxi Line Generator"
    bl_idname = "TAXILINES_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Taxi Lines"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Addon loaded ✅")
        layout.label(text="Next: setup Blender scripts path")
