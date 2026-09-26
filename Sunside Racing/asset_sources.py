"""Deterministic, top-down pixel art sources for the racing world.

Run this file to rebuild the editable bitmap JSON and atlas manifest. Generate
the PNGs from those JSON files with the toolkit's png_generator.py.
"""

from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BITMAP = ROOT / "bitmap"
ASSETS = ROOT / "assets"


def rgb(value: str) -> list[float]:
    value = value.lstrip("#")
    return [round(int(value[i:i + 2], 16) / 255, 6) for i in (0, 2, 4)] + [1.0]


class Atlas:
    def __init__(self, name: str, cell: int, columns: int, rows: int):
        self.name, self.cell, self.columns, self.rows = name, cell, columns, rows
        self.fill: list[dict] = []
        self.sprites: dict[str, dict] = {}

    def tile(self, name: str, column: int, row: int) -> "Painter":
        if name in self.sprites or not (0 <= column < self.columns and 0 <= row < self.rows):
            raise ValueError(f"Invalid tile: {name} ({column}, {row})")
        self.sprites[name] = {"tile": [column, self.rows - row - 1], "source_row": row}
        return Painter(self, column * self.cell, row * self.cell)

    def spec(self) -> dict:
        return {"dim": [self.cell * self.columns, self.cell * self.rows], "fill": self.fill}

    def manifest(self) -> dict:
        return {
            "png": f"{self.name}.png",
            "bitmap": f"../bitmap/{self.name}.json",
            "cell_px": self.cell,
            "atlas_grid": [self.columns, self.rows],
            "tile_origin": "bottom-left, as used by shaders/tex.frag",
            "sprites": self.sprites,
        }


class Painter:
    def __init__(self, atlas: Atlas, ox: int, oy: int):
        self.atlas, self.ox, self.oy, self.size = atlas, ox, oy, atlas.cell

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: str):
        if x0 >= x1 or y0 >= y1:
            return
        if not (0 <= x0 < x1 <= self.size and 0 <= y0 < y1 <= self.size):
            raise ValueError(f"Rectangle outside {self.atlas.name}: {(x0, y0, x1, y1)}")
        self.atlas.fill.append({
            "from": [self.ox + x0, self.oy + y0],
            "to": [self.ox + x1 - 1, self.oy + y1 - 1],
            "color": rgb(color),
        })

    def dots(self, coords: list[tuple[int, int]], color: str):
        if coords:
            self.atlas.fill.append({
                "coords": [[self.ox + x, self.oy + y] for x, y in coords],
                "color": rgb(color),
            })

    def ellipse(self, cx: int, cy: int, rx: int, ry: int, color: str):
        for y in range(max(0, cy - ry), min(self.size, cy + ry + 1)):
            fraction = 1 - ((y - cy) / max(ry, 1)) ** 2
            dx = round(rx * max(0, fraction) ** 0.5)
            self.rect(max(0, cx - dx), y, min(self.size, cx + dx + 1), y + 1, color)

    def flecks(self, seed: int, count: int, colors: tuple[str, ...], margin: int = 2):
        rng = random.Random(seed)
        for i in range(count):
            x, y = rng.randrange(margin, self.size - margin), rng.randrange(margin, self.size - margin)
            self.rect(x, y, x + rng.choice((1, 2)), y + 1, colors[i % len(colors)])


def terrain() -> Atlas:
    a = Atlas("terrain-atlas", 32, 8, 4)
    tiles = [
        ("grass", "#4c9758", ("#66ab64", "#3d824c")),
        ("jungle_ground", "#285a3d", ("#39774b", "#204b35")),
        ("desert_sand", "#d6ac68", ("#e9c989", "#bd8e55")),
        ("snow", "#e0edf0", ("#f4f8f4", "#bbd5df")),
        ("rural_earth", "#a7794b", ("#bc8d59", "#865e3e")),
        ("beach_sand", "#f0d59c", ("#ffe6b0", "#dabb83")),
        ("shallow_sea", "#3aadc0", ("#74d2cf", "#298fae")),
        ("deep_sea", "#28628f", ("#4284a8", "#1d517c")),
        ("city_pavement", "#a9aba4", ("#c7c8b9", "#929a99")),
        ("city_concrete", "#868f91", ("#a3abaa", "#6d7b7f")),
        ("desert_rock", "#aa875c", ("#cba36e", "#886d50")),
        ("snow_rock", "#9eafbb", ("#d5e4e7", "#758d9a")),
        ("jungle_mud", "#504d35", ("#6e6845", "#383c2c")),
        ("rural_grass", "#8aa253", ("#a6b666", "#6f8b48")),
        ("wet_sand", "#c7b18b", ("#e4caa0", "#ad997d")),
        ("island_grass", "#71aa6b", ("#8ac17e", "#58935f")),
        ("dirt_gravel", "#8e755b", ("#ac9275", "#6b5c4e")),
        ("ice", "#abd6dc", ("#d8f0ee", "#85bdcb")),
        ("farm_field", "#a58a4f", ("#bf9e62", "#817149")),
        ("jungle_leaves", "#33734c", ("#448c55", "#245a40")),
        ("desert_dunes", "#e5bb77", ("#f6d38e", "#cc9d5d")),
        ("snow_drift", "#cbdfe5", ("#f1f6f2", "#aac9d6")),
        ("city_plaza", "#b9b9aa", ("#d5d1bc", "#a5a592")),
        ("sea_foam", "#63bcc4", ("#a6e3dc", "#3d9eae")),
        ("shore_north", "#f0d59c", ("#ffe6b0", "#dabb83")),
        ("shore_east", "#f0d59c", ("#ffe6b0", "#dabb83")),
        ("shore_south", "#f0d59c", ("#ffe6b0", "#dabb83")),
        ("shore_west", "#f0d59c", ("#ffe6b0", "#dabb83")),
        ("farm_rows", "#765d3f", ("#9f814f", "#63533e")),
        ("parking_lot", "#555d62", ("#747b7f", "#42494e")),
        ("dark_asphalt", "#414a54", ("#555f65", "#313a42")),
        ("island_stone", "#8e9791", ("#abb6a5", "#6f7d75")),
    ]
    for idx, (name, base, detail) in enumerate(tiles):
        p = a.tile(name, idx % 8, idx // 8)
        p.rect(0, 0, 32, 32, base)
        p.flecks(idx + 104, 23 if "sea" not in name else 9, detail)
        if name in ("shallow_sea", "deep_sea", "sea_foam"):
            for y, x in ((6, 4), (19, 17), (27, 8)):
                p.rect(x, y, x + 8, y + 1, detail[0])
        elif name == "city_pavement":
            for n in (8, 16, 24):
                p.rect(n, 0, n + 1, 32, "#929a99")
                p.rect(0, n, 32, n + 1, "#929a99")
        elif name == "farm_rows":
            for x in range(3, 32, 7):
                p.rect(x, 0, min(32, x + 2), 32, "#b59157")
        elif name == "parking_lot":
            for x in (4, 16, 28):
                p.rect(x, 4, x + 1, 15, "#cdd1c1")
        elif name.startswith("shore_"):
            if name == "shore_north": p.rect(0, 0, 32, 7, "#68bfca")
            if name == "shore_south": p.rect(0, 25, 32, 32, "#68bfca")
            if name == "shore_east": p.rect(25, 0, 32, 32, "#68bfca")
            if name == "shore_west": p.rect(0, 0, 7, 32, "#68bfca")
    return a


def road(p: Painter, material: str, exits: str):
    color = {"city": "#4b5159", "dirt": "#936747", "ice": "#8aaeba"}[material]
    edge = {"city": "#b9b9aa", "dirt": "#ae895e", "ice": "#d8edf0"}[material]
    width = 42 if material == "city" else 30
    lo, hi = (64 - width) // 2, (64 + width) // 2
    p.rect(lo - 2, lo - 2, hi + 2, hi + 2, edge)
    p.rect(lo, lo, hi, hi, color)
    for direction in exits:
        if direction == "N":
            p.rect(lo - 2, 0, hi + 2, lo + 2, edge)
            p.rect(lo, 0, hi, lo + 1, color)
        elif direction == "S":
            p.rect(lo - 2, hi - 2, hi + 2, 64, edge)
            p.rect(lo, hi - 1, hi, 64, color)
        elif direction == "E":
            p.rect(hi - 2, lo - 2, 64, hi + 2, edge)
            p.rect(hi - 1, lo, 64, hi, color)
        elif direction == "W":
            p.rect(0, lo - 2, lo + 2, hi + 2, edge)
            p.rect(0, lo, lo + 1, hi, color)
    mark = {"city": "#e4c77c", "dirt": "#bd9565", "ice": "#ecf7ee"}[material]
    if exits in ("NS", "SN"):
        for y in (3, 18, 44, 58): p.rect(31, y, 33, min(64, y + 7), mark)
    elif exits in ("EW", "WE"):
        for x in (3, 18, 44, 58): p.rect(x, 31, min(64, x + 7), 33, mark)
    elif material == "city":
        p.rect(29, 29, 35, 35, "#697078")
    if material == "dirt":
        p.flecks(300 + sum(ord(x) for x in exits), 14, ("#b38b60", "#75553d"), 4)
    if material == "ice":
        for x, y in ((12, 28), (42, 16), (47, 49)):
            p.rect(x, y, x + 5, y + 1, "#dcf0ed")


def roads() -> Atlas:
    a = Atlas("road-atlas", 64, 8, 4)
    shapes = ["NS", "EW", "NE", "NW", "SE", "SW", "NSEW", "NSE"]
    for row, material in enumerate(("city", "dirt", "ice")):
        for col, exits in enumerate(shapes):
            name = f"{material}_{'cross' if exits == 'NSEW' else 'tee' if exits == 'NSE' else exits.lower()}"
            road(a.tile(name, col, row), material, exits)
    extras = ["city_t_nsw", "city_t_new", "city_t_sew", "city_start", "city_finish", "city_crosswalk", "city_parking", "rural_start"]
    for col, name in enumerate(extras):
        p = a.tile(name, col, 3)
        if name.startswith("city_t_"):
            road(p, "city", name[-3:].upper())
        elif name in ("city_start", "city_finish", "rural_start"):
            road(p, "dirt" if name == "rural_start" else "city", "NS")
            if name == "city_finish":
                for x in range(11, 53, 7):
                    p.rect(x, 28, x + 7, 35, "#f5f5e9" if x // 7 % 2 else "#283139")
            else:
                p.rect(11, 28, 53, 30, "#f5f5e9")
                p.rect(11, 33, 53, 35, "#f5f5e9")
        elif name == "city_crosswalk":
            road(p, "city", "NS")
            for x in range(11, 53, 7): p.rect(x, 25, x + 4, 39, "#e8e6d7")
        else:
            p.rect(3, 3, 61, 61, "#5c6668")
            for x in (8, 25, 42, 59): p.rect(x, 7, x + 1, 27, "#d6d8c7")
            p.rect(5, 31, 59, 33, "#d6d8c7")
    return a


def car(p: Painter, body: str, kind: str, stripe: str | None = None):
    # All cars face north; the engine rotates their centered textured quads.
    if kind == "bus":
        x0, x1, y0, y1 = 19, 45, 5, 59
    elif kind in ("van", "pickup"):
        x0, x1, y0, y1 = 20, 44, 8, 56
    elif kind == "racer":
        x0, x1, y0, y1 = 19, 45, 11, 54
    else:
        x0, x1, y0, y1 = 21, 43, 10, 54
    p.rect(x0 - 3, y0 + 8, x0 + 2, y0 + 19, "#1a2931")
    p.rect(x1 - 2, y0 + 8, x1 + 3, y0 + 19, "#1a2931")
    p.rect(x0 - 3, y1 - 19, x0 + 2, y1 - 8, "#1a2931")
    p.rect(x1 - 2, y1 - 19, x1 + 3, y1 - 8, "#1a2931")
    p.rect(x0 + 2, y0 + 2, x1 + 2, y1 + 2, "#24414a")
    p.rect(x0, y0, x1, y1, body)
    p.rect(x0 + 3, y0 + 4, x1 - 3, y0 + 7, "#f0edbd")
    p.rect(x0 + 4, y1 - 6, x1 - 4, y1 - 3, "#a72f34")
    if kind == "pickup":
        p.rect(x0 + 3, 34, x1 - 3, y1 - 8, "#42545c")
        p.rect(x0 + 5, 36, x1 - 5, y1 - 10, "#736a58")
    else:
        p.rect(x0 + 3, y0 + 12, x1 - 3, y0 + 23, "#a0c9cf")
        p.rect(x0 + 4, y1 - 20, x1 - 4, y1 - 12, "#75a6ad")
    p.rect(x0 + 2, y0 + 26, x0 + 4, y1 - 22, "#e6e5d4")
    p.rect(x1 - 4, y0 + 26, x1 - 2, y1 - 22, "#e6e5d4")
    if kind == "racer":
        p.rect(x0 - 5, y1 - 11, x1 + 5, y1 - 7, "#20313d")
        p.rect(x0 + 4, y0 + 8, x1 - 4, y0 + 10, "#20313d")
        p.rect(29, y0 + 11, 35, y1 - 13, stripe or "#f4e8b2")
        p.rect(x0 - 3, y0 + 22, x0 + 1, y0 + 31, stripe or "#f4e8b2")
        p.rect(x1 - 1, y0 + 22, x1 + 3, y0 + 31, stripe or "#f4e8b2")
    elif kind == "taxi":
        p.rect(26, y0 + 23, 38, y0 + 27, "#f8f0d0")
        p.rect(27, y0 + 24, 37, y0 + 26, "#23323a")
    elif kind == "bus":
        for y in range(17, 49, 9): p.rect(x0 + 2, y, x1 - 2, y + 5, "#9cc8ce")


def vehicles() -> Atlas:
    a = Atlas("vehicle-atlas", 64, 8, 3)
    traffic = [
        ("traffic_red", "#bf554e", "sedan"), ("traffic_blue", "#5189b4", "sedan"),
        ("traffic_green", "#5f9b76", "sedan"), ("traffic_white", "#d9d7cb", "sedan"),
        ("traffic_gray", "#808e93", "sedan"), ("traffic_yellow", "#e5bd53", "sedan"),
        ("traffic_taxi", "#eac453", "taxi"), ("traffic_van", "#e2e4d8", "van"),
    ]
    racers = [
        ("racer_player", "#e54e4a", "#fff4c0"), ("racer_cyan", "#45bdd1", "#ecfcf6"),
        ("racer_yellow", "#f5cb4c", "#243b4a"), ("racer_purple", "#9b6cce", "#f9de8d"),
        ("racer_orange", "#eb884c", "#f4edcd"), ("racer_lime", "#9ccb5d", "#304b48"),
        ("racer_blue", "#5174d5", "#e9f4f1"), ("racer_black", "#3d4856", "#efbd61"),
    ]
    utility = [
        ("traffic_pickup", "#b77c58", "pickup"), ("traffic_delivery", "#d5a65b", "van"),
        ("traffic_bus", "#d7ae53", "bus"), ("traffic_police", "#e2e7e2", "sedan"),
        ("traffic_suv", "#697e72", "van"), ("traffic_wagon", "#8771a2", "sedan"),
        ("traffic_compact", "#ba7c77", "sedan"), ("traffic_service", "#63a2a3", "pickup"),
    ]
    for col, (name, body, kind) in enumerate(traffic): car(a.tile(name, col, 0), body, kind)
    for col, (name, body, stripe) in enumerate(racers): car(a.tile(name, col, 1), body, "racer", stripe)
    for col, (name, body, kind) in enumerate(utility): car(a.tile(name, col, 2), body, kind)
    return a


def building(p: Painter, roof: str, kind: str, seed: int):
    p.rect(10, 13, 91, 93, "#34454c")
    p.rect(7, 8, 88, 89, "#233840")
    p.rect(10, 10, 85, 85, roof)
    p.rect(14, 14, 81, 81, "#d0c6a1" if kind in ("jungle", "desert", "rural") else "#9da8a4")
    p.rect(18, 18, 77, 77, roof)
    if kind == "office":
        for x in range(22, 76, 13):
            for y in range(23, 74, 13):
                p.rect(x, y, x + 8, y + 7, "#83b8c0")
                p.rect(x + 1, y + 1, x + 7, y + 3, "#c5e0d8")
    elif kind == "shop":
        p.rect(21, 25, 74, 59, "#d7d6be")
        for x in range(21, 75, 11): p.rect(x, 26, x + 6, 34, roof)
        p.rect(25, 67, 70, 73, "#d8d3bc")
    elif kind == "parking":
        for y in range(23, 75, 15):
            p.rect(18, y, 78, y + 2, "#ede8d0")
        p.rect(32, 18, 56, 77, "#515d63")
    elif kind == "center":
        p.rect(26, 23, 69, 52, "#ece1ac")
        p.rect(30, 27, 65, 48, "#273d49")
        p.rect(32, 30, 62, 34, "#f2ca57")
        p.rect(35, 38, 59, 43, "#f2ca57")
        p.rect(29, 65, 68, 71, "#f2ca57")
    elif kind == "barn":
        for x in (24, 46, 68): p.rect(x, 17, x + 3, 77, "#e2bb8b")
        p.rect(32, 62, 64, 78, "#503d36")
        p.rect(46, 62, 50, 78, "#dbb38a")
    elif kind == "dock":
        p.rect(23, 27, 71, 67, "#896a4c")
        for x in range(27, 70, 9): p.rect(x, 27, x + 2, 67, "#c19a67")
        p.rect(37, 65, 58, 96, "#896a4c")
        for y in range(71, 96, 7): p.rect(37, y, 58, y + 2, "#c19a67")
    else:
        rng = random.Random(seed)
        for _ in range(4):
            x, y = rng.randrange(24, 69), rng.randrange(24, 65)
            p.rect(x, y, x + 11, y + 7, "#647b80")
            p.rect(x + 2, y + 2, x + 9, y + 5, "#a3c3c1")


def structures() -> Atlas:
    a = Atlas("structure-atlas", 96, 4, 4)
    definitions = [
        ("city_apartment_red", "#ad756b", "office"), ("city_apartment_blue", "#698d9c", "office"),
        ("city_office_tower", "#5b798d", "office"), ("city_office_low", "#8d9a96", "office"),
        ("city_shop_red", "#c78566", "shop"), ("city_shop_blue", "#6c9d9b", "shop"),
        ("city_warehouse", "#b4ae99", "plain"), ("city_parking_deck", "#8c9798", "parking"),
        ("center_city", "#637d99", "center"), ("center_jungle", "#5f855c", "center"),
        ("center_desert", "#c5a474", "center"), ("center_snow", "#8fa9b6", "center"),
        ("center_rural", "#a97f5d", "center"), ("center_island", "#748f81", "center"),
        ("rural_barn", "#ae5c4c", "barn"), ("beach_ferry_dock", "#a78259", "dock"),
    ]
    for i, (name, roof, kind) in enumerate(definitions):
        building(a.tile(name, i % 4, i // 4), roof, kind, i)
    return a


def tree(p: Painter, canopy: str, trunk: str, shape: str):
    p.ellipse(34, 38, 21, 21, "#254438")
    p.rect(29, 43, 35, 59, trunk)
    if shape == "pine":
        for cy, rx in ((42, 19), (32, 16), (22, 12)):
            p.ellipse(32, cy, rx, 9, canopy)
        p.rect(29, 13, 35, 54, canopy)
    elif shape == "palm":
        p.rect(29, 30, 35, 57, trunk)
        for x0, y0, x1, y1 in ((8, 24, 31, 31), (33, 24, 57, 31), (15, 12, 31, 25), (33, 12, 51, 25), (24, 7, 41, 20)):
            p.rect(x0, y0, x1, y1, canopy)
    else:
        p.ellipse(31, 30, 22, 18, canopy)
        p.ellipse(23, 35, 14, 16, canopy)
        p.ellipse(43, 33, 14, 15, canopy)
        p.ellipse(24, 24, 5, 4, "#a6c774" if shape == "jungle" else "#8bc477")


def prop(p: Painter, name: str, index: int):
    if name.startswith("jungle_tree"):
        tree(p, ("#348657", "#3b985c", "#26784b", "#4c9e57")[index % 4], "#745b41", "jungle")
    elif name.startswith("pine"):
        tree(p, ("#326f62", "#477e70", "#4a837c", "#2c655d")[index % 4], "#675d54", "pine")
        p.rect(26, 18, 39, 20, "#dceeea")
        p.rect(21, 34, 44, 36, "#dceeea")
    elif name.startswith("palm"):
        tree(p, ("#519f61", "#64ab69", "#4d965a")[index % 3], "#9f7652", "palm")
    elif name.startswith("cactus"):
        p.rect(27, 13, 37, 57, "#357955")
        p.rect(19, 30, 27, 40, "#357955")
        p.rect(17, 23, 22, 39, "#357955")
        p.rect(37, 35, 45, 44, "#357955")
        p.rect(42, 27, 47, 44, "#357955")
        p.rect(31, 16, 33, 52, "#67a66a")
    elif name.startswith("rock"):
        base = "#8499a2" if "snow" in name else "#98795e"
        p.ellipse(32, 44, 21, 12, "#3c4a50")
        p.ellipse(30, 39, 20, 11, base)
        p.rect(18, 35, 35, 37, "#d1c2a1" if "desert" in name else "#c8dbdc")
    elif name.startswith("bush"):
        p.ellipse(32, 42, 19, 12, "#31573d")
        for x, y in ((20, 38), (31, 31), (43, 39)):
            p.ellipse(x, y, 10, 9, "#548d4e" if "green" in name else "#a4a357")
    elif name.startswith("hay"):
        p.rect(16, 34, 48, 53, "#8c663e")
        p.rect(14, 30, 46, 49, "#d0ac5e")
        for y in (35, 42): p.rect(17, y, 44, y + 2, "#e6c77c")
    elif name in ("race_checkpoint", "race_start", "race_finish"):
        p.rect(12, 16, 17, 57, "#263e4a")
        p.rect(47, 16, 52, 57, "#263e4a")
        p.rect(12, 13, 52, 21, "#f4ce64" if name == "race_checkpoint" else "#f4eee0")
        if name == "race_finish":
            for x in range(14, 51, 8): p.rect(x, 14, x + 4, 20, "#253641")
        else:
            p.rect(19, 15, 45, 18, "#e96150" if name == "race_start" else "#3eaabb")
    elif name == "traffic_light":
        p.rect(30, 19, 34, 59, "#35454b")
        p.rect(24, 5, 41, 32, "#28343c")
        for y, c in ((8, "#e05d52"), (16, "#e8ca60"), (24, "#6bb77d")):
            p.ellipse(32, y + 2, 3, 3, c)
    elif name == "street_lamp":
        p.rect(30, 12, 34, 59, "#43565c")
        p.rect(29, 9, 47, 13, "#43565c")
        p.rect(38, 13, 47, 19, "#f7e7a4")
    elif name == "barrier":
        p.rect(8, 27, 56, 40, "#273d45")
        p.rect(10, 29, 54, 38, "#e4e6d8")
        for x in (13, 27, 41): p.rect(x, 29, x + 7, 38, "#de5a47")
    elif name == "cone":
        p.rect(23, 48, 41, 53, "#374851")
        p.rect(29, 20, 35, 48, "#e98147")
        p.rect(26, 37, 38, 42, "#f5e6c0")
    elif name == "buoy":
        p.ellipse(32, 41, 13, 10, "#e1eee5")
        p.rect(29, 17, 35, 39, "#dc6257")
        p.rect(25, 37, 39, 43, "#dc6257")
    elif name == "direction_sign":
        p.rect(30, 19, 34, 58, "#5b5c52")
        p.rect(10, 12, 53, 30, "#e5c06c")
        p.rect(16, 17, 45, 20, "#354b4d")
    elif name == "farm_fence":
        p.rect(5, 24, 59, 27, "#b18c60")
        p.rect(5, 40, 59, 43, "#b18c60")
        for x in (9, 29, 49): p.rect(x, 18, x + 5, 52, "#846344")
    elif name == "snow_marker":
        p.rect(27, 14, 37, 57, "#e3e9df")
        p.rect(27, 23, 37, 31, "#d3584e")
        p.rect(27, 39, 37, 46, "#d3584e")
    else:
        raise ValueError(name)


def props() -> Atlas:
    a = Atlas("prop-atlas", 64, 8, 4)
    names = [
        "jungle_tree_a", "jungle_tree_b", "jungle_tree_c", "jungle_tree_d",
        "pine_a", "pine_b", "pine_c", "pine_d",
        "palm_a", "palm_b", "palm_c", "cactus_a", "cactus_b", "cactus_c",
        "rock_desert_a", "rock_desert_b", "rock_snow_a", "rock_snow_b",
        "bush_green", "bush_dry", "hay_a", "hay_b", "farm_fence", "snow_marker",
        "race_checkpoint", "race_start", "race_finish", "traffic_light",
        "street_lamp", "barrier", "cone", "buoy",
    ]
    for i, name in enumerate(names): prop(a.tile(name, i % 8, i // 8), name, i)
    return a


def person(p: Painter, frame: str, top: str, trim: str, head: str, head_color: str,
           accent: str | None = None, extra: str | None = None, skin: str = "#e2b48c"):
    """A top-down person facing north (up) in a 32 px cell; the engine rotates it.

    head: cap, hair, wide (straw hat), beanie, wrap (head scarf), or safari.
    extra: overalls, hood (fur-trimmed parka), robe, or backpack.
    """
    shoe = "#2a3238"
    p.ellipse(17, 18, 7, 5, "#24414a")                    # Ground shadow.
    if frame == "walk_a":                                 # Left foot forward, right back.
        p.rect(12, 7, 15, 11, shoe)
        p.rect(17, 21, 20, 25, shoe)
    elif frame == "walk_b":
        p.rect(17, 7, 20, 11, shoe)
        p.rect(12, 21, 15, 25, shoe)
    swing = {"walk_a": 2, "walk_b": -2}.get(frame, 0)     # Arms swing opposite the feet.
    p.rect(8, 15 - swing, 11, 20 - swing, top)
    p.rect(21, 15 + swing, 24, 20 + swing, top)
    p.rect(8, 19 - swing, 11, 21 - swing, skin)
    p.rect(21, 19 + swing, 24, 21 + swing, skin)
    if extra == "robe":
        p.ellipse(16, 19, 8, 4, top)                      # Loose robe past the shoulders.
        p.rect(10, 20, 23, 24, top)
    p.ellipse(16, 18, 7, 3, top)                          # Shoulders and back.
    if extra == "backpack":
        p.rect(12, 18, 21, 25, trim)
        p.rect(13, 22, 20, 23, "#3d2e20")
    elif extra == "overalls":
        p.rect(12, 16, 14, 21, trim)
        p.rect(18, 16, 20, 21, trim)
    elif extra != "robe":
        p.rect(15, 19, 17, 22, trim)                      # Stripe down the back.
    if extra == "hood":
        p.ellipse(16, 17, 6, 4, trim)                     # Fur-trimmed hood behind the head.
    if head == "wrap":
        p.rect(15, 18, 18, 24, head_color)                # Scarf tail hangs down the back.
    if head == "wide":
        p.ellipse(16, 15, 7, 6, head_color)
        p.ellipse(16, 15, 3, 3, accent)
        return
    if head == "safari":
        p.ellipse(16, 15, 6, 5, head_color)
        p.rect(11, 15, 22, 16, accent)
        p.ellipse(16, 15, 3, 3, head_color)
        return
    p.ellipse(16, 15, 5 if head == "wrap" else 4, 4, head_color)  # Head seen from above.
    if head == "cap":
        p.rect(13, 10, 19, 12, accent)                    # Dark brim shows the facing.
    elif head == "beanie":
        p.rect(15, 14, 17, 16, accent)                    # Pom-pom.
    elif head == "wrap":
        p.rect(12, 14, 21, 15, accent)                    # Band.
    else:
        p.rect(14, 11, 18, 12, skin)                      # Forehead peeking out.


# name, top, trim, head, head color, accent, extra, skin
PEOPLE = (
    ("player", "#d9453f", "#fff1c0", "cap", "#f4ead0", "#9c2f2b", None, "#e2b48c"),
    ("city_a", "#4f7fc4", "#dfe8f0", "hair", "#3a2a22", None, None, "#e2b48c"),
    ("city_b", "#5f9b76", "#e8e2c8", "hair", "#1f1f24", None, None, "#8d5a3b"),
    ("city_c", "#e2b84e", "#fff4d6", "hair", "#c9a15a", None, None, "#f0c9a6"),
    ("city_d", "#8a6bb8", "#e7dcf2", "cap", "#2f3f5f", "#1d2a40", None, "#c68a5e"),
    ("city_e", "#d9d7cb", "#9aa6ad", "hair", "#b5613a", None, None, "#f0c9a6"),
    ("city_f", "#3f9a9a", "#d6efe9", "cap", "#e6e1d2", "#2d6d6d", None, "#8d5a3b"),
    ("city_g", "#e08a4a", "#fff0dc", "hair", "#1f1f24", None, None, "#c68a5e"),
    ("city_h", "#7d8a90", "#cfd6d8", "beanie", "#a8443c", "#f0e6d0", None, "#e2b48c"),
    ("farmer_a", "#3f5f8f", "#e8d49a", "wide", "#d9b75a", "#a8843a", "overalls", "#e2b48c"),
    ("farmer_b", "#b5503f", "#e8d49a", "wide", "#e0c070", "#9c7a36", None, "#c68a5e"),
    ("snow_a", "#e07b3a", "#efe6d4", "beanie", "#3b5f8a", "#f4f0e6", "hood", "#f0c9a6"),
    ("snow_b", "#34507a", "#efe6d4", "beanie", "#c9453c", "#f4f0e6", "hood", "#c68a5e"),
    ("nomad_a", "#c9a46a", "#e8dcc0", "wrap", "#ece0c4", "#b0452f", "robe", "#c68a5e"),
    ("nomad_b", "#3f4f8a", "#d9cfb4", "wrap", "#e2d5b5", "#c9a24a", "robe", "#8d5a3b"),
    ("explorer_a", "#a89a64", "#6b4f35", "safari", "#c8b47a", "#6b4f35", "backpack", "#e2b48c"),
    ("explorer_b", "#6f7a45", "#6b4f35", "safari", "#b9a56a", "#4d3a28", "backpack", "#8d5a3b"),
)
PERSON_FRAMES = ("idle", "walk_a", "walk_b")


def people() -> Atlas:
    """Every kind gets idle and two walk frames; four kinds per 12-cell row."""
    per_row = 4
    rows = -(-len(PEOPLE) // per_row)
    a = Atlas("people-atlas", 32, per_row * len(PERSON_FRAMES), rows)
    for i, (name, top, trim, head, head_color, accent, extra, skin) in enumerate(PEOPLE):
        for f, frame in enumerate(PERSON_FRAMES):
            person(a.tile(f"{name}_{frame}", (i % per_row) * len(PERSON_FRAMES) + f, i // per_row),
                   frame, top, trim, head, head_color, accent, extra, skin)
    return a


def camp_prop(p: Painter, name: str):
    """Encampment props, 64 px, top-down; tent doors face south (down)."""
    if name.startswith("tent"):
        canvas, shade = {"tent_tan": ("#d8c08a", "#b39a64"),
                         "tent_green": ("#6f8f4f", "#56733c")}[name]
        p.rect(12, 14, 56, 56, "#24414a")                 # Shadow.
        for x, y in ((8, 10), (54, 10), (8, 52), (54, 52)):
            p.rect(x, y, x + 3, y + 3, "#5a4a3a")         # Pegs.
        p.rect(10, 12, 54, 52, canvas)
        p.rect(10, 12, 31, 52, shade)                     # Shaded west slope.
        p.rect(31, 12, 33, 52, "#4f4436")                 # Ridge pole.
        p.rect(25, 40, 39, 52, "#3a3027")                 # Open door flap.
        p.rect(27, 42, 37, 52, "#221c17")
    elif name == "campfire":
        p.ellipse(33, 35, 15, 12, "#24414a")
        p.ellipse(32, 33, 14, 12, "#8a8f8f")              # Stone ring.
        p.ellipse(32, 33, 10, 8, "#3a2e25")
        p.rect(20, 31, 44, 35, "#6b4a30")                 # Crossed logs.
        p.rect(30, 22, 34, 44, "#7a5638")
        p.ellipse(32, 31, 6, 7, "#e8783a")                # Flames.
        p.ellipse(32, 32, 3, 4, "#f6d05a")
    elif name == "crate_stack":
        for x, y in ((12, 22), (32, 26), (20, 8)):
            p.rect(x + 3, y + 3, x + 21, y + 21, "#24414a")
            p.rect(x, y, x + 18, y + 18, "#a47a4a")
            p.rect(x, y + 8, x + 18, y + 10, "#7a5638")
            p.rect(x + 8, y, x + 10, y + 18, "#7a5638")
    elif name == "barrel_pair":
        for cx in (22, 42):
            p.ellipse(cx + 2, 36, 10, 10, "#24414a")
            p.ellipse(cx, 33, 10, 10, "#6b4a30")
            p.ellipse(cx, 33, 7, 7, "#8a6440")
            p.rect(cx - 10, 32, cx + 11, 34, "#3a3a3a")   # Iron hoop.
    elif name.startswith("bedroll"):
        cloth = {"bedroll_red": "#b5503f", "bedroll_blue": "#3f5f8f"}[name]
        p.rect(22, 12, 44, 54, "#24414a")
        p.rect(20, 10, 42, 52, cloth)
        p.rect(20, 10, 42, 18, "#efe6d4")                 # Pillow end.
        p.rect(20, 30, 42, 32, "#2f2a26")                 # Strap.
    elif name == "log_bench":
        p.rect(10, 30, 58, 42, "#24414a")
        p.rect(8, 26, 56, 38, "#7a5638")
        p.rect(8, 26, 56, 28, "#9a7048")
        p.ellipse(10, 32, 3, 6, "#c9a070")                # Cut rings at the ends.
        p.ellipse(54, 32, 3, 6, "#c9a070")
    else:
        raise ValueError(name)


CAMP_PROPS = ("tent_tan", "tent_green", "campfire", "crate_stack",
              "barrel_pair", "bedroll_red", "bedroll_blue", "log_bench")


def camp() -> Atlas:
    a = Atlas("camp-atlas", 64, 4, 2)
    for i, name in enumerate(CAMP_PROPS):
        camp_prop(a.tile(name, i % 4, i // 4), name)
    return a


def marker(p: Painter, name: str):
    """Floating 32 px mission badges; harder givers get a red badge with a gold ring."""
    hard = name.endswith("_hard")
    kind = name.removesuffix("_hard").removeprefix("icon_")
    p.ellipse(16, 17, 14, 14, "#1d2a30")                  # Outline and drop shadow.
    p.ellipse(16, 15, 13, 13, "#f2ca57" if hard else "#27353d")
    p.ellipse(16, 15, 11, 11, "#c9453c" if hard else "#f4ead0")
    ink = "#fff4d6" if hard else "#27353d"
    if kind == "delivery":
        p.rect(9, 10, 23, 21, "#a47a4a")                  # Parcel with tape.
        p.rect(9, 14, 23, 16, "#e8d49a")
        p.rect(15, 10, 17, 21, "#e8d49a")
    elif kind == "speed":
        p.ellipse(16, 16, 7, 7, ink)                      # Stopwatch.
        p.ellipse(16, 16, 5, 5, "#c9453c" if hard else "#f4ead0")
        p.rect(15, 7, 18, 9, ink)
        p.rect(16, 11, 17, 17, ink)
        p.rect(16, 16, 20, 17, ink)
    elif kind == "drag":
        p.rect(9, 8, 10, 24, ink)                         # Checkered flag on a pole.
        for i in range(4):
            for j in range(3):
                if (i + j) % 2 == 0:
                    p.rect(10 + i * 3, 9 + j * 3, 13 + i * 3, 12 + j * 3, ink)
    elif kind == "dropoff":
        p.rect(14, 8, 18, 16, "#3f9a5a")                  # Down arrow: deliver here.
        p.rect(10, 16, 22, 18, "#3f9a5a")
        p.rect(12, 18, 20, 20, "#3f9a5a")
        p.rect(14, 20, 18, 22, "#3f9a5a")
    elif kind == "finish":
        for i in range(4):
            for j in range(4):
                if (i + j) % 2 == 0:
                    p.rect(10 + i * 3, 9 + j * 3, 13 + i * 3, 12 + j * 3, ink)


MARKERS = ("icon_delivery", "icon_speed", "icon_drag", "icon_dropoff",
           "icon_delivery_hard", "icon_speed_hard", "icon_drag_hard", "icon_finish")


def markers() -> Atlas:
    a = Atlas("marker-atlas", 32, 4, 2)
    for i, name in enumerate(MARKERS):
        marker(a.tile(name, i % 4, i // 4), name)
    return a


# Region race surfaces: base, two fleck shades, line, and two curb colors.
TRACK_SURFACES = {
    "city": ("#3b4148", ("#474e56", "#30353b"), "#eceae0", ("#c9453c", "#f4f0e6")),    # Asphalt.
    "snow": ("#9fc6d2", ("#c9e4ec", "#86b0bf"), "#f4f8f8", ("#3f6f9a", "#f4f8f8")),    # Ice.
    "rural": ("#6b4f35", ("#7f6040", "#58402a"), "#d8c48e", ("#d9b75a", "#8a6440")),   # Mud.
    "desert": ("#c9a063", ("#dab677", "#b08650"), "#f6e6ba", ("#d9803a", "#f6e6ba")),  # Packed sand.
    "jungle": ("#4f8a45", ("#62a052", "#3f7338"), "#e8e0b0", ("#2f5f35", "#e8e0b0")),  # Worn grass.
}
TRACK_PARTS = ("base", "edge", "corner", "inner", "start", "finish")


def track_tile(p: Painter, name: str):
    """Race-level tiles, 64 px. Edge art sits on the north side; the engine rotates it.

    Surface tiles are named track_<surface>_<part>; track_fence and track_tires are shared.
    """
    if name == "track_fence":
        p.rect(0, 26, 64, 42, "#24414a")                  # Concrete barrier wall.
        p.rect(0, 22, 64, 38, "#b9bdb8")
        for x in range(0, 64, 16):
            p.rect(x, 22, x + 8, 26, "#c9453c")           # Red and white safety band.
        p.rect(0, 36, 64, 38, "#8a8f8f")
        return
    if name == "track_tires":
        for cx, cy in ((20, 22), (42, 22), (20, 42), (42, 42)):
            p.ellipse(cx + 1, cy + 2, 10, 10, "#24414a")
            p.ellipse(cx, cy, 10, 10, "#23282c")
            p.ellipse(cx, cy, 5, 5, "#4a5157")
        return
    _, surface, part = name.split("_")
    base, flecks, line, (curb_a, curb_b) = TRACK_SURFACES[surface]
    p.rect(0, 0, 64, 64, base)
    p.flecks(900 + sum(map(ord, name)), 22, flecks)
    if surface == "snow":
        for x, y in ((6, 20), (30, 44), (40, 12)):
            p.rect(x, y, x + 16, y + 2, "#e2f2f6")        # Polished ice streaks.
    elif surface == "rural":
        for y in (22, 42):
            p.rect(0, y, 64, y + 2, "#4f3a26")            # Wheel ruts.

    def curb(horizontal: bool):
        for i in range(0, 64, 8):
            color = curb_a if (i // 8) % 2 == 0 else curb_b
            if horizontal:
                p.rect(i, 0, i + 8, 5, color)
            else:
                p.rect(0, i, 5, i + 8, color)
    if part in ("edge", "corner"):
        curb(True)
        p.rect(0, 5, 64, 8, line)
    if part == "corner":
        curb(False)
        p.rect(5, 5, 8, 64, line)
    elif part == "inner":
        p.rect(0, 0, 8, 8, curb_a)                        # Curb nub on the inside apex.
        p.rect(8, 0, 11, 11, line)
        p.rect(0, 8, 11, 11, line)
    elif part == "start":
        p.rect(28, 0, 36, 64, line)                       # Line across the track (N-S).
    elif part == "finish":
        for j in range(0, 64, 8):
            for i in (24, 32):
                p.rect(i, j, i + 8, j + 8, line if (i // 8 + j // 8) % 2 == 0 else "#1d2226")


TRACK_TILES = tuple(f"track_{surface}_{part}" for surface in TRACK_SURFACES
                    for part in TRACK_PARTS) + ("track_fence", "track_tires")


def track() -> Atlas:
    a = Atlas("track-atlas", 64, 8, 4)
    for i, name in enumerate(TRACK_TILES):
        track_tile(a.tile(name, i % 8, i // 8), name)
    return a


def main():
    BITMAP.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)
    atlases = [terrain(), roads(), vehicles(), structures(), props(), people(), camp(),
                markers(), track()]
    manifest = {"format": 1, "art_style": "top-down pixel art", "atlases": {}}
    for atlas in atlases:
        (BITMAP / f"{atlas.name}.json").write_text(json.dumps(atlas.spec(), indent=2) + "\n")
        manifest["atlases"][atlas.name] = atlas.manifest()
    (ASSETS / "atlas-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {len(atlases)} bitmap specifications and {sum(len(a.sprites) for a in atlases)} sprite entries")


if __name__ == "__main__":
    main()
