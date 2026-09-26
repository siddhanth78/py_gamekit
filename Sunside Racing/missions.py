"""Mission givers, offers, and in-world missions (delivery and time trial).

Drag races are accepted here but run in drag_race.DragRace, a separate level; their
result comes back through finish_drag(). At most one mission is ongoing. Ongoing missions
are never saved: quitting the game quits the mission (the giver keeps its offer, and the
save puts the player back at the giver), exactly like aborting it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from car import OFF_SURFACE, SURFACES, TOP_SPEED
from collision_manager import CollisionManager, nearest_clear_spot
from progression import FAST_TRAVEL_LEVEL, REGIONS, Progress, reward
from walker import Walker
from world import CENTERS, SECTOR_SIZE, SECTORS, TILE_SIZE, Sprite


TYPES = ("delivery", "speed", "drag")
# The "speed" key is the time trial (it was once called the speed check); saves use the key.
TITLES = {"delivery": "Delivery", "speed": "Time Trial", "drag": "Drag Race"}
BASE_REWARD = {"delivery": 2, "speed": 1, "drag": 3}  # Delivery at 75+ points; 1 at 50+.
DELIVERY_PENALTY = {"Easy": 5, "Medium": 10, "Hard": 15}
DELIVERY_TIERS = ((75, 2), (50, 1))
CRASH_GRACE = 1.0            # Seconds after a crash before another one counts.
TALK_RANGE = 40              # On foot, px from a giver to talk.
DROP_RANGE = 64              # px from the recipient (on foot or in the car) to deliver.
FINISH_RANGE = 90            # px from the speed-check finish, in the car.
DETOUR = 1.3                 # Straight-line distance x this approximates the drive.
SPEED_EFFICIENCY = 0.8       # Timer assumes 80% of top speed the whole way.
DELIVERY_DISTANCE = (3000, 15000)  # px (10 px = 1 m): 0.3-1.5 km, often another region.
SPEED_DISTANCE = (2000, 6000)
GIVER_RADIUS = 200           # Givers stand about this far from their racing center.
BASE_ANGLES = (200, 240, 280)   # Degrees (screen, y down) for delivery, speed, drag givers.
HARDER_ANGLES = (330, 10, 50)
GIVER_KINDS = {"city": "city_d", "rural": "farmer_b", "snow": "snow_a",
               "desert": "nomad_b", "jungle": "explorer_a"}


def difficulty(scale: float) -> str:
    return "Easy" if scale < 0.8 else "Medium" if scale < 1.05 else "Hard"


@dataclass
class Giver:
    id: str
    region: str
    type: str
    harder: bool
    x: float
    y: float

    @property
    def name(self):
        return f"{'Veteran ' if self.harder else ''}{self.region.title()} {TITLES[self.type]}"


@dataclass
class Offer:
    giver_id: str
    type: str
    scale: float
    target: tuple[float, float] | None = None   # Delivery recipient or speed-check finish.
    track: dict | None = None                   # Drag race level: kind, shape, theme.
    seed: int = 0

    def to_dict(self):
        return {"type": self.type, "scale": self.scale,
                "target": list(self.target) if self.target else None,
                "track": self.track, "seed": self.seed}

    @classmethod
    def from_dict(cls, giver_id, data):
        """Validated rebuild; raises ValueError for anything malformed."""
        if not isinstance(data, dict) or data.get("type") not in TYPES:
            raise ValueError("bad offer")
        scale = data.get("scale")
        if type(scale) not in (int, float) or not 0.5 <= scale <= 1.25:
            raise ValueError("bad scale")
        target = data.get("target")
        if target is not None:
            if (not isinstance(target, list) or len(target) != 2
                    or not all(type(v) in (int, float) and math.isfinite(v) for v in target)):
                raise ValueError("bad target")
            target = tuple(target)
        track = data.get("track")
        if track is not None and (not isinstance(track, dict)
                                  or track.get("kind") not in ("straight", "circuit")):
            raise ValueError("bad track")
        if (data["type"] == "drag") != (track is not None) or (data["type"] != "drag") != (target is not None):
            raise ValueError("offer shape does not match its type")
        return cls(giver_id, data["type"], float(scale), target, track, int(data.get("seed", 0)))


class ActiveMission:
    def __init__(self, offer: Offer, giver: Giver, time_limit: float = 0.0):
        self.offer, self.giver = offer, giver
        self.label = difficulty(offer.scale)
        self.points = 100
        self.crashes = 0
        self.grace = 0.0
        self.flash = 0.0           # Seconds left on the "crash" flash.
        self.time_limit = time_limit
        self.time_left = time_limit
        self.started = False       # Time trial: the clock starts once you drive off.


class Missions:
    def __init__(self, world, seed: int, data: dict | None = None):
        self.world = world
        self.seed = seed
        data = data if isinstance(data, dict) else {}
        self.progress = Progress(data.get("progress"))
        self.counter = data.get("counter") if type(data.get("counter")) is int else 0
        self.givers = self._place_givers()
        self.by_id = {g.id: g for g in self.givers}
        self.offers: dict[str, Offer] = {}
        for giver_id, offer in (data.get("offers") or {}).items():
            if giver_id in self.by_id:
                try:
                    parsed = Offer.from_dict(giver_id, offer)
                    if parsed.type == self.by_id[giver_id].type:
                        self.offers[giver_id] = parsed
                except (ValueError, TypeError):
                    pass
        # Saves from before this revamp may hold a "queued" mission; it is ignored.
        self.active: ActiveMission | None = None

    # Placement ------------------------------------------------------------------

    def _place_givers(self):
        """Stand three givers (plus three harder ones) on open ground near each center."""
        probe_collisions = CollisionManager(None, self.world)
        givers = []
        for (sx, sy), center in CENTERS.items():
            region = center.removeprefix("center_")
            if region not in REGIONS:
                continue  # The island has no givers.
            cx, cy = self.world.center_position(sx, sy)
            for harder, angles in ((False, BASE_ANGLES), (True, HARDER_ANGLES)):
                for mission_type, angle in zip(TYPES, angles):
                    ax = cx + math.cos(math.radians(angle)) * GIVER_RADIUS
                    ay = cy + math.sin(math.radians(angle)) * GIVER_RADIUS
                    spot = self._open_spot(probe_collisions, ax, ay, region, givers)
                    if spot:
                        gid = f"{region}-{mission_type}{'-hard' if harder else ''}"
                        givers.append(Giver(gid, region, mission_type, harder, *spot))
        return givers

    def _open_spot(self, collisions, x, y, region=None, others=(), clearance=24):
        """Nearest clear, off-road spot a person can stand on (and a car can reach)."""
        world = self.world

        class OffRoad:
            def can_move(self, rect):
                tx, ty = int(rect[0] // TILE_SIZE), int(rect[1] // TILE_SIZE)
                if world._road_style(tx, ty) or world.region_at(rect[0], rect[1]) in ("sea", "island"):
                    return False
                if region and world.region_at(rect[0], rect[1]) != region:
                    return False
                if any(math.dist((rect[0], rect[1]), (o.x, o.y)) < 48 for o in others):
                    return False
                return collisions.can_move(rect)

        return nearest_clear_spot(OffRoad(), Walker(x, y).collision_record, x, y, clearance, 200)

    # Offers ---------------------------------------------------------------------

    def visible_givers(self):
        return [g for g in self.givers if not g.harder or self.progress.harder_unlocked(g.region)]

    def offer_for(self, giver: Giver) -> Offer:
        if giver.id not in self.offers:
            self.offers[giver.id] = self._new_offer(giver)
        return self.offers[giver.id]

    def _new_offer(self, giver: Giver) -> Offer:
        self.counter += 1
        rng = random.Random(f"{self.seed}-{giver.id}-{self.counter}")
        scale = round(rng.uniform(0.8 if giver.harder else 0.5, 1.25), 3)
        seed = rng.randrange(1 << 30)
        if giver.type == "drag":
            kind = rng.choice(("straight", "circuit"))
            track = {"kind": kind, "theme": giver.region}
            if kind == "circuit":
                track.update(seed=seed, size=rng.randint(4, 7))  # Its own generated layout.
            return Offer(giver.id, "drag", scale, None, track, seed)
        low, high = DELIVERY_DISTANCE if giver.type == "delivery" else SPEED_DISTANCE
        collisions = CollisionManager(None, self.world)
        for _ in range(40):
            angle, distance = rng.uniform(0, 2 * math.pi), rng.uniform(low, high)
            x = giver.x + math.cos(angle) * distance
            y = giver.y + math.sin(angle) * distance
            if not (0 < x < SECTORS * SECTOR_SIZE and 0 < y < SECTORS * SECTOR_SIZE):
                continue
            if self.world.region_at(x, y) in ("sea", "island"):
                continue
            spot = self._open_spot(collisions, x, y, clearance=32)
            if spot and low * 0.8 <= math.dist(spot, (giver.x, giver.y)):
                return Offer(giver.id, giver.type, scale, spot, None, seed)
        # Fall back to another racing center, which always has open ground around it.
        sector = rng.choice([s for s, n in CENTERS.items() if n != "center_island"])
        cx, cy = self.world.center_position(*sector)
        return Offer(giver.id, giver.type, scale, self._open_spot(collisions, cx, cy + 220), None, seed)

    def speed_limit(self, offer: Offer, start) -> float:
        """Timer: distance x DETOUR at 80% x scale of the top speed of the ground covered."""
        (ax, ay), (bx, by) = start, offer.target
        steps = max(1, int(math.dist(start, offer.target) // 64))
        seconds = 0.0
        for i in range(steps):
            x, y = ax + (bx - ax) * (i + 0.5) / steps, ay + (by - ay) * (i + 0.5) / steps
            region = self.world.region_at(x, y)
            top = SURFACES.get(region, OFF_SURFACE)[1] * self.progress.speed_scale(region)
            seconds += math.dist(start, offer.target) / steps * DETOUR / (
                top * SPEED_EFFICIENCY * offer.scale)
        return seconds

    def reward_for(self, offer: Offer, base: int) -> int:
        giver = self.by_id[offer.giver_id]
        return reward(base, self.progress.levels[giver.region], giver.harder)

    def preview(self, offer: Offer) -> dict:
        """What the offer panel shows."""
        giver = self.by_id[offer.giver_id]
        label = difficulty(offer.scale)
        lines = {"title": giver.name, "difficulty": label}
        if offer.type == "delivery":
            where = self.world.region_at(*offer.target).title()
            km = math.dist((giver.x, giver.y), offer.target) / 10000
            lines["detail"] = f"Deliver a package to {where}, {km:.1f} km away"
            lines["rules"] = f"No time limit  ·  -{DELIVERY_PENALTY[label]} points per crash"
            lines["reward"] = (f"75+ points: {self.reward_for(offer, 2)} mastery  ·  "
                               f"50+: {self.reward_for(offer, 1)}")
        elif offer.type == "speed":
            limit = self.speed_limit(offer, (giver.x, giver.y))
            km = math.dist((giver.x, giver.y), offer.target) / 10000
            lines["detail"] = f"Reach the checkpoint {km:.1f} km away"
            lines["rules"] = f"Time limit {limit:.0f} s  ·  clock starts when you drive off"
            lines["reward"] = f"Beat the clock: {self.reward_for(offer, 1)} mastery"
        else:
            track = "quarter-mile straight" if offer.track["kind"] == "straight" else "single-lap circuit"
            lines["detail"] = f"Race a rival on a {track}"
            lines["rules"] = f"Rival at {offer.scale:.2f}x a stock car"
            lines["reward"] = f"Win: {self.reward_for(offer, 3)} mastery"
        return lines

    # Running missions -------------------------------------------------------------

    def accept(self, giver: Giver) -> Offer:
        """Start the giver's offer. Returns it; drag races are run by the caller."""
        offer = self.offer_for(giver)
        limit = self.speed_limit(offer, (giver.x, giver.y)) if offer.type == "speed" else 0.0
        self.active = ActiveMission(offer, giver, limit)
        return offer

    def update(self, dt: float, player_x: float, player_y: float, in_car: bool,
               moving: bool, crashed: bool):
        """Advance an in-world mission. Returns a result dict when it ends, else None."""
        mission = self.active
        if mission is None or mission.offer.type == "drag":
            return None
        mission.grace = max(0.0, mission.grace - dt)
        mission.flash = max(0.0, mission.flash - dt)
        target = mission.offer.target
        if mission.offer.type == "delivery":
            if crashed and in_car and mission.grace <= 0:
                mission.crashes += 1
                mission.points -= DELIVERY_PENALTY[mission.label]
                mission.grace, mission.flash = CRASH_GRACE, 1.0
                if mission.points < 50:
                    return self._finish(False, f"Too many crashes: {mission.points} points")
            if math.dist((player_x, player_y), target) <= DROP_RANGE:
                base = next((m for need, m in DELIVERY_TIERS if mission.points >= need), 0)
                return self._finish(True, f"Delivered with {mission.points} points", base)
            return None
        # Time trial.
        if not mission.started and in_car and moving:
            mission.started = True
        if mission.started:
            mission.time_left -= dt
            if in_car and math.dist((player_x, player_y), target) <= FINISH_RANGE:
                spare = mission.time_left
                return self._finish(True, f"Made it with {spare:.1f} s to spare", BASE_REWARD["speed"])
            if mission.time_left <= 0:
                return self._finish(False, "Out of time")
        return None

    def abort(self):
        """Give up the ongoing mission: it counts as failed, and the offer stays for a retry."""
        return self._finish(False, "You abandoned the mission")

    def finish_drag(self, won: bool, detail: str):
        return self._finish(won, detail, BASE_REWARD["drag"] if won else 0)

    def _finish(self, success: bool, detail: str, base: int = 0):
        mission = self.active
        giver = mission.giver
        earned = self.reward_for(mission.offer, base) if success else 0
        levels = self.progress.add(giver.region, earned) if earned else []
        if success:
            self.progress.record_completion(giver.region, mission.offer.type)
            del self.offers[giver.id]  # The giver has a fresh mission ready.
        self.active = None
        return {"success": success, "title": giver.name, "detail": detail, "mastery": earned,
                "region": giver.region, "levels": levels, "giver": giver,
                "level": self.progress.levels[giver.region],
                "progress": (self.progress.mastery[giver.region],
                             10 * self.progress.levels[giver.region])}

    # Display ----------------------------------------------------------------------

    def target(self):
        """Where the guide arrow should point, or None to point at the racing center."""
        if self.active and self.active.offer.target:
            return self.active.offer.target
        return None

    def status(self):
        """(title, line) for the HUD's mission panel, or None."""
        if self.active:
            m = self.active
            title = f"{TITLES[m.offer.type].upper()}  ·  {m.label.upper()}"
            if m.offer.type == "delivery":
                line = f"CRASH  -{DELIVERY_PENALTY[m.label]}" if m.flash else \
                    f"Points {m.points}  ·  Crashes {m.crashes}"
            elif m.offer.type == "speed":
                line = f"Time {max(0.0, m.time_left):.1f} s" if m.started else \
                    f"{m.time_limit:.0f} s  ·  starts when you drive"
            else:
                line = "Racing"
            return title, line
        return None

    def sprites(self, clock: float):
        """Givers with bobbing badges, plus the active mission's recipient or finish."""
        out = []
        bob = math.sin(clock * 3) * 3
        busy = self.active is not None
        for giver in self.visible_givers():
            kind = GIVER_KINDS[giver.region]
            out.append(Sprite("people-atlas", f"{kind}_idle", giver.x, giver.y, 32, 32, 180.0))
            if not busy:
                icon = f"icon_{giver.type}{'_hard' if giver.harder else ''}"
                out.append(Sprite("marker-atlas", icon, giver.x, giver.y - 34 + bob, 32, 32))
        if self.active and self.active.offer.target:
            x, y = self.active.offer.target
            if self.active.offer.type == "delivery":
                out.append(Sprite("people-atlas", "city_c_idle", x, y, 32, 32, 180.0))
                out.append(Sprite("marker-atlas", "icon_dropoff", x, y - 34 + bob, 32, 32))
            else:
                out.append(Sprite("prop-atlas", "race_finish", x, y, 96, 96))
                out.append(Sprite("marker-atlas", "icon_finish", x, y - 60 + bob, 32, 32))
        return out

    def mastery_rows(self, here: str = ""):
        """One row per region for the pause menu's mastery page; here is the player's region."""
        rows = []
        for region in REGIONS:
            level = self.progress.levels[region]
            mission = ""
            if self.active and self.active.giver.region == region:
                mission = f"Ongoing  ·  {TITLES[self.active.offer.type]}"
            rows.append({
                "region": region, "level": level,
                "mastery": self.progress.mastery[region], "need": 10 * level,
                "speed": round((self.progress.speed_scale(region) - 1) * 100),
                "veterans": self.progress.harder_unlocked(region),
                "completed": dict(self.progress.completed[region]),
                "mission": mission,
                "races": self.progress.races[region],
                # ready / here / busy (a mission is running) / locked (below level 3).
                "travel": ("locked" if level < FAST_TRAVEL_LEVEL else "here" if region == here
                           else "busy" if self.active else "ready"),
            })
        return rows

    def center_position(self, region: str):
        sector = next(sec for sec, name in CENTERS.items() if name == f"center_{region}")
        return self.world.center_position(*sector)

    def giver_near(self, x, y):
        return next((g for g in self.visible_givers()
                     if math.dist((x, y), (g.x, g.y)) <= TALK_RANGE), None)

    def to_dict(self):
        # The ongoing mission is deliberately absent: its offer stays with its giver.
        return {"progress": self.progress.to_dict(), "counter": self.counter,
                "offers": {gid: offer.to_dict() for gid, offer in self.offers.items()}}
