"""When to autosave: on a fixed interval, and soon after important events."""

from __future__ import annotations


AUTOSAVE_INTERVAL = 60.0  # Seconds between routine autosaves.
TOAST_TIME = 1.5          # Seconds the "Saved" note stays on screen.


class Autosave:
    def __init__(self, interval: float = AUTOSAVE_INTERVAL):
        self.interval = interval
        self.elapsed = 0.0
        self.requested = False
        self.toast = 0.0

    def request(self):
        """Save at the next allowed moment (e.g. right after a mission result)."""
        self.requested = True

    def tick(self, dt: float, allowed: bool = True) -> bool:
        """Advance the clock; True when a save should happen now."""
        self.elapsed += dt
        self.toast = max(0.0, self.toast - dt)
        if allowed and (self.requested or self.elapsed >= self.interval):
            self.elapsed, self.requested = 0.0, False
            self.toast = TOAST_TIME
            return True
        return False
