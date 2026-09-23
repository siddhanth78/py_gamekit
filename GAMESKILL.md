---
name: game-builder
description: Plan, build, or modify games in this project using the project's documented ModernGL rendering API (GLSKILL.md) and deterministic PNG asset workflow. Use when discussing, designing, implementing, debugging, or modifying game mechanics, rendering, objects, shaders, collisions, updates, assets, or other game behavior in this project.
---

# Game Builder

## Immediate Bootstrap

At the beginning of every new game task, run this command from the toolkit root
before planning, inspecting project code, or creating files:

```bash
python3 bootstrap.py
```

This is the one allowed filesystem change during planning. It is safe to run
repeatedly because it never overwrites existing project files.

Bootstrap establishes `New Project/` as the active game workspace and creates:

* `New Project/game_state.py` – entity and GPU-instance state
* `New Project/input_handler.py` – input-to-intent boundary
* `New Project/collision_manager.py` – collision enter/exit tracking
* `New Project/assets/` – generated PNG output and asset metadata
* `New Project/bitmap/` – editable bitmap JSON sources

The shared toolkit remains outside the game workspace. In particular,
`gl_utils.py`, `shaders/`, `png_generator.py`, `GLSKILL.md`, and `PNGSKILL.md`
stay at the repository root. Do not copy generated game code or assets into the
toolkit root.

## Required Documentation

Immediately after bootstrapping, read `GLSKILL.md` completely before planning,
reasoning about, debugging, or changing a game.

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
1. Run `python3 bootstrap.py` from the toolkit root immediately.
2. Treat `New Project/` as the active game workspace.
3. Read `GLSKILL.md`.
4. Identify the documentation sections relevant to the request.
5. Inspect the existing implementation inside `New Project/`.
6. Base the architecture entirely on the documented APIs and conventions.
7. If PNG work is required, read and follow `PNGSKILL.md`.
8. During implementation, use the documented interfaces from `GLSKILL.md` rather than creating parallel or replacement systems unless explicitly requested.

If documentation and existing code appear to disagree, call out the discrepancy and determine the smallest change that preserves the documented project contract.

## Planning Gate

Treat game ideas, feature discussions, architecture discussions, and requests to plan as planning-only work.

During planning:
* Read `GLSKILL.md` and any other relevant project files.
* Inspect existing code and assets under `New Project/` as needed.
* Use the documentation to determine what the engine already supports natively.
* Design the feature strictly around the documented project APIs.
* Apart from the mandatory bootstrap, **do not** create, modify, rename, or delete game code, assets, tests, configuration, or generated data.

A plan must identify the specific documented APIs or systems that the eventual implementation will use.

Begin implementation **only** after the user explicitly says **"let's build it"** or gives equivalent direct authorization to implement the agreed plan.

Implementation authorization permits changes only within the scope of the agreed plan unless the user explicitly expands that scope.

## Implementation

Once implementation is authorized:
1. Re-check that bootstrap ran at the start of the task.
2. Re-read or re-check the relevant sections of `GLSKILL.md`.
3. Inspect the generated boilerplate and other affected files in `New Project/`.
4. Modify and extend `game_state.py`, `input_handler.py`, and `collision_manager.py` when their responsibilities are needed. Do not bypass them with duplicate systems.
5. Create `New Project/main.py` as the composition root that initializes the engine and wires the adapted components together. It must resolve `PROJECT_ROOT` from its own file location, resolve `TOOLKIT_ROOT` as the parent directory, and add `TOOLKIT_ROOT` to `sys.path` before importing boilerplate modules that depend on `gl_utils`.
6. Create additional focused modules inside `New Project/` when functionality does not belong in the three boilerplate components or `main.py`.
7. Implement using the exact APIs, structures, formats, shaders, update behaviors, collision behaviors, and conventions documented in `GLSKILL.md`.
8. If PNG assets are involved, follow `PNGSKILL.md`; all bitmap sources and generated PNGs must stay inside `New Project/`.
9. Keep changes scoped strictly to the requested feature and verify the implementation against the documented behavior.

The boilerplate is a starting architecture, not immutable vendor code. Adapt it
to the game while preserving each module's responsibility, then wire those
components through `New Project/main.py`.

Do not rely on remembered versions of the documentation. The files currently present in the project are the source of truth.

## Returning to Planning

If the user asks to go back to planning, return immediately to planning-only work and stop making game changes.
* Any earlier implementation authorization is immediately revoked.
* Require fresh, explicit authorization before resuming implementation.
