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
from game import (  # noqa: E402
    ArenaGame,
    MAX_PLAYER_HEALTH,
    MAX_PLAYER_MOVE_SPEED,
    MAX_PLAYER_PROJECTILES,
    MAX_PLAYER_SHIELDS,
)


class FakeState:
    def __init__(self):
        names = (
            "environment", "actors", "late_enemies", "effects",
            "area_effects", "projectiles",
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

    def test_player_upgrade_caps_are_enforced(self):
        self.game.stats.max_health = MAX_PLAYER_HEALTH - 5
        self.game.stats.health = MAX_PLAYER_HEALTH - 5
        self.game.stats.shield_max = MAX_PLAYER_SHIELDS - 1
        self.game.stats.projectiles = MAX_PLAYER_PROJECTILES - 1
        self.game.stats.move_speed = MAX_PLAYER_MOVE_SPEED - 5

        for upgrade in (
            "ARMOR PLATE", "ENERGY SHIELD", "MULTISHOT", "FLEET FOOT"
        ):
            self.game._apply_upgrade(upgrade)
            self.game._apply_upgrade(upgrade)

        self.assertEqual(self.game.stats.max_health, MAX_PLAYER_HEALTH)
        self.assertEqual(self.game.stats.health, MAX_PLAYER_HEALTH)
        self.assertEqual(self.game.stats.shield_max, MAX_PLAYER_SHIELDS)
        self.assertEqual(self.game.stats.projectiles, MAX_PLAYER_PROJECTILES)
        self.assertEqual(self.game.stats.move_speed, MAX_PLAYER_MOVE_SPEED)

    def test_capped_player_upgrades_leave_the_selection_pool(self):
        self.game.stats.max_health = MAX_PLAYER_HEALTH
        self.game.stats.shield_max = MAX_PLAYER_SHIELDS
        self.game.stats.projectiles = MAX_PLAYER_PROJECTILES
        self.game.stats.move_speed = MAX_PLAYER_MOVE_SPEED

        eligible_names = {upgrade[0] for upgrade in self.game._eligible_upgrades()}
        self.assertNotIn("ARMOR PLATE", eligible_names)
        self.assertNotIn("ENERGY SHIELD", eligible_names)
        self.assertNotIn("MULTISHOT", eligible_names)
        self.assertNotIn("FLEET FOOT", eligible_names)

    def test_late_enemies_unlock_after_wave_twenty(self):
        self.game.wave = 20
        self.assertNotIn(self.game._choose_enemy_kind(0.05), ("nova", "bulwark"))
        self.game.wave = 21
        self.assertEqual(self.game._choose_enemy_kind(0.05), "nova")
        self.assertEqual(self.game._choose_enemy_kind(0.15), "bulwark")

    def test_existing_enemy_health_speed_and_damage_scale_per_wave(self):
        self.game.wave = 1
        self.game._spawn_enemy("chaser")
        early_enemy = next(iter(self.game.enemies.values()))

        self.game.enemies.clear()
        self.game.wave = 20
        self.game._spawn_enemy("chaser")
        late_enemy = next(iter(self.game.enemies.values()))

        self.assertGreater(late_enemy.health, early_enemy.health)
        self.assertGreater(late_enemy.speed, early_enemy.speed)
        self.assertGreater(late_enemy.contact_damage, early_enemy.contact_damage)

    def test_late_enemy_health_and_damage_scale_from_wave_twenty_one(self):
        self.game.wave = 21
        self.game._spawn_enemy("nova")
        wave_21_enemy = next(iter(self.game.enemies.values()))
        self.assertEqual(wave_21_enemy.health, 18)
        self.assertEqual(wave_21_enemy.aoe_damage, 20)

        self.game.enemies.clear()
        self.game.wave = 40
        self.game._spawn_enemy("nova")
        wave_40_enemy = next(iter(self.game.enemies.values()))
        self.assertEqual(wave_40_enemy.health, 39)
        self.assertEqual(wave_40_enemy.aoe_damage, 30)

    def test_late_enemy_aoe_warns_then_damages_every_five_seconds(self):
        self.game.wave = 21
        self.game._spawn_enemy("nova")
        enemy = next(iter(self.game.enemies.values()))
        enemy.spawn_timer = 0.0
        enemy.speed = 0.0
        enemy.x = self.game.player_x + 50
        enemy.y = self.game.player_y
        starting_health = self.game.stats.health

        for _ in range(86):
            self.game._update_enemies(0.05)
            self.game._update_aoe_pulses(0.05)
        self.assertEqual(self.game.stats.health, starting_health)
        self.assertTrue(self.game.aoe_pulses)

        for _ in range(15):
            self.game._update_enemies(0.05)
            self.game._update_aoe_pulses(0.05)
        self.assertEqual(
            self.game.stats.health, starting_health - enemy.aoe_damage
        )

        self.game.invulnerable = 0.0
        for _ in range(100):
            self.game._update_enemies(0.05)
            self.game._update_aoe_pulses(0.05)
        self.assertEqual(
            self.game.stats.health, starting_health - enemy.aoe_damage * 2
        )

    def test_killing_late_enemy_cancels_pending_aoe(self):
        self.game.wave = 21
        self.game._spawn_enemy("bulwark")
        enemy = next(iter(self.game.enemies.values()))
        enemy.spawn_timer = 0.0
        enemy.aoe_timer = 0.70
        self.game._update_enemies(0.05)
        self.assertTrue(self.game.aoe_pulses)
        self.game._kill_enemy(enemy.entity_id)
        self.assertFalse(self.game.aoe_pulses)

    def test_atlas_dimensions(self):
        expected = {
            "actors-24.png": (192, 24),
            "area-effects-32.png": (128, 32),
            "effects-8.png": (64, 8),
            "environment-32.png": (128, 32),
            "late-enemies-32.png": (128, 32),
            "ui-16.png": (128, 16),
        }
        for filename, dimensions in expected.items():
            with Image.open(PROJECT_ROOT / "assets" / filename) as image:
                self.assertEqual(image.size, dimensions)
                self.assertEqual(image.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
