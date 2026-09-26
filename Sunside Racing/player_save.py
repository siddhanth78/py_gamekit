"""Read and atomically write the player's local save file."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path

from car import Car
from walker import Walker, exit_spot


# Version 2 added the mode and the walker; version 3 adds missions and progression.
# Versions 1 and 2 still load.
SAVE_VERSION = 3
READABLE_VERSIONS = (1, 2, 3)
APP_NAME = "pygamekit-racer"


def default_save_path() -> Path:
    """Keep the player's save beside this game's source files."""
    return Path(__file__).resolve().parent / "player.json"


def legacy_save_path() -> Path:
    """Location used by earlier versions, for one-way save migration."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME / "player.json"


def _number(value) -> float:
    if type(value) not in (int, float):
        raise ValueError("Save coordinates and heading must be finite numbers")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("Save coordinates and heading must be finite numbers") from exc
    if not math.isfinite(number):
        raise ValueError("Save coordinates and heading must be finite numbers")
    return number


def _pose(thing) -> dict:
    return {"x": _number(thing.x), "y": _number(thing.y),
            "heading": _number(thing.heading) % 360}


class PlayerSave:
    def __init__(self, path: Path | None = None, legacy_path: Path | None = None):
        self.path = Path(path) if path is not None else default_save_path()
        self.legacy_path = Path(legacy_path) if legacy_path is not None else (
            legacy_save_path() if path is None else None
        )
        # Mission and progression state from the last load (validated by missions.Missions).
        self.missions_data: dict | None = None

    def load(self, collisions) -> Car | None:
        """Return a stationary car at a valid saved position, if available."""
        return self.load_state(collisions)[0]

    def load_state(self, collisions) -> tuple[Car | None, Walker | None]:
        """Return (car, walker); walker is set only when the save was made on foot."""
        source = self.path
        if not source.exists() and self.legacy_path is not None:
            source = self.legacy_path
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, None
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"Ignoring unreadable player save: {exc}", file=sys.stderr)
            return None, None

        try:
            if not isinstance(payload, dict) or type(payload.get("version")) is not int:
                raise ValueError("Missing save version")
            if payload["version"] not in READABLE_VERSIONS:
                raise ValueError(f"Unsupported save version {payload['version']}")
            state = payload["car" if payload["version"] >= 2 else "player"]
            if not isinstance(state, dict):
                raise ValueError("Missing car state")
            car = Car(
                x=_number(state["x"]),
                y=_number(state["y"]),
                heading=_number(state["heading"]) % 360,
                speed=0.0,
            )
            if not collisions.can_move(car.collision_record()):
                raise ValueError("Saved car position is blocked or outside the world")
            missions = payload.get("missions")
            self.missions_data = missions if isinstance(missions, dict) else None
            mode = payload.get("mode", "drive")
            if mode not in ("drive", "walk"):
                raise ValueError(f"Unknown save mode {mode!r}")
        except (KeyError, ValueError) as exc:
            print(f"Ignoring invalid player save: {exc}", file=sys.stderr)
            return None, None
        return car, (self._load_walker(payload.get("walker"), car, collisions)
                     if mode == "walk" else None)

    @staticmethod
    def _load_walker(state, car, collisions) -> Walker | None:
        """Resume on foot where saved; else step out beside the car; else drive."""
        walker = None
        try:
            if not isinstance(state, dict):
                raise ValueError("Missing walker state")
            walker = Walker(x=_number(state["x"]), y=_number(state["y"]),
                            heading=_number(state["heading"]) % 360)
        except (KeyError, ValueError) as exc:
            print(f"Ignoring invalid walker save: {exc}", file=sys.stderr)
        if walker is not None:
            saved_fixed = collisions.fixed
            collisions.fixed = [car.obstacle()]  # The parked car is solid on foot.
            try:
                can_walk = getattr(collisions, "can_walk", collisions.can_move)  # Piers too.
                if can_walk(walker.collision_record()):
                    return walker
            finally:
                collisions.fixed = saved_fixed
            print("Saved walker position is blocked; stepping out beside the car",
                  file=sys.stderr)
        spot = exit_spot(car, collisions)
        return Walker(*spot, heading=car.heading) if spot else None

    def save(self, car: Car, walker: Walker | None = None, missions: dict | None = None):
        """Replace the save only after the new JSON has been fully written."""
        payload = {
            "version": SAVE_VERSION,
            "mode": "walk" if walker else "drive",
            "car": _pose(car),
        }
        if missions is not None:
            payload["missions"] = missions
        if walker:
            payload["walker"] = _pose(walker)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".player-", suffix=".tmp", delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(payload, temp_file, indent=2, allow_nan=False)
                temp_file.write("\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
