"""Seed-generated circuit layouts: the outline of a random blob of grid cells.

A blob with no holes and no corner-only contacts has a simple (non-crossing) outline,
so every layout is a valid closed loop. Cells are CELL tiles wide, which keeps parallel
stretches of track CELL tiles apart: room for the 3-tile track, its barriers, and a gap.
Same seed, same track; nothing is cached (building one takes a few milliseconds).
"""

from __future__ import annotations

import random

TRACK_GENERATOR_VERSION = 1   # Bump when layouts change (e.g. if best times are ever saved).
CELL = 6                      # Tiles per blob cell.


def _pinches(cells, cell):
    """True if adding cell would touch an existing cell only at a corner."""
    x, y = cell
    for dx in (-1, 1):
        for dy in (-1, 1):
            if (x + dx, y + dy) in cells and (x + dx, y) not in cells and (x, y + dy) not in cells:
                return True
    return False


def _has_hole(cells):
    """True if some empty cell is enclosed (not reachable from outside the bounding box)."""
    xs, ys = [x for x, _ in cells], [y for _, y in cells]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    outside, stack = set(), [(x0, y0)]
    while stack:
        x, y = stack.pop()
        if (x, y) in outside or (x, y) in cells or not (x0 <= x <= x1 and y0 <= y <= y1):
            continue
        outside.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    empty = (x1 - x0 + 1) * (y1 - y0 + 1) - len(cells)
    return len(outside) != empty


def grow_blob(rng: random.Random, size: int):
    cells = {(0, 0)}
    while len(cells) < size:
        frontier = sorted({(x + dx, y + dy) for x, y in cells
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - cells)
        rng.shuffle(frontier)
        for cell in frontier:
            if not _pinches(cells, cell) and not _has_hole(cells | {cell}):
                cells.add(cell)
                break
    return cells


def outline(cells):
    """Clockwise (on screen, y down) corner list of the blob's boundary, in blob units."""
    edges = {}
    for x, y in cells:
        if (x, y - 1) not in cells:
            edges[(x, y)] = (x + 1, y)          # Top edge heads east.
        if (x + 1, y) not in cells:
            edges[(x + 1, y)] = (x + 1, y + 1)  # Right edge heads south.
        if (x, y + 1) not in cells:
            edges[(x + 1, y + 1)] = (x, y + 1)  # Bottom edge heads west.
        if (x - 1, y) not in cells:
            edges[(x, y + 1)] = (x, y)          # Left edge heads north.
    start = min(edges)
    points, point = [start], edges[start]
    while point != start:
        points.append(point)
        point = edges[point]
    # Keep only the corners: points where the direction of travel changes.
    def heading(a, b):
        return (b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1])
    n = len(points)
    return [p for i, p in enumerate(points)
            if heading(points[i - 1], p) != heading(p, points[(i + 1) % n])]


def generate(seed, size: int):
    """Corner list (tiles) of a closed, clockwise circuit that starts on its longest
    eastbound straight, so the start grid always has room."""
    rng = random.Random(f"track-{TRACK_GENERATOR_VERSION}-{seed}")
    corners = outline(grow_blob(rng, size))
    n = len(corners)
    east = [i for i in range(n) if corners[(i + 1) % n][1] == corners[i][1]
            and corners[(i + 1) % n][0] > corners[i][0]]
    start = max(east, key=lambda i: (corners[(i + 1) % n][0] - corners[i][0], -i))
    ordered = corners[start:] + corners[:start]
    return tuple((x * CELL, y * CELL) for x, y in ordered)
