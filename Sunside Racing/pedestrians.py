"""Rudimentary pedestrians: people walk fixed rounds near the player and pop into doors.

Groups (a city block's sidewalks, a farm, a camp, a racing-center plaza) are created
when the player comes within SCAN_SECTORS and dropped past KEEP_SECTORS, so the cost
stays bounded however big the world is. A few road walkers in the countryside are
always simulated, like traffic.
"""

from __future__ import annotations

import math
import random

from gl_utils import check_collision
from traffic import lane_path, there_and_back
from world import (
    CAMP_RING, CAMP_SEATS, CAMP_TENTS, CENTERS, CITY_BUILDINGS, CITY_SECTORS_X,
    CITY_SECTORS_Y, DIRT_ROUTES, SECTOR_SIZE, SNOW_ROUTE, TILE_SIZE, Sprite,
)


SCAN_SECTORS = 2       # Groups within this many sectors of the player are simulated.
KEEP_SECTORS = 3       # Groups farther than this are dropped (hysteresis).
CITY_PER_BLOCK = 12
PLAZA_CROWD = {"city": 4}  # Other regions get 3 people milling around their center.
ROAD_WALKERS = {"snow": 8, "rural": 8}
WALK_SPEED = (26.0, 40.0)
DOOR_TIME = (3.0, 9.0)     # Seconds spent inside a building or tent.
PAUSE_TIME = (0.8, 3.0)    # Seconds spent idling at a corner or across the street.
ROAD = 4.5 * TILE_SIZE     # Local center line of each city sector's roads.
SIDEWALK = 36              # Sidewalk line, measured from a road's center line.
SHOULDER = 30              # Country walkers keep this far right of the road's center.
BUILDING_FACE = 46         # Doorstep: 5 px outside a city building's 82 px wall.
SIZE = 32
SOLID = 10
YIELD_AHEAD = 20           # A pedestrian waits if the player stands this close in front.

CITY_KINDS = tuple(f"city_{c}" for c in "abcdefgh")
REGION_KINDS = {
    "city": CITY_KINDS, "island": CITY_KINDS, "beach": CITY_KINDS,
    "rural": ("farmer_a", "farmer_b"), "snow": ("snow_a", "snow_b"),
    "desert": ("nomad_a", "nomad_b"), "jungle": ("explorer_a", "explorer_b"),
}


class Pedestrian:
    """Walks a closed path forever, pausing at stops; 'door' stops hide them inside."""

    def __init__(self, kind, path, speed, start=0.0, stops=None, heading=0.0):
        self.kind = kind
        self.path = path
        self.stops = stops or {}  # Path index -> ("door" | "pause", (min_s, max_s)).
        self.lengths = [math.dist(path[i], path[(i + 1) % len(path)]) for i in range(len(path))]
        self.speed = speed
        self.segment, self.progress = 0, 0.0
        self.x, self.y = path[0]
        self.heading = heading
        self.stride = 0.0
        self.wait = 0.0
        self.inside = False
        self.moving = False
        self.overlapping_player = False
        self.still = len(path) == 1  # Seated or standing in place.
        if not self.still:
            self._walk(start % sum(self.lengths), None)

    def _walk(self, distance, rng):
        remaining = distance
        while remaining > 0:
            left = self.lengths[self.segment] - self.progress
            if remaining < left:
                self.progress += remaining
                break
            remaining -= left
            self.segment = (self.segment + 1) % len(self.path)
            self.progress = 0.0
            stop = self.stops.get(self.segment)
            if stop and rng is not None:
                kind, (low, high) = stop
                self.wait = rng.uniform(low, high)
                self.inside = kind == "door"
                break
        (ax, ay), (bx, by) = self.path[self.segment], self.path[(self.segment + 1) % len(self.path)]
        length = self.lengths[self.segment]
        t = self.progress / length if length else 0.0
        self.x, self.y = ax + (bx - ax) * t, ay + (by - ay) * t
        if length:
            # Degrees clockwise from north, matching the player and cars.
            self.heading = math.degrees(math.atan2(bx - ax, -(by - ay))) % 360

    def update(self, dt, rng, blocked):
        self.moving = False
        if self.still:
            return
        if self.wait > 0:
            self.wait -= dt
            if self.wait <= 0:
                self.inside = False
            return
        if blocked:
            return
        before = (self.x, self.y)
        self._walk(self.speed * dt, rng)
        self.stride += math.dist(before, (self.x, self.y))
        self.moving = True

    def frame(self) -> str:
        if not self.moving:
            return f"{self.kind}_idle"
        return f"{self.kind}_walk_a" if int(self.stride // 10) % 2 == 0 else f"{self.kind}_walk_b"

    def sprite(self) -> Sprite:
        return Sprite("people-atlas", self.frame(), self.x, self.y, SIZE, SIZE, -self.heading,
                      SOLID, SOLID)


def build_loop(corners, detours):
    """Walk the corners in order, stepping out to each detour from its point on an edge.

    detours: (edge_point, [(point, stop), ...]); the walker returns to edge_point after.
    Returns (path, stops) with stops keyed by path index.
    """
    path, stops = [], {}

    def add(point, stop=None):
        if path and path[-1] == point:
            if stop:
                stops[len(path) - 1] = stop
            return
        if stop:
            stops[len(path)] = stop
        path.append(point)

    for i, corner in enumerate(corners):
        end = corners[(i + 1) % len(corners)]
        add(corner)
        on_edge = []
        for edge_point, excursion in detours:
            # Collinear and between the corners (edges are axis-aligned).
            if (min(corner[0], end[0]) <= edge_point[0] <= max(corner[0], end[0])
                    and min(corner[1], end[1]) <= edge_point[1] <= max(corner[1], end[1])
                    and (corner[0] == end[0] == edge_point[0] or corner[1] == end[1] == edge_point[1])):
                on_edge.append((math.dist(corner, edge_point), edge_point, excursion))
        for _, edge_point, excursion in sorted(on_edge, key=lambda item: item[0]):
            add(edge_point)
            for point, stop in excursion:
                add(point, stop)
            add(edge_point)
    if len(path) > 1 and path[-1] == path[0]:
        path.pop()
    return path, stops


def reverse_route(path, stops):
    """The same loop walked the other way, with stops kept at the same points."""
    n = len(path)
    order = [0] + list(range(n - 1, 0, -1))
    return [path[i] for i in order], {order.index(i): stop for i, stop in stops.items()}


class Pedestrians:
    def __init__(self, world, seed: int):
        self.world = world
        self.seed = seed
        self.rng = random.Random(seed + 2718)
        self.groups: dict[tuple, list[Pedestrian]] = {}
        self._scanned_sector = None
        self.walkers = self._road_walkers()

    # Group creation -------------------------------------------------------------

    def _group_rng(self, key):
        return random.Random(f"{key}-{self.seed}")  # str seeds are stable across runs.

    def _people(self, rng, kinds, path, stops, count, reverse_half=True, inset_path=None):
        people = []
        total = sum(math.dist(path[i], path[(i + 1) % len(path)]) for i in range(len(path)))
        for i in range(count):
            route, route_stops = path, stops
            if reverse_half and i % 2:
                route, route_stops = reverse_route(*(inset_path or (path, stops)))
            people.append(Pedestrian(rng.choice(kinds), route, rng.uniform(*WALK_SPEED),
                                     rng.uniform(0, total), route_stops))
        return people

    def _city_block(self, bx, by, rng):
        """Sidewalks around the block whose north-west crossing is in sector (bx, by)."""
        def route(inset):
            x0 = bx * SECTOR_SIZE + ROAD + SIDEWALK + inset
            x1 = (bx + 1) * SECTOR_SIZE + ROAD - SIDEWALK - inset
            y0 = by * SECTOR_SIZE + ROAD + SIDEWALK + inset
            y1 = (by + 1) * SECTOR_SIZE + ROAD - SIDEWALK - inset
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            pause = ("pause", PAUSE_TIME)
            door = ("door", DOOR_TIME)
            detours = []
            # Buildings on the block's four lots get a door on the side facing the sidewalk.
            for sx, sy, lx, ly, edge_x, face in (
                (bx, by, 6, 6, x0, -1), (bx + 1, by, 2, 6, x1, 1),
                (bx, by + 1, 6, 2, x0, -1), (bx + 1, by + 1, 2, 2, x1, 1),
            ):
                lot_x, lot_y = sx * SECTOR_SIZE + lx * TILE_SIZE, sy * SECTOR_SIZE + ly * TILE_SIZE
                if self._building_at(sx, sy, lot_x, lot_y):
                    detours.append(((edge_x, lot_y), [((lot_x + face * BUILDING_FACE, lot_y), door)]))
            # Cross to the next block at a crosswalk, linger, and come back.
            if bx + 1 <= CITY_SECTORS_X[1] - 1:
                y = by * SECTOR_SIZE + 5.5 * TILE_SIZE
                detours.append(((x1, y), [((x1 + 2 * (SIDEWALK + inset), y), pause)]))
            x = bx * SECTOR_SIZE + 5.5 * TILE_SIZE
            detours.append(((x, y1), [((x, y1 + 2 * (SIDEWALK + inset)), pause)]))
            path, stops = build_loop(corners, detours)
            for i in range(len(path)):
                if path[i] in corners and i not in stops and rng.random() < 0.5:
                    stops[i] = pause
            return path, stops

        # Walkers going the other way keep 8 px closer to the buildings.
        return self._people(rng, CITY_KINDS, *route(0), CITY_PER_BLOCK, inset_path=route(8))

    def _building_at(self, sx, sy, x, y):
        return any(s.atlas == "structure-atlas" and s.name in CITY_BUILDINGS
                   and s.x == x and s.y == y for s in self.world.sector(sx, sy))

    def _plaza(self, sx, sy, rng):
        region = self.world.region(sx, sy)
        cx, cy = self.world.center_position(sx, sy)
        people = []
        for _ in range(PLAZA_CROWD.get(region, 3)):
            angles = sorted(rng.uniform(0, 2 * math.pi) for _ in range(5))
            path = [(cx + math.cos(a) * rng.uniform(96, 116), cy + math.sin(a) * rng.uniform(96, 116))
                    for a in angles]
            stops = {i: ("pause", PAUSE_TIME) for i in range(len(path))}
            people.append(Pedestrian(rng.choice(REGION_KINDS.get(region, CITY_KINDS)), path,
                                     rng.uniform(20, 30), rng.uniform(0, 400), stops))
        return people

    def _farm(self, sx, sy, rng):
        barn = next((s for s in self.world.sector(sx, sy) if s.name == "rural_barn"), None)
        if barn is None:
            return []
        ox, oy = sx * SECTOR_SIZE, sy * SECTOR_SIZE
        fx, fy = round((barn.x - ox) / TILE_SIZE) - 1, round((barn.y - oy) / TILE_SIZE) - 1
        x0, y0 = ox + fx * TILE_SIZE - 10, oy + fy * TILE_SIZE - 10
        x1, y1 = ox + (fx + 5) * TILE_SIZE + 10, oy + (fy + 3) * TILE_SIZE + 10
        # The barn door is on its south side, reached between the hay bales.
        path, stops = build_loop([(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                                 [((barn.x, y1), [((barn.x, barn.y + 46), ("door", DOOR_TIME))])])
        return self._people(rng, REGION_KINDS["rural"], path, stops, 2)

    def _camp(self, sx, sy, rng):
        region = self.world.camps[(sx, sy)]
        kinds = REGION_KINDS[region]
        cx, cy = self.world.camp_center(sx, sy)
        # Seated by the fire on the bench, facing south toward it.
        people = [Pedestrian(rng.choice(kinds), [(cx + dx, cy + dy)], 0, heading=180.0)
                  for dx, dy in CAMP_SEATS]
        ring = []
        for dx, dy in CAMP_TENTS:
            angle = math.atan2(dy, dx)
            ring.append((angle, "tent", dx, dy))
        # Extra ring points halfway between neighbouring tents.
        tent_angles = sorted(entry[0] for entry in ring)
        for a, b in zip(tent_angles, tent_angles[1:] + [tent_angles[0] + 2 * math.pi]):
            ring.append(((a + b) / 2, "ring", 0, 0))
        path, stops = [], {}
        for angle, what, dx, dy in sorted(ring):
            point = (cx + math.cos(angle) * CAMP_RING, cy + math.sin(angle) * CAMP_RING)
            path.append(point)
            if what == "tent":
                # Step up to the tent's door (facing the fire), duck inside, come back out.
                distance = math.hypot(dx, dy)
                door = (cx + dx - dx / distance * 40, cy + dy - dy / distance * 40)
                stops[len(path)] = ("door", DOOR_TIME)
                path += [door, point]
            else:
                stops[len(path) - 1] = ("pause", PAUSE_TIME)
        people += self._people(rng, kinds, path, stops, 2)
        return people

    def _road_walkers(self):
        """Country folk strolling the road shoulders; always simulated, like traffic."""
        rng = random.Random(self.seed + 31415)
        # The snow road ends inside its racing center, so walkers turn back before it.
        routes = {"snow": [SNOW_ROUTE[:-1] + ((104, 388),)],
                  "rural": list(DIRT_ROUTES)}
        walkers = []
        for region, count in ROAD_WALKERS.items():
            for i in range(count):
                # Most walk the main road; the last few take any side branches.
                branch = max(0, i - (count - len(routes[region])))
                route = routes[region][branch]
                centers = [((tx + 0.5) * TILE_SIZE, (ty + 0.5) * TILE_SIZE) for tx, ty in route]
                path = lane_path(there_and_back(centers), SHOULDER)
                walkers.append(Pedestrian(rng.choice(REGION_KINDS[region]), path,
                                          rng.uniform(28, 36), rng.uniform(0, 20000)))
        return walkers

    # Per-frame work -------------------------------------------------------------

    def _refresh_groups(self, x, y):
        px, py = int(x // SECTOR_SIZE), int(y // SECTOR_SIZE)
        if (px, py) == self._scanned_sector:
            return
        self._scanned_sector = (px, py)
        for key in [k for k in self.groups
                    if max(abs(k[1] - px), abs(k[2] - py)) > KEEP_SECTORS]:
            del self.groups[key]
        (cx_lo, cx_hi), (cy_lo, cy_hi) = CITY_SECTORS_X, CITY_SECTORS_Y
        for sy in range(py - SCAN_SECTORS, py + SCAN_SECTORS + 1):
            for sx in range(px - SCAN_SECTORS, px + SCAN_SECTORS + 1):
                candidates = []
                if cx_lo <= sx < cx_hi and cy_lo <= sy < cy_hi:
                    candidates.append(("block", sx, sy, self._city_block))
                if (sx, sy) in CENTERS:
                    candidates.append(("plaza", sx, sy, self._plaza))
                if (sx, sy) in self.world.camps:
                    candidates.append(("camp", sx, sy, self._camp))
                elif 0 <= sx < 64 and 0 <= sy < 64 and self.world.region(sx, sy) == "rural":
                    candidates.append(("farm", sx, sy, self._farm))
                for kind, gx, gy, make in candidates:
                    key = (kind, gx, gy)
                    if key not in self.groups:
                        self.groups[key] = make(gx, gy, self._group_rng(key))

    def people(self):
        for group in self.groups.values():
            yield from group
        yield from self.walkers

    def update(self, dt: float, player_rect: list[float]):
        """Advance everyone; a pedestrian waits while the player stands right in front."""
        self._refresh_groups(player_rect[0], player_rect[1])
        px, py = player_rect[0], player_rect[1]
        # Center-to-center distance at which the gap between them drops below YIELD_AHEAD.
        reach = max(player_rect[7], player_rect[8]) / 2 + SOLID / 2 + YIELD_AHEAD
        for person in self.people():
            blocked = False
            person.overlapping_player = False
            dx, dy = px - person.x, py - person.y
            if abs(dx) < reach + SOLID and abs(dy) < reach + SOLID and not person.inside:
                record = [person.x, person.y, 0, 0, 0, 0, 0, SOLID, SOLID, 0]
                person.overlapping_player = bool(check_collision(record, [player_rect], "rect"))
                angle = math.radians(person.heading)
                ahead = dx * math.sin(angle) - dy * math.cos(angle)
                blocked = not person.overlapping_player and 0 < ahead < reach
            person.update(dt, self.rng, blocked)

    def sprites(self, camera_x, camera_y, width, height):
        margin = SIZE
        return [p.sprite() for p in self.people()
                if not p.inside and camera_x - margin <= p.x <= camera_x + width + margin
                and camera_y - margin <= p.y <= camera_y + height + margin]

    def nearby_obstacles(self, x, y):
        """Solid to the player, except anyone already overlapping them (never trapped)."""
        return [p.sprite() for p in self.people()
                if not p.inside and not p.overlapping_player
                and abs(p.x - x) < 60 and abs(p.y - y) < 60]

    def road_blockers(self):
        """People crossing a road, for traffic to stop for.

        Country road walkers stay on the shoulder, clear of the lanes, so only
        group members (city crosswalks) are checked.
        """
        return [[p.x, p.y, 0, 0, 0, 0, 0, SOLID + 4, SOLID + 4, 0]
                for group in self.groups.values() for p in group
                if not p.inside and self.world._road_style(int(p.x // TILE_SIZE),
                                                           int(p.y // TILE_SIZE))]
