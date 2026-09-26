"""The player on foot: screen-direction walking, wall sliding, and getting in or out of the car."""

from __future__ import annotations

import math
from dataclasses import dataclass

from collision_manager import nearest_clear_spot
from world import Sprite


WALK_SPEED = 60.0   # px/s; the car tops out at 170.
RUN_SPEED = 105.0
BODY = 12           # Square collision box, px.
STRIDE = 12         # px walked per animation frame.
ENTER_RANGE = 44    # Max distance from the car's center to get in.
EXIT_GAP = 30       # Door-side distance from the car's center when getting out.
CALL_RANGE = 320    # Farthest the called car may appear from the walker, px.
CALL_MIN_DISTANCE = 80  # Closer than this, the car is already right here.
CALL_PROMPT_DISTANCE = 320  # Show "Q  Call car" once the car is this far away.


@dataclass
class Walker:
    x: float
    y: float
    heading: float = 0.0  # Degrees clockwise from north, matching Car.heading.
    speed: float = 0.0
    stride: float = 0.0

    def collision_record(self, x: float | None = None, y: float | None = None):
        return [self.x if x is None else x, self.y if y is None else y,
                255, 255, 255, 255, 0, BODY, BODY, 0.0]

    def update(self, dt: float, move_x: int, move_y: int, run: bool, collisions):
        """Move in screen directions (W is north); slide along walls instead of stopping."""
        if not (move_x or move_y):
            self.speed = 0.0
            return
        length = math.hypot(move_x, move_y)
        dx, dy = move_x / length, move_y / length
        self.heading = math.degrees(math.atan2(dx, -dy)) % 360
        self.speed = RUN_SPEED if run else WALK_SPEED
        step = self.speed * min(max(dt, 0.0), 0.05)
        start = (self.x, self.y)
        for tx, ty in ((self.x + dx * step, self.y + dy * step),
                       (self.x + dx * step, self.y), (self.x, self.y + dy * step)):
            if (tx, ty) != (self.x, self.y) and collisions.can_move(self.collision_record(tx, ty)):
                self.x, self.y = tx, ty
                break
        moved = math.dist(start, (self.x, self.y))
        self.stride += moved
        if not moved:
            self.speed = 0.0

    def frame(self) -> str:
        if not self.speed:
            return "player_idle"
        return "player_walk_a" if int(self.stride // STRIDE) % 2 == 0 else "player_walk_b"

    def respawn_nearby(self, collisions) -> bool:
        spot = nearest_clear_spot(collisions, self.collision_record, self.x, self.y, 8)
        if spot is None:
            return False
        self.x, self.y = spot
        return True

    def obstacle(self, padding: float = 0.0):
        """The walker as a solid sprite, e.g. to keep a called car from landing on them."""
        return Sprite("people-atlas", "player_idle", self.x, self.y, 32, 32, 0.0,
                      BODY + padding, BODY + padding)

    def can_enter(self, car) -> bool:
        return math.dist((self.x, self.y), (car.x, car.y)) <= ENTER_RANGE


def exit_spot(car, collisions):
    """Where the player steps out: driver's side first, then passenger, back, front."""
    angle = math.radians(car.heading)
    fx, fy = math.sin(angle), -math.cos(angle)  # Forward.
    lx, ly = fy, -fx                            # Driver's (left) side.
    probe = Walker(car.x, car.y)
    for ox, oy in ((lx * EXIT_GAP, ly * EXIT_GAP), (-lx * EXIT_GAP, -ly * EXIT_GAP),
                   (-fx * 40, -fy * 40), (fx * 40, fy * 40)):
        x, y = car.x + ox, car.y + oy
        if collisions.can_move(probe.collision_record(x, y)):
            return x, y
    return None


def call_spot(walker, car, collisions):
    """Closest clear spot for the car beside the walker, facing the way they face.

    Returns None when the car is already close or no spot within CALL_RANGE is free.
    """
    if math.dist((walker.x, walker.y), (car.x, car.y)) < CALL_MIN_DISTANCE:
        return None
    saved_fixed, saved_heading = collisions.fixed, car.heading
    car.heading = walker.heading
    # Only the walker blocks the search; the car's old parking spot no longer matters.
    collisions.fixed = [walker.obstacle(padding=16)]
    spot = None
    try:
        spot = nearest_clear_spot(collisions, car.collision_record, walker.x, walker.y, 12,
                                  CALL_RANGE)
    finally:
        collisions.fixed = saved_fixed
        if spot is None:
            car.heading = saved_heading
    return spot
