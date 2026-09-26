"""Parked city cars that occasionally leave their stall, lap a block, and park again."""

from __future__ import annotations

import random

from traffic import CITY_LANE, TrafficCar, lane_path
from world import (
    CITY_SECTORS_X, CITY_SECTORS_Y, PARKED_SIZE, PARKED_SOLID, SECTOR_SIZE, STALL_Y,
    TILE_SIZE,
)


COMMUTER_SHARE = 0.35    # Share of nose-in parked cars that ever drive off.
FIRST_WAIT = (3.0, 25.0)  # Seconds parked before the first trip once nearby.
REST_WAIT = (15.0, 45.0)  # Seconds parked between trips.
SPEED = 115.0
SCAN_SECTORS = 2          # Sectors around the player whose lots are simulated.
AISLE_Y = 54              # Aisle line below the stalls, from the tile's top edge.


def _is_commuter(sprite, seed):
    # Stable per stall, so the same cars are commuters every session.
    key = int(sprite.x) * 73856093 ^ int(sprite.y) * 19349663 ^ seed
    return random.Random(key).random() < COMMUTER_SHARE


class Parking:
    def __init__(self, world, traffic, seed: int):
        self.world = world
        self.traffic = traffic
        self.seed = seed
        self.rng = random.Random(seed + 911)
        self.waits = {}   # Parked commuter sprite -> seconds until it leaves.
        self.away = {}    # Parked sprite -> TrafficCar currently driving its trip.

    def _commuters(self, sx, sy):
        if not (CITY_SECTORS_X[0] <= sx <= CITY_SECTORS_X[1]
                and CITY_SECTORS_Y[0] <= sy <= CITY_SECTORS_Y[1]):
            return []
        # Only nose-in cars; they back out and later pull forward into the same stall.
        return [s for s in self.world.sector(sx, sy)
                if s.atlas == "vehicle-atlas" and s.rotation == 0.0
                and _is_commuter(s, self.seed)]

    def trip_path(self, sprite):
        """Stall -> aisle -> road -> one city block lap -> road -> aisle, closed back to the stall."""
        sx, sy = int(sprite.x // SECTOR_SIZE), int(sprite.y // SECTOR_SIZE)
        ox, oy = sx * SECTOR_SIZE, sy * SECTOR_SIZE
        road = 4.5 * TILE_SIZE  # Local center of this sector's north-south and east-west roads.
        tile_top = sprite.y - STALL_Y
        aisle = (sprite.x, tile_top + AISLE_Y)
        lot_north = aisle[1] - oy < road
        # Right-hand lanes: heading south uses the west side, heading north the east side.
        toward_x = ox + road + (-CITY_LANE if lot_north else CITY_LANE)
        back_x = ox + road + (CITY_LANE if lot_north else -CITY_LANE)
        dx = 1 if sx + 1 <= CITY_SECTORS_X[1] else -1
        # Lap away from the lot so the car returns straight up the road it left by.
        dy = 1 if lot_north else -1
        if not CITY_SECTORS_Y[0] <= sy + dy <= CITY_SECTORS_Y[1]:
            dy = -dy

        def crossing(cx, cy):
            return (cx * SECTOR_SIZE + road, cy * SECTOR_SIZE + road)

        lap = lane_path([crossing(sx, sy), crossing(sx + dx, sy),
                         crossing(sx + dx, sy + dy), crossing(sx, sy + dy)], CITY_LANE)
        points = [(sprite.x, sprite.y), aisle, (toward_x, aisle[1]),
                  *lap, lap[0], (back_x, aisle[1]), aisle]
        return [p for i, p in enumerate(points) if p != points[i - 1]]

    def _depart(self, sprite):
        car = TrafficCar(sprite.name, self.trip_path(sprite), SPEED, 0, size=PARKED_SIZE,
                         solid=PARKED_SOLID, reverse_segments=frozenset({0}), trip=True)
        self.traffic.cars.append(car)
        self.away[sprite] = car

    def update(self, dt: float, x: float, y: float):
        for sprite, car in list(self.away.items()):
            if car.finished:
                self.traffic.cars.remove(car)
                del self.away[sprite]
                self.waits[sprite] = self.rng.uniform(*REST_WAIT)
        px, py = int(x // SECTOR_SIZE), int(y // SECTOR_SIZE)
        nearby = set()
        for sy in range(py - SCAN_SECTORS, py + SCAN_SECTORS + 1):
            for sx in range(px - SCAN_SECTORS, px + SCAN_SECTORS + 1):
                for sprite in self._commuters(sx, sy):
                    nearby.add(sprite)
                    if sprite in self.away:
                        continue
                    wait = self.waits.get(sprite)
                    if wait is None:
                        wait = self.rng.uniform(*FIRST_WAIT)
                    wait -= dt
                    if wait <= 0:
                        self._depart(sprite)
                        self.waits.pop(sprite, None)
                    else:
                        self.waits[sprite] = wait
        # Forget parked timers for lots the player has left; trips in progress finish.
        for sprite in [s for s in self.waits if s not in nearby]:
            del self.waits[sprite]

    def is_away(self, sprite) -> bool:
        return sprite in self.away
