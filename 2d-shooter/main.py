"""Chrome Ember: a top-down pixel-art arena shooter."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

import moderngl  # noqa: E402
import pygame  # noqa: E402

from collision_manager import CollisionManager  # noqa: E402
from config import FPS, HEIGHT, OXBLOOD, WIDTH  # noqa: E402
from game import ArenaGame  # noqa: E402
from game_state import GameState  # noqa: E402
from gl_utils import load_program, load_texture, set_viewport_size  # noqa: E402
from input_handler import InputHandler  # noqa: E402
from pixel_font import PixelFont  # noqa: E402


def create_runtime():
    pygame.init()
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(
        pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE
    )
    pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption("CHROME EMBER")
    set_viewport_size(WIDTH, HEIGHT)

    ctx = moderngl.create_context()
    ctx.enable(moderngl.BLEND)
    ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

    rect_program = load_program(
        ctx,
        str(TOOLKIT_ROOT / "shaders" / "rect.vert"),
        str(TOOLKIT_ROOT / "shaders" / "rect.frag"),
    )
    tex_program = load_program(
        ctx,
        str(TOOLKIT_ROOT / "shaders" / "tex.vert"),
        str(TOOLKIT_ROOT / "shaders" / "tex.frag"),
    )
    rect_program["u_viewport_size"].value = (WIDTH, HEIGHT)
    tex_program["u_viewport_size"].value = (WIDTH, HEIGHT)

    textures = {
        "actors": load_texture(ctx, str(PROJECT_ROOT / "assets" / "actors-24.png")),
        "late_enemies": load_texture(ctx, str(PROJECT_ROOT / "assets" / "late-enemies-32.png")),
        "effects": load_texture(ctx, str(PROJECT_ROOT / "assets" / "effects-8.png")),
        "area_effects": load_texture(ctx, str(PROJECT_ROOT / "assets" / "area-effects-32.png")),
        "environment": load_texture(ctx, str(PROJECT_ROOT / "assets" / "environment-32.png")),
        "ui": load_texture(ctx, str(PROJECT_ROOT / "assets" / "ui-16.png")),
    }

    state = GameState(ctx)
    state.register_batch("environment", "tex", tex_program, 1200, 0, textures["environment"], (4, 1))
    state.register_batch("actors", "tex", tex_program, 512, 20, textures["actors"], (8, 1))
    state.register_batch("late_enemies", "tex", tex_program, 256, 21, textures["late_enemies"], (4, 1))
    state.register_batch("effects", "tex", tex_program, 1024, 30, textures["effects"], (8, 1))
    state.register_batch("area_effects", "tex", tex_program, 256, 35, textures["area_effects"], (4, 1))
    state.register_batch("projectiles", "tex", tex_program, 1024, 40, textures["effects"], (8, 1))
    state.register_batch("ui_overlay", "rect", rect_program, 1024, 80)
    state.register_batch("upgrade_icons", "tex", tex_program, 64, 90, textures["ui"], (8, 1))
    state.register_batch("ui_text", "rect", rect_program, 8000, 100)

    font = PixelFont(state)
    game = ArenaGame(state, CollisionManager(), font)
    game.create_environment()
    return ctx, state, textures, game


def main():
    ctx, state, textures, game = create_runtime()
    controls = InputHandler()
    clock = pygame.time.Clock()
    accumulator = 0.0
    fixed_step = 1.0 / 120.0
    running = True

    try:
        while running:
            frame = controls.poll()
            if frame.quit:
                running = False
                continue
            accumulator = min(0.1, accumulator + clock.tick(FPS) / 1000.0)
            while accumulator >= fixed_step:
                game.update(fixed_step, frame)
                accumulator -= fixed_step

            ctx.clear(*(component / 255.0 for component in OXBLOOD), 1.0)
            state.render_all()
            pygame.display.flip()
    finally:
        state.release()
        for texture in textures.values():
            texture.release()
        pygame.quit()


if __name__ == "__main__":
    main()
