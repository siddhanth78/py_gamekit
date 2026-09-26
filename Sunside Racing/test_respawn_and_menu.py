"""Nearby respawn and pause-menu input checks."""

import math
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from car import START_X, START_Y, TOP_SPEED, Car
from collision_manager import CollisionManager
from hud import (
    ARRIVED_DISTANCE, ARROW_LENGTH, GREEN, ORBIT_RADIUS, RED, SPEED_SEGMENTS, YELLOW,
    lit_segments, orbit_tip, speed_color,
)
from pause_menu import PauseMenu
from world import World


class RespawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = World()
        cls.collisions = CollisionManager(None, cls.world)

    def test_stuck_in_building_moves_a_short_way_to_a_clear_spot(self):
        building = next(s for s in self.world.sector(26, 31) if s.atlas == "structure-atlas")
        car = Car(x=building.x, y=building.y, speed=120)
        self.assertFalse(self.collisions.can_move(car.collision_record()))
        self.assertTrue(car.respawn_nearby(self.collisions))
        self.assertTrue(self.collisions.can_move(car.collision_record()))
        self.assertLess(math.dist((car.x, car.y), (building.x, building.y)), 120)
        self.assertEqual(car.speed, 0.0)

    def test_clear_spot_only_stops_the_car(self):
        car = Car(speed=200, heading=90)
        car.respawn_nearby(self.collisions)
        self.assertEqual((car.x, car.y, car.heading, car.speed), (START_X, START_Y, 90, 0.0))

    def test_no_clear_spot_falls_back_to_start(self):
        class Blocked:
            def can_move(self, _):
                return False
        car = Car(x=100, y=100)
        self.assertFalse(car.respawn_nearby(Blocked(), max_radius=16))
        self.assertEqual((car.x, car.y), (START_X, START_Y))


class PauseMenuInputTests(unittest.TestCase):
    def menu(self):
        menu = PauseMenu.__new__(PauseMenu)  # Input logic only; skip GL setup.
        menu.viewport, menu.open, menu.page, menu.selected = (1280, 720), True, "main", 0
        return menu

    def test_keyboard_navigation_and_confirm(self):
        menu = self.menu()
        self.assertEqual(menu.handle("confirm", None), "resume")
        menu.handle("menu_down", None)
        menu.handle("menu_down", None)
        self.assertEqual(menu.handle("confirm", None), "exit")
        menu.handle("menu_down", None)
        self.assertEqual(menu.selected, 0)
        self.assertEqual(menu.handle("pause", None), "resume")

    def test_help_page_opens_and_returns(self):
        menu = self.menu()
        menu.handle("menu_down", None)
        self.assertIsNone(menu.handle("confirm", None))
        self.assertEqual(menu.page, "help")
        self.assertIsNone(menu.handle("pause", None))  # Esc on help goes back, not resume.
        self.assertEqual((menu.page, menu.items[menu.selected]), ("main", "help"))
        menu.handle("confirm", None)
        (bx, by), = menu._button_centers()
        self.assertIsNone(menu.handle("click", (bx, by)))
        self.assertEqual(menu.page, "main")

    def test_mouse_hover_and_click(self):
        menu = self.menu()
        (rx, ry), _, (ex, ey) = menu._button_centers()
        self.assertIsNone(menu.handle("pointer", (ex, ey)))
        self.assertEqual(menu.selected, 2)
        self.assertEqual(menu.handle("click", (rx + 100, ry)), "resume")
        self.assertIsNone(menu.handle("click", (5, 5)))


class HudAndHandlingTests(unittest.TestCase):
    def test_speed_bar_runs_green_to_red(self):
        self.assertEqual(speed_color(0.0), GREEN)
        self.assertEqual(speed_color(0.5), YELLOW)
        self.assertEqual(speed_color(1.0), RED)
        self.assertEqual(lit_segments(0, TOP_SPEED), 0)
        self.assertEqual(lit_segments(2, TOP_SPEED), 1)
        self.assertEqual(lit_segments(TOP_SPEED / 2, TOP_SPEED), SPEED_SEGMENTS // 2)
        self.assertEqual(lit_segments(-TOP_SPEED * 3, TOP_SPEED), SPEED_SEGMENTS)

    def test_arrow_orbits_the_car_toward_the_center(self):
        # Car at screen (640, 360); center far to the north-west.
        tip_x, tip_y, dx, dy = orbit_tip(0, 0, 3000, 3000, 3000 - 640, 3000 - 360)
        self.assertAlmostEqual(math.hypot(tip_x - 640, tip_y - 360), ORBIT_RADIUS + ARROW_LENGTH)
        self.assertLess(tip_x, 640)
        self.assertLess(tip_y, 360)
        self.assertAlmostEqual((dx, dy)[0], -math.sqrt(0.5))
        # Near the camera clamp, the orbit follows the car, not the screen center.
        tip_x, _, _, _ = orbit_tip(5000, 100, 40, 100, 0, 0)
        self.assertAlmostEqual(tip_x, 40 + ORBIT_RADIUS + ARROW_LENGTH)
        self.assertIsNone(orbit_tip(100, 100, 100 + ARRIVED_DISTANCE - 1, 100, 0, 0))

    def test_acceleration_is_gradual(self):
        world = World()
        collisions = CollisionManager(None, world)
        car = Car()
        for _ in range(30):  # Half a second of full throttle.
            car.update(1 / 60, 1, 0, False, world, collisions)
        self.assertLess(car.speed, TOP_SPEED * 0.3)
        for _ in range(120):
            car.update(1 / 60, 1, 0, False, world, collisions)
        self.assertAlmostEqual(car.speed, TOP_SPEED, delta=1)


if __name__ == "__main__":
    unittest.main()
