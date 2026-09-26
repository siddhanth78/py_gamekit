"""Per-region mastery and levels: missions pay mastery; level-ups grant upgrades."""

from __future__ import annotations


REGIONS = ("city", "jungle", "desert", "snow", "rural")
MISSION_TYPES = ("delivery", "speed", "drag")
SPEED_PER_LEVEL = 0.04   # +4% top speed in a region per level above 1.
HARDER_LEVEL = 5         # Harder mission givers appear from this level.
HARDER_MULTIPLIER = 2
FAST_TRAVEL_LEVEL = 3    # Reaching this level lets the player fast travel to the region.


def mastery_to_next(level: int) -> int:
    """Mastery needed to go from level to level + 1."""
    return 10 * level


def reward(base: int, level: int, harder: bool = False) -> int:
    """Rewards grow by 1 per level; harder givers double them. Nothing earned stays 0."""
    if base <= 0:
        return 0
    return (base + level - 1) * (HARDER_MULTIPLIER if harder else 1)


class Progress:
    def __init__(self, data: dict | None = None):
        self.levels = {region: 1 for region in REGIONS}
        self.mastery = {region: 0 for region in REGIONS}  # Toward the next level.
        self.completed = {region: {kind: 0 for kind in MISSION_TYPES} for region in REGIONS}
        for region, state in (data or {}).items():
            if region in REGIONS and isinstance(state, dict):
                level, mastery = state.get("level"), state.get("mastery")
                if type(level) is int and level >= 1 and type(mastery) is int and mastery >= 0:
                    self.levels[region], self.mastery[region] = level, mastery
                done = state.get("completed")  # Absent in saves made before it was tracked.
                if isinstance(done, dict):
                    for kind in MISSION_TYPES:
                        if type(done.get(kind)) is int and done[kind] >= 0:
                            self.completed[region][kind] = done[kind]

    def to_dict(self) -> dict:
        return {region: {"level": self.levels[region], "mastery": self.mastery[region],
                         "completed": dict(self.completed[region])}
                for region in REGIONS}

    def record_completion(self, region: str, kind: str):
        self.completed[region][kind] += 1

    def add(self, region: str, amount: int) -> list[int]:
        """Add mastery; return every new level reached (possibly several)."""
        gained = []
        self.mastery[region] += amount
        while self.mastery[region] >= mastery_to_next(self.levels[region]):
            self.mastery[region] -= mastery_to_next(self.levels[region])
            self.levels[region] += 1
            gained.append(self.levels[region])
        return gained

    def speed_scale(self, region: str) -> float:
        """Top-speed multiplier where the car is; beaches, sea, and island have no level."""
        level = self.levels.get(region, 1)
        return 1.0 + SPEED_PER_LEVEL * (level - 1)

    def harder_unlocked(self, region: str) -> bool:
        return self.levels[region] >= HARDER_LEVEL
