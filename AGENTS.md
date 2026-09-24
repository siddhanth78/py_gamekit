# Repository Instructions

This repository is the reusable **PygameKit** toolkit. Shared engine and
generation tools live at the repository root. Game-specific work belongs in the
active project directory identified by a `.pygamekit-project` marker.

## Skill Routing

Read every selected `SKILL.md` completely before taking task actions.

- For any request to discuss, plan, build, debug, review, or modify a game, use
  `skills/game-builder/SKILL.md`.
- For rendering, shaders, buffers, instance layouts, geometry, textures, mouse
  interaction, or collision behavior, also use
  `skills/gl-utils-reference/SKILL.md`.
- For creating or modifying PNG sprites, atlases, textures, bitmap JSON, or
  other generated PNG artwork, also use
  `skills/png-bitmap-generator/SKILL.md`.

When multiple skills apply, read the game-builder skill first, followed by the
GL reference and then the PNG skill as relevant. After loading the required
skills, the first action for a game or game-asset task is the bootstrap command
required by those skills.

## Workspace Boundary

- Run `python3 bootstrap.py` to discover or create the active project. Use the
  project path printed by bootstrap; never assume its directory is still named
  `New Project/`.
- The directory containing `.pygamekit-project` is `<project-root>`. The marker
  is a JSON inventory of all intentional directories and categorized code,
  asset, bitmap, and other files in that project.
- Treat `.pygamekit-project` as generated metadata; do not edit it by hand.
  Bootstrap refreshes it and excludes caches, virtual environments, compiled
  Python files, and operating-system metadata.
- `<project-root>/` contains all game-specific source code, tests, bitmap JSON,
  generated assets, and supporting modules.
- `gl_utils.py`, `shaders/`, and `png_generator.py` are shared toolkit
  components. Treat them as read-only during ordinary game work unless the user
  explicitly requests a toolkit or engine change.
- `bootstrap.py`, `skills/`, and this file define the reusable workflow. Do not
  copy them into `<project-root>/`.
- A renamed project remains active because its marker moves with it. If
  bootstrap finds multiple marked projects, stop and ask the user which project
  should remain active.
- Preserve the active project's contents. Never delete, reset, or replace it
  merely because a request mentions a new task. Starting a different clean
  project requires explicit user direction about the existing workspace.
- Run bootstrap again after implementation or asset changes so the marker
  inventory reflects the completed project.

Toolkit-maintenance requests that only change bootstrap, shared helpers,
shaders, generators, skills, or repository instructions do not create a game
workspace and therefore do not require bootstrap unless the requested
verification specifically needs it.
