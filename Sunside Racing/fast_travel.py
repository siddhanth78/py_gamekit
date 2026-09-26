"""Fast travel: jump (in the car) to the edge of a region unlocked at level 3."""

from __future__ import annotations

import math

from collision_manager import nearest_clear_spot
from world import CENTERS, SECTOR_SIZE


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


MAINLAND_DOCK = (47, 31)   # Mainland ferry-dock sector; returning from the island lands here.
ISLAND_CENTER = (56, 31)


def island_destination(world, collisions, car, to_island: bool):
    """A clear spot on Elite Island (south of its center) or back at the mainland dock."""
    sector = ISLAND_CENTER if to_island else MAINLAND_DOCK
    x, y = world.center_position(*sector)
    y += 200 if to_island else 0
    mass = "island" if to_island else "mainland"

    class OnLandmass:
        def can_move(self, rect):
            sx, sy = int(rect[0] // SECTOR_SIZE), int(rect[1] // SECTOR_SIZE)
            return world._landmass(sx, sy) == mass and world.region_at(rect[0], rect[1]) != "sea" \
                and collisions.can_move(rect)

    saved = car.heading
    car.heading = 0.0
    try:
        spot = nearest_clear_spot(OnLandmass(), car.collision_record, x, y, 24, 600)
    finally:
        car.heading = saved
    return (*spot, 0.0) if spot else None


def on_island(world, x, y) -> bool:
    return world._landmass(int(x // SECTOR_SIZE), int(y // SECTOR_SIZE)) == "island"


def on_mainland_beach(world, x, y) -> bool:
    return world.region_at(x, y) == "beach" and not on_island(world, x, y)
