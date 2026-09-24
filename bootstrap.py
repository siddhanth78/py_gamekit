#!/usr/bin/env python3
"""Create or discover an isolated PyGameKit project workspace.

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
Each entity type (rect, point, tex) maps to a slot in the corresponding GPU buffer.
"""

import numpy as np
from gl_utils import (
    to_gl, update_instances, get_new_instances, rstride, pstride, tstride
)


class GameState:
    """Manages entities, GPU buffers, VAOs, and VBOs."""
    
    def __init__(self, ctx, rect_cap=5000, point_cap=5000, tex_cap=5000):
        """
        Initialize game state with buffer capacity and GPU context.
        
        Args:
            ctx: ModernGL context
            rect_cap: Max rect entities
            point_cap: Max point entities
            tex_cap: Max textured rect entities
        """
        self.ctx = ctx
        self.entity_counter = 0
        
        # Entity registry: id -> {type, slot, data}
        self.entities = {}
        
        # Free slot tracking per type
        self.free_slots = {
            'rect': [],
            'point': [],
            'tex': []
        }
        
        # GPU capacity
        self.capacity = {
            'rect': rect_cap,
            'point': point_cap,
            'tex': tex_cap
        }
        
        # Entity lists (indexed by slot, not by ID)
        self.data = {
            'rect': [],
            'point': [],
            'tex': []
        }
        
        # GPU instances (numpy arrays)
        self.instances = {}
        self.instances['rect'], self.instances['point'], self.instances['tex'] = \\
            get_new_instances(rect_cap, point_cap, tex_cap)
        
        # VAOs and VBOs (set later after program setup)
        self.vao = {}
        self.vbo = {}
    
    def set_vao_vbo(self, entity_type, vao, vbo):
        """Attach VAO and VBO after GPU program setup."""
        self.vao[entity_type] = vao
        self.vbo[entity_type] = vbo
    
    def _allocate_slot(self, entity_type):
        """Get the next available slot for an entity type."""
        if self.free_slots[entity_type]:
            return self.free_slots[entity_type].pop()
        slot = len(self.data[entity_type])
        if slot >= self.capacity[entity_type]:
            raise RuntimeError(f"Exceeded capacity for {entity_type} entities")
        self.data[entity_type].append(None)
        return slot
    
    def _free_slot(self, entity_type, slot):
        """Mark a slot as available for reuse."""
        self.free_slots[entity_type].append(slot)
    
    def spawn(self, entity_type, **kwargs):
        """
        Create a new entity.
        
        Args:
            entity_type: 'rect', 'point', or 'tex'
            **kwargs: Entity data (x, y, r, g, b, a, size/width/height, etc.)
        
        Returns:
            Entity ID
        """
        if entity_type not in self.capacity:
            raise ValueError(f"Unknown entity type: {entity_type}")
        
        entity_id = self.entity_counter
        self.entity_counter += 1
        
        slot = self._allocate_slot(entity_type)
        
        # Construct data record from kwargs
        if entity_type == 'rect':
            # [x, y, r, g, b, a, thickness, width, height, rotation]
            record = [
                kwargs.get('x', 0),
                kwargs.get('y', 0),
                kwargs.get('r', 255),
                kwargs.get('g', 255),
                kwargs.get('b', 255),
                kwargs.get('a', 255),
                kwargs.get('thickness', 0.0),
                kwargs.get('width', 32),
                kwargs.get('height', 32),
                kwargs.get('rotation', 0)
            ]
        elif entity_type == 'point':
            # [x, y, r, g, b, a, size]
            record = [
                kwargs.get('x', 0),
                kwargs.get('y', 0),
                kwargs.get('r', 255),
                kwargs.get('g', 255),
                kwargs.get('b', 255),
                kwargs.get('a', 255),
                kwargs.get('size', 10)
            ]
        elif entity_type == 'tex':
            # [x, y, r, g, b, a, thickness, width, height, rotation, tile_x, tile_y]
            record = [
                kwargs.get('x', 0),
                kwargs.get('y', 0),
                kwargs.get('r', 255),
                kwargs.get('g', 255),
                kwargs.get('b', 255),
                kwargs.get('a', 255),
                kwargs.get('thickness', 0.0),
                kwargs.get('width', 32),
                kwargs.get('height', 32),
                kwargs.get('rotation', 0),
                kwargs.get('tile_x', 0),
                kwargs.get('tile_y', 0)
            ]
        
        self.data[entity_type][slot] = record
        self._sync_to_gpu(entity_type, slot)
        
        self.entities[entity_id] = {
            'type': entity_type,
            'slot': slot,
            'active': True
        }
        
        return entity_id
    
    def destroy(self, entity_id):
        """Remove an entity and mark its slot for reuse."""
        if entity_id not in self.entities:
            return
        
        meta = self.entities[entity_id]
        entity_type = meta['type']
        slot = meta['slot']
        
        # Swap with last and pop
        last_slot = len(self.data[entity_type]) - 1
        if slot != last_slot:
            self.data[entity_type][slot] = self.data[entity_type][last_slot]
            self.instances[entity_type][slot] = self.instances[entity_type][last_slot]
            
            # Find entity at last_slot and update its slot reference
            for eid, emeta in self.entities.items():
                if emeta['type'] == entity_type and emeta['slot'] == last_slot:
                    emeta['slot'] = slot
                    break
            
            self._sync_to_gpu(entity_type, slot)
        
        self.data[entity_type].pop()
        self._free_slot(entity_type, last_slot)
        del self.entities[entity_id]
    
    def get(self, entity_id):
        """Get entity metadata."""
        return self.entities.get(entity_id)
    
    def get_data(self, entity_id):
        """Get entity data record (modifiable)."""
        if entity_id not in self.entities:
            return None
        meta = self.entities[entity_id]
        return self.data[meta['type']][meta['slot']]
    
    def _sync_to_gpu(self, entity_type, slot):
        """Update GPU buffer for a single entity slot (three-step sync)."""
        # Step 1: Data already mutated in Python
        # Step 2: Re-pack to GPU format
        self.instances[entity_type] = update_instances(
            slot, self.data[entity_type], self.instances[entity_type]
        )
        # Step 3: Write to GPU
        stride = {'rect': rstride, 'point': pstride, 'tex': tstride}[entity_type]
        self.vbo[entity_type].write(
            self.instances[entity_type][slot].tobytes(),
            offset=slot * stride
        )
    
    def modify(self, entity_id, **kwargs):
        """
        Modify entity properties and sync to GPU.
        
        Args:
            entity_id: Entity to modify
            **kwargs: Properties to change (x, y, r, g, b, a, size/width/height, rotation, etc.)
        """
        meta = self.get(entity_id)
        if not meta:
            return
        
        entity_type = meta['type']
        slot = meta['slot']
        record = self.data[entity_type][slot]
        
        # Update fields by name
        field_map = {
            'rect': {'x': 0, 'y': 1, 'r': 2, 'g': 3, 'b': 4, 'a': 5, 'thickness': 6, 'width': 7, 'height': 8, 'rotation': 9},
            'point': {'x': 0, 'y': 1, 'r': 2, 'g': 3, 'b': 4, 'a': 5, 'size': 6},
            'tex': {'x': 0, 'y': 1, 'r': 2, 'g': 3, 'b': 4, 'a': 5, 'thickness': 6, 'width': 7, 'height': 8, 'rotation': 9, 'tile_x': 10, 'tile_y': 11}
        }
        
        fields = field_map[entity_type]
        for key, value in kwargs.items():
            if key in fields:
                record[fields[key]] = value
        
        self._sync_to_gpu(entity_type, slot)
    
    def render_all(self):
        """Render all active entities."""
        import moderngl
        for entity_type in ['rect', 'point', 'tex']:
            if not self.data[entity_type]:
                continue
            count = len(self.data[entity_type])
            if entity_type == 'point':
                self.vao[entity_type].render(moderngl.POINTS, vertices=1, instances=count)
            else:
                self.vao[entity_type].render(moderngl.TRIANGLES, instances=count)
    
    def get_entities_by_type(self, entity_type):
        """Get all entity IDs of a given type."""
        return [eid for eid, meta in self.entities.items() if meta['type'] == entity_type]
    
    def get_colliding_entities(self, entity_id, check_against_type):
        """
        Check collision between one entity and all entities of a type.
        
        Args:
            entity_id: Entity to check from
            check_against_type: 'rect', 'point', or 'tex'
        
        Returns:
            List of (type_tag, entity_id) tuples of colliding entities
        """
        from gl_utils import check_collision
        
        source_meta = self.get(entity_id)
        if not source_meta:
            return []
        
        source_type = source_meta['type']
        source_slot = source_meta['slot']
        source_record = self.data[source_type][source_slot]
        
        target_records = self.data[check_against_type]
        if not target_records:
            return []
        
        # Use gl_utils collision check
        collisions = check_collision(source_record, target_records, check_against_type)
        
        # Map slot indices back to entity IDs
        slot_to_id = {}
        for eid, meta in self.entities.items():
            if meta['type'] == check_against_type:
                slot_to_id[meta['slot']] = eid
        
        return [(tag, slot_to_id[slot]) for tag, slot in collisions]
''',

    'input_handler.py': '''"""
InputHandler: Decouples keyboard and mouse events from game logic.

Returns intent tuples (action, data) that the game loop processes.
"""

import pygame


class InputHandler:
    """Processes pygame events and returns game intents."""
    
    def __init__(self, game_state, player_entity_id):
        """
        Args:
            game_state: GameState instance
            player_entity_id: Entity ID of the player (for movement)
        """
        self.game_state = game_state
        self.player_id = player_entity_id
        self.speed = 10
        self.keys_held = set()
        
        # Movement mapping
        self.move_keys = {
            pygame.K_w: (0, -1),   # Up
            pygame.K_s: (0, 1),    # Down
            pygame.K_a: (-1, 0),   # Left
            pygame.K_d: (1, 0)     # Right
        }
    
    def handle_events(self, mx, my):
        """
        Process all pending events.
        
        Returns:
            List of (action, data) tuples:
                ('quit', None)
                ('move_player', (new_x, new_y))
                ('click_rect', (x, y))
                ('click_point', (x, y))
                ('delete_point', (x, y))
        """
        intents = []
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                intents.append(('quit', None))
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    intents.append(('quit', None))
                elif event.key in self.move_keys:
                    self.keys_held.add(event.key)
            
            elif event.type == pygame.KEYUP:
                if event.key in self.move_keys:
                    self.keys_held.discard(event.key)
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    intents.append(('click_lmb', (mx, my)))
                elif event.button == 3:  # Right click
                    intents.append(('click_rmb', (mx, my)))
        
        # Handle held keys (movement)
        if self.keys_held:
            player_data = self.game_state.get_data(self.player_id)
            if player_data:
                px, py = player_data[0], player_data[1]
                
                # Apply all held directions
                for key in self.keys_held:
                    dx, dy = self.move_keys[key]
                    px += dx * self.speed
                    py += dy * self.speed
                
                # Clamp to bounds
                px = max(32, min(800 - 32, px))
                py = max(32, min(600 - 32, py))
                
                intents.append(('move_player', (px, py)))
        
        return intents
    
    def set_speed(self, speed):
        """Update player movement speed."""
        self.speed = speed
    
    def set_player(self, player_entity_id):
        """Switch which entity is controlled by WASD."""
        self.player_id = player_entity_id
''',

    'collision_manager.py': '''"""
CollisionManager: Tracks collision enter/exit events using set diffing.

Maintains previous and current collision sets, emits enter/exit callbacks.
"""

from gl_utils import check_collision, check_mouse_collisions


class CollisionManager:
    """Manages collision detection and tracks state changes."""
    
    def __init__(self, game_state):
        """
        Args:
            game_state: GameState instance
        """
        self.game_state = game_state
        
        # Track collision state per entity
        # entity_id -> set of (type_tag, entity_id) tuples colliding with it
        self.current_collisions = {}
        self.previous_collisions = {}
        
        # Callbacks
        self.on_collision_enter = {}  # entity_id -> callable
        self.on_collision_exit = {}   # entity_id -> callable
    
    def register_enter_callback(self, entity_id, callback):
        """
        Register a callback when entity collides.
        
        callback(entity_id, collided_entity_id, collision_type)
        """
        self.on_collision_enter[entity_id] = callback
    
    def register_exit_callback(self, entity_id, callback):
        """
        Register a callback when entity stops colliding.
        
        callback(entity_id, collided_entity_id, collision_type)
        """
        self.on_collision_exit[entity_id] = callback
    
    def update(self, entity_id, check_against_type):
        """
        Update collision state for one entity.
        
        Args:
            entity_id: Entity to check collisions for
            check_against_type: 'rect', 'point', or 'tex'
        """
        if entity_id not in self.current_collisions:
            self.current_collisions[entity_id] = set()
            self.previous_collisions[entity_id] = set()
        
        # Get current collisions
        collisions = self.game_state.get_colliding_entities(entity_id, check_against_type)
        self.current_collisions[entity_id] = set(collisions)
        
        # Detect enter events
        for type_tag, collided_id in self.current_collisions[entity_id] - self.previous_collisions[entity_id]:
            if entity_id in self.on_collision_enter:
                self.on_collision_enter[entity_id](entity_id, collided_id, type_tag)
        
        # Detect exit events
        for type_tag, collided_id in self.previous_collisions[entity_id] - self.current_collisions[entity_id]:
            if entity_id in self.on_collision_exit:
                self.on_collision_exit[entity_id](entity_id, collided_id, type_tag)
        
        self.previous_collisions[entity_id] = self.current_collisions[entity_id].copy()
    
    def update_all_collisions(self, entity_id, types_to_check):
        """
        Check collisions against multiple entity types.
        
        Args:
            entity_id: Entity to check
            types_to_check: List of entity types ('rect', 'point', 'tex')
        """
        for entity_type in types_to_check:
            self.update(entity_id, entity_type)
    
    def get_mouse_collisions(self, mx, my, check_against_type):
        """
        Get entity IDs under the mouse cursor.
        
        Args:
            mx, my: Mouse coordinates
            check_against_type: 'rect', 'point', or 'tex'
        
        Returns:
            List of entity IDs under cursor
        """
        records = self.game_state.data[check_against_type]
        if not records:
            return []
        
        collided_slots = check_mouse_collisions(mx, my, records, check_against_type)
        
        # Map slots back to entity IDs
        slot_to_id = {}
        for eid, meta in self.game_state.entities.items():
            if meta['type'] == check_against_type:
                slot_to_id[meta['slot']] = eid
        
        return [slot_to_id[slot] for slot in collided_slots if slot in slot_to_id]
    
    def clear(self):
        """Reset all collision tracking."""
        self.current_collisions.clear()
        self.previous_collisions.clear()
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
            "Multiple PyGameKit projects were found. Move inactive projects "
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
        "tool": "PyGameKit",
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
        description="PyGameKit project directory management",
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
            print("No PyGameKit project directories found.")
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