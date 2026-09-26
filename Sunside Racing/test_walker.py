"""On-foot movement, getting in and out of the car, and render-gather checks."""

import math
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from car import Car
from collision_manager import CollisionManager
from main import camera_position
from traffic import Traffic, TrafficCar
from walker import ENTER_RANGE, WALK_SPEED, Walker, exit_spot
from world import SECTOR_SIZE, TILE_SIZE, World


class WalkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = World()

    def setUp(self):
        self.collisions = CollisionManager(None, self.world)

    def test_keys_move_in_screen_directions(self):
        walker = Walker(Car().x, Car().y + 100)
        for _ in range(60):
            walker.update(1 / 60, 0, -1, False, self.collisions)  # W: north.
        self.assertAlmostEqual(walker.y, Car().y + 100 - WALK_SPEED, delta=1)
        self.assertEqual(walker.heading, 0)
        walker.update(1 / 60, 1, 0, False, self.collisions)
        self.assertEqual(walker.heading, 90)
        self.assertNotEqual(walker.frame(), "player_idle")
        walker.update(1 / 60, 0, 0, False, self.collisions)
        self.assertEqual(walker.frame(), "player_idle")

    def test_walk_frames_alternate(self):
        walker = Walker(Car().x, Car().y + 100)
        frames = set()
        for _ in range(60):
            walker.update(1 / 60, 0, 1, False, self.collisions)
            frames.add(walker.frame())
        self.assertEqual(frames, {"player_walk_a", "player_walk_b"})

    def test_slides_along_buildings(self):
        building = next(s for s in self.world.sector(26, 31) if s.atlas == "structure-atlas")
        # Stand just below the building and push up-right: y is blocked, x keeps moving.
        walker = Walker(building.x, building.y + building.solid_height / 2 + 8)
        start = (walker.x, walker.y)
        for _ in range(30):
            walker.update(1 / 60, 1, -1, False, self.collisions)
        self.assertGreater(walker.x, start[0] + 10)
        self.assertAlmostEqual(walker.y, start[1], delta=2)

    def test_get_out_on_drivers_side_and_back_in(self):
        car = Car()
        spot = exit_spot(car, self.collisions)
        self.assertEqual(spot, (car.x - 30, car.y))  # Facing north, the driver is on the west.
        walker = Walker(*spot)
        self.assertTrue(walker.can_enter(car))
        walker.x -= ENTER_RANGE
        self.assertFalse(walker.can_enter(car))

    def test_parked_car_is_solid_on_foot(self):
        car = Car()
        self.collisions.fixed = [car.obstacle()]
        walker = Walker(car.x - 30, car.y)
        for _ in range(60):
            walker.update(1 / 60, 1, 0, False, self.collisions)  # Walk east into the car.
        self.assertLess(walker.x, car.x - 12)

    def test_traffic_stops_for_parked_player_car(self):
        traffic = Traffic(self.world, self.world.seed)
        waiting = TrafficCar("traffic_red", [(0, 0), (0, -1000)], 100, 0)
        traffic.cars = [waiting]
        parked = Car(x=0, y=-60).collision_record()
        far_walker = [300, 300, 0, 0, 0, 0, 0, 12, 12, 0]
        traffic.update(0.1, far_walker, [parked])
        self.assertEqual((waiting.x, waiting.y), (0, 0))


class RenderGatherTests(unittest.TestCase):
    def test_tight_gather_keeps_every_on_screen_sprite(self):
        world = World()
        cam_x, cam_y, w, h = 26 * SECTOR_SIZE + 100, 31 * SECTOR_SIZE + 50, 1280, 720
        gathered = set(world.visible_sprites(cam_x, cam_y, w, h))
        for sy in range(29, 35):
            for sx in range(24, 31):
                for s in world.sector(sx, sy):
                    on_screen = (cam_x - s.width / 2 < s.x < cam_x + w + s.width / 2
                                 and cam_y - s.height / 2 < s.y < cam_y + h + s.height / 2)
                    if on_screen:
                        self.assertIn(s, gathered)

    def test_zoomed_camera_lands_on_whole_screen_pixels(self):
        walker = Walker(26 * SECTOR_SIZE + 123.37, 31 * SECTOR_SIZE + 77.71)
        x, y = camera_position(walker, 640, 360, 2.0)
        self.assertEqual((x * 2) % 1, 0)
        self.assertEqual((y * 2) % 1, 0)
        self.assertLess(abs(x + 320 - walker.x), 1)


if __name__ == "__main__":
    unittest.main()
