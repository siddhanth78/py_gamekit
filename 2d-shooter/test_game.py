import sys
from pathlib import Path
import unittest

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from collision_manager import CollisionManager  # noqa: E402
from config import ARENA_BOUNDS  # noqa: E402
from game import ArenaGame  # noqa: E402


class FakeState:
    def __init__(self):
        names = (
            "environment", "actors", "effects", "projectiles",
            "ui_overlay", "upgrade_icons", "ui_text",
        )
        self.batches = {name: {} for name in names}
        self.entities = {}
        self.next_id = 0

    def spawn(self, batch, **values):
        entity_id = self.next_id
        self.next_id += 1
        self.entities[entity_id] = {"batch": batch, **values}
        return entity_id

    def modify(self, entity_id, **values):
        if entity_id in self.entities:
            self.entities[entity_id].update(values)

    def destroy(self, entity_id):
        self.entities.pop(entity_id, None)

    def clear_batch(self, batch):
        for entity_id in [key for key, value in self.entities.items() if value["batch"] == batch]:
            self.destroy(entity_id)


class FakeFont:
    def __init__(self):
        self.groups = {}
        self.signatures = {}

    def set_text(self, key, *args, **kwargs):
        self.groups[key] = []

    def clear(self, key):
        self.groups.pop(key, None)


class ArenaTests(unittest.TestCase):
    def setUp(self):
        self.state = FakeState()
        self.game = ArenaGame(self.state, CollisionManager(), FakeFont(), seed=7)

    def test_clamp_keeps_full_player_inside_arena(self):
        x, y = self.game.collision.clamp_center(-500, 900, 20, 20, ARENA_BOUNDS)
        self.assertEqual((x, y), (52, 588))

    def test_enemy_spawns_on_an_arena_boundary(self):
        self.game._spawn_enemy()
        enemy = next(iter(self.game.enemies.values()))
        left, top, right, bottom = ARENA_BOUNDS
        half = enemy.size / 2
        on_edge = (
            enemy.x in (left + half, right - half)
            or enemy.y in (top + half, bottom - half)
        )
        self.assertTrue(on_edge)

    def test_upgrades_apply_and_advance_wave(self):
        previous_cooldown = self.game.stats.fire_cooldown
        self.game._apply_upgrade("RAPID FIRE")
        self.assertLess(self.game.stats.fire_cooldown, previous_cooldown)
        self.assertEqual(self.game.wave, 2)

    def test_atlas_dimensions(self):
        expected = {
            "actors-24.png": (192, 24),
            "effects-8.png": (64, 8),
            "environment-32.png": (128, 32),
            "ui-16.png": (128, 16),
        }
        for filename, dimensions in expected.items():
            with Image.open(PROJECT_ROOT / "assets" / filename) as image:
                self.assertEqual(image.size, dimensions)
                self.assertEqual(image.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
