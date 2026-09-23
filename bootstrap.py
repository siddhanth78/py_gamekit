#!/usr/bin/env python3
"""Create an isolated workspace for the next game project.

The shared rendering and PNG tools stay beside this script. Game-specific code,
bitmap specifications, and generated assets live under ``New Project/``.
Existing project files are never overwritten.
"""

from pathlib import Path


PROJECT_DIRECTORY = "New Project"
PROJECT_DIRECTORIES = ("assets", "bitmap")

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

def bootstrap():
    """Create the project folder, asset folders, and missing boilerplate."""
    toolkit_root = Path(__file__).resolve().parent
    project_root = toolkit_root / PROJECT_DIRECTORY
    created = []
    skipped = []

    if project_root.exists():
        skipped.append(f"{PROJECT_DIRECTORY}/")
    else:
        project_root.mkdir()
        created.append(f"{PROJECT_DIRECTORY}/")

    for directory in PROJECT_DIRECTORIES:
        directory_path = project_root / directory
        relative_path = f"{PROJECT_DIRECTORY}/{directory}/"
        if directory_path.exists():
            skipped.append(relative_path)
        else:
            directory_path.mkdir()
            created.append(relative_path)
    
    for filename, content in BOILERPLATE_FILES.items():
        filepath = project_root / filename
        relative_path = f"{PROJECT_DIRECTORY}/{filename}"
        
        if filepath.exists():
            skipped.append(relative_path)
        else:
            filepath.write_text(content, encoding="utf-8")
            created.append(relative_path)
    
    # Print results
    print("=" * 60)
    print("BOOTSTRAP COMPLETE")
    print("=" * 60)
    print(f"\nProject workspace: {project_root}")
    
    if created:
        print(f"\n✓ Created {len(created)} item(s):")
        for fname in created:
            print(f"  - {fname}")
    
    if skipped:
        print(f"\n⊘ Skipped {len(skipped)} item(s) (already exist):")
        for fname in skipped:
            print(f"  - {fname}")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    bootstrap()
