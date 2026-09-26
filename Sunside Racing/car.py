"""Small arcade driving model with terrain-dependent grip and speed."""

from __future__ import annotations

import math
from dataclasses import dataclass

from collision_manager import nearest_clear_spot
from world import SECTOR_SIZE, TILE_SIZE, Sprite


START_X = 26 * SECTOR_SIZE + 4.5 * TILE_SIZE
START_Y = 31 * SECTOR_SIZE + 4.5 * TILE_SIZE
ACCELERATION = 85          # px/s^2 before terrain grip.
BRAKING = 420
REVERSE_ACCELERATION = 90
TOP_SPEED = 170            # Fastest surface (city); the HUD scales its bar to this.
RESPAWN_STEP = 8        # Search ring spacing in pixels.
RESPAWN_CLEARANCE = 16  # Extra width and length so the car is not left wedged.


@dataclass
class Car:
    x: float = START_X
    y: float = START_Y
    heading: float = 0.0  # Degrees clockwise from north.
    speed: float = 0.0

    def reset(self):
        self.x, self.y, self.heading, self.speed = START_X, START_Y, 0.0, 0.0

    def respawn_nearby(self, collisions, max_radius: int = 480) -> bool:
        """Stop at the closest spot with some clearance; fall back to the start."""
        spot = nearest_clear_spot(collisions, self.collision_record, self.x, self.y,
                                  RESPAWN_CLEARANCE, max_radius, RESPAWN_STEP)
        if spot is None:
            self.reset()
            return False
        (self.x, self.y), self.speed = spot, 0.0
        return True

    def obstacle(self):
        """The car as a solid world sprite, used while the player is on foot."""
        return Sprite("vehicle-atlas", "racer_player", self.x, self.y, 64, 64,
                      -self.heading, 24, 44)

    def collision_record(self, x: float | None = None, y: float | None = None):
        return [self.x if x is None else x, self.y if y is None else y,
                255, 255, 255, 255, 0, 24, 44, -self.heading]

    def update(self, dt: float, throttle: int, steer: int, handbrake: bool,
               world, collisions):
        dt = min(max(dt, 0.0), 0.05)
        surface = world.region_at(self.x, self.y)
        # Top speeds are kept low so the car stays controllable in traffic.
        grip, max_speed = {
            "city": (1.0, TOP_SPEED), "jungle": (0.72, 110),
            "desert": (0.78, 132), "snow": (0.55, 128),
            "rural": (0.80, 140), "beach": (0.68, 105),
            "island": (0.90, 155),
        }.get(surface, (0.75, 110))
        # Gentle acceleration (about 2 s to top speed in the city), firm brakes.
        if throttle > 0:
            self.speed += (ACCELERATION if self.speed >= 0 else BRAKING) * grip * dt
        elif throttle < 0:
            self.speed -= (BRAKING if self.speed > 0 else REVERSE_ACCELERATION) * grip * dt
        else:
            drag = (180 if handbrake else 95) * dt
            self.speed = math.copysign(max(0.0, abs(self.speed) - drag), self.speed)
        self.speed = max(-80 * grip, min(max_speed, self.speed))

        if steer and abs(self.speed) > 4:
            turn = 135 * grip * min(1.0, abs(self.speed) / 130)
            if handbrake:
                turn *= 1.45
                self.speed *= max(0.0, 1 - 1.2 * dt)
            self.heading = (self.heading + steer * turn * dt *
                            (1 if self.speed > 0 else -1)) % 360

        distance = self.speed * dt
        if not distance:
            return
        direction = math.radians(self.heading)
        dx, dy = math.sin(direction) * distance, -math.cos(direction) * distance
        steps = max(1, math.ceil(abs(distance) / 12))
        for _ in range(steps):
            candidate_x, candidate_y = self.x + dx / steps, self.y + dy / steps
            if collisions.can_move(self.collision_record(candidate_x, candidate_y)):
                self.x, self.y = candidate_x, candidate_y
            else:
                self.speed = 0.0
                break
