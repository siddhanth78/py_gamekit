"""Race levels: separate, empty tracks (straight or circuit) with one AI rival.

Used by drag race missions (a quarter mile or a single lap) and racing-center races
(3 laps). Each track uses its region's surface (city asphalt, snow ice, rural mud,
desert sand, jungle grass) with that region's grip and top speed.

TrackLevel stands in for World while racing: the player's Car and CollisionManager use its
region_at, can_place_car, and nearby_obstacles, so driving and crashes work unchanged.
"""

from __future__ import annotations

import math
import random

from car import ACCELERATION, BRAKING, SURFACES, Car
from collision_manager import CollisionManager
from progression import SPEED_PER_LEVEL
from track_gen import generate
from traffic import lane_path
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
    ((0, 0), (20, 0), (20, 6), (30, 6), (30, 16), (12, 16), (12, 10), (0, 10)),
    ((0, 0), (34, 0), (34, 10), (0, 10)),
)
# Region -> off-track ground tile. The track itself is that region's surface, driven with
# the region's grip and top speed (car.SURFACES); the runoff off the track is slower.
THEMES = {"city": "city_concrete", "rural": "rural_grass", "snow": "snow",
          "desert": "desert_sand", "jungle": "jungle_ground"}
OFF_TRACK = "offtrack"        # Not in car.SURFACES, so it drives with car.OFF_SURFACE.
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
    def __init__(self, kind: str, theme: str, shape: int = 0, laps: int = 1,
                 corners=None):
        """corners: a generated circuit (track_gen); otherwise the fixed layout `shape`."""
        self.kind = kind
        self.surface = theme if theme in THEMES else "city"
        self.ground = THEMES[self.surface]
        self.laps = laps if kind == "circuit" else 1
        if kind == "straight":
            corners = [(0, 0), (STRAIGHT_LEAD + STRAIGHT_RACE_TILES + STRAIGHT_RUNOFF, 0)]
            self.closed = False
        else:
            corners = list(corners or CIRCUITS[shape % len(CIRCUITS)])
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
                        name, rotation = self._tile("finish" if self.closed else "start"), 0.0
                    elif on_line and not self.closed and tx == start_col + STRAIGHT_RACE_TILES:
                        name, rotation = self._tile("finish"), 0.0
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
            return self._tile("edge"), EDGE_ROTATION[off[0]]
        if len(off) == 2 and frozenset(off) in CORNER_ROTATION:
            return self._tile("corner"), CORNER_ROTATION[frozenset(off)]
        missing = [d for d in DIAGONALS if (tx + d[0], ty + d[1]) not in self.track]
        if not off and len(missing) == 1:
            return self._tile("inner"), DIAGONALS[missing[0]]
        return self._tile("base"), 0.0

    def _tile(self, part):
        return f"track_{self.surface}_{part}"

    # World stand-in -------------------------------------------------------------

    def region_at(self, x, y):
        on_track = (int(x // TILE_SIZE), int(y // TILE_SIZE)) in self.track
        return self.surface if on_track else OFF_TRACK

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
        return self.finish_x - self.start_x if not self.closed else self.lap_length * self.laps


APEX = 84                     # A cut corner's apex: this far inside the centerline corner.
CUT_REACH = 2 * APEX          # A cut is one straight diagonal (a 45-degree chamfer): leave
                              # the centerline this far before the corner and rejoin this far
                              # after, and the diagonal passes exactly through the apex.


def _toward(point, other, distance):
    """The point `distance` px from point in the direction of other."""
    length = math.dist(point, other)
    return (point[0] + (other[0] - point[0]) * distance / length,
            point[1] + (other[1] - point[1]) * distance / length)


def apex(prev, corner, following):
    """Inside apex of a centerline corner (the tightest line a car can take through it)."""
    (ax, ay), (px, py), (bx, by) = prev, corner, following
    cross = (px - ax) * (by - py) - (py - ay) * (bx - px)  # > 0: a right turn (screen y down).
    return lane_path([prev, corner, following], APEX if cross > 0 else -APEX)[1]


def best_line_length(level: TrackLevel) -> float:
    """Race distance on the ideal line: every corner cut at its apex."""
    if not level.closed:
        return level.race_length
    pts, n = level.path, len(level.path)
    apexes = [apex(pts[i - 1], pts[i], pts[(i + 1) % n]) for i in range(n)]
    lap = sum(math.dist(apexes[i], apexes[(i + 1) % n]) for i in range(n))
    return lap * level.laps


class Rival:
    """Drives a line fixed for the whole race: full throttle on straights, braking for
    every corner. On 3-lap center races it cuts each corner with probability cut_chance
    (seeded, so a race always plays out the same way); drag rivals never cut."""

    def __init__(self, level: TrackLevel, scale: float, rng: random.Random,
                 sprite: str | None = None, cut_chance: float = 0.0):
        self.level = level
        self.name = sprite or rng.choice(RIVALS)
        self.reaction = rng.uniform(0.2, 0.6)
        self.set_scale(scale)
        x, y, self.heading = level.start_pose(1)  # Starts in the right-hand grid slot.
        points, self.cuts = [(x, y)], 0
        brake_points = set()  # Indexes into points where the rival slows for a corner.
        if level.closed:
            pts, n = level.path, len(level.path)
            # Merge from the grid slot onto the centerline right away (the first corner is
            # at least 3 tiles ahead, and a cut leaves the centerline only 1.5 tiles early).
            points.append((x + TILE_SIZE, pts[0][1]))
            # One extra lap of path so the car never runs out of road before it finishes.
            for _ in range(level.laps + 1):
                for i in list(range(1, n)) + [0]:
                    prev, corner, following = pts[i - 1], pts[i], pts[(i + 1) % n]
                    if rng.random() < cut_chance:
                        # Cut only the corner, in one diagonal through its apex; the rival
                        # brakes where the diagonal begins and the straights stay central.
                        self.cuts += 1
                        brake_points.add(len(points))
                        points.append(_toward(corner, prev, CUT_REACH))
                        points.append(_toward(corner, following, CUT_REACH))
                    else:
                        brake_points.add(len(points))
                        points.append(corner)
            if points[2][0] <= points[1][0]:
                # The first corner's cut begins before the merge point: steer straight for
                # the diagonal instead of doubling back.
                points.pop(1)
                brake_points = {i - 1 for i in brake_points}
        else:
            points.append((level.finish_x + 8 * TILE_SIZE, y))
        self.points = points
        self.lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
        # Distances along the path of every corner (a centerline corner or a cut apex).
        self.corners, run = [], 0.0
        for index, length in enumerate(self.lengths, start=1):
            run += length
            if index in brake_points:
                self.corners.append(run)
        self.distance, self.speed = 0.0, 0.0
        self.x, self.y = x, y
        self.progress = (level.progress_of(x, y, -1.5 * TILE_SIZE) if level.closed
                         else x - level.start_x)

    def set_scale(self, scale: float):
        """Scale the base car on this surface (not the player's upgrades: levels are the
        player's edge). Grip limits acceleration, braking, and cornering, as for the player."""
        grip, top = SURFACES[self.level.surface]
        self.scale = scale
        self.top = top * scale
        self.accel = ACCELERATION * grip * scale
        self.brake = BRAKING * 0.6 * grip * scale
        self.corner = CORNER_SPEED * grip * scale

    def update(self, dt, clock):
        if clock < self.reaction:
            return
        target = self.top
        for corner in self.corners:
            ahead = corner - self.distance
            if ahead >= 0:
                if self.speed ** 2 - self.corner ** 2 > 2 * self.brake * max(ahead - 8, 0):
                    target = self.corner
                break
        if self.speed < target:
            self.speed = min(target, self.speed + self.accel * dt)
        else:
            self.speed = max(target, self.speed - self.brake * dt)
        self.distance += self.speed * dt
        self._place(dt)
        # Race progress is measured on the centerline, exactly like the player's.
        self.progress = self.level.progress_of(self.x, self.y, self.progress)

    def _place(self, dt):
        run = self.distance
        last = len(self.lengths) - 1
        # Corners repeat every lap, so the final segment is found by index, not by point.
        for i, ((a, b), length) in enumerate(zip(zip(self.points, self.points[1:]), self.lengths)):
            if run <= length or i == last:
                t = min(1.0, run / length)
                self.x, self.y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                target = math.degrees(math.atan2(b[0] - a[0], -(b[1] - a[1]))) % 360
                turn = (target - self.heading + 180) % 360 - 180
                step = AI_TURN_RATE * dt
                self.heading = (self.heading + max(-step, min(step, turn))) % 360
                return
            run -= length

    def sprite(self):
        return Sprite("vehicle-atlas", self.name, self.x, self.y, 64, 64, -self.heading, 24, 44)


def level_multiplier(region_level: int) -> float:
    return 1 + SPEED_PER_LEVEL * (region_level - 1)


def flawless_time(level: TrackLevel, region_level: int = 1, multiplier: float | None = None) -> float:
    """Race time of a flawless player: flat out on the ideal line (every corner cut),
    at region_level (or a given top-speed multiplier)."""
    grip, top = SURFACES[level.surface]
    speed = top * (multiplier if multiplier is not None else level_multiplier(region_level))
    accel = ACCELERATION * grip
    distance = best_line_length(level) + 1.5 * TILE_SIZE  # Grid slot is behind the line.
    return speed / accel + (distance - speed * speed / (2 * accel)) / speed


def rival_time(level: TrackLevel, rival_seed: int, cut_chance: float, scale: float = 1.0) -> float:
    """Seconds this exact rival (same seeded line) needs at this scale, ignoring reaction."""
    rival = Rival(level, scale, random.Random(rival_seed), cut_chance=cut_chance)
    seconds, dt = 0.0, 1 / 60  # The game's rate; near level 20 one level is only ~2% speed.
    while rival.progress < level.race_length:
        rival.update(dt, rival.reaction)
        seconds += dt
        if seconds > 1200:  # Twenty minutes: the rival is stuck, not slow.
            raise RuntimeError("rival never finished the calibration run")
    return seconds


def calibrated_scale(level: TrackLevel, multiplier: float, rival_seed: int,
                     cut_chance: float = 0.0, margin: float = 1.0) -> float:
    """Rival scale at which a flawless player with this top-speed multiplier wins by margin.

    Race time falls roughly as 1 / scale, but not exactly (acceleration and braking also
    scale), so start from that estimate and correct it with a few runs of the same
    seeded rival until it lands within 0.02 s of the target."""
    target = flawless_time(level, multiplier=multiplier) * margin
    scale = rival_time(level, rival_seed, cut_chance) / target
    for _ in range(6):
        seconds = rival_time(level, rival_seed, cut_chance, scale)
        if abs(seconds - target) < 0.02:
            break
        scale *= seconds / target
    return round(scale, 4)


class DragRace:
    """One race: countdown, both racers go, first across the finish wins."""

    def __init__(self, track: dict, scale: float | None, speed_scale: float, seed: int,
                 rival_sprite: str | None = None):
        rng = random.Random(seed)
        corners = (generate(track["seed"], track.get("size", 5))
                   if track["kind"] == "circuit" and "seed" in track else None)
        self.level = TrackLevel(track["kind"], track.get("theme", "city"), track.get("shape", 0),
                                track.get("laps", 1), corners)
        self.speed_scale = speed_scale
        x, y, heading = self.level.start_pose(-1)
        self.car = Car(x=x, y=y, heading=heading)
        cut_chance = track.get("cut_chance", 0.0)  # Only racing-center rivals cut corners.
        rival_seed = rng.randrange(1 << 30)
        if self.level.closed:
            if scale is None:
                # Center race: a flawless driver at target_level, on the ideal line, just wins.
                multiplier, margin = level_multiplier(track["target_level"]), 1.005
            else:
                # Drag circuit: the offer's scale means "a flawless s x stock car on the ideal
                # line", the same meaning it has on a straight.
                multiplier, margin = scale, 1.0
            scale = calibrated_scale(self.level, multiplier, rival_seed, cut_chance, margin)
        self.rival = Rival(self.level, scale, random.Random(rival_seed), rival_sprite, cut_chance)
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

    def lap(self):
        """Current lap (1-based) of the player, for multi-lap races."""
        if not self.level.closed:
            return 1
        return max(1, min(self.level.laps, int(self.player_progress // self.level.lap_length) + 1))

    def sprites(self, camera_x, camera_y, width, height):
        return self.level.visible_sprites(camera_x, camera_y, width, height) + [self.rival.sprite()]
