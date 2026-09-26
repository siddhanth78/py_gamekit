"""Player save round-trip and validation checks."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from car import Car, START_X, START_Y
from collision_manager import CollisionManager
from player_save import PlayerSave, default_save_path
from walker import Walker
from world import SECTOR_SIZE, World


class PlayerSaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "nested" / "player.json"
        self.store = PlayerSave(self.path)
        self.collisions = CollisionManager(None, World())

    def test_round_trip_resumes_position_and_heading_at_rest(self):
        self.assertIsNone(self.store.load(self.collisions))
        car = Car(x=START_X + 20, y=START_Y + 20, heading=450, speed=180)
        self.assertTrue(self.collisions.can_move(car.collision_record()))
        self.store.save(car)
        saved = json.loads(self.path.read_text())
        self.assertEqual(set(saved), {"version", "mode", "car"})
        self.assertEqual((saved["version"], saved["mode"]), (2, "drive"))
        self.assertEqual(set(saved["car"]), {"x", "y", "heading"})
        self.assertEqual(saved["car"]["heading"], 90)
        resumed = self.store.load(self.collisions)
        self.assertEqual((resumed.x, resumed.y, resumed.heading, resumed.speed),
                         (car.x, car.y, 90, 0))
        self.assertEqual(list(self.path.parent.glob(".player-*.tmp")), [])

    def test_default_path_is_project_root(self):
        self.assertEqual(default_save_path(), PROJECT_ROOT / "player.json")

    def test_legacy_save_is_loaded_when_project_save_is_missing(self):
        old_path = Path(self.temp.name) / "old" / "player.json"
        old_store = PlayerSave(old_path)
        car = Car(x=START_X + 20, y=START_Y + 20, heading=135)
        old_store.save(car)
        migrating = PlayerSave(self.path, legacy_path=old_path)
        resumed = migrating.load(self.collisions)
        self.assertEqual((resumed.x, resumed.y, resumed.heading),
                         (car.x, car.y, car.heading))
        migrating.save(resumed)
        self.assertTrue(self.path.exists())
        self.assertTrue(old_path.exists())

    def test_invalid_and_blocked_positions_fall_back(self):
        cases = [
            "{broken json",
            json.dumps({"version": 1, "player": {"x": 20, "y": 20, "heading": 0}}),
            json.dumps({"version": 1, "player": {
                "x": 26 * SECTOR_SIZE + 128, "y": 31 * SECTOR_SIZE + 128,
                "heading": 0,
            }}),
            json.dumps({"version": 1, "player": {"x": True, "y": START_Y, "heading": 0}}),
        ]
        self.path.parent.mkdir(parents=True)
        for content in cases:
            with self.subTest(content=content):
                self.path.write_text(content)
                self.assertIsNone(self.store.load(self.collisions))

    def test_version_1_save_still_loads_as_driving(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"version": 1, "player": {
            "x": START_X + 20, "y": START_Y + 20, "heading": 45}}))
        car, walker = self.store.load_state(self.collisions)
        self.assertEqual((car.x, car.y, car.heading), (START_X + 20, START_Y + 20, 45))
        self.assertIsNone(walker)

    def test_on_foot_round_trip_resumes_walking(self):
        car = Car(x=START_X, y=START_Y, heading=0)
        walker = Walker(START_X - 60, START_Y + 10, heading=270)
        self.store.save(car, walker)
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["mode"], "walk")
        self.assertEqual(saved["walker"], {"x": START_X - 60, "y": START_Y + 10, "heading": 270})
        resumed_car, resumed_walker = self.store.load_state(self.collisions)
        self.assertEqual((resumed_car.x, resumed_car.y), (car.x, car.y))
        self.assertEqual((resumed_walker.x, resumed_walker.y, resumed_walker.heading),
                         (walker.x, walker.y, 270))
        self.assertEqual(self.collisions.fixed, [])  # Validation leaves no side effects.

    def test_blocked_walker_steps_out_beside_the_car(self):
        car = Car(x=START_X, y=START_Y, heading=0)
        # Saved standing inside the parked car itself.
        self.store.save(car, Walker(START_X, START_Y))
        _, walker = self.store.load_state(self.collisions)
        self.assertEqual((walker.x, walker.y), (START_X - 30, START_Y))

    def test_corrupt_walker_steps_out_and_bad_mode_is_rejected(self):
        self.path.parent.mkdir(parents=True)
        base = {"version": 2, "car": {"x": START_X, "y": START_Y, "heading": 0}}
        self.path.write_text(json.dumps({**base, "mode": "walk", "walker": {"x": "?"}}))
        car, walker = self.store.load_state(self.collisions)
        self.assertIsNotNone(car)
        self.assertEqual((walker.x, walker.y), (START_X - 30, START_Y))
        self.path.write_text(json.dumps({**base, "mode": "fly"}))
        self.assertEqual(self.store.load_state(self.collisions), (None, None))


if __name__ == "__main__":
    unittest.main()
