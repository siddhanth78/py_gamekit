"""Fast travel: jump (in the car) to the edge of a region unlocked at level 3."""

from __future__ import annotations

import math

from collision_manager import nearest_clear_spot
from world import CENTERS


STEP = 32          # px between samples along the line toward the region.
INSET = 192        # How far past the region's edge the car lands.
SEARCH = 400       # Radius searched for a clear, car-sized spot.


def region_anchor(world, region: str):
    """The region's racing center: a point known to lie well inside it."""
    sector = next(s for s, name in CENTERS.items() if name == f"center_{region}")
    return world.center_position(*sector)


def destination(world, collisions, car, region: str, from_x: float, from_y: float):
    """Where the car lands: just inside the region's boundary on the line from the player
    toward its racing center, on clear ground in that region. Returns (x, y, heading)."""
    ax, ay = region_anchor(world, region)
    distance = math.dist((from_x, from_y), (ax, ay))
    dx, dy = (ax - from_x) / distance, (ay - from_y) / distance
    edge = next(((from_x + dx * d, from_y + dy * d) for d in range(0, int(distance), STEP)
                 if world.region_at(from_x + dx * d, from_y + dy * d) == region), (ax, ay))
    inset = min(INSET, math.dist(edge, (ax, ay)))
    x, y = edge[0] + dx * inset, edge[1] + dy * inset
    heading = math.degrees(math.atan2(dx, -dy)) % 360

    class InRegion:
        def can_move(self, rect):
            return world.region_at(rect[0], rect[1]) == region and collisions.can_move(rect)

    saved = car.heading
    car.heading = heading  # Search with the car turned the way it will face.
    try:
        spot = nearest_clear_spot(InRegion(), car.collision_record, x, y, 24, SEARCH)
    finally:
        car.heading = saved
    return (*spot, heading) if spot else None
