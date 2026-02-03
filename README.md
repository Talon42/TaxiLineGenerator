# Airport Taxi Lines for Blender (Taxi Line Generator)

Blender 3.6 LTS add-on for creating airport taxiway marking curves and generating export-ready ribbon meshes with straight-strip UVs.

Status: **In development** (tools and UI may change).

## Requirements

- Blender **3.6 LTS** (tested with **3.6.14**)

## Install

### Option A - Install from a `.zip` (recommended)

1. Create a zip that contains the add-on folder at the top level:
   - Zip `addon/taxi_line_generator/`
   - The zip should contain `taxi_line_generator/__init__.py` at its root.
2. In Blender: `Edit` -> `Preferences` -> `Add-ons` -> `Install...`
3. Select your zip, then enable **Taxi Line Generator**.

### Option B - Copy the folder into Blender's add-ons directory

1. Copy `addon/taxi_line_generator/` into your Blender add-ons folder.
2. In Blender: `Edit` -> `Preferences` -> `Add-ons`
3. Search for **Taxi Line Generator** and enable it.

## Where the UI is

1. Open the **3D Viewport**
2. Press `N` (Sidebar)
3. Go to the **Taxi Lines** tab
4. Open **Taxi Line Generator**

## Quick start (create a line)

Important: points are placed on the **world Z=0 plane**.

1. (Optional) Set `Default Line Width` (meters)
2. Click `Create Taxi Line`
3. In the viewport:
   - `Left Click` = add point (on Z=0)
   - `Enter` or `Right Click`/`Esc` = finish
   - `Ctrl+Z` while drawing = remove the last placed point (keeps drawing active)

This creates a **source curve** object (the editable "authoring" object) and a live preview setup.

## Editing workflow (Edit Curve vs Edit Mesh)

Each taxi line is managed as a linked set of objects (names typically end in `_SRC`, `_MESH`, `_BASE`):

- **Edit Curve** = show/select the source curve and hide/lock meshes.
- **Edit Mesh** = regenerate/unwrap the export mesh, then put you in mesh edit mode.

### Edit the curve (shape/path changes)

1. Select the taxi line curve (`*_SRC`) **or** select its export mesh (`*_MESH`)
2. Click `Edit Curve`
3. Adjust control points as normal in **Edit Mode** for curves
4. If corners kink after edits, click `Recompute Taxi Handles`

### Edit the mesh (material/UV/mesh tweaks)

1. Select the taxi line curve (`*_SRC`) **or** select its export mesh (`*_MESH`)
2. Click `Edit Mesh`

This will:

- Generate/update the export ribbon mesh from the curve
- Unwrap UVs as straight strips
- Switch you into mesh editing on the export mesh

## Extend a line (Resume)

`Resume` only works when:

- You are in **Edit Mode** on the curve, and
- You have **exactly one end point** selected (first or last point of a non-cyclic spline).

Steps:

1. Select the taxi line curve (`*_SRC`)
2. Enter **Edit Mode**
3. Select one endpoint
4. Click `Resume`
5. `Left Click` to add points on Z=0, `Enter`/`Right Click` to finish

## Useful tools (Modifiers box)

- `Line Width` (meters): adjusts the ribbon width.
- `Segments`: increases mesh density (higher = smoother, heavier).
- `Auto Smooth Handles`: keeps curve handles clean and taxi-line-like (recommended).
- `Normalize Curve`: in Edit Curve mode, select **2+** Bezier points to evenly redistribute points between the first and last selected.
- `Recompute Taxi Handles`: fixes sharp corner kinks by re-applying Taxi Line Generator smoothing rules.

## Insert a point into an existing line

In **Edit Curve** mode, you can insert a point into the active curve while preserving shape:

- `Shift + Right Click` in the viewport to insert at the clicked location.
- Also available from the Edit Curve right-click context menu as `Insert Taxi Point Here`.

## Collections created in the Outliner

The add-on organizes objects under a root collection named `Taxi Lines`:

- `EDIT - Curves` (authoring curves)
- `EXPORT - Meshes` (export/editable meshes)
- `_INTERNAL - Base` (internal base meshes used for regeneration)

Tip: avoid deleting or editing `_INTERNAL - Base` objects; they are used to preserve edits during regeneration.

## Notes / current limitations

- Drawing/resuming/inserting points currently projects clicks to **Z=0** (not to arbitrary surfaces).
- The `Reload Taxi Line Generator` button is a development helper; you can ignore it for normal use.
