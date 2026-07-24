import pygame
import json
import math
import random
import os
import webbrowser
import time
import sys

from blocks import *
from renderer import draw_item_icon, render_clouds, render_weather
from mobs import DroppedItem, Slime, Zombie, DemonEye, Skeleton, Sheep
from world import GameWorld
from save import SaveManager   


# ------------------- ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ -------------------
class GamePlayer:
    """Управление игроком: физика с учётом dt, таймеры в секундах."""
    def __init__(self, world):
        self.world = world
        self.x, self.y = 0, 0
        self.vx, self.vy = 0, 0
        self.w, self.h = PLAYER_WIDTH, PLAYER_HEIGHT
        self.facing_right = True
        self.anim_frame = 0
        self.is_grounded = False
        self.hp = 100
        self.max_hp = 100
        self.invulnerable_timer = 0.0
        self.swing_anim = 0.0

    def spawn(self):
        ground_h = self.world._get_land_height(0)
        self.x = 0
        self.y = (ground_h - 2) * BLOCK_SIZE
        self.vx = self.vy = 0
        self.is_grounded = False
        self.hp = self.max_hp
        self.invulnerable_timer = 0.0

        # --- Поднимаем игрока, если он застрял в блоке ---
        attempts = 200
        while self._check_collision() and attempts > 0:
            self.y -= 1
            attempts -= 1
        if attempts == 0:  
            self.y = (ground_h - 10) * BLOCK_SIZE

    def update(self, keys, dt):
        self.vx = 0
        if keys.get(pygame.K_a) or keys.get(pygame.K_LEFT):
            self.vx = -PLAYER_SPEED
            self.facing_right = False
        if keys.get(pygame.K_d) or keys.get(pygame.K_RIGHT):
            self.vx = PLAYER_SPEED
            self.facing_right = True

        if (keys.get(pygame.K_w) or keys.get(pygame.K_SPACE) or keys.get(pygame.K_UP)) and self.is_grounded:
            self.vy = JUMP_FORCE
            self.is_grounded = False

        self.vy += GRAVITY * dt

        self.x += self.vx * dt
        if self._check_collision():
            self.x -= self.vx * dt

        self.y += self.vy * dt
        if self._check_collision():
            if self.vy > 0:
                self.is_grounded = True
            self.y -= self.vy * dt
            self.vy = 0

        if self.vx != 0:
            self.anim_frame += PLAYER_ANIM_SPEED * dt

        if self.invulnerable_timer > 0:
            self.invulnerable_timer -= dt
        if self.swing_anim > 0:
            self.swing_anim -= dt

    def _check_collision(self):
        left = int((self.x - self.w/2) // BLOCK_SIZE)
        right = int((self.x + self.w/2) // BLOCK_SIZE)
        top = int((self.y - self.h/2) // BLOCK_SIZE)
        bottom = int((self.y + self.h/2) // BLOCK_SIZE)
        for gx in range(left, right + 1):
            for gy in range(top, bottom + 1):
                b = self.world.get_block(gx, gy)
                if b != BLOCK_AIR and b not in (BLOCK_LEAVES, BLOCK_TALL_GRASS, BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW, BLOCK_FLOWER_BLUE):
                    return True
        return False

    def take_damage(self, damage, knockback_x=0):
        if self.invulnerable_timer <= 0:
            self.hp -= damage
            self.invulnerable_timer = 0.4
            self.vx = knockback_x
            self.vy = -7 * 60
            if self.hp <= 0:
                self.hp = self.max_hp
                self.spawn()

    def get_weapon_damage(self, inventory):
        itype = inventory.get_selected_item()['type']
        if itype == ITEM_SWORD_WOOD: return 12
        if itype == ITEM_SWORD_COPPER: return 18
        if itype == ITEM_SWORD_IRON: return 28
        if itype == ITEM_SWORD_GOLD: return 38
        if itype == ITEM_SWORD_DIAMOND: return 55
        return 6


class GameInventory:
    """Управление инвентарём и крафтом."""
    def __init__(self):
        self.slots = [{'type': BLOCK_AIR, 'count': 0} for _ in range(40)]
        self.slots[0] = {'type': ITEM_SWORD_WOOD, 'count': 1}
        self.slots[1] = {'type': ITEM_PICKAXE_WOOD, 'count': 1}
        self.slots[2] = {'type': BLOCK_DIRT, 'count': 20}
        self.selected_slot = 0
        self.dragged_slot = None

    def get_selected_item(self):
        return self.slots[self.selected_slot]

    def add_item(self, item_type, count=1):
        for slot in self.slots:
            if slot['type'] == item_type and slot['count'] < MAX_STACK:
                add = min(count, MAX_STACK - slot['count'])
                slot['count'] += add
                count -= add
                if count <= 0:
                    return True
        for slot in self.slots:
            if slot['type'] == BLOCK_AIR:
                slot['type'] = item_type
                slot['count'] = min(count, MAX_STACK)
                count -= slot['count']
                if count <= 0:
                    return True
        return False

    def can_craft(self, ingredients):
        for itype, count in ingredients:
            total = sum(s['count'] for s in self.slots if s['type'] == itype)
            if total < count:
                return False
        return True

    def craft(self, result, ingredients):
        if not self.can_craft(ingredients):
            return False
        for itype, count in ingredients:
            needed = count
            for slot in self.slots:
                if slot['type'] == itype:
                    take = min(needed, slot['count'])
                    slot['count'] -= take
                    needed -= take
                    if slot['count'] <= 0:
                        slot['type'] = BLOCK_AIR
                    if needed <= 0:
                        break
        return self.add_item(result['type'], result['count'])

    def swap_slots(self, idx1, idx2):
        self.slots[idx1], self.slots[idx2] = self.slots[idx2], self.slots[idx1]

    def get_slot(self, idx):
        return self.slots[idx]

    def to_dict(self):
        return self.slots

    def from_dict(self, data):
        self.slots = data


class GameMobManager:
    """Управление мобами и дропом с dt, спавн по времени."""
    def __init__(self, world):
        self.world = world
        self.mobs = []
        self.dropped_items = []
        self.spawn_timer = 0.0

    def update(self, player_x, player_y, is_night, player, dt):
        for mob in self.mobs[:]:
            mob.update(player_x, player_y, self.world.get_block, dt)
            if player.invulnerable_timer <= 0:
                if abs(player_x - mob.x) < 22 and abs(player_y - mob.y) < 26:
                    player.take_damage(mob.damage, 8 if player_x > mob.x else -8)

        for item in self.dropped_items[:]:
            item.update(player_x, player_y, self.world.get_block, dt)

        self.spawn_timer += dt
        if self.spawn_timer >= 2.0:
            self.spawn_timer = 0.0
            if len(self.mobs) < MAX_MOBS:
                offset = random.choice([-1, 1]) * random.randint(450, 750)
                sx = player_x + offset
                gx = int(sx // BLOCK_SIZE)
                sy = (self.world._get_land_height(gx) - 2) * BLOCK_SIZE

                if is_night:
                    r = random.random()
                    if r < 0.4:
                        mob = Zombie(sx, sy)
                    elif r < 0.7:
                        mob = DemonEye(sx, sy - 100)
                    else:
                        mob = Skeleton(sx, sy)
                else:
                    if random.random() < 0.4:
                        mob = Sheep(sx, sy)
                    else:
                        is_blue = random.random() < 0.35
                        mob = Slime(sx, sy, is_blue)

                # --- Поднимаем моба, если он внутри блока ---
                attempts = 100
                while mob.check_collision(self.world.get_block) and attempts > 0:
                    mob.y -= 1
                    attempts -= 1

                self.mobs.append(mob)

    def add_dropped_item(self, x, y, item_type, count=1):
        self.dropped_items.append(DroppedItem(x, y, item_type, count))

    def remove_mob(self, mob):
        if mob in self.mobs:
            self.mobs.remove(mob)

    def clear(self):
        self.mobs.clear()
        self.dropped_items.clear()
        self.spawn_timer = 0.0

    def to_dict(self):
        return [m.to_dict() for m in self.mobs], [i.to_dict() for i in self.dropped_items]

    def from_dict(self, mobs_data, items_data):
        self.mobs.clear()
        for md in mobs_data:
            m_type = md['type']
            if m_type == 'Slime':
                m = Slime(md['x'], md['y'], md.get('is_blue', False))
            elif m_type == 'Zombie':
                m = Zombie(md['x'], md['y'])
            elif m_type == 'DemonEye':
                m = DemonEye(md['x'], md['y'])
            elif m_type == 'Skeleton':
                m = Skeleton(md['x'], md['y'])
            elif m_type == 'Sheep':
                m = Sheep(md['x'], md['y'])
            else:
                continue
            m.hp = md['hp']
            self.mobs.append(m)
        self.dropped_items = [DroppedItem.from_dict(it) for it in items_data]


# ------------------- ОСНОВНОЙ КЛАСС GAME -------------------
class Game:
    def __init__(self):
        pygame.init()
        self.screen_width = SCREEN_WIDTH
        self.screen_height = SCREEN_HEIGHT
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("MinePy 2D")
        self.clock = pygame.time.Clock()
        self.running = True
        self.is_fullscreen = False

        self.init_fonts()
        self.game_state = "menu"

        self.world = GameWorld()
        self.player = GamePlayer(self.world)
        self.inventory = GameInventory()
        self.mob_manager = GameMobManager(self.world)

        # Менеджер сохранения – создаём после всех компонентов
        self.save_manager = SaveManager(self)   

        self.day_time = 3000
        self.day_counter = 0
        self.save_notification_timer = 0.0
        self.inventory_open = False
        self.pause_menu_open = False
        self.keys = {}
        self.mouse_x, self.mouse_y = 0, 0

        self.fps_counter = 0
        self.current_fps = 0
        self.last_fps_time = time.time()

        self.menu_buttons = []
        self.pause_buttons = []

        # Погода
        self.weather = WEATHER_CLEAR
        self.weather_timer = 0.0
        self.weather_alpha = 1.0
        self.weather_transition_time = WEATHER_TRANSITION_TIME

        self._init_weather_particles()
        self._init_clouds()
        self._init_stars()

        # --- КЕШИРОВАНИЕ ФОНА ---
        self.bg_surfaces = {}
        self._build_background_surfaces()

    def _init_clouds(self):
        self.clouds = []
        for _ in range(CLOUDS_COUNT):
            self.clouds.append({
                'x': random.randint(0, self.screen_width * 2),
                'y': random.randint(-200, 100),
                'w': random.randint(200, 400),
                'h': random.randint(40, 80),
                'speed': random.uniform(10, 30)
            })

    def _init_weather_particles(self):
        self.rain_particles = []
        for _ in range(RAIN_PARTICLES):
            x = random.randint(0, self.screen_width)
            y = random.randint(-self.screen_height, self.screen_height)
            speed = random.uniform(300, 500)
            self.rain_particles.append((x, y, speed))

        self.snow_particles = []
        for _ in range(SNOW_PARTICLES):
            x = random.randint(0, self.screen_width)
            y = random.randint(-self.screen_height, self.screen_height)
            size = random.uniform(2, 5)
            speed = random.uniform(50, 120)
            self.snow_particles.append((x, y, size, speed))

    def _init_stars(self):
        self.stars = []
        for _ in range(STARS_COUNT):
            x = random.randint(0, self.screen_width)
            y = random.randint(0, self.screen_height)
            size = random.uniform(1, 3)
            brightness = random.uniform(0.3, 1.0)
            twinkle_speed = random.uniform(0.5, 2.0)
            phase = random.uniform(0, 6.28)
            self.stars.append([x, y, size, brightness, twinkle_speed, phase])

    def _build_background_surfaces(self):
        """Создаёт закешированные поверхности для фона при текущем разрешении."""
        self.bg_surfaces.clear()
        intervals = {
            'day': 0,
            'sunset': 11000,
            'night': 17000,
            'sunrise': 23000
        }
        for key, t in intervals.items():
            surf = pygame.Surface((self.screen_width, self.screen_height))
            top_color, bottom_color = self.get_sky_gradient(t)
            for y in range(self.screen_height):
                blend = y / self.screen_height
                r = int(top_color[0] + (bottom_color[0] - top_color[0]) * blend)
                g = int(top_color[1] + (bottom_color[1] - top_color[1]) * blend)
                b = int(top_color[2] + (bottom_color[2] - top_color[2]) * blend)
                pygame.draw.line(surf, (r, g, b), (0, y), (self.screen_width, y))
            self.bg_surfaces[key] = surf

    def init_fonts(self):
        font_name = pygame.font.match_font('arial') or pygame.font.match_font('dejavusans')
        self.font_small = pygame.font.Font(font_name, 13)
        self.font_med = pygame.font.Font(font_name, 18)
        self.font_big = pygame.font.Font(font_name, 32)
        self.font_huge = pygame.font.Font(font_name, 52)

    def is_night(self):
        return 11000 <= (self.day_time % 24000) <= 23000

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            info = pygame.display.Info()
            self.screen_width, self.screen_height = info.current_w, info.current_h
        else:
            self.screen_width, self.screen_height = 1100, 700
            self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        self._init_weather_particles()
        self._init_clouds()
        self._init_stars()
        self._build_background_surfaces()

    def toggle_inventory(self):
        if self.pause_menu_open:
            return
        self.inventory_open = not self.inventory_open
        if not self.inventory_open:
            self.inventory.dragged_slot = None

    def toggle_pause(self):
        if self.inventory_open:
            self.inventory_open = False
        self.pause_menu_open = not self.pause_menu_open

    def open_github(self):
        webbrowser.open("https://github.com/KIziName/MinePy")

    def start_game(self, is_new=True):
        if is_new:
            self.reset_game_data()
            self.player.spawn()
        self.game_state = "game"
        self.inventory_open = False
        self.pause_menu_open = False

    def load_and_start_game(self):
        if self.save_manager.load():          
            self.start_game(is_new=False)

    def reset_game_data(self):
        self.inventory_open = False
        self.pause_menu_open = False
        self.day_time = 3000
        self.day_counter = 0
        self.save_notification_timer = 0.0
        self.keys.clear()
        self.world.clear()
        self.mob_manager.clear()
        self.inventory = GameInventory()
        self.player = GamePlayer(self.world)
        self.player.spawn()
        self.weather = WEATHER_CLEAR
        self.weather_timer = 0.0
        self.weather_alpha = 1.0
        self._init_weather_particles()
        self._init_clouds()
        self._init_stars()
        self._build_background_surfaces()

    def update_physics(self, dt):
        if self.game_state != "game":
            return
        if self.inventory_open or self.pause_menu_open:
            return

        old_day_time = self.day_time
        self.day_time = (self.day_time + 120 * dt) % 24000
        if old_day_time > 23000 and self.day_time < 1000:
            self.day_counter += 1

        self.player.update(self.keys, dt)
        self.mob_manager.update(self.player.x, self.player.y, self.is_night(), self.player, dt)

        for item in self.mob_manager.dropped_items[:]:
            if math.hypot(self.player.x - item.x, self.player.y - item.y) < 28:
                if self.inventory.add_item(item.item_type, item.count):
                    self.mob_manager.dropped_items.remove(item)

        if self.save_notification_timer > 0:
            self.save_notification_timer -= dt

        # Погода
        self.weather_timer -= dt
        if self.weather_timer <= 0:
            new_weather = random.choice([WEATHER_CLEAR, WEATHER_RAIN, WEATHER_SNOW])
            if new_weather != self.weather:
                self.weather = new_weather
                self.weather_alpha = 0.0
            self.weather_timer = random.uniform(WEATHER_CHANGE_INTERVAL_MIN, WEATHER_CHANGE_INTERVAL_MAX)

        if self.weather_alpha < 1.0:
            self.weather_alpha += dt / self.weather_transition_time
            if self.weather_alpha > 1.0:
                self.weather_alpha = 1.0

        if self.weather == WEATHER_RAIN and self.weather_alpha > 0:
            for i, (x, y, speed) in enumerate(self.rain_particles):
                y += speed * dt
                if y > self.screen_height + 20:
                    y = random.randint(-30, -10)
                    x = random.randint(0, self.screen_width)
                self.rain_particles[i] = (x, y, speed)
        elif self.weather == WEATHER_SNOW and self.weather_alpha > 0:
            for i, (x, y, size, speed) in enumerate(self.snow_particles):
                y += speed * dt
                x += math.sin(y * 0.01) * 0.5
                if y > self.screen_height + 20:
                    y = random.randint(-30, -10)
                    x = random.randint(0, self.screen_width)
                self.snow_particles[i] = (x, y, size, speed)

        for cloud in self.clouds:
            cloud['x'] += cloud['speed'] * dt
            if cloud['x'] > self.screen_width + 400:
                cloud['x'] = -400 - cloud['w']
                cloud['y'] = random.randint(-200, 100)
                cloud['w'] = random.randint(200, 400)
                cloud['h'] = random.randint(40, 80)
                cloud['speed'] = random.uniform(10, 30)

    def get_sky_gradient(self, t):
        if t < 10000:
            return (30, 80, 200), (135, 206, 250)
        elif t < 12000:
            return (30, 80, 200), (255, 140, 0)
        elif t < 22000:
            return (5, 7, 20), (20, 30, 60)
        else:
            return (5, 7, 20), (255, 180, 100)

    def draw_moon(self, cx, cy, radius=30):
        if not self.is_night():
            return
        phase = (self.day_counter % 8) / 8.0
        moon_color = (220, 220, 240)
        pygame.draw.circle(self.screen, moon_color, (cx, cy), radius)
        if 0.05 < phase < 0.95:
            offset = radius * (1 - 2 * phase)
            shadow_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
            pygame.draw.circle(shadow_surf, (0, 0, 0, 200), (radius + offset, radius), radius)
            self.screen.blit(shadow_surf, (cx - radius, cy - radius), special_flags=pygame.BLEND_RGBA_SUB)

    def draw_player(self, px, py):
        if self.player.invulnerable_timer > 0:
            if int(time.time() * 10) % 2 == 0:
                return

        face_dir = 1 if self.player.facing_right else -1
        leg_step = math.sin(self.player.anim_frame) * 5 if self.player.is_grounded and self.player.vx != 0 else 0

        pygame.draw.rect(self.screen, (21, 101, 192), (px - 6 + leg_step, py + 8, 5, 14))
        pygame.draw.rect(self.screen, (13, 71, 161), (px + 1 - leg_step, py + 8, 5, 14))
        pygame.draw.rect(self.screen, (198, 40, 40), (px - 7, py - 8, 14, 16), 0, 2)
        pygame.draw.circle(self.screen, (255, 204, 128), (int(px), int(py - 14)), 8)
        pygame.draw.arc(self.screen, (121, 85, 72), (px - 8, py - 22, 16, 12), 0, math.pi, 4)

        eye_x = px + (3 * face_dir)
        pygame.draw.circle(self.screen, (33, 33, 33), (int(eye_x), int(py - 15)), 2)

        hand_x = px + (6 * face_dir)
        hand_y = py - 2
        swing_progress = self.player.swing_anim / 0.15 if self.player.swing_anim > 0 else 0
        swing_angle = (1 - swing_progress) * 80 if self.player.swing_anim > 0 else 0
        if not self.player.facing_right:
            swing_angle = -swing_angle

        curr_item = self.inventory.get_selected_item()['type']
        if curr_item != BLOCK_AIR:
            item_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            draw_item_icon(item_surf, curr_item, 0, 0, size=32)
            if not self.player.facing_right:
                item_surf = pygame.transform.flip(item_surf, True, False)
            rotated_item = pygame.transform.rotate(item_surf, -swing_angle if self.player.facing_right else swing_angle)
            item_rect = rotated_item.get_rect(center=(hand_x + (8 * face_dir), hand_y))
            self.screen.blit(rotated_item, item_rect)

        pygame.draw.circle(self.screen, (255, 204, 128), (int(hand_x), int(hand_y)), 3)

    def render(self):
        if self.game_state != "game":
            return

        # --- Используем закешированную поверхность фона ---
        t = self.day_time % 24000
        if t < 10000:
            bg = self.bg_surfaces['day']
        elif t < 12000:
            bg = self.bg_surfaces['sunset']
        elif t < 22000:
            bg = self.bg_surfaces['night']
        else:
            bg = self.bg_surfaces['sunrise']
        self.screen.blit(bg, (0, 0))

        # Звёзды (рисуются поверх фона)
        if self.is_night():
            moon_x = self.screen_width - 100
            moon_y = 100
            moon_radius = 40
            now = time.time()
            for star in self.stars:
                x, y, size, brightness, twinkle_speed, phase = star
                dist = math.hypot(x - moon_x, y - moon_y)
                if dist < moon_radius * 2:
                    factor = max(0, (dist - moon_radius) / moon_radius)
                    brightness *= factor
                alpha = int(255 * brightness * (0.7 + 0.3 * math.sin(now * twinkle_speed + phase)))
                if alpha > 0:
                    star_surf = pygame.Surface((int(size*2)+2, int(size*2)+2), pygame.SRCALPHA)
                    pygame.draw.circle(star_surf, (255, 255, 255, alpha), (int(size)+1, int(size)+1), int(size))
                    self.screen.blit(star_surf, (int(x-size-1), int(y-size-1)))

        # Облака
        render_clouds(self.screen, self.clouds, self.screen_width, self.screen_height)

        # Солнце
        sun_angle = ((t % 24000) / 24000.0) * math.pi * 2 - math.pi / 2
        sun_x = self.screen_width / 2 + math.cos(sun_angle) * (self.screen_width * 0.45)
        sun_y = self.screen_height / 2 + math.sin(sun_angle) * (self.screen_height * 0.4)
        if sun_y < self.screen_height - 100:
            col = (255, 215, 0) if 0 <= t < 12000 else (236, 239, 241)
            pygame.draw.circle(self.screen, col, (int(sun_x), int(sun_y)), 22)

        self.draw_moon(self.screen_width - 100, 100, 35)

        # Чанки
        cam_x = self.player.x - self.screen_width / 2
        cam_y = self.player.y - self.screen_height / 2
        start_chunk = int(cam_x // (CHUNK_WIDTH * BLOCK_SIZE)) - 1
        end_chunk = int((cam_x + self.screen_width) // (CHUNK_WIDTH * BLOCK_SIZE)) + 2
        for cx in range(start_chunk, end_chunk):
            surf = self.world.get_chunk_surface(cx)
            x = cx * CHUNK_WIDTH * BLOCK_SIZE - cam_x
            y = -cam_y
            self.screen.blit(surf, (x, y))

        # Дроп
        for item in self.mob_manager.dropped_items:
            sx = item.x - cam_x
            sy = item.y - cam_y + math.sin(item.bob_angle) * 4
            draw_item_icon(self.screen, item.item_type, int(sx - 12), int(sy - 12), size=24)

        # Мобы
        for mob in self.mob_manager.mobs:
            sx, sy = mob.x - cam_x, mob.y - cam_y
            if isinstance(mob, Slime):
                pygame.draw.ellipse(self.screen, mob.color, (sx-16, sy-12, 32, 24), 0)
                pygame.draw.ellipse(self.screen, (255,255,255), (sx-16, sy-12, 32, 24), 2)
            elif isinstance(mob, Zombie):
                pygame.draw.rect(self.screen, (56, 142, 60), (sx-12, sy-22, 24, 44), 0)
                pygame.draw.rect(self.screen, (93, 64, 55), (sx-10, sy-20, 20, 12))
            elif isinstance(mob, DemonEye):
                pygame.draw.circle(self.screen, (236, 239, 241), (int(sx), int(sy)), 14)
                pygame.draw.circle(self.screen, (211, 47, 47), (int(sx), int(sy)), 6)
            elif isinstance(mob, Skeleton):
                pygame.draw.rect(self.screen, (224, 224, 224), (sx-11, sy-21, 22, 42), 0)
            elif isinstance(mob, Sheep):
                pygame.draw.ellipse(self.screen, (255, 255, 255), (sx-15, sy-10, 30, 22), 0)
                pygame.draw.ellipse(self.screen, (200, 200, 200), (sx-15, sy-10, 30, 22), 2)

            bar_w = 30
            hp_pct = max(0, mob.hp / mob.max_hp)
            pygame.draw.rect(self.screen, (50,50,50), (sx - bar_w//2, sy - mob.h//2 - 10, bar_w, 4))
            if hp_pct > 0:
                pygame.draw.rect(self.screen, (118, 255, 3), (sx - bar_w//2, sy - mob.h//2 - 10, bar_w * hp_pct, 4))

        # Игрок
        px, py = self.player.x - cam_x, self.player.y - cam_y
        self.draw_player(px, py)

        # HP
        hp_x, hp_y = self.screen_width - 220, 20
        hp_pct = max(0, self.player.hp / self.player.max_hp)
        pygame.draw.rect(self.screen, (28, 37, 65), (hp_x, hp_y, 180, 22), 0)
        pygame.draw.rect(self.screen, (58, 80, 107), (hp_x, hp_y, 180, 22), 2)
        if hp_pct > 0:
            pygame.draw.rect(self.screen, (230, 57, 70), (hp_x+2, hp_y+2, 176*hp_pct, 18))
        hp_text = self.font_small.render(f"HP: {self.player.hp} / {self.player.max_hp}", True, (255,255,255))
        self.screen.blit(hp_text, (hp_x+45, hp_y+4))

        # FPS
        fps_color = (118, 255, 3) if self.current_fps >= 30 else (255, 82, 82)
        pygame.draw.rect(self.screen, (11, 19, 43), (self.screen_width // 2 - 45, 15, 90, 26), 0)
        pygame.draw.rect(self.screen, (58, 80, 107), (self.screen_width // 2 - 45, 15, 90, 26), 2)
        fps_text = self.font_small.render(f"FPS: {self.current_fps}", True, fps_color)
        self.screen.blit(fps_text, (self.screen_width // 2 - 25, 20))

        self.draw_hotbar()

        # Погода (дождь/снег)
        render_weather(self.screen, self.weather, self.rain_particles, self.snow_particles,
                       alpha=self.weather_alpha, width=self.screen_width, height=self.screen_height)

        if self.inventory_open:
            self.draw_inventory()
        if self.pause_menu_open:
            self.draw_pause()

        if self.save_notification_timer > 0:
            msg_surf = self.font_med.render("✓ Мир успешно сохранен!", True, (118, 255, 3))
            rect_w, rect_h = msg_surf.get_width() + 30, 36
            rect_x = self.screen_width // 2 - rect_w // 2
            rect_y = self.screen_height - 60
            pygame.draw.rect(self.screen, (11, 19, 43), (rect_x, rect_y, rect_w, rect_h), 0, 4)
            pygame.draw.rect(self.screen, (118, 255, 3), (rect_x, rect_y, rect_w, rect_h), 2, 4)
            self.screen.blit(msg_surf, (rect_x + 15, rect_y + 8))

        if self.inventory.dragged_slot is not None:
            item = self.inventory.get_slot(self.inventory.dragged_slot)
            if item['type'] != BLOCK_AIR:
                draw_item_icon(self.screen, item['type'], self.mouse_x - 16, self.mouse_y - 16, size=32)

    # ------------------- ИНТЕРФЕЙСНЫЕ МЕТОДЫ -------------------
    def draw_hotbar(self):
        bar_x, bar_y = 15, 15
        for i in range(10):
            x, y = bar_x + i*48, bar_y
            item = self.inventory.get_slot(i)
            color = (11, 19, 43) if i != self.inventory.selected_slot else (255, 215, 0)
            pygame.draw.rect(self.screen, color, (x, y, 44, 44), 0)
            pygame.draw.rect(self.screen, (58, 80, 107), (x, y, 44, 44), 2 if i != self.inventory.selected_slot else 3)
            if item['type'] != BLOCK_AIR:
                draw_item_icon(self.screen, item['type'], x + 6, y + 6, size=32)
                if item['count'] > 1:
                    cnt = self.font_small.render(str(item['count']), True, (255,255,255))
                    self.screen.blit(cnt, (x + 22, y + 25))

    def draw_inventory(self):
        inv_w, inv_h = 490, 360
        inv_x, inv_y = 15, 70

        s = pygame.Surface((inv_w, inv_h))
        s.set_alpha(225)
        s.fill((11, 19, 43))
        self.screen.blit(s, (inv_x, inv_y))
        pygame.draw.rect(self.screen, (255, 215, 0), (inv_x, inv_y, inv_w, inv_h), 2)

        title = self.font_med.render("ИНВЕНТАРЬ И КРАФТ", True, (255, 215, 0))
        self.screen.blit(title, (inv_x + 160, inv_y + 10))

        for row in range(3):
            for col in range(10):
                idx = (row+1)*10 + col
                x, y = inv_x + 12 + col*46, inv_y + 40 + row*46
                item = self.inventory.get_slot(idx)
                is_selected = (self.inventory.dragged_slot == idx)
                bg_col = (28, 37, 65) if not is_selected else (58, 80, 107)
                pygame.draw.rect(self.screen, bg_col, (x, y, 42, 42), 0)
                pygame.draw.rect(self.screen, (58, 80, 107), (x, y, 42, 42), 1)
                if item['type'] != BLOCK_AIR and not is_selected:
                    draw_item_icon(self.screen, item['type'], x + 5, y + 5, size=32)
                    if item['count'] > 1:
                        cnt = self.font_small.render(str(item['count']), True, (255,255,255))
                        self.screen.blit(cnt, (x + 22, y + 24))

        craft_y = inv_y + 185
        for result, ingredients in CRAFTING_RECIPES:
            can_craft = self.inventory.can_craft(ingredients)
            color = (46, 125, 50) if can_craft else (38, 50, 56)
            rect = pygame.Rect(inv_x + 12, craft_y, 466, 24)
            pygame.draw.rect(self.screen, color, rect, 0)
            pygame.draw.rect(self.screen, (255,255,255), rect, 1)
            res_name = ITEM_NAMES.get(result['type'], "Предмет")
            req_text = " + ".join([f"{count}x {ITEM_NAMES.get(itype, '')}" for itype, count in ingredients])
            label = f"{res_name} (x{result['count']}) <-- [{req_text}]"
            text = self.font_small.render(label, True, (255,255,255))
            self.screen.blit(text, (inv_x + 20, craft_y + 4))
            craft_y += 27

    def draw_pause(self):
        s = pygame.Surface((self.screen_width, self.screen_height))
        s.set_alpha(180)
        s.fill((0,0,0))
        self.screen.blit(s, (0,0))

        box_w, box_h = 300, 270
        box_x = self.screen_width // 2 - box_w // 2
        box_y = self.screen_height // 2 - box_h // 2
        pygame.draw.rect(self.screen, (11, 19, 43), (box_x, box_y, box_w, box_h))
        pygame.draw.rect(self.screen, (58, 80, 107), (box_x, box_y, box_w, box_h), 2)

        title = self.font_big.render("ПАУЗА", True, (255, 215, 0))
        self.screen.blit(title, (box_x + box_w // 2 - title.get_width() // 2, box_y + 20))

        self.pause_buttons = []
        btn_y = box_y + 75
        btn_texts = [
            ("Продолжить", self.toggle_pause, (46, 125, 50), (27, 94, 32)),
            ("Полный экран", self.toggle_fullscreen, (255, 183, 3), (251, 133, 0)),
            ("Сохранить мир", self.save_manager.save, (21, 101, 192), (13, 71, 161)),   
            ("Главное меню", self.show_main_menu, (211, 47, 47), (154, 0, 7))
        ]
        for text, action, color, hover_color in btn_texts:
            rect = pygame.Rect(box_x + 30, btn_y, 240, 36)
            is_hover = rect.collidepoint((self.mouse_x, self.mouse_y))
            draw_color = hover_color if is_hover else color
            self.pause_buttons.append((rect, action))
            pygame.draw.rect(self.screen, draw_color, rect, 0)
            pygame.draw.rect(self.screen, (255,255,255), rect, 1)
            txt = self.font_med.render(text, True, (255,255,255))
            self.screen.blit(txt, (rect.x + (rect.width - txt.get_width()) // 2, rect.y + 7))
            btn_y += 43

    def draw_menu(self):
        self.screen.fill((11, 19, 43))
        title = self.font_huge.render("MinePy 2D", True, (255, 215, 0))
        self.screen.blit(title, (self.screen_width // 2 - title.get_width() // 2, 60))
        sub = self.font_small.render("Версия: 0.2", True, (141, 153, 174))
        self.screen.blit(sub, (self.screen_width // 2 - sub.get_width() // 2, 120))

        self.menu_buttons = []
        btn_y = 155
        btn_data = [
            ("GitHub: MinePy", self.open_github, (0, 0, 0, 0), (28, 37, 65)),
            ("НОВАЯ ИГРА", self.start_game, (46, 125, 50), (27, 94, 32)),
            ("ЗАГРУЗИТЬ МИР", self.load_and_start_game, (21, 101, 192), (13, 71, 161)),
            ("Полный экран", self.toggle_fullscreen, (255, 183, 3), (251, 133, 0)),
            ("ВЫХОД", sys.exit, (211, 47, 47), (154, 0, 7))
        ]
        for text, action, color, hover_color in btn_data:
            if text == "GitHub: MinePy":
                rect = pygame.Rect(self.screen_width // 2 - 130, btn_y, 260, 30)
                is_hover = rect.collidepoint((self.mouse_x, self.mouse_y))
                self.menu_buttons.append((rect, action))
                txt = self.font_med.render(text, True, (76, 201, 240) if is_hover else (0, 180, 216))
                self.screen.blit(txt, (rect.x + (rect.width - txt.get_width()) // 2, rect.y + 4))
                btn_y += 40
            else:
                rect = pygame.Rect(self.screen_width // 2 - 130, btn_y, 260, 42)
                is_hover = rect.collidepoint((self.mouse_x, self.mouse_y))
                self.menu_buttons.append((rect, action))
                draw_color = hover_color if is_hover else color
                pygame.draw.rect(self.screen, draw_color, rect, 0)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)
                txt = self.font_med.render(text, True, (255, 255, 255))
                self.screen.blit(txt, (rect.x + (rect.width - txt.get_width()) // 2, rect.y + 9))
                btn_y += 52
        author = self.font_small.render("Автор: KIziName", True, (224, 225, 221))
        self.screen.blit(author, (self.screen_width // 2 - author.get_width() // 2, self.screen_height - 35))

    def show_main_menu(self):
        self.game_state = "menu"
        self.inventory_open = False
        self.pause_menu_open = False
        self.world.clear()
        self.mob_manager.clear()

    # ------------------- ОБРАБОТКА СОБЫТИЙ -------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if self.game_state == "game":
                    if event.key == pygame.K_e:
                        self.toggle_inventory()
                    elif event.key == pygame.K_ESCAPE:
                        self.toggle_pause()
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                                       pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0):
                        if event.key == pygame.K_0:
                            self.inventory.selected_slot = 9
                        else:
                            self.inventory.selected_slot = event.key - pygame.K_1
                self.keys[event.key] = True

            elif event.type == pygame.KEYUP:
                self.keys[event.key] = False

            elif event.type == pygame.MOUSEMOTION:
                self.mouse_x, self.mouse_y = event.pos

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if self.game_state == "menu":
                        self.handle_menu_click(event.pos)
                    elif self.game_state == "game":
                        if self.pause_menu_open:
                            self.handle_pause_click(event.pos)
                        elif self.inventory_open:
                            self.handle_inventory_click(event.pos)
                        else:
                            if not self.check_hotbar_click(event.pos):
                                self.handle_game_click(event.pos, button=1)
                elif event.button == 3:
                    if self.game_state == "game" and not self.inventory_open and not self.pause_menu_open:
                        self.handle_game_click(event.pos, button=3)
                elif event.button == 4:
                    if self.game_state == "game" and not self.inventory_open and not self.pause_menu_open:
                        self.inventory.selected_slot = (self.inventory.selected_slot - 1) % 10
                elif event.button == 5:
                    if self.game_state == "game" and not self.inventory_open and not self.pause_menu_open:
                        self.inventory.selected_slot = (self.inventory.selected_slot + 1) % 10

    def check_hotbar_click(self, pos):
        bar_x, bar_y = 15, 15
        for i in range(10):
            rect = pygame.Rect(bar_x + i * 48, bar_y, 44, 44)
            if rect.collidepoint(pos):
                if self.inventory_open:
                    if self.inventory.dragged_slot is None:
                        if self.inventory.get_slot(i)['type'] != BLOCK_AIR:
                            self.inventory.dragged_slot = i
                    else:
                        self.inventory.swap_slots(i, self.inventory.dragged_slot)
                        self.inventory.dragged_slot = None
                else:
                    self.inventory.selected_slot = i
                return True
        return False

    def handle_menu_click(self, pos):
        for rect, action in self.menu_buttons:
            if rect.collidepoint(pos):
                action()

    def handle_pause_click(self, pos):
        for rect, action in self.pause_buttons:
            if rect.collidepoint(pos):
                action()

    def handle_inventory_click(self, pos):
        if self.check_hotbar_click(pos):
            return

        inv_x, inv_y = 15, 70
        for row in range(3):
            for col in range(10):
                idx = (row + 1) * 10 + col
                rect = pygame.Rect(inv_x + 12 + col * 46, inv_y + 40 + row * 46, 42, 42)
                if rect.collidepoint(pos):
                    if self.inventory.dragged_slot is None:
                        if self.inventory.get_slot(idx)['type'] != BLOCK_AIR:
                            self.inventory.dragged_slot = idx
                    else:
                        self.inventory.swap_slots(idx, self.inventory.dragged_slot)
                        self.inventory.dragged_slot = None
                    return

        craft_y = inv_y + 185
        for result, ingredients in CRAFTING_RECIPES:
            rect = pygame.Rect(inv_x + 12, craft_y, 466, 24)
            if rect.collidepoint(pos):
                self.inventory.craft(result, ingredients)
                return
            craft_y += 27

        if not (inv_x <= pos[0] <= inv_x + 490 and inv_y <= pos[1] <= inv_y + 360):
            self.toggle_inventory()

    def handle_game_click(self, pos, button=1):
        cam_x = self.player.x - self.screen_width / 2
        cam_y = self.player.y - self.screen_height / 2
        wx, wy = pos[0] + cam_x, pos[1] + cam_y

        if math.hypot(wx - self.player.x, wy - self.player.y) > BUILD_REACH:
            return

        if button == 1:
            self.player.swing_anim = 0.15
            slot = self.inventory.get_selected_item()

            if slot['type'] in (ITEM_POTION, ITEM_BIG_POTION):
                heal = 40 if slot['type'] == ITEM_POTION else 80
                if self.player.hp < self.player.max_hp:
                    self.player.hp = min(self.player.max_hp, self.player.hp + heal)
                    slot['count'] -= 1
                    if slot['count'] <= 0:
                        slot['type'] = BLOCK_AIR
                return

            dmg = self.player.get_weapon_damage(self.inventory)
            for mob in self.mob_manager.mobs[:]:
                if abs(mob.x - wx) < 30 and abs(mob.y - wy) < 30:
                    mob.hp -= dmg
                    mob.vy = -4.0 * 60
                    if mob.hp <= 0:
                        drop_type = None
                        if isinstance(mob, Slime):
                            drop_type, count = ITEM_GEL, random.randint(1, 3)
                        elif isinstance(mob, Zombie):
                            drop_type, count = ITEM_COIN, random.randint(1, 4)
                        elif isinstance(mob, DemonEye):
                            drop_type, count = ITEM_LENS, 1
                        elif isinstance(mob, Skeleton):
                            drop_type, count = ITEM_BONE, random.randint(1, 2)
                        elif isinstance(mob, Sheep):
                            drop_type, count = ITEM_GEL, random.randint(1, 2)
                        if drop_type is not None:
                            self.mob_manager.add_dropped_item(mob.x, mob.y, drop_type, count)
                        self.mob_manager.remove_mob(mob)
                    return

            gx, gy = int(wx // BLOCK_SIZE), int(wy // BLOCK_SIZE)
            b_type = self.world.get_block(gx, gy)
            if b_type != BLOCK_AIR:
                if b_type in (BLOCK_TALL_GRASS, BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW, BLOCK_FLOWER_BLUE):
                    if not self.inventory.add_item(b_type, 1):
                        self.mob_manager.add_dropped_item((gx + 0.5) * BLOCK_SIZE, (gy + 0.5) * BLOCK_SIZE, b_type, 1)
                    self.world.set_block(gx, gy, BLOCK_AIR)
                    return
                self.world.set_block(gx, gy, BLOCK_AIR)
                drop_item = ITEM_COAL if b_type == BLOCK_COAL_ORE else b_type
                self.mob_manager.add_dropped_item((gx + 0.5) * BLOCK_SIZE, (gy + 0.5) * BLOCK_SIZE, drop_item, 1)

        elif button == 3:
            gx, gy = int(wx // BLOCK_SIZE), int(wy // BLOCK_SIZE)
            slot = self.inventory.get_selected_item()
            placeable = [BLOCK_DIRT, BLOCK_GRASS, BLOCK_STONE, BLOCK_WOOD,
                         BLOCK_LEAVES, BLOCK_COPPER_ORE, BLOCK_IRON_ORE,
                         BLOCK_GOLD_ORE, BLOCK_COAL_ORE,
                         BLOCK_TALL_GRASS, BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW, BLOCK_FLOWER_BLUE]
            if slot['type'] in placeable and slot['count'] > 0:
                if self.world.get_block(gx, gy) == BLOCK_AIR:
                    # Проверка, не перекрывает ли новый блок игрока 
                    block_rect = pygame.Rect(gx * BLOCK_SIZE, gy * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                    player_rect = pygame.Rect(
                        self.player.x - self.player.w / 2,
                        self.player.y - self.player.h / 2,
                        self.player.w,
                        self.player.h
                    )
                    if not block_rect.colliderect(player_rect):
                        self.world.set_block(gx, gy, slot['type'])
                        slot['count'] -= 1
                        if slot['count'] <= 0:
                            slot['type'] = BLOCK_AIR