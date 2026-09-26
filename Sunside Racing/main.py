"""Sunside Racing: an open-world top-down racing game."""

import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

import moderngl
import pygame

from car import TOP_SPEED, Car
from collision_manager import CollisionManager
from game_state import GameState
from hud import CenterArrow, Hud, compass
from input_handler import InputHandler
from parking import Parking
from pause_menu import PauseMenu
from player_save import PlayerSave
from traffic import Traffic
from walker import Walker, exit_spot
from world import WORLD_SIZE, World
from world_save import WorldStore


WINDOW_SIZE = (1280, 720)
TITLE = "Sunside Racing"
DRIVE_ZOOM = 1.0
WALK_ZOOM = 2.0     # On foot the camera zooms in so people read at 64 screen px.
ZOOM_RATE = 6.0     # Higher is a faster zoom transition.
EXIT_SPEED = 15.0   # The car must be nearly stopped to get out.


def camera_position(target, width: float, height: float, zoom: float = 1.0):
    """Center the view (in world px) on the car or walker, clamped to the world."""
    x = max(0.0, min(target.x - width / 2, WORLD_SIZE - width))
    y = max(0.0, min(target.y - height / 2, WORLD_SIZE - height))
    # Whole-screen-pixel camera keeps NEAREST-filtered tiles from shimmering.
    return round(x * zoom) / zoom, round(y * zoom) / zoom


def center_guide(car, center) -> str:
    if not center:
        return "Open water"
    dx, dy = center[1] - car.x, center[2] - car.y
    name = center[0].removeprefix("center_").title()
    # 10 px per metre, for a readable distance.
    return f"{name} racing center  ·  {math.hypot(dx, dy) / 10:.0f} m {compass(dx, dy)}"


def main():
    pygame.init()
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK,
                                    pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_mode(WINDOW_SIZE, pygame.OPENGL | pygame.DOUBLEBUF, vsync=1)
    pygame.display.set_caption(TITLE)
    ctx = moderngl.create_context()
    ctx.enable(moderngl.BLEND)
    ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA)

    world_store = WorldStore(PROJECT_ROOT / "world.json")
    world = World(store=world_store)
    state = GameState(ctx, PROJECT_ROOT, TOOLKIT_ROOT, WINDOW_SIZE)
    inputs = InputHandler(state)
    collisions = CollisionManager(state, world)
    player_save = PlayerSave()
    saved_car, walker = player_save.load_state(collisions)
    car = saved_car or Car()
    traffic = Traffic(world, world.seed)
    collisions.traffic = traffic
    parking = Parking(world, traffic, world.seed)
    collisions.parking = parking
    arrow = CenterArrow(ctx, TOOLKIT_ROOT, state.viewport)
    menu = PauseMenu(ctx, TOOLKIT_ROOT, state.viewport)
    hud = Hud(ctx, TOOLKIT_ROOT, state.viewport, TOP_SPEED)
    player_id = state.spawn_player(car.x, car.y)
    walker_id = None  # walker is set while the player is on foot.
    zoom = DRIVE_ZOOM
    if walker:
        # Resume a session saved on foot: parked car solid, camera already zoomed in.
        walker_id = state.spawn_walker(walker.x, walker.y)
        state.set_player_pose(walker_id, walker.x, walker.y, walker.heading)
        state.set_player_pose(player_id, car.x, car.y, car.heading)
        collisions.fixed = [car.obstacle()]
        zoom = WALK_ZOOM
    clock = pygame.time.Clock()
    running = True
    try:
        while running:
            # Vsync'd flip() paces frames; a second software cap drops frames.
            dt = min(clock.tick() / 1000.0, 0.05)
            for action, value in inputs.handle_events():
                if action == "quit":
                    running = False
                elif menu.open:
                    choice = menu.handle(action, value)
                    if choice == "resume":
                        menu.toggle()
                    elif choice == "exit":
                        running = False
                elif action in ("pause", "focus_lost"):
                    menu.toggle()
                elif action == "reset":
                    (walker or car).respawn_nearby(collisions)
                elif action == "interact":
                    if walker is None:
                        spot = exit_spot(car, collisions) if abs(car.speed) < EXIT_SPEED else None
                        if spot:
                            car.speed = 0.0
                            walker = Walker(*spot, heading=car.heading)
                            if walker_id is None:
                                walker_id = state.spawn_walker(*spot)
                            # While parked, the car is solid for the walker and traffic.
                            collisions.fixed = [car.obstacle()]
                    elif walker.can_enter(car):
                        walker = None
                        collisions.fixed = []
            if not running:
                break
            player = walker or car
            if not menu.open:
                blockers = [car.collision_record()] if walker else []
                parking.update(dt, player.x, player.y)
                traffic.update(dt, player.collision_record(), blockers)
                if walker:
                    walker.update(dt, *inputs.walking(), collisions)
                    state.set_player_pose(walker_id, walker.x, walker.y, walker.heading)
                    state.set_frame(walker_id, walker.frame())
                else:
                    throttle, steer, handbrake = inputs.driving()
                    car.update(dt, throttle, steer, handbrake, world, collisions)
                    state.set_player_pose(player_id, car.x, car.y, car.heading)
                    collisions.update(player_id, car.collision_record())
                target_zoom = WALK_ZOOM if walker else DRIVE_ZOOM
                zoom += (target_zoom - zoom) * min(1.0, dt * ZOOM_RATE)
                if abs(target_zoom - zoom) < 0.01:
                    zoom = target_zoom  # Settle on an exact zoom for crisp pixels.
            view_w, view_h = state.viewport[0] / zoom, state.viewport[1] / zoom
            camera_x, camera_y = camera_position(player, view_w, view_h, zoom)
            # Parked cars out on a trip leave an empty stall behind.
            visible = [sprite for sprite in world.visible_sprites(camera_x, camera_y, view_w, view_h)
                       if not parking.is_away(sprite)]
            visible += traffic.sprites(camera_x, camera_y, view_w, view_h)
            center = world.center_for(player.x, player.y)
            ctx.clear(0.10, 0.25, 0.36, 1.0)
            entities = [player_id] + ([walker_id] if walker else [])
            state.render(visible, camera_x, camera_y, entities, zoom)
            prompt = "E   Get in" if walker and walker.can_enter(car) else ""
            hud.render(car.speed, world.region_at(player.x, player.y), center_guide(player, center),
                       prompt, show_speed=walker is None)
            if center and not menu.open:
                # Drawn last so nothing in the world or HUD can cover it.
                arrow.render(center[1], center[2], player.x, player.y, camera_x, camera_y, zoom)
            if menu.open:
                menu.render()
            pygame.display.flip()
        world_store.save()
        player_save.save(car, walker)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
