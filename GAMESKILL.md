---
name: game-builder
description: Plan, build, or modify games in this project using the project's documented ModernGL rendering API (GLSKILL.md) and deterministic PNG asset workflow. Use when discussing, designing, implementing, debugging, or modifying game mechanics, rendering, objects, shaders, collisions, updates, assets, or other game behavior in this project.
---

# Game Builder

## Required Documentation

Before planning, reasoning about, debugging, or changing a game in this project, read `GLSKILL.md` completely.

Treat `GLSKILL.md` as the authoritative technical documentation for the project. Base all technical decisions and implementations on its current contents rather than memory, assumptions, generic ModernGL patterns, or inferred behavior.

Use `GLSKILL.md` for all implementation details, including:
* Rendering APIs and hardware bindings
* Object layouts and dynamic data formats
* Vertex and fragment shaders
* Core game loop and engine update cycles
* Collision detection behavior and math
* Project structures, engine conventions, and expected implementation patterns

Do not invent APIs, formats, methods, shader behaviors, engine capabilities, or implementation patterns that conflict with or are not supported by `GLSKILL.md`.

When implementing or modifying code, re-check the relevant sections of `GLSKILL.md` before writing the implementation.

If the requested behavior is not documented clearly enough to implement safely, inspect the existing project code and reconcile it with `GLSKILL.md`. Prefer documented project behavior over generic assumptions.

## PNG Assets

When the task involves creating, modifying, replacing, or generating PNG assets, also read `PNGSKILL.md` completely before doing asset work.

Treat `PNGSKILL.md` as the authoritative workflow for PNG creation and modification.

Follow both documents when PNG assets interact with game code:
* Use `GLSKILL.md` for how assets are loaded, represented, rendered, or referenced by the game loop.
* Use `PNGSKILL.md` for how the PNG files themselves are created or modified via `png_generator.py`.

Do not use `PNGSKILL.md` as a substitute for the implementation rules in `GLSKILL.md`.

## Documentation-First Workflow

For every game task:
1. Read `GLSKILL.md`.
2. Identify the specific documentation sections relevant to the request.
3. Inspect the existing codebase implementation to verify the current application state.
4. Base the proposed architecture entirely on the documented APIs and conventions.
5. If PNG work is required, read and follow `PNGSKILL.md`.
6. During implementation, use the documented interfaces from `GLSKILL.md` rather than creating parallel or replacement systems unless explicitly requested.

If documentation and existing code appear to disagree, call out the discrepancy and determine the smallest change that preserves the documented project contract.

## Planning Gate

Treat game ideas, feature discussions, architecture discussions, and requests to plan as planning-only work.

During planning:
* Read `GLSKILL.md` and any other relevant project files.
* Inspect existing code and assets as needed.
* Use the documentation to determine what the engine already supports natively.
* Design the feature strictly around the documented project APIs.
* **Do not** create, modify, rename, or delete game code, assets, tests, configuration, or generated data.

A plan must identify the specific documented APIs or systems that the eventual implementation will use.

Begin implementation **only** after the user explicitly says **"let's build it"** or gives equivalent direct authorization to implement the agreed plan.

Implementation authorization permits changes only within the scope of the agreed plan unless the user explicitly expands that scope.

## Implementation

Once implementation is authorized:
1. Re-read or re-check the relevant sections of `GLSKILL.md`.
2. Inspect the current implementation files affected by the change.
3. Implement using the exact APIs, structures, formats, shaders, update behaviors, collision behaviors, and conventions documented in `GLSKILL.md`.
4. Reuse existing project abstractions instead of recreating functionality already provided by the engine.
5. If PNG assets are involved, follow `PNGSKILL.md` for the asset workflow while continuing to use `GLSKILL.md` for their integration into the game loop.
6. Keep changes scoped strictly to the requested feature; avoid unrelated refactors unless required for correctness.
7. Verify the implementation against the documented behavior after making changes.

Do not rely on remembered versions of the documentation. The files currently present in the project are the source of truth.

## Returning to Planning

If the user asks to go back to planning, return immediately to planning-only work and stop making game changes.
* Any earlier implementation authorization is immediately revoked.
* Require fresh, explicit authorization before resuming implementation.
