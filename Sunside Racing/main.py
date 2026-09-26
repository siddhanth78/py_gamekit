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
from collision_manager import CollisionManager, nearest_clear_spot
from drag_race import DragRace
from fast_travel import destination
from game_state import GameState
from hud import CenterArrow, Hud, compass
from input_handler import InputHandler
from mission_ui import MissionPanel
from missions import TITLES, Missions
from parking import Parking
from pedestrians import Pedestrians
from pause_menu import PauseMenu
from player_save import PlayerSave
from traffic import Traffic
from walker import CALL_PROMPT_DISTANCE, Walker, call_spot, exit_spot
from world import WORLD_SIZE, World
from world_save import WorldStore


WINDOW_SIZE = (1280, 720)
TITLE = "Sunside Racing"
DRIVE_ZOOM = 1.0
WALK_ZOOM = 2.0     # On foot the camera zooms in so people read at 64 screen px.
ZOOM_RATE = 6.0     # Higher is a faster zoom transition.
EXIT_SPEED = 15.0   # The car must be nearly stopped to get out.
RACE_OVER_DELAY = 2.0  # Seconds the race result shows before returning to the world.


def camera_position(target, width: float, height: float, zoom: float = 1.0,
                    bounds: tuple[float, float] = (WORLD_SIZE, WORLD_SIZE)):
    """Center the view (in world px) on the car or walker, clamped to the world or level."""
    x = max(0.0, min(target.x - width / 2, bounds[0] - width))
    y = max(0.0, min(target.y - height / 2, bounds[1] - height))
    # Whole-screen-pixel camera keeps NEAREST-filtered tiles from shimmering.
    return round(x * zoom) / zoom, round(y * zoom) / zoom


def center_guide(car, center) -> str:
    if not center:
        return "Open water"
    dx, dy = center[1] - car.x, center[2] - car.y
    name = center[0].removeprefix("center_").title()
    # 10 px per metre, for a readable distance.
    return f"{name} racing center  ·  {math.hypot(dx, dy) / 10:.0f} m {compass(dx, dy)}"


def target_guide(player, target, label) -> str:
    dx, dy = target[0] - player.x, target[1] - player.y
    return f"{label}  ·  {math.hypot(dx, dy) / 10:.0f} m {compass(dx, dy)}"


class Game:
    def __init__(self, ctx):
        self.ctx = ctx
        self.world_store = WorldStore(PROJECT_ROOT / "world.json")
        self.world = world = World(store=self.world_store)
        self.state = GameState(ctx, PROJECT_ROOT, TOOLKIT_ROOT, WINDOW_SIZE)
        self.inputs = InputHandler(self.state)
        self.collisions = CollisionManager(self.state, world)
        self.player_save = PlayerSave()
        saved_car, self.walker = self.player_save.load_state(self.collisions)
        self.car = saved_car or Car()
        self.missions = Missions(world, world.seed, self.player_save.missions_data)
        self.traffic = Traffic(world, world.seed)
        self.collisions.traffic = self.traffic
        self.parking = Parking(world, self.traffic, world.seed)
        self.collisions.parking = self.parking
        self.pedestrians = Pedestrians(world, world.seed)
        self.collisions.pedestrians = self.pedestrians
        viewport = self.state.viewport
        self.arrow = CenterArrow(ctx, TOOLKIT_ROOT, viewport)
        self.menu = PauseMenu(ctx, TOOLKIT_ROOT, viewport)
        self.panel = MissionPanel(ctx, TOOLKIT_ROOT, viewport)
        self.hud = Hud(ctx, TOOLKIT_ROOT, viewport, TOP_SPEED)
        self.player_id = self.state.spawn_player(self.car.x, self.car.y)
        self.walker_id = None
        self.zoom = DRIVE_ZOOM
        self.race: DragRace | None = None
        self.race_over = 0.0        # Seconds the finished race has been showing its result.
        self.clock = 0.0
        self.pending_offer = None   # Giver whose offer the panel is showing.
        if self.walker:
            # Resume a session saved on foot: parked car solid, camera already zoomed in.
            self._spawn_walker_entity()
            self.state.set_player_pose(self.player_id, self.car.x, self.car.y, self.car.heading)
            self.collisions.fixed = [self.car.obstacle()]
            self.zoom = WALK_ZOOM

    # Helpers --------------------------------------------------------------------

    def _spawn_walker_entity(self):
        if self.walker_id is None:
            self.walker_id = self.state.spawn_walker(self.walker.x, self.walker.y)
        self.state.set_player_pose(self.walker_id, self.walker.x, self.walker.y, self.walker.heading)

    def _step_out(self, walker: Walker):
        self.car.speed = 0.0
        self.walker = walker
        self._spawn_walker_entity()
        # While parked, the car is solid for the walker and traffic.
        self.collisions.fixed = [self.car.obstacle()]

    def _return_to_giver(self, giver):
        """Failed or finished-level missions end beside their giver, on foot, car nearby."""
        probe = Walker(giver.x, giver.y + 30)
        spot = nearest_clear_spot(self.collisions, probe.collision_record, probe.x, probe.y, 6) \
            or (giver.x, giver.y + 30)
        self.walker = Walker(*spot, heading=0.0)
        self._spawn_walker_entity()
        self.collisions.fixed = []
        car_spot = call_spot(self.walker, self.car, self.collisions)
        if car_spot:
            (self.car.x, self.car.y) = car_spot
        self.car.speed = 0.0
        self.state.set_player_pose(self.player_id, self.car.x, self.car.y, self.car.heading)
        self.collisions.fixed = [self.car.obstacle()]
        self.zoom = WALK_ZOOM

    def _refresh_mastery(self):
        player = self.walker or self.car
        here = "" if self.race else self.world.region_at(player.x, player.y)
        self.menu.set_mastery(self.missions.mastery_rows(here))

    def _fast_travel(self, region):
        """Jump to the region's edge in the car; only offered when no mission is running."""
        player = self.walker or self.car
        landing = destination(self.world, self.collisions, self.car, region, player.x, player.y)
        self.menu.toggle()
        if landing is None:
            self.panel.show_message("Fast travel", f"No clear spot at the {region} border right now.")
            return
        self.car.x, self.car.y, self.car.heading = landing
        self.car.speed = 0.0
        self.walker = None
        self.collisions.fixed = []
        self.zoom = DRIVE_ZOOM
        self.state.set_player_pose(self.player_id, self.car.x, self.car.y, self.car.heading)

    def _show_result(self, result):
        self.panel.show_result(result)
        if not result["success"] and self.race is None:
            self._return_to_giver(result["giver"])

    # Input ----------------------------------------------------------------------

    def handle(self, action, value) -> bool:
        """Apply one input intent; returns False to quit."""
        if action == "quit":
            return False
        if self.menu.open:
            self._refresh_mastery()  # Travel buttons depend on the latest state.
            choice = self.menu.handle(action, value)
            if choice == "resume":
                self.menu.toggle()
            elif choice and choice.startswith("travel:"):
                self._fast_travel(choice.split(":", 1)[1])
            return choice != "exit"
        if self.panel.open:
            outcome = self.panel.handle(action, value)
            if outcome == "accept":
                self._accept(self.pending_offer)
            return True
        if action in ("pause", "focus_lost"):
            self.menu.toggle()
        elif self.race:
            if action == "reset" and self.race.result is None:
                self.race.car.respawn_nearby(self.race.collisions)
        elif action == "reset":
            (self.walker or self.car).respawn_nearby(self.collisions)
        elif action == "interact":
            self._interact()
        elif action == "call_car" and self.walker:
            spot = call_spot(self.walker, self.car, self.collisions)
            if spot:
                (self.car.x, self.car.y), self.car.speed = spot, 0.0
                self.state.set_player_pose(self.player_id, self.car.x, self.car.y, self.car.heading)
                self.collisions.fixed = [self.car.obstacle()]
        return True

    def _interact(self):
        if self.walker is None:
            spot = exit_spot(self.car, self.collisions) if abs(self.car.speed) < EXIT_SPEED else None
            if spot:
                self._step_out(Walker(*spot, heading=self.car.heading))
            return
        giver = self.missions.giver_near(self.walker.x, self.walker.y)
        if giver:
            if self.missions.active:
                self.panel.show_message(giver.name, "Finish your current mission first.")
            else:
                self.pending_offer = giver
                self.panel.show_offer(self.missions.preview(self.missions.offer_for(giver)))
        elif self.walker.can_enter(self.car):
            self.walker = None
            self.collisions.fixed = []

    def _accept(self, giver):
        offer = self.missions.accept(giver)
        if offer.type == "drag":
            scale = self.missions.progress.speed_scale(giver.region)
            self.race = DragRace(offer.track, offer.scale, scale, offer.seed)
            self.race_over = 0.0
            self.zoom = DRIVE_ZOOM

    # Update -----------------------------------------------------------------------

    def update(self, dt):
        self.clock += dt
        if self.menu.open or self.panel.open:
            return
        if self.race:
            self._update_race(dt)
        else:
            self._update_world(dt)

    def _update_world(self, dt):
        car, walker = self.car, self.walker
        player = walker or car
        blockers = [car.collision_record()] if walker else []
        self.parking.update(dt, player.x, player.y)
        self.pedestrians.update(dt, player.collision_record())
        self.traffic.update(dt, player.collision_record(), blockers + self.pedestrians.road_blockers())
        if walker:
            walker.update(dt, *self.inputs.walking(), self.collisions)
            self.state.set_player_pose(self.walker_id, walker.x, walker.y, walker.heading)
            self.state.set_frame(self.walker_id, walker.frame())
        else:
            throttle, steer, handbrake = self.inputs.driving()
            scale = self.missions.progress.speed_scale(self.world.region_at(car.x, car.y))
            car.update(dt, throttle, steer, handbrake, self.world, self.collisions, scale)
            self.state.set_player_pose(self.player_id, car.x, car.y, car.heading)
            self.collisions.update(self.player_id, car.collision_record())
        player = self.walker or car
        result = self.missions.update(dt, player.x, player.y, self.walker is None,
                                      abs(car.speed) > 5, car.crashed and self.walker is None)
        if result:
            self._show_result(result)
        target_zoom = WALK_ZOOM if self.walker else DRIVE_ZOOM
        self.zoom += (target_zoom - self.zoom) * min(1.0, dt * ZOOM_RATE)
        if abs(target_zoom - self.zoom) < 0.01:
            self.zoom = target_zoom  # Settle on an exact zoom for crisp pixels.

    def _update_race(self, dt):
        race = self.race
        race.update(dt, *self.inputs.driving())
        if race.result:
            self.race_over += dt
            if self.race_over >= RACE_OVER_DELAY:
                won = race.result == "win"
                seconds = race.times.get("player", race.clock)
                detail = (f"You won in {seconds:.1f} s" if won
                          else f"The rival finished first ({race.times['rival']:.1f} s)")
                giver = self.missions.active.giver
                result = self.missions.finish_drag(won, detail)
                self.race = None
                self._return_to_giver(giver)  # Leaving the level puts you back at the giver.
                self.panel.show_result(result)

    # Render -----------------------------------------------------------------------

    def render(self):
        self.ctx.clear(0.10, 0.25, 0.36, 1.0)
        if self.race:
            self._render_race()
        else:
            self._render_world()
        if self.panel.open:
            self.panel.render()
        if self.menu.open:
            if self.menu.page == "mastery":
                self._refresh_mastery()
            self.menu.render()

    def _render_world(self):
        car, walker, zoom = self.car, self.walker, self.zoom
        player = walker or car
        view_w, view_h = self.state.viewport[0] / zoom, self.state.viewport[1] / zoom
        camera_x, camera_y = camera_position(player, view_w, view_h, zoom)
        # Parked cars out on a trip leave an empty stall behind.
        visible = [s for s in self.world.visible_sprites(camera_x, camera_y, view_w, view_h)
                   if not self.parking.is_away(s)]
        visible += self.traffic.sprites(camera_x, camera_y, view_w, view_h)
        visible += self.pedestrians.sprites(camera_x, camera_y, view_w, view_h)
        visible += self.missions.sprites(self.clock)
        entities = [self.player_id] + ([self.walker_id] if walker else [])
        self.state.render(visible, camera_x, camera_y, entities, zoom)

        region = self.world.region_at(player.x, player.y)
        center = self.world.center_for(player.x, player.y)
        target = self.missions.target()
        if target:
            label = ("Deliver here" if self.missions.active and self.missions.active.offer.type == "delivery"
                     else "Checkpoint" if self.missions.active else "Mission giver")
            guide = target_guide(player, target, label)
        else:
            guide = center_guide(player, center)
        prompt = ""
        giver = self.missions.giver_near(player.x, player.y) if walker else None
        if giver:
            prompt = f"E   Talk  ·  {TITLES[giver.type]}"
        elif walker and walker.can_enter(car):
            prompt = "E   Get in"
        elif walker and math.dist((walker.x, walker.y), (car.x, car.y)) > CALL_PROMPT_DISTANCE:
            prompt = "Q   Call car"
        self.hud.top_speed = TOP_SPEED * self.missions.progress.speed_scale(region)
        self.hud.render(car.speed, region, guide, prompt, show_speed=walker is None,
                        mission=self.missions.status())
        point = target or (center[1:] if center else None)
        if point and not (self.menu.open or self.panel.open):
            # Drawn last so nothing in the world or HUD can cover it.
            self.arrow.render(point[0], point[1], player.x, player.y, camera_x, camera_y, zoom)

    def _render_race(self):
        race = self.race
        level, car = race.level, race.car
        view_w, view_h = self.state.viewport
        camera_x, camera_y = camera_position(car, view_w, view_h, 1.0, (level.width, level.height))
        self.state.set_player_pose(self.player_id, car.x, car.y, car.heading)
        self.state.render(race.sprites(camera_x, camera_y, view_w, view_h), camera_x, camera_y,
                          [self.player_id], 1.0)
        remaining = max(0.0, level.race_length - race.player_progress) / 10
        place = "1ST" if race.position() == 1 else "2ND"
        banner = ""
        if race.clock < 0:
            banner = str(race.countdown)
        elif race.clock < 0.8 and not race.result:
            banner = "GO!"
        elif race.result:
            banner = "YOU WIN!" if race.result == "win" else "YOU LOSE"
        self.hud.top_speed = TOP_SPEED * race.speed_scale
        kind = "Quarter mile" if level.kind == "straight" else "Single lap"
        self.hud.render(car.speed, "Drag race", f"{kind}  ·  {remaining:.0f} m to go",
                        show_speed=True,
                        mission=("DRAG RACE", f"{place}  ·  {max(0.0, race.clock):.1f} s"),
                        banner=banner)

    def save(self):
        self.world_store.save()
        # An ongoing mission (even mid-race) is saved as queued at its giver.
        self.player_save.save(self.car, self.walker, self.missions.to_dict())


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
    game = Game(ctx)
    clock = pygame.time.Clock()
    running = True
    try:
        while running:
            # Vsync'd flip() paces frames; a second software cap drops frames.
            dt = min(clock.tick() / 1000.0, 0.05)
            for action, value in game.inputs.handle_events():
                if not game.handle(action, value):
                    running = False
                    break
            if not running:
                break
            game.update(dt)
            game.render()
            pygame.display.flip()
        game.save()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
