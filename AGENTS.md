# Repository Instructions

This repository is the reusable **PyGameKit** toolkit. Shared engine and
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
- For bundling, packaging, exporting, or shipping a marked game as a native
  desktop release, also use `skills/game-bundler/SKILL.md`.

When multiple skills apply, read the game-builder skill first, followed by the
game-bundler skill for packaging tasks, the GL reference, and then the PNG skill
as relevant. After loading the required skills, the first action for a game or
game-asset task is the bootstrap command required by those skills.

## Game Implementation Authorization

- Treat every game request as planning-only unless the user's current request
  explicitly uses **"build"** or **"building"** as a complete word within a
  direct instruction to create or modify the game. Qualifying examples include
  "let's build the game" and "begin building it." The word need not appear by
  itself or make up the entire request.
- Synonyms such as "make," "create," "implement," "code," "start," or "work
  on" do not authorize implementation. Discuss the idea, inspect the project,
  and produce or refine a plan without changing game code or assets.
- Merely quoting, describing, or asking about the words "build" or "building"
  is not authorization. The word must be part of a direct instruction to build
  the game (or a previously agreed game plan).
- Authorization does not carry into a later task after the user returns to
  planning or changes the subject. Require **"build"** or **"building"** again
  before resuming game implementation.
- During planning, bootstrap and `<project-root>/plan.txt` are the only
  permitted filesystem changes. Create or update that plan as decisions are
  made; it records intent but never grants implementation authorization.
- Before an authorized build, read the active project's `plan.txt` and
  reconcile it with the user's current request. Implement only the authorized
  scope, then update the plan's progress and remaining work.
- A direct instruction to **bundle**, **package**, **export**, or **ship** a
  game is a packaging operation rather than game implementation. It authorizes
  the dependency installation, marker refresh, bundler execution, and `dist/`
  output required by `skills/game-bundler/SKILL.md`, but does not authorize
  changes to gameplay code, assets, or shared engine code.

## Dependency Setup

- Before implementing, running, testing, or bundling a game, install the shared
  toolkit and packaging dependencies from the repository root with
  `python3 -m pip install -r requirements.txt`. Run this at least once per
  environment or session so required runtime, asset, and PyInstaller packages
  are not missed.
- Do not silently skip dependency installation because a package is missing or
  a download is blocked. If sandbox or network restrictions prevent the install,
  request the required approval and retry using the same command.

## Workspace Boundary

- Run `python3 bootstrap.py` to discover or create the active project directory. 
  Use these modes for specific operations:
  - `python3 bootstrap.py` – discover or create the default project
  - `python3 bootstrap.py --new` – create a new project directory (interactive)
  - `python3 bootstrap.py --scan` – list all existing marked project directories
  - `python3 bootstrap.py --exists <name>` – check if a project directory exists
  
  Use the project path printed by bootstrap; never assume its directory is still named
  `New Project/`.
- The directory containing `.pygamekit-project` is `<project-root>`. The marker
  is a JSON inventory of all intentional directories and categorized code,
  asset, bitmap, and other files in that project.
- Treat `.pygamekit-project` as generated metadata; do not edit it by hand.
  Bootstrap refreshes it and excludes caches, virtual environments, compiled
  Python files, and operating-system metadata.
- `<project-root>/` contains all game-specific source code, tests, bitmap JSON,
  generated assets, supporting modules, and `plan.txt`.
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
