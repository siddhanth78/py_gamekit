# PyGameKit: 2D Graphics Engine & Project Toolkit

A pixel-native 2D rendering system built on ModernGL and Pygame, with multi-project workspace management, entity-based architecture, and deterministic PNG asset generation.

**Key distinction:** Shared tools (`gl_utils.py`, `png_generator.py`, `bootstrap.py`, `skills/`) live in the toolkit root. Each game project lives in its own isolated directory marked by `.pygamekit-project`.

---

## Quick Start

### 1. Install Dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 2. Bootstrap Your First Project

From the toolkit root:

```bash
python3 bootstrap.py
```

Available bootstrap modes:
- `python3 bootstrap.py` – discover the active project or create `New Project/`
- `python3 bootstrap.py --new` – create a new project (interactive prompt)
- `python3 bootstrap.py --scan` – list all existing marked projects
- `python3 bootstrap.py --exists MyGame` – check if a project exists

Bootstrap will print the active project path. Use that path as `<project-root>`.

### 3. Start Building

Inside `<project-root>/main.py`:

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

import pygame
import moderngl
from gl_utils import load_program, set_viewport_size, build_rect_objs
from game_state import GameState
from input_handler import InputHandler
from collision_manager import CollisionManager

# ... rest of your game loop
```

---

## Toolkit Structure

```
pygamekit/                          # Toolkit root
├── gl_utils.py                     # Core rendering helper (shared)
├── png_generator.py                # PNG asset generator (shared)
├── bootstrap.py                    # Project workspace manager
├── bundle_game.py                  # Native desktop bundle exporter
├── requirements.txt                # Runtime, asset, and bundle dependencies
├── shaders/                        # Shared shader files (used by all projects)
│   ├── rect.vert / rect.frag
│   ├── point.vert / point.frag
│   └── tex.vert / tex.frag
├── skills/
│   ├── game-builder/
│   │   └── SKILL.md                # Game development workflow
│   ├── gl-utils-reference/
│   │   └── SKILL.md                # Rendering API reference
│   ├── png-bitmap-generator/
│   │   └── SKILL.md                # PNG asset generation
│   └── game-bundler/
│       └── SKILL.md                # Native release packaging workflow
│
├── MyGame/                         # Project 1 (marked with .pygamekit-project)
│   ├── .pygamekit-project          # Project marker (JSON manifest)
│   ├── main.py
│   ├── game_state.py               # Boilerplate (auto-generated)
│   ├── input_handler.py            # Boilerplate (auto-generated)
│   ├── collision_manager.py        # Boilerplate (auto-generated)
│   ├── assets/
│   │   └── *.png
│   └── bitmap/
│       └── *.json
│
└── OtherGame/                      # Project 2 (separate workspace)
    ├── .pygamekit-project
    ├── main.py
    └── ... (same structure)
```

---

## Bootstrap Workflow

Bootstrap creates a complete project workspace. Run it **before** planning or implementation:

```bash
python3 bootstrap.py
```

This generates:
- `<project-root>/` directory with boilerplate
- `<project-root>/.pygamekit-project` – project identity and file inventory (JSON)
- `<project-root>/game_state.py` – entity-ID-based component for scalable architecture
- `<project-root>/input_handler.py` – event → intent decoupler
- `<project-root>/collision_manager.py` – collision enter/exit tracking
- `<project-root>/bitmap/` – directory for PNG specifications (JSON)
- `<project-root>/assets/` – directory for generated PNG files

**Safe to run repeatedly** — never overwrites existing files.

### Bootstrap Modes

| Command | Purpose |
|---------|---------|
| `python3 bootstrap.py` | Discover active project or create `New Project/` |
| `python3 bootstrap.py --new` | Create a new project (interactive) |
| `python3 bootstrap.py --scan` | List all marked projects |
| `python3 bootstrap.py --exists NAME` | Check if project exists |

---

## Shipping a Game

PyGameKit can package a marked project, its generated assets, the shared
`gl_utils.py` module, and the shared shaders into a native desktop application.
Install the build dependency in the same Python environment as the game:

```bash
python3 -m pip install -r requirements.txt
```

Validate the active project and preview the command without building:

```bash
python3 bundle_game.py --dry-run
```

Build the recommended one-folder release:

```bash
python3 bundle_game.py
```

Build a single-file release after the one-folder build has been tested:

```bash
python3 bundle_game.py --onefile
```

Useful options include `--project PATH`, `--name NAME`, `--icon PATH`,
`--console`, `--dist-dir PATH`, `--include-bitmaps`, and repeatable
`--hidden-import MODULE`. Output defaults to `dist/` at the toolkit root.

PyInstaller creates an application for the host operating system. Run the
bundler on Windows to produce an `.exe`, on macOS for a macOS build, and on
Linux for a Linux build. The shipped application does not require a separate
Python installation.

---

## Using with LLM Agents (Skills)

Each skill file defines a reusable workflow for agents.

### Available Skills

| Skill | Location | When to Use |
|-------|----------|------------|
| **game-builder** | `skills/game-builder/SKILL.md` | Plan, build, debug any game feature |
| **gl-utils-reference** | `skills/gl-utils-reference/SKILL.md` | Rendering, shaders, buffers, collision |
| **png-bitmap-generator** | `skills/png-bitmap-generator/SKILL.md` | Create PNG sprites from JSON |
| **game-bundler** | `skills/game-bundler/SKILL.md` | Package and ship native game releases |

### Skill Routing for Agents

**Always read in this order:**
1. `skills/game-builder/SKILL.md` – first, for all game tasks
2. `skills/game-bundler/SKILL.md` – if packaging or shipping a game
3. `skills/gl-utils-reference/SKILL.md` – if rendering/collision is involved
4. `skills/png-bitmap-generator/SKILL.md` – if creating PNG assets

### Game Implementation Authorization

LLM agents only implement when the user explicitly uses **"build"** or **"building"** as a complete word in a direct instruction:

**Authorized:**
- "let's build the game"
- "begin building it"
- "let's build enemies that move"

**NOT authorized (stay in planning):**
- "make a player character"
- "create an enemy system"
- "implement collision"
- "let me build a game" (passive voice, not direct instruction)
- Mentioning or discussing "build" without instructing to build

Synonyms like "make," "create," "implement," "code," "start" do NOT authorize implementation.

---

## Using `gl_utils.py` (Rendering API)

See `skills/gl-utils-reference/SKILL.md` for complete API documentation.

### Three Entity Types

All entities are Python lists with fixed-length records:

**Rectangle (`"rect"`):** 10 elements
```python
[x, y, r, g, b, a, thickness, width, height, rotation]
```

**Point (`"point"`):** 7 elements
```python
[x, y, r, g, b, a, size]
```

**Textured Rectangle (`"tex"`):** 12 elements
```python
[x, y, r, g, b, a, thickness, width, height, rotation, tile_x, tile_y]
```

### Three-Step Sync Rule

Every GPU update follows this pattern:

```python
# 1. Mutate Python data
my_entities[idx][0] = new_x
my_entities[idx][1] = new_y

# 2. Repack to GPU format
gpu_instances = update_instances(idx, my_entities, gpu_instances)

# 3. Write to GPU buffer
vbo.write(gpu_instances[idx].tobytes(), offset=idx * stride)
```

Where `stride` is `rstride` (40 bytes), `pstride` (28 bytes), or `tstride` (48 bytes).

### Basic Example

```python
from gl_utils import (
    get_new_instances, to_gl, update_instances,
    build_rect_objs, check_collision, rstride
)

# Create instance arrays
rect_instances, _, _ = get_new_instances(5000, 0, 0)

# Define entities
all_rects = [
    [100, 100,  255, 255, 255, 255,  0.0,  32, 32, 0],
    [200, 200,  255, 0, 0, 255,       0.5,  32, 32, 0]
]

# Convert to GPU format
all_rects, rect_instances = to_gl(all_rects, rect_instances, 'rect')

# Build VAO/VBO
rect_vao, rvbo = build_rect_objs(ctx, program_rect, rect_instances)

# Modify and sync (three-step)
all_rects[0][0] = 150
rect_instances = update_instances(0, all_rects, rect_instances)
rvbo.write(rect_instances[0].tobytes(), offset=0 * rstride)

# Check collision
collisions = check_collision(all_rects[0], all_rects[1:], 'rect')
# Returns: [('rt', 0)]
```

---

## Using `png_generator.py` (PNG Assets)

See `skills/png-bitmap-generator/SKILL.md` for complete asset generation documentation.

### Create an Asset

Create `<project-root>/bitmap/my_sprite.json`:

```json
{
  "dim": [32, 32],
  "fill": [
    {"coord": [15, 15], "color": [1.0, 0.0, 0.0, 1.0]},
    {"coords": [[14, 16], [15, 16], [16, 16]], "color": [0.8, 0.2, 0.2, 1.0]},
    {"from": [10, 20], "to": [20, 22], "color": [1.0, 1.0, 0.0, 1.0]}
  ]
}
```

Generate the PNG from the toolkit root:

```bash
python3 png_generator.py --bitmap "<project-root>/bitmap/my_sprite.json" --output "<project-root>/assets/my_sprite.png"
```

**Schema Rules:**
- `dim`: `[width, height]`
- Coordinates: top-left origin, X→, Y↓
- Colors: 0.0–1.0 per channel (OpenGL format, not 0–255)
- `coord`: single pixel
- `coords`: array of pixels (same color)
- `from`/`to`: inclusive rectangle
- Later fills overwrite earlier ones
- Unfilled pixels are transparent

### Compact Format

```json
{
  "dim": "16x16",
  "fill": {
    "0,0": [1.0, 0.0, 0.0, 1.0],
    "1,0": [0.0, 1.0, 0.0, 1.0],
    "2,0": [0.0, 0.0, 1.0, 1.0]
  }
}
```

---

## Boilerplate Components

Bootstrap generates three reusable components in `<project-root>/`:

### GameState (Entity-ID System)

Scalable entity management with GPU instance synchronization.

```python
game_state = GameState(ctx, rect_cap=5000, point_cap=5000, tex_cap=5000)
rect_vao, rvbo = build_rect_objs(ctx, program_rect, game_state.instances['rect'])
game_state.set_vao_vbo('rect', rect_vao, rvbo)

# Spawn an entity
player_id = game_state.spawn('tex', 
    x=100, y=100,
    r=255, g=255, b=255, a=255,
    width=64, height=64, rotation=0,
    tile_x=0, tile_y=0
)

# Modify (syncs to GPU automatically)
game_state.modify(player_id, x=150, y=150, r=255, g=0, b=0)

# Get data
data = game_state.get_data(player_id)
print(data[0], data[1])  # x, y

# Check collision
collisions = game_state.get_colliding_entities(player_id, 'rect')
# Returns: [('rt', rect_id_1), ('rt', rect_id_2), ...]

# Destroy
game_state.destroy(player_id)

# Render all
game_state.render_all()
```

### InputHandler (Event Decoupler)

Converts pygame events to game intents.

```python
input_handler = InputHandler(game_state, player_id)

intents = input_handler.handle_events(mx, my)
# Returns: [('move_player', (x, y)), ('click_lmb', (mx, my)), ('quit', None), ...]

for action, data in intents:
    if action == 'move_player':
        px, py = data
        game_state.modify(player_id, x=px, y=py)
    elif action == 'click_lmb':
        mx, my = data
        # Handle click
    elif action == 'quit':
        running = False
```

### CollisionManager (Enter/Exit Tracking)

Automatic collision enter/exit detection with callbacks.

```python
collision_manager = CollisionManager(game_state)

def on_collision_enter(eid, collided_eid, ctype):
    print(f"Entity {eid} hit {collided_eid}")

def on_collision_exit(eid, collided_eid, ctype):
    print(f"Entity {eid} no longer touching {collided_eid}")

collision_manager.register_enter_callback(player_id, on_collision_enter)
collision_manager.register_exit_callback(player_id, on_collision_exit)

# Update collisions
collision_manager.update_all_collisions(player_id, ['rect', 'point'])

# Get entities under cursor
mouse_collisions = collision_manager.get_mouse_collisions(mx, my, 'rect')
# Returns: [rect_id_1, rect_id_2, ...]
```

---

## Workspace Boundaries

### What Goes in `<project-root>/`

- `main.py` – composition root, wires components together
- `game_state.py`, `input_handler.py`, `collision_manager.py` – boilerplate (adapt as needed)
- Additional game-specific modules (e.g., `enemies.py`, `physics.py`)
- `bitmap/` – PNG specifications (JSON)
- `assets/` – generated PNG files and metadata
- `.pygamekit-project` – project manifest (auto-generated, don't edit)

### What Stays at Toolkit Root

- `gl_utils.py` – shared rendering API (read-only)
- `png_generator.py` – shared asset generator (read-only)
- `bootstrap.py` – project manager
- `shaders/` – shared shader files (used by all projects via TOOLKIT_ROOT path)
- `skills/` – LLM skill documentation
- Other projects' directories (e.g., `MyGame/`, `OtherGame/`)

**Do NOT copy toolkit files into projects.** Agents must resolve `TOOLKIT_ROOT` and add it to `sys.path` for imports to work.

### Project Manifest (`.pygamekit-project`)

Auto-generated JSON file tracking project structure:

```json
{
  "tool": "PyGameKit",
  "schema_version": 1,
  "project_root": ".",
  "directories": ["shaders", "bitmap", "assets"],
  "files": {
    "code": ["game_state.py", "main.py"],
    "assets": ["assets/character.png"],
    "bitmaps": ["bitmap/player.json"],
    "other": []
  }
}
```

**Do not edit by hand.** Bootstrap refreshes it automatically. It's used by agents to understand project structure.

---

## Complete Game Loop Example

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

import pygame
import moderngl
from gl_utils import (
    load_program, set_viewport_size, build_rect_objs, 
    build_point_objs, build_tex_objs, load_texture
)
from game_state import GameState
from input_handler import InputHandler
from collision_manager import CollisionManager

pygame.init()
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)

WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
viewport_size = set_viewport_size(WIDTH, HEIGHT)

ctx = moderngl.create_context()
ctx.viewport = (0, 0, *viewport_size)
ctx.enable(moderngl.PROGRAM_POINT_SIZE)
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

print(f"GPU: {ctx.info['GL_RENDERER']}")

# Load shaders
program_rect = load_program(ctx, str(TOOLKIT_ROOT / "shaders" / "rect.vert"), 
                             str(TOOLKIT_ROOT / "shaders" / "rect.frag"))
program_tex = load_program(ctx, str(TOOLKIT_ROOT / "shaders" / "tex.vert"),
                            str(TOOLKIT_ROOT / "shaders" / "tex.frag"))

program_rect["u_viewport_size"] = viewport_size
program_tex["u_viewport_size"] = viewport_size

# Initialize game state
game_state = GameState(ctx)
rect_vao, rvbo = build_rect_objs(ctx, program_rect, game_state.instances['rect'])
tex_vao, tvbo = build_tex_objs(ctx, program_tex, game_state.instances['tex'])

game_state.set_vao_vbo('rect', rect_vao, rvbo)
game_state.set_vao_vbo('tex', tex_vao, tvbo)

# Load textures
atlas_texture = load_texture(ctx, str(PROJECT_ROOT / "assets" / "character.png"))
atlas_texture.use(location=0)
program_tex['u_texture'] = 0
program_tex["u_atlas_grid"] = (1.0, 1.0)

# Spawn entities
player_id = game_state.spawn('tex', x=400, y=300, r=255, g=255, b=255, a=255,
                             width=64, height=64, rotation=0, tile_x=0, tile_y=0)

rect1_id = game_state.spawn('rect', x=200, y=200, r=255, g=255, b=255, a=255,
                            thickness=0.08, width=30, height=30)

# Setup input and collision
input_handler = InputHandler(game_state, player_id)
collision_manager = CollisionManager(game_state)

def on_hit(eid, collided_eid, ctype):
    game_state.modify(collided_eid, r=255, g=0, b=255)

collision_manager.register_enter_callback(player_id, on_hit)

clock = pygame.time.Clock()
running = True

while running:
    mx, my = pygame.mouse.get_pos()
    intents = input_handler.handle_events(mx, my)
    
    for action, data in intents:
        if action == 'quit':
            running = False
        elif action == 'move_player':
            px, py = data
            game_state.modify(player_id, x=px, y=py)
            collision_manager.update_all_collisions(player_id, ['rect'])
    
    ctx.clear(0, 0, 0)
    game_state.render_all()
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```

---

## Troubleshooting

### "ModernGL context not created"
Call `pygame.display.gl_set_attribute()` **before** `set_mode()`.

### "ImportError: No module named 'gl_utils'"
Ensure `PROJECT_ROOT` and `TOOLKIT_ROOT` are resolved correctly in `main.py`, and `TOOLKIT_ROOT` is added to `sys.path`.

### "Exceeded capacity for rect entities"
Increase capacity when creating GameState:
```python
game_state = GameState(ctx, rect_cap=10000, point_cap=5000, tex_cap=5000)
```

### "PNG generated with wrong colors"
Colors must be 0.0–1.0 (OpenGL), not 0–255. Red = `[1.0, 0.0, 0.0, 1.0]`.

### "Multiple PyGameKit projects found"
Move inactive projects outside the toolkit root, or bootstrap will ask which to activate.

---

## Performance Notes

- **Instance rendering:** Scales to thousands of entities per type
- **Collision detection:** Uses Separating Axis Theorem (SAT) — O(n²) worst case
- **GPU buffer writes:** Single-entity updates via `offset=` are cheap
- **Swap-and-pop deletion:** Prevents slot fragmentation
- **For 10k+ entities:** Consider batching collision checks or spatial partitioning

---

## License

This project is provided as-is for educational and personal use.
