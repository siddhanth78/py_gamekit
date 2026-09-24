#!/usr/bin/env python3
"""Create or discover an isolated PygameKit project workspace.

The shared rendering and PNG tools stay beside this script. Game-specific code,
bitmap specifications, and generated assets live in the directory marked by
``.pygamekit-project``. Existing project files are never overwritten.

Usage:
  python3 bootstrap.py --new              # Create a new project (interactive)
  python3 bootstrap.py --scan             # List all existing .pygamekit-project dirs
  python3 bootstrap.py --exists <name>    # Check if a project exists
  python3 bootstrap.py                    # Default: discover or create (interactive)
"""

import argparse
import json
import sys
from pathlib import Path


DEFAULT_PROJECT_DIRECTORY = "New Project"
PROJECT_DIRECTORIES = ("assets", "bitmap")
PROJECT_MARKER = ".pygamekit-project"
IGNORED_DIRECTORIES = {
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "venv",
}
IGNORED_FILES = {PROJECT_MARKER, ".DS_Store"}
CODE_SUFFIXES = {".py", ".vert", ".frag", ".glsl", ".wgsl"}

BOILERPLATE_FILES = {
    'game_state.py': '''"""
GameState: Entity-ID-based component storage for GPU-instanced rendering.

Entities are stored by ID with type tags and component data.
Refer to gl-utils-reference/SKILL.md for data layout and GPU sync details.
"""

from gl_utils import get_new_instances, update_instances, rstride, pstride, tstride


class GameState:
    """Manages entities, GPU buffers, VAOs, and VBOs."""
    
    def __init__(self, ctx, rect_cap=5000, point_cap=5000, tex_cap=5000):
        """
        Initialize game state.
        
        Args:
            ctx: ModernGL context
            rect_cap, point_cap, tex_cap: Max entities per type
        """
        self.ctx = ctx
        self.entity_counter = 0
        self.entities = {}  # id -> {type, slot}
        self.data = {'rect': [], 'point': [], 'tex': []}
        self.instances = {}
        self.vao = {}
        self.vbo = {}
        self.free_slots = {'rect': [], 'point': [], 'tex': []}
        self.capacity = {'rect': rect_cap, 'point': point_cap, 'tex': tex_cap}
        
        # Allocate GPU memory
        self.instances['rect'], self.instances['point'], self.instances['tex'] = \\
            get_new_instances(rect_cap, point_cap, tex_cap)
    
    def set_vao_vbo(self, entity_type, vao, vbo):
        """Attach VAO and VBO after GPU program setup."""
        self.vao[entity_type] = vao
        self.vbo[entity_type] = vbo
    
    def _allocate_slot(self, entity_type):
        """Get next available slot for entity type."""
        if self.free_slots[entity_type]:
            return self.free_slots[entity_type].pop()
        slot = len(self.data[entity_type])
        if slot >= self.capacity[entity_type]:
            raise RuntimeError(f"Exceeded capacity for {entity_type}")
        self.data[entity_type].append(None)
        return slot
    
    def _free_slot(self, entity_type, slot):
        """Mark slot as available for reuse."""
        self.free_slots[entity_type].append(slot)
    
    def _sync_to_gpu(self, entity_type, slot):
        """Sync entity data to GPU (three-step: mutate, re-pack, write)."""
        self.instances[entity_type] = update_instances(
            slot, self.data[entity_type], self.instances[entity_type]
        )
        stride = {'rect': rstride, 'point': pstride, 'tex': tstride}[entity_type]
        self.vbo[entity_type].write(
            self.instances[entity_type][slot].tobytes(),
            offset=slot * stride
        )
    
    def spawn(self, entity_type, **kwargs):
        """
        Create entity. Data layout depends on type:
        - rect: [x, y, r, g, b, a, thickness, width, height, rotation]
        - point: [x, y, r, g, b, a, size]
        - tex: [x, y, r, g, b, a, thickness, width, height, rotation, tile_x, tile_y]
        """
        if entity_type not in self.capacity:
            raise ValueError(f"Unknown type: {entity_type}")
        
        entity_id = self.entity_counter
        self.entity_counter += 1
        slot = self._allocate_slot(entity_type)
        
        # TODO: Fill record with kwargs, see data layout above
        record = []  # Build record list matching layout for entity_type
        
        self.data[entity_type][slot] = record
        self._sync_to_gpu(entity_type, slot)
        self.entities[entity_id] = {'type': entity_type, 'slot': slot}
        
        return entity_id
    
    def destroy(self, entity_id):
        """Remove entity and free its slot."""
        if entity_id not in self.entities:
            return
        
        meta = self.entities[entity_id]
        entity_type = meta['type']
        slot = meta['slot']
        
        # Swap with last, pop
        last_slot = len(self.data[entity_type]) - 1
        if slot != last_slot:
            self.data[entity_type][slot] = self.data[entity_type][last_slot]
            self.instances[entity_type][slot] = self.instances[entity_type][last_slot]
            for eid, m in self.entities.items():
                if m['type'] == entity_type and m['slot'] == last_slot:
                    m['slot'] = slot
                    break
            self._sync_to_gpu(entity_type, slot)
        
        self.data[entity_type].pop()
        self._free_slot(entity_type, last_slot)
        del self.entities[entity_id]
    
    def get(self, entity_id):
        """Get entity metadata."""
        return self.entities.get(entity_id)
    
    def get_data(self, entity_id):
        """Get entity data record (mutable)."""
        if entity_id not in self.entities:
            return None
        meta = self.entities[entity_id]
        return self.data[meta['type']][meta['slot']]
    
    def modify(self, entity_id, **kwargs):
        """Modify entity properties by name and sync to GPU."""
        meta = self.get(entity_id)
        if not meta:
            return
        
        entity_type = meta['type']
        slot = meta['slot']
        record = self.data[entity_type][slot]
        
        # TODO: Map kwargs to record indices based on entity_type layout
        # Then sync to GPU
        self._sync_to_gpu(entity_type, slot)
    
    def render_all(self):
        """Render all entities."""
        import moderngl
        for entity_type in ['rect', 'point', 'tex']:
            if not self.data[entity_type]:
                continue
            count = len(self.data[entity_type])
            mode = moderngl.POINTS if entity_type == 'point' else moderngl.TRIANGLES
            self.vao[entity_type].render(mode, vertices=1 if entity_type == 'point' else 0, instances=count)
''',

    'input_handler.py': '''"""
InputHandler: Decouples pygame events from game logic.

Converts events into intent tuples (action, data) for the game loop.
"""

import pygame


class InputHandler:
    """Processes pygame events and returns game intents."""
    
    def __init__(self, game_state=None):
        """
        Args:
            game_state: GameState instance (optional, for state-aware intents)
        """
        self.game_state = game_state
        self.keys_held = set()
    
    def handle_events(self, mx, my):
        """
        Process pending pygame events.
        
        Returns:
            List of (action, data) tuples. Examples:
            - ('quit', None)
            - ('key_down', key)
            - ('key_up', key)
            - ('mouse_down', (button, mx, my))
            - ('mouse_up', (button, mx, my))
            - ('mouse_motion', (mx, my))
        """
        intents = []
        
        # TODO: Process pygame.event.get()
        # Common patterns:
        # - pygame.QUIT -> ('quit', None)
        # - pygame.KEYDOWN/KEYUP -> track in self.keys_held
        # - pygame.MOUSEBUTTONDOWN/UP -> click intents
        # - pygame.MOUSEMOTION -> mouse position
        
        return intents
    
    def get_held_keys(self):
        """Return set of keys currently held down."""
        return self.keys_held.copy()
''',

    'collision_manager.py': '''"""
CollisionManager: Collision detection and state tracking.

Detects enter/exit events by diffing collision sets.
Use gl_utils.check_collision and check_mouse_collisions for collision checks.
"""

from gl_utils import check_collision, check_mouse_collisions


class CollisionManager:
    """Manages collision detection and enter/exit callbacks."""
    
    def __init__(self, game_state):
        """
        Args:
            game_state: GameState instance
        """
        self.game_state = game_state
        self.current_collisions = {}   # entity_id -> set of colliding entities
        self.previous_collisions = {}  # track changes frame-to-frame
        self.on_collision_enter = {}   # entity_id -> callback
        self.on_collision_exit = {}    # entity_id -> callback
    
    def register_enter_callback(self, entity_id, callback):
        """Register callback(entity_id, collided_id, type_tag) on collision entry."""
        self.on_collision_enter[entity_id] = callback
    
    def register_exit_callback(self, entity_id, callback):
        """Register callback(entity_id, collided_id, type_tag) on collision exit."""
        self.on_collision_exit[entity_id] = callback
    
    def update(self, entity_id, check_against_type):
        """
        Update collision state for entity against one type.
        
        Compares previous vs current collisions, fires callbacks.
        """
        if entity_id not in self.current_collisions:
            self.current_collisions[entity_id] = set()
            self.previous_collisions[entity_id] = set()
        
        # TODO: Call gl_utils.check_collision or get_colliding_entities
        # Set self.current_collisions[entity_id] = set(result)
        
        # Fire enter/exit callbacks by set diffing
        # TODO: Implement callback logic
        
        self.previous_collisions[entity_id] = self.current_collisions[entity_id].copy()
    
    def get_mouse_collisions(self, mx, my, check_against_type):
        """Get entity IDs under mouse cursor using gl_utils.check_mouse_collisions."""
        records = self.game_state.data[check_against_type]
        if not records:
            return []
        
        # TODO: Call check_mouse_collisions, map slots back to entity IDs
        return []
'''
}

def find_all_projects(toolkit_root):
    """Find all directories marked with PROJECT_MARKER."""
    marked_projects = sorted(
        marker.parent
        for marker in toolkit_root.glob(f"*/{PROJECT_MARKER}")
        if marker.is_file()
    )
    return marked_projects


def find_project_root(toolkit_root):
    """Find the active project, or select from multiple, or return default."""
    marked_projects = find_all_projects(toolkit_root)

    if len(marked_projects) > 1:
        choices = "\n".join(f"  - {path}" for path in marked_projects)
        raise SystemExit(
            "Multiple PygameKit projects were found. Move inactive projects "
            f"outside the toolkit root or ask the user which one to use:\n{choices}"
        )
    if marked_projects:
        return marked_projects[0]
    return toolkit_root / DEFAULT_PROJECT_DIRECTORY


def get_project_inventory(project_root):
    directories = []
    files = {
        "code": [],
        "assets": [],
        "bitmaps": [],
        "other": [],
    }

    for path in sorted(project_root.rglob('*')):
        relative = path.relative_to(project_root)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue

        relative_path = relative.as_posix()
        if path.is_dir():
            directories.append(relative_path)
            continue
        if path.name in IGNORED_FILES or path.suffix == '.pyc':
            continue

        if relative.parts[0] == 'assets':
            files['assets'].append(relative_path)
        elif relative.parts[0] == 'bitmap':
            files['bitmaps'].append(relative_path)
        elif path.suffix.lower() in CODE_SUFFIXES:
            files['code'].append(relative_path)
        else:
            files['other'].append(relative_path)

    return directories, files


def update_project_marker(project_root):
    directories, files = get_project_inventory(project_root)
    manifest = {
        "tool": "PygameKit",
        "schema_version": 1,
        "project_root": ".",
        "directories": directories,
        "files": files,
    }
    marker_path = project_root / PROJECT_MARKER
    content = json.dumps(manifest, indent=2) + '\n'

    if marker_path.exists() and marker_path.read_text(encoding='utf-8') == content:
        return "unchanged"
    status = "updated" if marker_path.exists() else "created"
    marker_path.write_text(content, encoding='utf-8')
    return status


def bootstrap(toolkit_root=None, project_name=None):
    """Discover or create the active project and refresh its inventory."""
    if toolkit_root is None:
        toolkit_root = Path(__file__).resolve().parent
    else:
        toolkit_root = Path(toolkit_root).resolve()
    
    # If a project name is specified, use it; otherwise discover
    if project_name:
        project_root = toolkit_root / project_name
    else:
        project_root = find_project_root(toolkit_root)
    
    created = []
    skipped = []

    if project_root.exists():
        skipped.append(f"{project_root.name}/")
    else:
        project_root.mkdir()
        created.append(f"{project_root.name}/")

    for directory in PROJECT_DIRECTORIES:
        directory_path = project_root / directory
        relative_path = f"{project_root.name}/{directory}/"
        if directory_path.exists():
            skipped.append(relative_path)
        else:
            directory_path.mkdir()
            created.append(relative_path)
    
    for filename, content in BOILERPLATE_FILES.items():
        filepath = project_root / filename
        relative_path = f"{project_root.name}/{filename}"
        
        if filepath.exists():
            skipped.append(relative_path)
        else:
            filepath.write_text(content, encoding="utf-8")
            created.append(relative_path)

    marker_status = update_project_marker(project_root)
    
    # Print results
    print("=" * 60)
    print("PYGAMEKIT BOOTSTRAP COMPLETE")
    print("=" * 60)
    print(f"\nProject workspace: {project_root}")
    print(f"Project marker: {project_root / PROJECT_MARKER} ({marker_status})")
    
    if created:
        print(f"\n✓ Created {len(created)} item(s):")
        for fname in created:
            print(f"  - {fname}")
    
    if skipped:
        print(f"\n⊘ Skipped {len(skipped)} item(s) (already exist):")
        for fname in skipped:
            print(f"  - {fname}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="PygameKit project directory management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 bootstrap.py --new              # Create a new project directory
  python3 bootstrap.py --scan             # List all existing project directories
  python3 bootstrap.py --exists MyGame    # Check if 'MyGame' directory exists
  python3 bootstrap.py                    # Default: discover or create
        """
    )
    
    parser.add_argument(
        '--new',
        action='store_true',
        help='Create a new project directory with interactive prompts'
    )
    parser.add_argument(
        '--scan',
        action='store_true',
        help='List all existing project directories (marked with .pygamekit-project)'
    )
    parser.add_argument(
        '--exists',
        metavar='NAME',
        help='Check if a project directory exists by name'
    )
    parser.add_argument(
        '--toolkit-root',
        default=None,
        help='Toolkit root directory (default: script directory)'
    )
    
    args = parser.parse_args()
    toolkit_root = Path(args.toolkit_root) if args.toolkit_root else Path(__file__).resolve().parent
    
    # Handle --scan
    if args.scan:
        projects = find_all_projects(toolkit_root)
        if not projects:
            print("No PygameKit project directories found.")
            return
        
        print("=" * 60)
        print("PYGAMEKIT PROJECT DIRECTORIES")
        print("=" * 60)
        for i, proj in enumerate(projects, 1):
            marker_path = proj / PROJECT_MARKER
            status = ""
            try:
                manifest = json.loads(marker_path.read_text(encoding='utf-8'))
                file_count = sum(len(v) for v in manifest.get('files', {}).values())
                status = f" ({file_count} files)"
            except Exception:
                pass
            print(f"{i}. {proj.name}{status}")
        print("=" * 60)
        return
    
    # Handle --exists
    if args.exists:
        projects = find_all_projects(toolkit_root)
        project_names = {p.name for p in projects}
        
        if args.exists in project_names:
            matching_project = next(p for p in projects if p.name == args.exists)
            print(f"✓ Project directory '{args.exists}' exists at: {matching_project}")
            sys.exit(0)
        else:
            print(f"✗ Project directory '{args.exists}' does not exist")
            if project_names:
                print(f"Available project directories: {', '.join(sorted(project_names))}")
            sys.exit(1)
    
    # Handle --new
    if args.new:
        project_name = input("Enter project directory name (default: 'New Project'): ").strip()
        if not project_name:
            project_name = DEFAULT_PROJECT_DIRECTORY
        
        project_path = toolkit_root / project_name
        if project_path.exists():
            print(f"✗ Project directory '{project_name}' already exists at {project_path}")
            sys.exit(1)
        
        print(f"Creating new project directory: {project_name}")
        bootstrap(toolkit_root, project_name)
        return
    
    # Default behavior: discover or create
    bootstrap(toolkit_root)


if __name__ == '__main__':
    main()