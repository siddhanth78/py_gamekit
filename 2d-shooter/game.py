"""Arena combat, waves, upgrades, and presentation state."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from config import (
    ARENA_BOUNDS,
    BRIGHT_CHROME,
    CHROME,
    HEIGHT,
    HOT_YELLOW,
    SIGNAL_RED,
    WIDTH,
)


@dataclass
class PlayerStats:
    max_health: int = 100
    health: int = 100
    move_speed: float = 260.0
    fire_cooldown: float = 0.22
    bullet_speed: float = 590.0
    damage: int = 1
    dash_cooldown: float = 1.5
    shield_max: int = 0
    shield: int = 0
    projectiles: int = 1


@dataclass
class Enemy:
    entity_id: int
    kind: str
    x: float
    y: float
    health: int
    speed: float
    size: float
    spawn_timer: float
    telegraph_id: int
    shot_timer: float = 1.0
    anim_timer: float = 0.0
    strafe: float = 1.0


@dataclass
class Bullet:
    entity_id: int
    x: float
    y: float
    vx: float
    vy: float
    damage: int
    hostile: bool
    life: float = 2.0


@dataclass
class Effect:
    entity_id: int
    x: float
    y: float
    life: float
    total_life: float
    start_size: float
    end_size: float


UPGRADES = (
    ("RAPID FIRE", "LOWER SHOT COOLDOWN", 2),
    ("BULLET SPEED", "FASTER PROJECTILES", 7),
    ("HEAVY ROUNDS", "MORE SHOT DAMAGE", 4),
    ("FLEET FOOT", "MOVE FASTER", 3),
    ("PHASE DRIVE", "DASH RECHARGES FASTER", 6),
    ("ARMOR PLATE", "MORE MAX HEALTH", 0),
    ("ENERGY SHIELD", "BLOCK ONE HIT PER WAVE", 1),
    ("MULTISHOT", "ADD A SPREAD ROUND", 5),
)


class ArenaGame:
    def __init__(self, state, collision, font, seed=None):
        self.state = state
        self.collision = collision
        self.font = font
        self.rng = random.Random(seed)
        self.environment_ready = False
        self.effects = []
        self.enemies = {}
        self.bullets = {}
        self.overlay_ids = []
        self.upgrade_choices = []
        self.reset()

    def create_environment(self):
        if self.environment_ready:
            return
        for y in range(16, HEIGHT, 32):
            for x in range(16, WIDTH, 32):
                self.state.spawn(
                    "environment", x=x, y=y, width=32, height=32,
                    tile_x=0, tile_y=0,
                )
        for x in range(16, WIDTH, 32):
            self.state.spawn("environment", x=x, y=16, width=32, height=32, tile_x=1)
            self.state.spawn("environment", x=x, y=HEIGHT - 16, width=32, height=32, tile_x=1)
        for y in range(48, HEIGHT - 32, 32):
            self.state.spawn(
                "environment", x=16, y=y, width=32, height=32,
                rotation=90, tile_x=1,
            )
            self.state.spawn(
                "environment", x=WIDTH - 16, y=y, width=32, height=32,
                rotation=90, tile_x=1,
            )
        self.environment_ready = True

    def reset(self):
        for batch in (
            "actors", "effects", "projectiles", "ui_overlay",
            "upgrade_icons", "ui_text",
        ):
            if batch in self.state.batches:
                self.state.clear_batch(batch)
        self.font.groups.clear()
        self.font.signatures.clear()
        self.effects = []
        self.enemies = {}
        self.bullets = {}
        self.overlay_ids = []
        self.stats = PlayerStats()
        self.player_x = WIDTH / 2
        self.player_y = HEIGHT / 2
        self.player_rotation = 0.0
        self.player_id = self.state.spawn(
            "actors", x=self.player_x, y=self.player_y,
            width=40, height=40, tile_x=0,
        )
        self.wave = 1
        self.score = 0
        self.phase = "playing"
        self.fire_timer = 0.0
        self.dash_timer = 0.0
        self.dash_time_left = 0.0
        self.dash_x = 0.0
        self.dash_y = 0.0
        self.invulnerable = 0.0
        self.remaining_to_spawn = 0
        self.spawn_timer = 0.0
        self.wave_intro_timer = 0.0
        self.wave_clear_timer = 0.0
        self.upgrade_choices = []
        self._create_hud()
        self._begin_wave()

    def _create_hud(self):
        self.health_back = self.state.spawn(
            "ui_overlay", x=145, y=22, width=210, height=12,
            r=92, g=17, b=24, a=255,
        )
        self.health_fill = self.state.spawn(
            "ui_overlay", x=145, y=22, width=204, height=6,
            r=197, g=42, b=29, a=255,
        )
        self.dash_back = self.state.spawn(
            "ui_overlay", x=145, y=38, width=210, height=8,
            r=56, g=64, b=71, a=255,
        )
        self.dash_fill = self.state.spawn(
            "ui_overlay", x=145, y=38, width=204, height=3,
            r=255, g=174, b=36, a=255,
        )
        self.font.set_text("controls", "WASD MOVE  MOUSE FIRE  SPACE DASH", 12, HEIGHT - 18, 1, CHROME)

    def _begin_wave(self):
        self.phase = "playing"
        self.remaining_to_spawn = 4 + self.wave * 2
        self.spawn_timer = 0.35
        self.wave_intro_timer = 1.15
        self.wave_clear_timer = 0.0
        self.stats.shield = self.stats.shield_max
        self.font.set_text("banner", f"WAVE {self.wave}", WIDTH / 2, 104, 4, HOT_YELLOW, center=True)

    @staticmethod
    def _direction(x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        return (dx / length, dy / length) if length else (1.0, 0.0)

    def _edge_spawn(self, half_size):
        left, top, right, bottom = ARENA_BOUNDS
        candidates = []
        for _ in range(12):
            edge = self.rng.randrange(4)
            if edge == 0:
                candidate = (left + half_size, self.rng.uniform(top + half_size, bottom - half_size))
            elif edge == 1:
                candidate = (right - half_size, self.rng.uniform(top + half_size, bottom - half_size))
            elif edge == 2:
                candidate = (self.rng.uniform(left + half_size, right - half_size), top + half_size)
            else:
                candidate = (self.rng.uniform(left + half_size, right - half_size), bottom - half_size)
            candidates.append(candidate)
        return max(candidates, key=lambda p: math.hypot(p[0] - self.player_x, p[1] - self.player_y))

    def _spawn_enemy(self):
        roll = self.rng.random()
        if self.wave >= 4 and roll < 0.16:
            kind, tile, size, speed, health = "brute", 6, 48.0, 72.0, 7 + self.wave
        elif self.wave >= 2 and roll < 0.42:
            kind, tile, size, speed, health = "shooter", 4, 38.0, 92.0, 2 + self.wave // 3
        else:
            kind, tile, size, speed, health = "chaser", 2, 38.0, 112.0 + self.wave * 4, 2 + self.wave // 3
        x, y = self._edge_spawn(size / 2)
        dx, dy = self._direction(x, y, self.player_x, self.player_y)
        rotation = math.degrees(math.atan2(dy, dx))
        entity_id = self.state.spawn(
            "actors", x=x, y=y, width=size, height=size,
            rotation=rotation, tile_x=tile, a=100,
        )
        telegraph_id = self.state.spawn(
            "effects", x=x, y=y, width=size + 18, height=size + 18,
            tile_x=4, a=255,
        )
        self.enemies[entity_id] = Enemy(
            entity_id, kind, x, y, health, speed, size, 0.68,
            telegraph_id, shot_timer=self.rng.uniform(0.7, 1.3),
            strafe=self.rng.choice((-1.0, 1.0)),
        )

    def _spawn_effect(self, tile, x, y, size, life, rotation=0.0):
        entity_id = self.state.spawn(
            "effects", x=x, y=y, width=size, height=size,
            rotation=rotation, tile_x=tile,
        )
        self.effects.append(Effect(entity_id, x, y, life, life, size, size * 1.75))

    def _spawn_bullet(self, x, y, dx, dy, hostile=False, damage=1, speed=None):
        speed = speed if speed is not None else self.stats.bullet_speed
        rotation = math.degrees(math.atan2(dy, dx))
        tile = 1 if hostile else 0
        entity_id = self.state.spawn(
            "projectiles", x=x, y=y, width=18 if not hostile else 14,
            height=10, rotation=rotation, tile_x=tile,
        )
        self.bullets[entity_id] = Bullet(
            entity_id, x, y, dx * speed, dy * speed,
            damage, hostile,
        )

    def _shoot_player(self, aim_x, aim_y):
        dx, dy = self._direction(self.player_x, self.player_y, aim_x, aim_y)
        base_angle = math.atan2(dy, dx)
        count = self.stats.projectiles
        spacing = math.radians(8)
        for index in range(count):
            offset = (index - (count - 1) / 2) * spacing
            direction_x = math.cos(base_angle + offset)
            direction_y = math.sin(base_angle + offset)
            self._spawn_bullet(
                self.player_x + direction_x * 25,
                self.player_y + direction_y * 25,
                direction_x, direction_y,
                damage=self.stats.damage,
            )
        self._spawn_effect(2, self.player_x + dx * 28, self.player_y + dy * 28, 18, 0.10, self.player_rotation)

    def _shoot_enemy(self, enemy):
        dx, dy = self._direction(enemy.x, enemy.y, self.player_x, self.player_y)
        self._spawn_bullet(enemy.x + dx * 22, enemy.y + dy * 22, dx, dy, hostile=True, speed=265 + self.wave * 5)

    def update(self, dt, controls):
        dt = min(dt, 0.05)
        if controls.restart and self.phase == "game_over":
            self.reset()
            return
        if self.phase == "upgrade":
            choice = controls.upgrade_choice
            if choice is None and controls.click_pos is not None:
                choice = self._upgrade_at(*controls.click_pos)
            if choice is not None and 0 <= choice < len(self.upgrade_choices):
                self._apply_upgrade(self.upgrade_choices[choice][0])
            return
        if self.phase == "game_over":
            return

        self.fire_timer = max(0.0, self.fire_timer - dt)
        self.dash_timer = max(0.0, self.dash_timer - dt)
        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.wave_intro_timer = max(0.0, self.wave_intro_timer - dt)
        if self.wave_intro_timer == 0:
            self.font.clear("banner")

        aim_dx, aim_dy = self._direction(self.player_x, self.player_y, controls.aim_x, controls.aim_y)
        self.player_rotation = math.degrees(math.atan2(aim_dy, aim_dx))

        if controls.dash and self.dash_timer <= 0:
            if controls.move_x or controls.move_y:
                self.dash_x, self.dash_y = controls.move_x, controls.move_y
            else:
                self.dash_x, self.dash_y = aim_dx, aim_dy
            self.dash_time_left = 0.13
            self.dash_timer = self.stats.dash_cooldown
            self.invulnerable = max(self.invulnerable, 0.22)
            self._spawn_effect(7, self.player_x, self.player_y, 32, 0.16, self.player_rotation)

        if self.dash_time_left > 0:
            self.dash_time_left -= dt
            move_x, move_y, speed = self.dash_x, self.dash_y, 900.0
        else:
            move_x, move_y, speed = controls.move_x, controls.move_y, self.stats.move_speed
        self.player_x += move_x * speed * dt
        self.player_y += move_y * speed * dt
        self.player_x, self.player_y = self.collision.clamp_center(
            self.player_x, self.player_y, 20, 20, ARENA_BOUNDS
        )
        moving = bool(move_x or move_y)
        player_tile = 1 if moving and int(pygame_time() * 10) % 2 else 0
        tint = (255, 255, 255)
        if self.invulnerable > 0 and int(self.invulnerable * 20) % 2:
            tint = (255, 174, 120)
        self.state.modify(
            self.player_id, x=self.player_x, y=self.player_y,
            rotation=self.player_rotation, tile_x=player_tile,
            r=tint[0], g=tint[1], b=tint[2],
        )

        if controls.shooting and self.fire_timer <= 0:
            self._shoot_player(controls.aim_x, controls.aim_y)
            self.fire_timer = self.stats.fire_cooldown

        self._update_spawns(dt)
        self._update_enemies(dt)
        self._update_bullets(dt)
        self._update_effects(dt)
        self._update_wave(dt)
        self._update_hud()

    def _update_spawns(self, dt):
        if self.wave_intro_timer > 0 or self.remaining_to_spawn <= 0:
            return
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self._spawn_enemy()
            self.remaining_to_spawn -= 1
            self.spawn_timer = max(0.22, 0.68 - self.wave * 0.025)

    def _enemy_hitbox(self, enemy):
        hit_size = enemy.size * (0.68 if enemy.kind != "brute" else 0.76)
        return self.collision.rect_record(enemy.x, enemy.y, hit_size, hit_size)

    def _player_hitbox(self):
        return self.collision.rect_record(self.player_x, self.player_y, 24, 20, self.player_rotation)

    def _update_enemies(self, dt):
        player_box = self._player_hitbox()
        active_enemies = [enemy for enemy in self.enemies.values() if enemy.spawn_timer <= 0]
        for enemy in list(self.enemies.values()):
            enemy.anim_timer += dt
            dx, dy = self._direction(enemy.x, enemy.y, self.player_x, self.player_y)
            rotation = math.degrees(math.atan2(dy, dx))
            if enemy.spawn_timer > 0:
                enemy.spawn_timer -= dt
                pulse = 80 + int(175 * (1.0 - max(0.0, enemy.spawn_timer) / 0.68))
                self.state.modify(enemy.entity_id, rotation=rotation, a=pulse)
                if enemy.spawn_timer <= 0:
                    self.state.destroy(enemy.telegraph_id)
                    enemy.telegraph_id = -1
                    self.state.modify(enemy.entity_id, a=255)
                continue

            distance = math.hypot(self.player_x - enemy.x, self.player_y - enemy.y)
            move_x, move_y = dx, dy
            if enemy.kind == "shooter":
                if distance < 175:
                    move_x, move_y = -dx, -dy
                elif distance <= 285:
                    move_x, move_y = -dy * enemy.strafe, dx * enemy.strafe
                enemy.shot_timer -= dt
                if enemy.shot_timer <= 0:
                    self._shoot_enemy(enemy)
                    enemy.shot_timer = max(0.62, 1.45 - self.wave * 0.035)

            separation_x = separation_y = 0.0
            for other in active_enemies:
                if other.entity_id == enemy.entity_id:
                    continue
                offset_x, offset_y = enemy.x - other.x, enemy.y - other.y
                separation_distance = math.hypot(offset_x, offset_y)
                if 0 < separation_distance < (enemy.size + other.size) * 0.55:
                    separation_x += offset_x / separation_distance
                    separation_y += offset_y / separation_distance
            move_x += separation_x * 0.55
            move_y += separation_y * 0.55
            move_length = math.hypot(move_x, move_y)
            if move_length:
                move_x, move_y = move_x / move_length, move_y / move_length
            enemy.x += move_x * enemy.speed * dt
            enemy.y += move_y * enemy.speed * dt
            enemy.x, enemy.y = self.collision.clamp_center(
                enemy.x, enemy.y, enemy.size / 2, enemy.size / 2, ARENA_BOUNDS
            )
            base_tile = {"chaser": 2, "shooter": 4, "brute": 6}[enemy.kind]
            tile = base_tile + (1 if int(enemy.anim_timer * 6) % 2 else 0)
            if enemy.kind == "brute":
                tile = 6
            self.state.modify(enemy.entity_id, x=enemy.x, y=enemy.y, rotation=rotation, tile_x=tile)

            if self.invulnerable <= 0 and self.collision.rects_overlap(player_box, self._enemy_hitbox(enemy)):
                self._damage_player(28 if enemy.kind == "brute" else 18)

    def _update_bullets(self, dt):
        left, top, right, bottom = ARENA_BOUNDS
        player_box = self._player_hitbox()
        for entity_id, bullet in list(self.bullets.items()):
            bullet.life -= dt
            bullet.x += bullet.vx * dt
            bullet.y += bullet.vy * dt
            self.state.modify(entity_id, x=bullet.x, y=bullet.y)
            if bullet.life <= 0 or not (left <= bullet.x <= right and top <= bullet.y <= bottom):
                self._destroy_bullet(entity_id)
                continue
            if bullet.hostile:
                if self.collision.point_hits_rect(bullet.x, bullet.y, player_box):
                    self._destroy_bullet(entity_id)
                    if self.invulnerable <= 0:
                        self._damage_player(14)
                continue
            for enemy_id, enemy in list(self.enemies.items()):
                if enemy.spawn_timer > 0:
                    continue
                if self.collision.point_hits_rect(bullet.x, bullet.y, self._enemy_hitbox(enemy)):
                    enemy.health -= bullet.damage
                    self._destroy_bullet(entity_id)
                    self._spawn_effect(3, bullet.x, bullet.y, 14, 0.14)
                    if enemy.health <= 0:
                        self._kill_enemy(enemy_id)
                    break

    def _destroy_bullet(self, entity_id):
        self.state.destroy(entity_id)
        self.bullets.pop(entity_id, None)

    def _kill_enemy(self, entity_id):
        enemy = self.enemies.pop(entity_id, None)
        if enemy is None:
            return
        if enemy.telegraph_id >= 0:
            self.state.destroy(enemy.telegraph_id)
        self.state.destroy(entity_id)
        self._spawn_effect(3, enemy.x, enemy.y, enemy.size, 0.28)
        self.score += {"chaser": 100, "shooter": 175, "brute": 350}[enemy.kind]

    def _damage_player(self, damage):
        self.invulnerable = 0.72
        if self.stats.shield > 0:
            self.stats.shield -= 1
            self._spawn_effect(5, self.player_x, self.player_y, 54, 0.26)
            return
        self.stats.health = max(0, self.stats.health - damage)
        self._spawn_effect(3, self.player_x, self.player_y, 30, 0.22)
        if self.stats.health == 0:
            self.phase = "game_over"
            self.font.set_text("game_over", "SYSTEM FAILURE", WIDTH / 2, 250, 5, SIGNAL_RED, center=True)
            self.font.set_text("restart", "PRESS R TO RESTART", WIDTH / 2, 310, 3, BRIGHT_CHROME, center=True)

    def _update_effects(self, dt):
        for effect in list(self.effects):
            effect.life -= dt
            if effect.life <= 0:
                self.state.destroy(effect.entity_id)
                self.effects.remove(effect)
                continue
            progress = 1.0 - effect.life / effect.total_life
            size = effect.start_size + (effect.end_size - effect.start_size) * progress
            self.state.modify(effect.entity_id, width=size, height=size, a=int(255 * (1.0 - progress)))

    def _update_wave(self, dt):
        if self.remaining_to_spawn == 0 and not self.enemies:
            self.wave_clear_timer += dt
            if self.wave_clear_timer >= 0.8:
                self._show_upgrades()
        else:
            self.wave_clear_timer = 0.0

    def _eligible_upgrades(self):
        result = []
        for upgrade in UPGRADES:
            name = upgrade[0]
            if name == "RAPID FIRE" and self.stats.fire_cooldown <= 0.085:
                continue
            if name == "BULLET SPEED" and self.stats.bullet_speed >= 950:
                continue
            if name == "FLEET FOOT" and self.stats.move_speed >= 420:
                continue
            if name == "PHASE DRIVE" and self.stats.dash_cooldown <= 0.52:
                continue
            if name == "MULTISHOT" and self.stats.projectiles >= 5:
                continue
            result.append(upgrade)
        return result

    def _show_upgrades(self):
        self.phase = "upgrade"
        for entity_id, bullet in list(self.bullets.items()):
            if bullet.hostile:
                self._destroy_bullet(entity_id)
        choices = self._eligible_upgrades()
        self.upgrade_choices = self.rng.sample(choices, k=min(3, len(choices)))
        self.font.set_text("upgrade_title", "CHOOSE AN UPGRADE", WIDTH / 2, 145, 4, HOT_YELLOW, center=True)
        card_centers = (220, 480, 740)
        for index, (name, description, icon) in enumerate(self.upgrade_choices):
            x = card_centers[index]
            self.overlay_ids.append(self.state.spawn(
                "ui_overlay", x=x, y=335, width=220, height=240,
                r=18, g=9, b=10, a=245,
            ))
            self.overlay_ids.append(self.state.spawn(
                "ui_overlay", x=x, y=335, width=220, height=240,
                r=255, g=174, b=36, a=255, thickness=0.025,
            ))
            self.state.spawn(
                "upgrade_icons", x=x, y=275, width=56, height=56,
                tile_x=icon,
            )
            self.font.set_text(f"upgrade_num_{index}", str(index + 1), x, 220, 3, BRIGHT_CHROME, center=True)
            self.font.set_text(f"upgrade_name_{index}", name, x, 325, 2, HOT_YELLOW, center=True)
            self.font.set_text(f"upgrade_desc_{index}", description, x, 375, 1, CHROME, center=True)

    @staticmethod
    def _upgrade_at(x, y):
        for index, center in enumerate((220, 480, 740)):
            if center - 110 <= x <= center + 110 and 215 <= y <= 455:
                return index
        return None

    def _apply_upgrade(self, name):
        if name == "RAPID FIRE":
            self.stats.fire_cooldown = max(0.08, self.stats.fire_cooldown * 0.84)
        elif name == "BULLET SPEED":
            self.stats.bullet_speed = min(960, self.stats.bullet_speed * 1.18)
        elif name == "HEAVY ROUNDS":
            self.stats.damage += 1
        elif name == "FLEET FOOT":
            self.stats.move_speed = min(430, self.stats.move_speed * 1.10)
        elif name == "PHASE DRIVE":
            self.stats.dash_cooldown = max(0.5, self.stats.dash_cooldown * 0.82)
        elif name == "ARMOR PLATE":
            self.stats.max_health += 20
            self.stats.health = min(self.stats.max_health, self.stats.health + 30)
        elif name == "ENERGY SHIELD":
            self.stats.shield_max += 1
        elif name == "MULTISHOT":
            self.stats.projectiles = min(5, self.stats.projectiles + 1)

        self.state.clear_batch("upgrade_icons")
        for entity_id in self.overlay_ids:
            self.state.destroy(entity_id)
        self.overlay_ids.clear()
        for key in list(self.font.groups):
            if key.startswith("upgrade_"):
                self.font.clear(key)
        self.stats.health = min(self.stats.max_health, self.stats.health + 12)
        self.wave += 1
        self._begin_wave()

    def _update_hud(self):
        health_ratio = self.stats.health / self.stats.max_health
        health_width = max(0.0, 204 * health_ratio)
        self.state.modify(self.health_fill, x=43 + health_width / 2, width=health_width)
        dash_ratio = 1.0 - self.dash_timer / self.stats.dash_cooldown
        dash_width = max(0.0, 204 * dash_ratio)
        self.state.modify(self.dash_fill, x=43 + dash_width / 2, width=dash_width)
        self.font.set_text("health", f"HP {self.stats.health}/{self.stats.max_health}", 42, 16, 1, BRIGHT_CHROME)
        self.font.set_text("wave", f"WAVE {self.wave}", WIDTH / 2, 16, 2, HOT_YELLOW, center=True)
        self.font.set_text("score", f"SCORE {self.score}", WIDTH - 100, 16, 2, CHROME, center=True)
        if self.stats.shield:
            self.font.set_text("shield", f"SHIELD {self.stats.shield}", 42, 48, 1, CHROME)
        else:
            self.font.clear("shield")


def pygame_time():
    """Late import keeps the gameplay module easy to import in logic tests."""
    import pygame
    return pygame.time.get_ticks() / 1000.0
