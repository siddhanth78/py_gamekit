---
name: game-builder
description: Plan, build, debug, or modify games in a PygameKit project workspace identified by .pygamekit-project. Use for game mechanics, rendering, objects, shaders, collisions, updates, architecture, or game assets.
---

# Game Builder

## Immediate Bootstrap

At the beginning of every new game task, run this command from the toolkit root
before planning, inspecting project code, or creating files:

```bash
python3 bootstrap.py
```

Available bootstrap modes:
- `python3 bootstrap.py` – discover the active project directory or create `New Project/`
- `python3 bootstrap.py --new` – create a new project directory (interactive prompt)
- `python3 bootstrap.py --scan` – list all existing marked project directories
- `python3 bootstrap.py --exists <name>` – check if a project directory exists

This is the one allowed filesystem change during planning. It is safe to run
repeatedly because it never overwrites existing project files.

Bootstrap discovers the active workspace by its `.pygamekit-project` marker. If
no marked project directory exists, it creates `New Project/` as the initial workspace.
Always use the project path printed by bootstrap and refer to it as
`<project-root>`. Bootstrap creates:

* `<project-root>/.pygamekit-project` – project identity and file inventory
* `<project-root>/game_state.py` – entity and GPU-instance state
* `<project-root>/input_handler.py` – input-to-intent boundary
* `<project-root>/collision_manager.py` – collision enter/exit tracking
* `<project-root>/assets/` – generated PNG output and asset metadata
* `<project-root>/bitmap/` – editable bitmap JSON sources

The shared toolkit remains outside the game workspace. In particular,
`gl_utils.py`, `shaders/`, `png_generator.py`, and `skills/` stay outside
`<project-root>/`. Do not copy generated game code or assets into the toolkit
root.

## Required Documentation

Immediately after bootstrapping, read
[`../gl-utils-reference/SKILL.md`](../gl-utils-reference/SKILL.md) completely
before planning, reasoning about, debugging, or changing a game.

Treat the GL reference skill as the authoritative technical documentation for
the project. Base all technical decisions and implementations on its current
contents rather than memory, assumptions, generic ModernGL patterns, or
inferred behavior.

Use the GL reference skill for all implementation details, including:
* Rendering APIs and hardware bindings
* Object layouts and dynamic data formats
* Vertex and fragment shaders
* Core game loop and engine update cycles
* Collision detection behavior and math
* Project structures, engine conventions, and expected implementation patterns

Do not invent APIs, formats, methods, shader behaviors, engine capabilities, or implementation patterns that conflict with or are not supported by the GL reference skill.

When implementing or modifying code, re-check the relevant sections of the GL reference skill before writing the implementation.

If the requested behavior is not documented clearly enough to implement safely, inspect the existing project code and reconcile it with the GL reference skill. Prefer documented project behavior over generic assumptions.

## PNG Assets

When the task involves creating, modifying, replacing, or generating PNG assets,
also read
[`../png-bitmap-generator/SKILL.md`](../png-bitmap-generator/SKILL.md)
completely before doing asset work.

Treat the PNG bitmap skill as the authoritative workflow for PNG creation and modification.

Follow both documents when PNG assets interact with game code:
* Use the GL reference skill for how assets are loaded, represented, rendered, or referenced by the game loop.
* Use the PNG bitmap skill for how the PNG files themselves are created or modified via `png_generator.py`.

Do not use the PNG bitmap skill as a substitute for the implementation rules in the GL reference skill.

## Documentation-First Workflow

For every game task:
1. Run `python3 bootstrap.py` from the toolkit root immediately.
2. Read the project path printed by bootstrap and treat it as `<project-root>`.
3. Read `../gl-utils-reference/SKILL.md`.
4. Identify the documentation sections relevant to the request.
5. Inspect the existing implementation inside `<project-root>/`.
6. Base the architecture entirely on the documented APIs and conventions.
7. If PNG work is required, read and follow `../png-bitmap-generator/SKILL.md`.
8. During implementation, use the documented interfaces from the GL reference skill rather than creating parallel or replacement systems unless explicitly requested.

If documentation and existing code appear to disagree, call out the discrepancy and determine the smallest change that preserves the documented project contract.

## Planning Gate

Treat every game request as planning-only work unless the user's current
request explicitly uses **"build"** or **"building"** as a complete word within
a direct instruction to create or modify the game (or execute a previously
agreed game plan). Qualifying examples include "let's build the game" and
"begin building it." The word need not appear by itself or make up the entire
request.

Do not infer implementation authority from intent, enthusiasm, or synonyms.
Words and phrases such as "make," "create," "implement," "code," "start," "go
ahead," or "let's do it" do not pass this gate. A mention that merely quotes,
discusses, negates, or asks about "build" or "building" also does not pass it.
When the gate is not passed, remain in planning even if the request otherwise
sounds actionable.

During planning:
* Read the GL reference skill and any other relevant project files.
* Inspect existing code and assets under `<project-root>/` as needed.
* Use the documentation to determine what the engine already supports natively.
* Design the feature strictly around the documented project APIs.
* Apart from the mandatory bootstrap, **do not** create, modify, rename, or delete game code, assets, tests, configuration, or generated data.

A plan must identify the specific documented APIs or systems that the eventual implementation will use.

Begin implementation only when the explicit **"build"** / **"building"** gate
above is satisfied. There is no equivalent wording.

Implementation authorization permits changes only within the scope of the agreed plan unless the user explicitly expands that scope.

## Implementation

Once implementation is authorized by a qualifying **"build"** or
**"building"** instruction:
1. Re-check that bootstrap ran at the start of the task.
2. Re-read or re-check the relevant sections of the GL reference skill.
3. Inspect the generated boilerplate and other affected files in `<project-root>/`.
4. Modify and extend `game_state.py`, `input_handler.py`, and `collision_manager.py` when their responsibilities are needed. Do not bypass them with duplicate systems.
5. Create `<project-root>/main.py` as the composition root that initializes the engine and wires the adapted components together. It must resolve `PROJECT_ROOT` from its own file location, resolve `TOOLKIT_ROOT` as the parent directory, and add `TOOLKIT_ROOT` to `sys.path` before importing boilerplate modules that depend on `gl_utils`.
6. Create additional focused modules inside `<project-root>/` when functionality does not belong in the three boilerplate components or `main.py`.
7. Implement using the exact APIs, structures, formats, shaders, update behaviors, collision behaviors, and conventions documented in the GL reference skill.
8. If PNG assets are involved, follow the PNG bitmap skill; all bitmap sources and generated PNGs must stay inside `<project-root>/`.
9. Keep changes scoped strictly to the requested feature and verify the implementation against the documented behavior.
10. Run `python3 bootstrap.py` again after changes so `.pygamekit-project` records the final directory and file inventory.

The boilerplate is a starting architecture, not immutable vendor code. Adapt it
to the game while preserving each module's responsibility, then wire those
components through `<project-root>/main.py`.

Do not rely on remembered versions of the documentation. The files currently present in the project are the source of truth.

## Returning to Planning

If the user asks to go back to planning, return immediately to planning-only work and stop making game changes.
* Any earlier implementation authorization is immediately revoked.
* Require a fresh qualifying **"build"** or **"building"** instruction before
  resuming implementation.