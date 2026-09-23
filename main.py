"""Asteroid dodging game built with gl_utils.

Controls: W/Up thrust, Left/Right or A/D rotate, Space fires a missile,
R restarts after game over, and Escape quits.
"""

import math
import random

import moderngl
import pygame

from gl_utils import (
    build_point_objs,
    build_rect_objs,
    build_tex_objs,
    get_new_instances,
    load_program,
    load_texture,
    set_viewport_size,
    to_gl,
)


WIDTH, HEIGHT = 960, 720
MAX_HULL = 100
SHIELD_DURATION = 20.0
COAST_STOP_TIME = 2.0
RECT_CAPACITY = 2048
STAR_COUNT = 110


def rect(x, y, color, width, height, rotation=0.0, thickness=0.0):
    """Return a gl_utils rectangle record."""
    return [x, y, *color, thickness, width, height, rotation]


def circles_touch(a, b, padding=0.0):
    radius = a["radius"] + b["radius"] + padding
    return (a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 <= radius**2


def local_to_world(x, y, lateral, forward, angle):
    """Transform rocket-local coordinates; angle 0 points upward."""
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    return (
        x + lateral * cosine - forward * sine,
        y + lateral * sine + forward * cosine,
    )


def add_shield(shapes, ship):
    x, y, angle = ship["x"], ship["y"], ship["angle"]
    if ship["shield_until"] > ship["time"]:
        pulse = 66 + math.sin(ship["time"] * 7) * 2
        shapes.append(rect(x, y, (70, 220, 255, 185), pulse, pulse, angle, 0.055))
        shapes.append(rect(x, y, (70, 150, 255, 90), pulse + 8, pulse + 8, -angle, 0.035))


def add_asteroid(shapes, asteroid):
    shade = asteroid["shade"]
    size = asteroid["radius"] * 2
    color = (shade, shade - 8, shade - 18, 255)
    shapes.append(rect(asteroid["x"], asteroid["y"], color, size, size, asteroid["angle"], 0.12))
    shapes.append(
        rect(
            asteroid["x"] + size * 0.12,
            asteroid["y"] - size * 0.10,
            (95, 88, 82, 190),
            size * 0.34,
            size * 0.23,
            asteroid["angle"] + 28,
            0.18,
        )
    )


def add_powerup(shapes, powerup):
    x, y = powerup["x"], powerup["y"]
    spin = powerup["spin"]
    kind = powerup["kind"]
    color = {
        "shield": (60, 215, 255, 255),
        "missile": (255, 175, 55, 255),
        "heal": (70, 245, 120, 255),
    }[kind]
    shapes.append(rect(x, y, color, 30, 30, spin, 0.10))

    if kind == "shield":
        shapes.append(rect(x, y, color, 17, 17, -spin, 0.17))
    elif kind == "missile":
        shapes.append(rect(x, y, color, 6, 21, spin))
        mx, my = local_to_world(x, y, 0, -12, spin)
        shapes.append(rect(mx, my, (255, 235, 175, 255), 7, 7, spin + 45))
    else:
        shapes.append(rect(x, y, color, 6, 21, spin))
        shapes.append(rect(x, y, color, 21, 6, spin))


def add_hud(shapes, state):
    # Hull meter, missile pips, and shield timer.
    hull_ratio = state["hull"] / MAX_HULL
    hull_color = (70, 225, 105, 255) if hull_ratio > 0.5 else (245, 190, 55, 255)
    if hull_ratio <= 0.25:
        hull_color = (245, 70, 70, 255)
    shapes.append(rect(122, 24, (90, 100, 118, 255), 204, 18, 0, 0.12))
    if hull_ratio > 0:
        shapes.append(rect(21 + 100 * hull_ratio, 24, hull_color, 200 * hull_ratio, 12))

    for index in range(state["missiles"]):
        shapes.append(rect(25 + index * 13, 50, (255, 175, 55, 255), 6, 15))

    shield_left = max(0.0, state["ship"]["shield_until"] - state["time"])
    if shield_left:
        ratio = shield_left / SHIELD_DURATION
        shapes.append(rect(WIDTH - 122, 24, (50, 90, 110, 255), 204, 14, 0, 0.14))
        shapes.append(rect(WIDTH - 21 - 100 * ratio, 24, (60, 215, 255, 230), 200 * ratio, 8))


def new_asteroid(difficulty):
    radius = random.uniform(15, 29)
    return {
        "x": random.uniform(radius, WIDTH - radius),
        "y": -radius,
        "vx": random.uniform(-48, 48),
        "vy": random.uniform(105, 165) + difficulty * 4,
        "radius": radius,
        "angle": random.uniform(0, 360),
        "spin": random.uniform(-80, 80),
        "shade": random.randint(145, 195),
    }


def new_powerup():
    return {
        "x": random.uniform(35, WIDTH - 35),
        "y": -25,
        "vy": 82.0,
        "radius": 15.0,
        "spin": 0.0,
        "kind": random.choice(("shield", "missile", "heal")),
    }


def reset_game():
    return {
        "ship": {
            "x": WIDTH / 2,
            "y": HEIGHT * 0.76,
            "vx": 0.0,
            "vy": 0.0,
            "coast_vx": 0.0,
            "coast_vy": 0.0,
            "coast_elapsed": COAST_STOP_TIME,
            "was_thrusting": False,
            "angle": 0.0,
            "radius": 24.0,
            "shield_until": 0.0,
            "time": 0.0,
        },
        "asteroids": [],
        "powerups": [],
        "shots": [],
        "hull": MAX_HULL,
        "missiles": 0,
        "time": 0.0,
        "score": 0,
        "asteroid_timer": 0.55,
        "powerup_timer": 4.0,
        "game_over": False,
    }


pygame.init()
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
pygame.display.gl_set_attribute(
    pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE
)
pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
viewport_size = set_viewport_size(*screen.get_size())

ctx = moderngl.create_context()
ctx.viewport = (0, 0, *viewport_size)
ctx.enable(moderngl.PROGRAM_POINT_SIZE)
ctx.enable(moderngl.BLEND)
ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

rect_program = load_program(ctx, "shaders/rect.vert", "shaders/rect.frag")
point_program = load_program(ctx, "shaders/point.vert", "shaders/point.frag")
tex_program = load_program(ctx, "shaders/tex.vert", "shaders/tex.frag")
rect_program["u_viewport_size"] = viewport_size
point_program["u_viewport_size"] = viewport_size
tex_program["u_viewport_size"] = viewport_size

rect_instances, point_instances, tex_instances = get_new_instances(
    RECT_CAPACITY, STAR_COUNT, 1
)
stars = [
    [
        random.randrange(WIDTH), random.randrange(HEIGHT),
        150 + random.randrange(106), 150 + random.randrange(106),
        190 + random.randrange(66), random.randrange(100, 230),
        random.choice((1.0, 1.5, 2.0, 2.5)),
    ]
    for _ in range(STAR_COUNT)
]
stars, point_instances = to_gl(stars, point_instances, "point")
rect_vao, rect_vbo = build_rect_objs(ctx, rect_program, rect_instances)
point_vao, point_vbo = build_point_objs(ctx, point_program, point_instances)
tex_vao, tex_vbo = build_tex_objs(ctx, tex_program, tex_instances)
rocket_texture = load_texture(ctx, "assets/rocket.png")
rocket_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
rocket_texture.use(location=0)
tex_program["u_texture"] = 0
tex_program["u_atlas_grid"] = (1.0, 1.0)

state = reset_game()
clock = pygame.time.Clock()
running = True
caption_timer = 0.0
print(__doc__)

while running:
    dt = min(clock.tick(120) / 1000.0, 0.05)
    fire_pressed = False

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_SPACE:
                fire_pressed = True
            elif event.key == pygame.K_r and state["game_over"]:
                state = reset_game()

    keys = pygame.key.get_pressed()
    ship = state["ship"]
    if not state["game_over"]:
        state["time"] += dt
        ship["time"] = state["time"]

        turn_right = float(keys[pygame.K_RIGHT] or keys[pygame.K_d])
        turn_left = float(keys[pygame.K_LEFT] or keys[pygame.K_a])
        ship["angle"] = (ship["angle"] + (turn_right - turn_left) * 190 * dt) % 360
        angle_radians = math.radians(ship["angle"])
        forward_x, forward_y = math.sin(angle_radians), -math.cos(angle_radians)

        thrusting = keys[pygame.K_UP] or keys[pygame.K_w]
        if thrusting:
            ship["vx"] += forward_x * 245 * dt
            ship["vy"] += forward_y * 245 * dt
            ship["was_thrusting"] = True
            ship["coast_elapsed"] = 0.0
        else:
            if ship["was_thrusting"]:
                # Capture the release velocity once. Scaling this snapshot makes
                # every coast stop take exactly two seconds at any speed.
                ship["coast_vx"] = ship["vx"]
                ship["coast_vy"] = ship["vy"]
                ship["coast_elapsed"] = 0.0
                ship["was_thrusting"] = False
            ship["coast_elapsed"] = min(
                COAST_STOP_TIME, ship["coast_elapsed"] + dt
            )
            coast_factor = 1.0 - ship["coast_elapsed"] / COAST_STOP_TIME
            ship["vx"] = ship["coast_vx"] * coast_factor
            ship["vy"] = ship["coast_vy"] * coast_factor

        speed = math.hypot(ship["vx"], ship["vy"])
        if speed > 315:
            ship["vx"] *= 315 / speed
            ship["vy"] *= 315 / speed
        ship["x"] = (ship["x"] + ship["vx"] * dt) % WIDTH
        ship["y"] = (ship["y"] + ship["vy"] * dt) % HEIGHT

        if fire_pressed and state["missiles"] > 0:
            mx, my = local_to_world(ship["x"], ship["y"], 0, -29, ship["angle"])
            state["shots"].append({
                "x": mx, "y": my,
                    "vx": ship["vx"] + forward_x * 520,
                    "vy": ship["vy"] + forward_y * 520,
                "angle": ship["angle"], "radius": 5.0,
            })
            state["missiles"] -= 1

        difficulty = min(12.0, state["time"] / 15.0)
        state["asteroid_timer"] -= dt
        if state["asteroid_timer"] <= 0:
            state["asteroids"].append(new_asteroid(difficulty))
            state["asteroid_timer"] = max(0.28, 0.82 - difficulty * 0.035)

        state["powerup_timer"] -= dt
        if state["powerup_timer"] <= 0:
            state["powerups"].append(new_powerup())
            state["powerup_timer"] = random.uniform(6.5, 10.0)

        for asteroid in state["asteroids"]:
            asteroid["x"] += asteroid["vx"] * dt
            asteroid["y"] += asteroid["vy"] * dt
            asteroid["angle"] += asteroid["spin"] * dt
            if asteroid["x"] < -asteroid["radius"]:
                asteroid["x"] = WIDTH + asteroid["radius"]
            elif asteroid["x"] > WIDTH + asteroid["radius"]:
                asteroid["x"] = -asteroid["radius"]

        for powerup in state["powerups"]:
            powerup["y"] += powerup["vy"] * dt
            powerup["spin"] = (powerup["spin"] + 90 * dt) % 360
        for shot in state["shots"]:
            shot["x"] += shot["vx"] * dt
            shot["y"] += shot["vy"] * dt

        # Each missile destroys at most one asteroid.
        hit_shots, hit_asteroids = set(), set()
        for shot_index, shot in enumerate(state["shots"]):
            for asteroid_index, asteroid in enumerate(state["asteroids"]):
                if asteroid_index not in hit_asteroids and circles_touch(shot, asteroid):
                    hit_shots.add(shot_index)
                    hit_asteroids.add(asteroid_index)
                    state["score"] += 100
                    break

        # Asteroids are consumed on impact, preventing repeated damage.
        for asteroid_index, asteroid in enumerate(state["asteroids"]):
            if asteroid_index in hit_asteroids or not circles_touch(ship, asteroid, -3):
                continue
            hit_asteroids.add(asteroid_index)
            if ship["shield_until"] > state["time"]:
                ship["shield_until"] = 0.0
            else:
                state["hull"] = max(0, state["hull"] - 20)

        kept_powerups = []
        for powerup in state["powerups"]:
            if circles_touch(ship, powerup):
                if powerup["kind"] == "shield":
                    ship["shield_until"] = state["time"] + SHIELD_DURATION
                elif powerup["kind"] == "missile":
                    state["missiles"] = min(9, state["missiles"] + 3)
                else:
                    state["hull"] = min(MAX_HULL, state["hull"] + 10)
                state["score"] += 25
            elif powerup["y"] < HEIGHT + 40:
                kept_powerups.append(powerup)
        state["powerups"] = kept_powerups

        state["asteroids"] = [
            asteroid for index, asteroid in enumerate(state["asteroids"])
            if index not in hit_asteroids and asteroid["y"] < HEIGHT + asteroid["radius"]
        ]
        state["shots"] = [
            shot for index, shot in enumerate(state["shots"])
            if index not in hit_shots
            and -40 < shot["x"] < WIDTH + 40
            and -40 < shot["y"] < HEIGHT + 40
        ]

        state["score"] += dt * 10
        if state["hull"] <= 0:
            state["game_over"] = True
            ship["shield_until"] = 0.0

    shapes = []
    for asteroid in state["asteroids"]:
        add_asteroid(shapes, asteroid)
    for powerup in state["powerups"]:
        add_powerup(shapes, powerup)
    for shot in state["shots"]:
        # Shader rotation is counterclockwise in screen space; gameplay angles
        # are clockwise, so render with the opposite sign.
        render_angle = -shot["angle"]
        shapes.append(rect(shot["x"], shot["y"], (255, 195, 65, 255), 6, 17, render_angle))
        shapes.append(rect(shot["x"], shot["y"], (255, 245, 190, 255), 2, 13, render_angle))
    add_shield(shapes, ship)
    add_hud(shapes, state)

    if state["game_over"]:
        shapes.append(rect(WIDTH / 2, HEIGHT / 2, (245, 55, 65, 225), 390, 150, 0, 0.035))
        shapes.append(rect(WIDTH / 2, HEIGHT / 2, (245, 55, 65, 100), 360, 120, 45, 0.025))

    if len(shapes) > RECT_CAPACITY:
        raise RuntimeError("Rectangle capacity exceeded")
    shapes, rect_instances = to_gl(shapes, rect_instances, "rect")
    if shapes:
        rect_vbo.write(rect_instances[: len(shapes)].tobytes(), offset=0)

    # One texture instance keeps the entire rocket rigid while it rotates.
    ship_sprite = [[
        ship["x"], ship["y"], 255, 255, 255, 255,
        0, 82, 82, -ship["angle"], 0, 0,
    ]]
    ship_sprite, tex_instances = to_gl(ship_sprite, tex_instances, "tex")
    tex_vbo.write(tex_instances[0].tobytes(), offset=0)

    ctx.clear(0.012, 0.018, 0.045)
    point_vao.render(moderngl.POINTS, vertices=1, instances=len(stars))
    if shapes:
        rect_vao.render(moderngl.TRIANGLES, instances=len(shapes))
    rocket_texture.use(location=0)
    tex_vao.render(moderngl.TRIANGLES, instances=1)
    pygame.display.flip()

    caption_timer -= dt
    if caption_timer <= 0:
        shield_left = max(0, math.ceil(ship["shield_until"] - state["time"]))
        status = (
            f"Hull {state['hull']}/100  |  Missiles {state['missiles']}  |  "
            f"Shield {shield_left}s  |  Score {int(state['score'])}"
        )
        if state["game_over"]:
            status += "  |  GAME OVER - press R to restart"
        pygame.display.set_caption(f"Rocket Dodge - {status}")
        caption_timer = 0.15

pygame.quit()
