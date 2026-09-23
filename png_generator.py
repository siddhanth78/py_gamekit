"""Generate a transparent PNG from an LLM-friendly bitmap JSON file.

Example bitmap.json::

    {
      "dim": [4, 3],
      "fill": [
        {"coord": [1, 0], "color": [1.0, 0.0, 0.0, 1.0]},
        {"coords": [[0, 1], [1, 1], [2, 1]], "color": [0.0, 0.7, 1.0, 1.0]},
        {"from": [1, 2], "to": [3, 2], "color": [1.0, 1.0, 1.0, 0.5]}
      ]
    }

Coordinates use a top-left origin: x increases rightward and y downward.
Unfilled pixels are transparent. Later fill entries overwrite earlier ones.

Usage::

    python3 png_generator.py --bitmap bitmap.json --output asset.png
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - depends on the local environment
    raise SystemExit(
        "Pillow is required. Install it with: python3 -m pip install Pillow"
    ) from exc


class BitmapError(ValueError):
    """Raised when the bitmap specification is invalid."""


def parse_dimensions(value: Any) -> tuple[int, int]:
    """Accept [width, height] or a string such as '16x16'."""
    if isinstance(value, str):
        parts = value.lower().split("x")
        if len(parts) != 2:
            raise BitmapError("'dim' must look like 'WIDTHxHEIGHT'")
        try:
            width, height = (int(part.strip()) for part in parts)
        except ValueError as exc:
            raise BitmapError("'dim' width and height must be integers") from exc
    elif isinstance(value, list) and len(value) == 2:
        width, height = value
        if isinstance(width, bool) or isinstance(height, bool):
            raise BitmapError("'dim' width and height must be integers")
        if not isinstance(width, int) or not isinstance(height, int):
            raise BitmapError("'dim' width and height must be integers")
    else:
        raise BitmapError("'dim' must be [width, height] or 'WIDTHxHEIGHT'")

    if width <= 0 or height <= 0:
        raise BitmapError("'dim' width and height must be positive")
    return width, height


def parse_coord(value: Any, width: int, height: int, label: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise BitmapError(f"{label} must be [x, y]")
    x, y = value
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
    ):
        raise BitmapError(f"{label} x and y must be integers")
    if not (0 <= x < width and 0 <= y < height):
        raise BitmapError(
            f"{label} ({x}, {y}) is outside the {width}x{height} bitmap"
        )
    return x, y


def parse_color(value: Any, label: str) -> tuple[int, int, int, int]:
    if not isinstance(value, list) or len(value) not in (3, 4):
        raise BitmapError(f"{label} must be [r, g, b] or [r, g, b, a]")

    components = list(value)
    if len(components) == 3:
        components.append(1.0)

    rgba = []
    for component in components:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise BitmapError(f"{label} components must be numbers from 0 to 1")
        number = float(component)
        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
            raise BitmapError(f"{label} components must be numbers from 0 to 1")
        rgba.append(round(number * 255))
    return tuple(rgba)  # type: ignore[return-value]


def coordinate_map_to_entries(fill: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert {"x,y": [r,g,b,a]} shorthand into normal fill entries."""
    entries = []
    for raw_coord, color in fill.items():
        parts = raw_coord.split(",")
        if len(parts) != 2:
            raise BitmapError(
                "coordinate-map keys must look like 'x,y', for example '3,4'"
            )
        try:
            coord = [int(part.strip()) for part in parts]
        except ValueError as exc:
            raise BitmapError(f"invalid coordinate-map key: {raw_coord!r}") from exc
        entries.append({"coord": coord, "color": color})
    return entries


def normalize_fill(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        entries = value
    elif isinstance(value, dict):
        if any(key in value for key in ("coord", "coords", "from", "to")):
            entries = [value]
        else:
            entries = coordinate_map_to_entries(value)
    else:
        raise BitmapError("'fill' must be a fill object, a list, or a coordinate map")

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise BitmapError(f"fill[{index}] must be an object")
    return entries


def entry_coordinates(
    entry: dict[str, Any], index: int, width: int, height: int
) -> list[tuple[int, int]]:
    label = f"fill[{index}]"
    modes = sum(key in entry for key in ("coord", "coords", "from"))
    if modes != 1:
        raise BitmapError(
            f"{label} must contain exactly one of 'coord', 'coords', or 'from'"
        )

    if "coord" in entry:
        return [parse_coord(entry["coord"], width, height, f"{label}.coord")]

    if "coords" in entry:
        raw_coords = entry["coords"]
        if not isinstance(raw_coords, list) or not raw_coords:
            raise BitmapError(f"{label}.coords must be a non-empty list")
        return [
            parse_coord(coord, width, height, f"{label}.coords[{coord_index}]")
            for coord_index, coord in enumerate(raw_coords)
        ]

    if "to" not in entry:
        raise BitmapError(f"{label} with 'from' must also contain 'to'")
    start_x, start_y = parse_coord(entry["from"], width, height, f"{label}.from")
    end_x, end_y = parse_coord(entry["to"], width, height, f"{label}.to")
    left, right = sorted((start_x, end_x))
    top, bottom = sorted((start_y, end_y))
    return [(x, y) for y in range(top, bottom + 1) for x in range(left, right + 1)]


def render_bitmap(spec: Any) -> Image.Image:
    if not isinstance(spec, dict):
        raise BitmapError("the bitmap JSON root must be an object")
    if "dim" not in spec:
        raise BitmapError("the bitmap JSON must contain 'dim'")

    width, height = parse_dimensions(spec["dim"])
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pixels = image.load()

    for index, entry in enumerate(normalize_fill(spec.get("fill"))):
        if "color" not in entry:
            raise BitmapError(f"fill[{index}] must contain 'color'")
        color = parse_color(entry["color"], f"fill[{index}].color")
        for x, y in entry_coordinates(entry, index, width, height):
            pixels[x, y] = color
    return image


def load_spec(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as bitmap_file:
            return json.load(bitmap_file)
    except FileNotFoundError as exc:
        raise BitmapError(f"bitmap file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BitmapError(
            f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a transparent PNG from a JSON pixel bitmap."
    )
    parser.add_argument("--bitmap", required=True, type=Path, help="input bitmap JSON")
    parser.add_argument("--output", required=True, type=Path, help="output PNG path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.output.suffix.lower() != ".png":
            raise BitmapError("--output must end in .png")
        image = render_bitmap(load_spec(args.bitmap))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.output, format="PNG")
    except (BitmapError, OSError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(f"Saved {image.width}x{image.height} PNG to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
