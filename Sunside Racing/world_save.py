"""Versioned, atomic disk cache for generated world sectors."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


SAVE_VERSION = 1
DEFAULT_WORLD_SEED = 2026
# Bump when world.py places scenery differently so cached sectors regenerate.
GENERATOR_VERSION = 3


class WorldStore:
    def __init__(self, path: Path | None = None, default_seed: int = DEFAULT_WORLD_SEED):
        self.path = Path(path) if path is not None else Path(__file__).resolve().parent / "world.json"
        if type(default_seed) is not int:
            raise ValueError("World seed must be an integer")
        self.seed = default_seed
        self.sectors: dict[str, list] = {}
        self.dirty = not self.path.exists()
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Cannot read world save {self.path}: {exc}") from exc
            if (not isinstance(data, dict) or type(data.get("version")) is not int
                    or data["version"] != SAVE_VERSION or type(data.get("seed")) is not int
                    or not isinstance(data.get("sectors"), dict)):
                raise ValueError(f"Invalid or unsupported world save: {self.path}")
            self.seed = data["seed"]
            if data.get("generator") == GENERATOR_VERSION:
                self.sectors = data["sectors"]
            else:
                # Stale scenery from an older generator; keep the seed, regenerate lazily.
                self.dirty = True

    @staticmethod
    def key(sx: int, sy: int) -> str:
        return f"{sx},{sy}"

    def get(self, sx: int, sy: int):
        return self.sectors.get(self.key(sx, sy))

    def put(self, sx: int, sy: int, sprites: list):
        self.sectors[self.key(sx, sy)] = sprites
        self.dirty = True

    def save(self):
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": SAVE_VERSION, "generator": GENERATOR_VERSION,
                   "seed": self.seed, "sectors": self.sectors}
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".world-", suffix=".tmp", delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                json.dump(payload, temp_file, separators=(",", ":"), allow_nan=False)
                temp_file.write("\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_path, self.path)
            self.dirty = False
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
