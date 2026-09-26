"""Drag race missions: a separate, empty level (straight or single-lap circuit) and an AI rival.

TrackLevel stands in for World while racing: the player's Car and CollisionManager use its
region_at, can_place_car, and nearby_obstacles, so driving and crashes work unchanged.
"""

from __future__ import annotations

import math
import random

from car import ACCELERATION, BRAKING, TOP_SPEED, Car
from collision_manager import CollisionManager
from world import TILE_SIZE, Sprite


STRAIGHT_RACE_TILES = 63      # 63 x 64 px = 4,032 px = a quarter mile at 10 px per metre.
STRAIGHT_LEAD, STRAIGHT_RUNOFF = 4, 14
MARGIN_TILES = 10             # Ground drawn around the track.
TRACK_HALF = 1                # Track is 3 tiles wide: centerline cell +/- 1.
# Rectilinear single-lap circuits, centerline corners in tile units, driven clockwise.
CIRCUITS = (
    ((0, 0), (26, 0), (26, 14), (0, 14)),
    ((0, 0), (28, 0), (28, 10), (14, 10), (14, 18), (0, 18)),
    ((0, 0), (28, 0), (28, 18), (20, 18), (20, 8), (8, 8), (8, 18), (0, 18)),
)
THEMES = {  # Giver region -> (off-track ground tile, off-track surface for grip).
    "city": ("city_concrete", "city"), "rural": ("rural_grass", "rural"),
    "snow": ("snow", "snow"), "desert": ("desert_sand", "desert"),
    "jungle": ("jungle_ground", "jungle"),
}
COUNTDOWN = 3.0
CORNER_SPEED = 70.0           # AI corner speed at scale 1; a clean player line carries more.
AI_TURN_RATE = 300.0
RIVALS = ("racer_cyan", "racer_yellow", "racer_purple", "racer_orange",
          "racer_lime", "racer_blue", "racer_black")
# Edge art sits on a tile's north side; GL rotation is counterclockwise in degrees.
EDGE_ROTATION = {"N": 0.0, "W": 90.0, "S": 180.0, "E": -90.0}
CORNER_ROTATION = {frozenset("NW"): 0.0, frozenset("NE"): -90.0,
                   frozenset("SE"): 180.0, frozenset("SW"): 90.0}
DIAGONALS = {(-1, -1): 0.0, (1, -1): -90.0, (1, 1): 180.0, (-1, 1): 90.0}


def _cells_along(corners, closed):
    """Every tile on the centerline between successive corners."""
    cells = []
    pairs = zip(corners, corners[1:] + corners[:1]) if closed else zip(corners, corners[1:])
    for (ax, ay), (bx, by) in pairs:
        steps = max(abs(bx - ax), abs(by - ay))
        for i in range(steps):
            cells.append((ax + (bx - ax) * i // steps, ay + (by - ay) * i // steps))
    if not closed:
        cells.append(corners[-1])
    return cells


class TrackLevel:
    def __init__(self, kind: str, theme: str, shape: int = 0):
        self.kind = kind
        self.ground, self.off_surface = THEMES.get(theme, THEMES["city"])
        if kind == "straight":
            corners = [(0, 0), (STRAIGHT_LEAD + STRAIGHT_RACE_TILES + STRAIGHT_RUNOFF, 0)]
            self.closed = False
        else:
            corners = list(CIRCUITS[shape % len(CIRCUITS)])
            self.closed = True
        # Shift so the whole level (with margins) sits at positive coordinates.
        min_x = min(x for x, _ in corners) - MARGIN_TILES
        min_y = min(y for _, y in corners) - MARGIN_TILES
        self.corners = [(x - min_x, y - min_y) for x, y in corners]
        centerline = _cells_along(self.corners, self.closed)
        self.track = {(cx + i, cy + j) for cx, cy in centerline
                      for i in range(-TRACK_HALF, TRACK_HALF + 1)
                      for j in range(-TRACK_HALF, TRACK_HALF + 1)}
        self.cols = max(x for x, _ in self.track) + MARGIN_TILES + 1
        self.rows = max(y for _, y in self.track) + MARGIN_TILES + 1
        self.width, self.height = self.cols * TILE_SIZE, self.rows * TILE_SIZE
        # Centerline in pixels; the race runs from the start line along it.
        self.path = [((x + 0.5) * TILE_SIZE, (y + 0.5) * TILE_SIZE) for x, y in self.corners]
        start_col = self.corners[0][0] + STRAIGHT_LEAD
        self.start_x = (start_col + 0.5) * TILE_SIZE
        self.finish_x = (start_col + STRAIGHT_RACE_TILES + 0.5) * TILE_SIZE
        self.lap_length = sum(math.dist(a, b) for a, b in self._segments())
        self.sprites, self.obstacles = [], []
        self._build(start_col)
        self._bins = {}
        for sprite in self.sprites:
            self._bins.setdefault((int(sprite.x // 512), int(sprite.y // 512)), []).append(sprite)
        self._obstacle_bins = {}
        for sprite in self.obstacles:
            self._obstacle_bins.setdefault((int(sprite.x // 256), int(sprite.y // 256)), []).append(sprite)

    def _segments(self):
        points = self.path + (self.path[:1] if self.closed else [])
        return list(zip(points, points[1:]))

    def _build(self, start_col):
        track, sprites = self.track, self.sprites
        start_row = self.corners[0][1]
        for ty in range(self.rows):
            for tx in range(self.cols):
                x, y = (tx + 0.5) * TILE_SIZE, (ty + 0.5) * TILE_SIZE
                sprites.append(Sprite("terrain-atlas", self.ground, x, y, TILE_SIZE, TILE_SIZE))
                if (tx, ty) in track:
                    name, rotation = self._track_tile(tx, ty)
                    on_line = abs(ty - start_row) <= TRACK_HALF
                    if on_line and tx == start_col:
                        # A single lap starts and ends on the same checkered line.
                        name, rotation = ("track_finish" if self.closed else "track_start"), 0.0
                    elif on_line and not self.closed and tx == start_col + STRAIGHT_RACE_TILES:
                        name, rotation = "track_finish", 0.0
                    sprites.append(Sprite("track-atlas", name, x, y, TILE_SIZE, TILE_SIZE, rotation))
                    continue
                # Barriers wall off the track on both sides; tire stacks fill the corners.
                beside = [(dx, dy) for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                          if (tx + dx, ty + dy) in track]
                diagonal = any((tx + dx, ty + dy) in track for dx, dy in DIAGONALS)
                if len(beside) == 1:
                    horizontal = beside[0][0] == 0
                    # The solid box rotates with the sprite, like every obstacle record.
                    fence = Sprite("track-atlas", "track_fence", x, y, TILE_SIZE, TILE_SIZE,
                                   0.0 if horizontal else 90.0, TILE_SIZE, 16)
                    sprites.append(fence)
                    self.obstacles.append(fence)
                elif beside or diagonal:
                    tires = Sprite("track-atlas", "track_tires", x, y, TILE_SIZE, TILE_SIZE,
                                   0.0, 44, 44)
                    sprites.append(tires)
                    self.obstacles.append(tires)

    def _track_tile(self, tx, ty):
        off = [side for side, (dx, dy) in (("N", (0, -1)), ("S", (0, 1)), ("W", (-1, 0)), ("E", (1, 0)))
               if (tx + dx, ty + dy) not in self.track]
        if len(off) == 1:
            return "track_edge", EDGE_ROTATION[off[0]]
        if len(off) == 2 and frozenset(off) in CORNER_ROTATION:
            return "track_corner", CORNER_ROTATION[frozenset(off)]
        missing = [d for d in DIAGONALS if (tx + d[0], ty + d[1]) not in self.track]
        if not off and len(missing) == 1:
            return "track_inner", DIAGONALS[missing[0]]
        return "track_asphalt", 0.0

    # World stand-in -------------------------------------------------------------

    def region_at(self, x, y):
        return "track" if (int(x // TILE_SIZE), int(y // TILE_SIZE)) in self.track else self.off_surface

    def can_place_car(self, rect):
        return 0 <= rect[0] <= self.width and 0 <= rect[1] <= self.height

    def nearby_obstacles(self, x, y):
        bx, by = int(x // 256), int(y // 256)
        return [s for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                for s in self._obstacle_bins.get((bx + dx, by + dy), ())
                if abs(s.x - x) < 145 and abs(s.y - y) < 145]

    def visible_sprites(self, camera_x, camera_y, width, height):
        pad = TILE_SIZE
        x0, x1 = int((camera_x - pad) // 512), int((camera_x + width + pad) // 512)
        y0, y1 = int((camera_y - pad) // 512), int((camera_y + height + pad) // 512)
        return [s for by in range(y0, y1 + 1) for bx in range(x0, x1 + 1)
                for s in self._bins.get((bx, by), ())]

    # Race geometry ----------------------------------------------------------------

    def start_pose(self, lane: int):
        """Start behind the line; lane -1 is left of the centerline, +1 right."""
        (ax, ay), (bx, by) = self.path[0], self.path[1]
        heading = math.degrees(math.atan2(bx - ax, -(by - ay))) % 360
        fx, fy = (bx - ax) / math.dist((ax, ay), (bx, by)), (by - ay) / math.dist((ax, ay), (bx, by))
        rx, ry = -fy, fx
        back = 1.5 * TILE_SIZE
        line_x, line_y = self.start_x, ay
        return line_x - fx * back + rx * lane * 44, line_y - fy * back + ry * lane * 44, heading

    def progress_of(self, x, y, previous):
        """Distance driven along the course, kept continuous from the previous value."""
        if not self.closed:
            return x - self.start_x
        best, best_gap = previous, math.inf
        run = 0.0
        for (ax, ay), (bx, by) in self._segments():
            length = math.dist((ax, ay), (bx, by))
            t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / (length * length)))
            along = run + t * length - (self.start_x - self.path[0][0])
            distance = math.dist((x, y), (ax + (bx - ax) * t, ay + (by - ay) * t))
            # Pick the projection closest to where we were (handles the lap seam).
            laps = round((previous - along) / self.lap_length)
            candidate = along + laps * self.lap_length
            if distance < 160 and abs(candidate - previous) < best_gap:
                best, best_gap = candidate, abs(candidate - previous)
            run += length
        return best if best_gap < 300 else previous

    @property
    def race_length(self):
        return self.finish_x - self.start_x if not self.closed else self.lap_length


class Rival:
    """Follows the centerline (inside lane): full throttle on straights, brakes for corners."""

    def __init__(self, level: TrackLevel, scale: float, player_top: float, rng: random.Random):
        self.level = level
        self.name = rng.choice(RIVALS)
        self.top = player_top * scale
        self.accel = ACCELERATION * scale
        self.brake = BRAKING * 0.6 * scale
        self.corner = CORNER_SPEED * scale
        self.reaction = rng.uniform(0.2, 0.6)
        points = level.path + (level.path[:1] if level.closed else [])
        self.points = points
        self.lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        # Distances along the lap of the corners the AI brakes for. Circuits are
        # rectilinear, so every vertex after the first (and the lap seam) is a corner.
        self.corners = []
        run = 0.0
        for length in self.lengths[:-1] if not level.closed else self.lengths:
            run += length
            self.corners.append(run)
        self.offset = level.start_x - level.path[0][0] - 1.5 * TILE_SIZE  # Start behind the line.
        self.distance = self.offset
        self.speed = 0.0
        self.heading = level.start_pose(1)[2]
        self.x, self.y = level.start_pose(1)[:2]
        self.lane = 44  # Starts in the right lane and eases onto the centerline.

    @property
    def progress(self):
        return self.distance - (self.level.start_x - self.level.path[0][0])

    def update(self, dt, clock):
        if clock < self.reaction:
            return
        target = self.top
        lap = self.level.lap_length if self.level.closed else math.inf
        for corner in self.corners:
            ahead = (corner - self.distance) % lap if self.level.closed else corner - self.distance
            if 0 <= ahead:
                if self.speed ** 2 - self.corner ** 2 > 2 * self.brake * max(ahead - 8, 0):
                    target = self.corner
                break
        if self.speed < target:
            self.speed = min(target, self.speed + self.accel * dt)
        else:
            self.speed = max(target, self.speed - self.brake * dt)
        self.distance += self.speed * dt
        self.lane = max(0.0, self.lane - 30 * dt)
        self._place(dt)

    def _place(self, dt):
        run = self.distance % self.level.lap_length if self.level.closed else self.distance
        for (a, b), length in zip(zip(self.points, self.points[1:]), self.lengths):
            if run <= length or (a, b) == (self.points[-2], self.points[-1]):
                t = run / length
                fx, fy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
                self.x = a[0] + (b[0] - a[0]) * t - fy * self.lane
                self.y = a[1] + (b[1] - a[1]) * t + fx * self.lane
                target = math.degrees(math.atan2(fx, -fy)) % 360
                turn = (target - self.heading + 180) % 360 - 180
                step = AI_TURN_RATE * dt
                self.heading = (self.heading + max(-step, min(step, turn))) % 360
                return
            run -= length

    def sprite(self):
        return Sprite("vehicle-atlas", self.name, self.x, self.y, 64, 64, -self.heading, 24, 44)


class DragRace:
    """One race: countdown, both racers go, first across the finish wins."""

    def __init__(self, track: dict, scale: float, speed_scale: float, seed: int):
        rng = random.Random(seed)
        self.level = TrackLevel(track["kind"], track.get("theme", "city"), track.get("shape", 0))
        self.speed_scale = speed_scale
        x, y, heading = self.level.start_pose(-1)
        self.car = Car(x=x, y=y, heading=heading)
        # The rival scales the base car, not the player's upgrades: levels are the player's edge.
        self.rival = Rival(self.level, scale, TOP_SPEED, rng)
        self.collisions = CollisionManager(None, self.level)
        self.clock = -COUNTDOWN     # Negative while counting down.
        self.player_progress = self.level.progress_of(x, y, -1.5 * TILE_SIZE) \
            if self.level.closed else x - self.level.start_x
        self.result = None          # "win" or "lose" once decided.
        self.times = {}

    @property
    def countdown(self):
        return max(0, math.ceil(-self.clock)) if self.clock < 0 else 0

    def update(self, dt, throttle, steer, handbrake):
        if self.result:
            self.car.speed *= max(0.0, 1 - 2 * dt)
            return
        self.clock += dt
        if self.clock < 0:
            return
        # The rival is solid to the player; it holds its line regardless.
        self.collisions.fixed = [self.rival.sprite()]
        self.car.update(dt, throttle, steer, handbrake, self.level, self.collisions,
                        self.speed_scale)
        self.rival.update(dt, self.clock)
        self.player_progress = self.level.progress_of(self.car.x, self.car.y, self.player_progress)
        length = self.level.race_length
        if self.player_progress >= length and "player" not in self.times:
            self.times["player"] = self.clock
        if self.rival.progress >= length and "rival" not in self.times:
            self.times["rival"] = self.clock
        if self.times:
            self.result = "win" if "player" in self.times and (
                "rival" not in self.times or self.times["player"] <= self.times["rival"]) else "lose"

    def position(self):
        return 1 if self.player_progress >= self.rival.progress else 2

    def sprites(self, camera_x, camera_y, width, height):
        return self.level.visible_sprites(camera_x, camera_y, width, height) + [self.rival.sprite()]
