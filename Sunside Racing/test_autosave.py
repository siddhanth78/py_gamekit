"""Autosave timing and background world writes."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from autosave import AUTOSAVE_INTERVAL, Autosave
from world import World
from world_save import WorldStore


class AutosaveTimingTests(unittest.TestCase):
    def test_interval_and_requests(self):
        autosave = Autosave()
        self.assertFalse(autosave.tick(AUTOSAVE_INTERVAL - 1))
        self.assertTrue(autosave.tick(1))
        self.assertGreater(autosave.toast, 0)
        autosave.request()
        self.assertFalse(autosave.tick(0.1, allowed=False))  # e.g. mid drag race
        self.assertTrue(autosave.tick(0.1))
        self.assertFalse(autosave.tick(0.1))


class BackgroundWorldSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "world.json"

    def test_background_write_is_complete_and_reloadable(self):
        store = WorldStore(self.path)
        world = World(store=store)
        for sx in range(20, 26):
            world.sector(sx, 30)
        self.assertTrue(store.save(background=True))
        store.wait()
        data = json.loads(self.path.read_text())
        self.assertEqual(len(data["sectors"]), 6)
        self.assertFalse(store.dirty)
        self.assertFalse(store.save(background=True))  # Nothing new to write.
        self.assertEqual(list(self.path.parent.glob(".world-*.tmp")), [])

    def test_sectors_added_during_a_write_are_kept_for_the_next_save(self):
        store = WorldStore(self.path)
        world = World(store=store)
        world.sector(25, 30)
        store.save(background=True)
        world.sector(26, 30)          # Explored while the first write may still run.
        store.save()                  # Exit save waits for the writer, then writes again.
        self.assertEqual(set(json.loads(self.path.read_text())["sectors"]), {"25,30", "26,30"})


if __name__ == "__main__":
    unittest.main()
