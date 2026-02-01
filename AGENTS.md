# AGENTS.md — TaxiLineGenerator

This repository contains a Blender add-on for creating airport taxiway markings.
Agents contributing to this project should follow the guidelines below.

---

## 1) Core Vision

The goal of this project is to provide a professional, efficient tool for creating
airport taxiway line markings inside Blender for scenery and simulation workflows.

The add-on should feel:
- Precise
- Fast
- Predictable
- Non-destructive
- Suitable for large airport layouts

It should support long-term use in production environments.

---

## 2) Primary Project Goals

The add-on must ultimately allow users to:

1) Draw taxi lines interactively in the viewport using mouse clicks.
2) Automatically generate smooth, well-behaved Bezier curves.
3) Adjust line width at any time without breaking topology.
4) Generate flat, single-sided ribbon meshes.
5) Produce clean, predictable UVs that unwrap as straight strips.
6) Provide flexible UV controls so that all marking styles
   (solid, dashed, double, edge, hold-short, custom) are handled
   through textures and materials rather than geometry variants.

---

## 3) Technical Constraints

- Must remain compatible with Blender 3.6 LTS.
- Avoid APIs exclusive to newer Blender versions.
- Do not introduce external Python dependencies.
- Prefer stable, documented Blender features.
- Maintain a non-destructive workflow whenever possible.

---

## 4) Design Principles

Agents should follow these principles when making changes:

### Simplicity
- Prefer clear, maintainable solutions over clever shortcuts.
- Avoid unnecessary abstraction.

### Modularity
- Separate UI, operators, geometry, and utilities.
- Keep components reusable.

### Predictability
- User actions should always produce consistent results.
- Avoid “magic” behavior that is hard to control.

### Performance
- Tools must remain responsive for large airports.
- Avoid heavy computation in modal loops.

### Artist-Friendly Workflow
- Features should match real-world airport layout practices.
- Controls should use real-world units.
- Output should be export-ready for simulators.

---

## 5) Geometry and UV Standards

Generated geometry should:

- Be flat (no thickness unless explicitly requested).
- Use consistent vertex ordering.
- Have correct normals for backface culling.
- Be optimized for export.

UVs should:

- Use length-based U coordinates.
- Use width-based V coordinates.
- Remain stable when width or shape changes.
- Avoid fragmentation.
- Support texture-driven marking styles.

---

## 6) Long-Term Architecture Goals

The add-on should eventually support:

- Style presets based on UV/material mappings
- Parameterized UV scaling
- Batch editing
- Non-destructive regeneration
- Optional Geometry Nodes integration
- Export-friendly pipelines

Design changes should not block these future features.

---

## 7) Change Policy for Agents

When contributing:

- Respect existing architecture.
- Keep changes scoped to the intended feature.
- Avoid unnecessary restructuring.
- Document non-obvious Blender API behavior.
- Prefer backward-compatible solutions.

Large refactors should only be performed when clearly justified.

---

## 8) User Experience Priority

The user experience should prioritize:

1) Fast layout creation
2) Easy adjustment
3) Minimal manual cleanup
4) Predictable results
5) Low learning curve

Every major feature should support at least one of these goals.

---
