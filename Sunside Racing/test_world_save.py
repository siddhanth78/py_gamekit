"""Seed and lazy sector-cache persistence checks."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from world import World
from world_save import DEFAULT_WORLD_SEED, GENERATOR_VERSION, WorldStore


class WorldSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "world.json"

    def test_seed_and_explored_sectors_round_trip_without_regeneration(self):
        store = WorldStore(self.path)
        world = World(store=store)
        original = world.sector(25, 30)
        self.assertEqual(len(store.sectors), 1)
        store.save()
        payload = json.loads(self.path.read_text())
        self.assertEqual(payload["seed"], DEFAULT_WORLD_SEED)
        self.assertEqual(set(payload["sectors"]), {"25,30"})

        restored_store = WorldStore(self.path, default_seed=999)
        restored = World(store=restored_store)
        with patch.object(restored, "_generate_sector", side_effect=AssertionError("regenerated")):
            self.assertEqual(restored.sector(25, 30), original)
        self.assertFalse(restored_store.dirty)
        restored.sector(25, 31)
        self.assertTrue(restored_store.dirty)
        self.assertEqual(len(restored_store.sectors), 2)

    def test_seed_controls_unexplored_scenery(self):
        self.assertEqual(World(seed=17).sector(12, 14), World(seed=17).sector(12, 14))
        self.assertNotEqual(World(seed=17).sector(12, 14), World(seed=18).sector(12, 14))

    def test_invalid_world_file_is_not_overwritten(self):
        self.path.write_text("{broken json")
        with self.assertRaises(ValueError):
            WorldStore(self.path)
        self.assertEqual(self.path.read_text(), "{broken json")

    def test_invalid_saved_sprite_is_rejected(self):
        self.path.write_text(json.dumps({
            "version": 1, "generator": GENERATOR_VERSION, "seed": 2026,
            "sectors": {"25,30": [["terrain-atlas", "snow", True]]},
        }))
        with self.assertRaisesRegex(ValueError, "Invalid saved world sector"):
            World(store=WorldStore(self.path)).sector(25, 30)

    def test_older_generator_sectors_regenerate_with_saved_seed(self):
        self.path.write_text(json.dumps({
            "version": 1, "seed": 77, "sectors": {"25,30": [["terrain-atlas", "snow", True]]},
        }))
        store = WorldStore(self.path)
        self.assertEqual((store.seed, store.sectors, store.dirty), (77, {}, True))
        self.assertEqual(World(store=store).sector(25, 30), World(seed=77).sector(25, 30))
        store.save()
        self.assertEqual(json.loads(self.path.read_text())["generator"], GENERATOR_VERSION)


if __name__ == "__main__":
    unittest.main()
