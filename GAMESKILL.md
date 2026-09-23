---

name: game-builder
description: Plan, build, or modify games in this project using the project's documented ModernGL rendering API and deterministic PNG asset workflow. Use when discussing, designing, implementing, debugging, or modifying game mechanics, rendering, objects, shaders, collisions, updates, assets, or other game behavior in this project.
---

# Game Builder

## Required documentation

Before planning, reasoning about, debugging, or changing a game in this project, read `README.md` completely.

Treat `README.md` as the authoritative technical documentation for the project. Base all technical decisions and implementations on its current contents rather than memory, assumptions, generic ModernGL patterns, or inferred behavior.

Use `README.md` for all implementation details, including:

* rendering APIs
* object and data formats
* shaders
* game/update loops
* collision behavior
* engine conventions
* supported APIs and abstractions
* project structure and expected implementation patterns

Do not invent APIs, formats, methods, shader behavior, engine capabilities, or implementation patterns that conflict with or are not supported by `README.md`.

When implementing or modifying code, re-check the relevant sections of `README.md` before writing the implementation.

If the requested behavior is not documented clearly enough to implement safely, inspect the existing project code and reconcile it with `README.md`. Prefer documented project behavior over generic assumptions.

## PNG assets

When the task involves creating, modifying, replacing, or generating PNG assets, also read `PNGSKILL.md` completely before doing asset work.

Treat `PNGSKILL.md` as the authoritative workflow for PNG creation and modification.

Follow both documents when PNG assets interact with game code:

* use `README.md` for how assets are loaded, represented, rendered, or referenced by the game;
* use `PNGSKILL.md` for how the PNG files themselves are created or modified.

Do not use `PNGSKILL.md` as a substitute for the implementation rules in `README.md`.

## Documentation-first workflow

For every game task:

1. Read `README.md`.
2. Identify the sections relevant to the request.
3. Inspect existing implementation where necessary to understand the current state.
4. Base the proposed approach on the documented APIs and conventions.
5. If PNG work is required, read and follow `PNGSKILL.md`.
6. During implementation, use the documented interfaces from `README.md` rather than creating parallel or replacement systems unless the user explicitly requests an architectural change.

If documentation and existing code appear to disagree, call out the discrepancy and determine the smallest change that preserves the documented project contract.

## Planning gate

Treat game ideas, feature discussions, architecture discussions, and requests to plan as planning-only work.

During planning:

* read `README.md` and any other relevant project files;
* inspect existing code and assets as needed;
* use the documentation to determine what the engine already supports;
* design the feature around the documented project APIs;
* do not create, modify, rename, or delete game code, assets, tests, configuration, or generated data.

A plan should identify the relevant documented APIs or systems that the eventual implementation will use.

Begin implementation only after the user explicitly says **"let's build it"** or gives equivalent direct authorization to implement the agreed plan.

Implementation authorization permits changes only within the scope of the agreed plan unless the user expands that scope.

## Implementation

Once implementation is authorized:

1. Re-read or re-check the relevant sections of `README.md`.
2. Inspect the current implementation files affected by the change.
3. Implement using the APIs, structures, formats, shaders, update behavior, collision behavior, and conventions documented in `README.md`.
4. Reuse existing project abstractions instead of recreating functionality already provided by the engine.
5. If PNG assets are involved, follow `PNGSKILL.md` for the asset workflow while continuing to use `README.md` for their integration into the game.
6. Keep changes scoped to the requested feature and avoid unrelated refactors unless they are required for correctness.
7. Verify the implementation against the documented behavior after making changes.

Do not rely on remembered versions of the documentation. The files currently present in the project are the source of truth.

## Returning to planning

If the user asks to go back to planning, return immediately to planning-only work and stop making game changes.

Any earlier implementation authorization is revoked.

Require fresh explicit authorization before resuming implementation.
