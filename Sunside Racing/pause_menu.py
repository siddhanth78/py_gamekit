"""Pause overlay: dimmed world, a framed panel, Resume / Help / Exit, and a controls page."""

from __future__ import annotations

import moderngl

from gl_utils import build_rect_objs, build_tex_objs, check_mouse_collisions, get_new_instances, load_program, to_gl
from ui_text import LabelAtlas


# Text is rendered white into equal atlas cells, then tinted per state by the shader.
LABEL_CELL = (512, 64)
CONTROLS = (
    ("W  /  UP", "Accelerate  ·  walk north"),
    ("S  /  DOWN", "Brake, reverse  ·  walk south"),
    ("A  D  /  LEFT  RIGHT", "Steer  ·  walk west, east"),
    ("SPACE", "Handbrake"),
    ("SHIFT", "Run while on foot"),
    ("E", "Get out of or into the car"),
    ("R", "Unstick yourself nearby"),
    ("ESC", "Pause menu"),
)
LABELS = {
    "paused": ("PAUSED", 72, True, "center"),
    "controls": ("CONTROLS", 60, True, "center"),
    "resume": ("RESUME", 36, True, "center"),
    "help": ("HELP", 36, True, "center"),
    "exit": ("EXIT", 36, True, "center"),
    "back": ("BACK", 36, True, "center"),
    "hint": ("W/S or arrows to choose  ·  Enter to confirm  ·  Esc to resume", 20, False, "center"),
    "goal": ("Follow the yellow arrow to each region's racing center.", 24, False, "center"),
    **{f"key{i}": (key, 28, True, "left") for i, (key, _) in enumerate(CONTROLS)},
    **{f"act{i}": (action, 28, False, "left") for i, (_, action) in enumerate(CONTROLS)},
}
PAGES = {"main": ("resume", "help", "exit"), "help": ("back",)}

INK = (32, 45, 52)
ACCENT = (242, 202, 87)
CREAM = (238, 232, 208)
MUTED = (150, 170, 172)
PANEL = (26, 40, 48, 242)
BUTTON = (44, 66, 76, 255)
BUTTON_EDGE = (78, 104, 112, 255)
KEY_CAP = (44, 66, 76, 255)
SHADOW = (8, 14, 18, 150)

PANEL_SIZE = {"main": (480, 470), "help": (720, 640)}
BUTTON_SIZE = (312, 64)
BUTTON_GAP = 84
ROW_GAP = 40


def _rect(x, y, width, height, rgba, thickness=0.0):
    return [x, y, *rgba, thickness, width, height, 0.0]


class PauseMenu:
    def __init__(self, ctx, toolkit_root, viewport):
        self.ctx = ctx
        self.viewport = viewport
        self.open = False
        self.page = "main"
        self.selected = 0
        shaders = toolkit_root / "shaders"
        self.rect_program = load_program(ctx, str(shaders / "rect.vert"), str(shaders / "rect.frag"))
        self.text_program = load_program(ctx, str(shaders / "tex.vert"), str(shaders / "tex.frag"))
        size = tuple(float(v) for v in viewport)
        self.rect_program["u_viewport_size"].value = size
        self.text_program["u_viewport_size"].value = size
        self.text_program["u_texture"].value = 0
        self.labels = LabelAtlas(ctx, LABEL_CELL, LABELS)
        self.text_program["u_atlas_grid"].value = self.labels.grid
        rects, _, texts = get_new_instances(48, 0, 32)
        self.rect_instances, self.text_instances = rects, texts
        self.rect_vao, self.rect_vbo = build_rect_objs(ctx, self.rect_program, rects)
        self.text_vao, self.text_vbo = build_tex_objs(ctx, self.text_program, texts)

    @property
    def items(self):
        return PAGES[self.page]

    def toggle(self):
        self.open = not self.open
        self.page, self.selected = "main", 0

    def _show(self, page):
        self.page, self.selected = page, 0

    def _button_centers(self):
        width, height = self.viewport
        if self.page == "help":
            return [(width // 2, height // 2 + 262)]
        return [(width // 2, height // 2 - 40 + i * BUTTON_GAP) for i in range(len(self.items))]

    def _button_records(self):
        return [_rect(x, y, *BUTTON_SIZE, (0, 0, 0, 0)) for x, y in self._button_centers()]

    def _choose(self, item):
        if item == "help":
            self._show("help")
        elif item == "back":
            self._show("main")
            self.selected = PAGES["main"].index("help")
        else:
            return item
        return None

    def handle(self, action, value):
        """Apply one input intent; return 'resume', 'exit', or None."""
        if action == "pause":
            if self.page == "help":
                return self._choose("back")
            return "resume"
        if action == "menu_up":
            self.selected = (self.selected - 1) % len(self.items)
        elif action == "menu_down":
            self.selected = (self.selected + 1) % len(self.items)
        elif action == "confirm":
            return self._choose(self.items[self.selected])
        elif action in ("pointer", "click"):
            hits = check_mouse_collisions(*value, self._button_records(), "rect")
            if hits:
                self.selected = hits[0]
                if action == "click":
                    return self._choose(self.items[hits[0]])
        return None

    def render(self):
        width, height = self.viewport
        cx, cy = width // 2, height // 2
        panel_w, panel_h = PANEL_SIZE[self.page]
        top = cy - panel_h // 2
        rects = [
            _rect(cx, cy, width, height, (8, 16, 22, 165)),                       # Dim the world.
            _rect(cx + 8, cy + 10, panel_w, panel_h, SHADOW),                    # Drop shadow.
            _rect(cx, cy, panel_w + 8, panel_h + 8, (*ACCENT, 255)),             # Accent frame.
            _rect(cx, cy, panel_w, panel_h, PANEL),
            _rect(cx, top + 6, panel_w, 12, (*ACCENT, 255)),                     # Header stripe.
            _rect(cx, top + 136, 132, 4, (*ACCENT, 255)),                        # Title underline.
        ]
        texts = [self.labels.record("paused" if self.page == "main" else "controls",
                                    cx, top + 82, ACCENT)]
        if self.page == "main":
            texts.append(self.labels.record("hint", cx, cy + panel_h // 2 - 30, MUTED))
        else:
            key_left, action_left = cx - 320, cx - 50
            for i in range(len(CONTROLS)):
                y = top + 190 + i * ROW_GAP
                rects.append(_rect(key_left + 118, y, 244, 34, KEY_CAP))
                texts.append(self.labels.record(f"key{i}", key_left + 8, y, ACCENT, align="left"))
                texts.append(self.labels.record(f"act{i}", action_left, y, CREAM, align="left"))
            texts.append(self.labels.record("goal", cx, top + 190 + len(CONTROLS) * ROW_GAP, MUTED))
        for i, (x, y) in enumerate(self._button_centers()):
            chosen = i == self.selected
            bw, bh = BUTTON_SIZE
            rects.append(_rect(x + 4, y + 5, bw, bh, SHADOW))
            rects.append(_rect(x, y, bw + 4, bh + 4, (*ACCENT, 255) if chosen else BUTTON_EDGE))
            rects.append(_rect(x, y, bw, bh, (*ACCENT, 255) if chosen else BUTTON))
            if chosen:
                rects.append(_rect(x - bw // 2 + 14, y, 6, bh - 24, (*INK, 255)))  # Selection tick.
            texts.append(self.labels.record(self.items[i], x, y + 2, INK if chosen else CREAM))

        _, self.rect_instances = to_gl(rects, self.rect_instances, "rect")
        self.rect_vbo.write(self.rect_instances[:len(rects)].tobytes(), offset=0)
        self.rect_vao.render(moderngl.TRIANGLES, instances=len(rects))
        _, self.text_instances = to_gl(texts, self.text_instances, "tex")
        self.text_vbo.write(self.text_instances[:len(texts)].tobytes(), offset=0)
        self.labels.texture.use(location=0)
        self.text_vao.render(moderngl.TRIANGLES, instances=len(texts))
