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


# ------------------- ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ (внутри Game) -------------------

class GameWorld:
    """Отвечает за генерацию, хранение и рендеринг чанков."""
    def __init__(self):
        self.chunks = {}
        self.chunk_surfaces = {}
        self.dirty_chunks = set()
        self.land_height_cache = {}

    def _get_land_height(self, global_gx):
        if global_gx not in self.land_height_cache:
            h = int(40 - (math.sin(global_gx * 0.04) * 6 + math.cos(global_gx * 0.1) * 3))
            self.land_height_cache[global_gx] = h
        return self.land_height_cache[global_gx]

    def get_chunk(self, chunk_x):
        if chunk_x not in self.chunks:
            self.chunks[chunk_x] = self._generate_chunk(chunk_x)
            self.dirty_chunks.add(chunk_x)
        return self.chunks[chunk_x]

    def _generate_chunk(self, chunk_x):
        chunk = [[BLOCK_AIR for _ in range(CHUNK_WIDTH)] for _ in range(WORLD_HEIGHT)]
        for local_x in range(CHUNK_WIDTH):
            global_gx = chunk_x * CHUNK_WIDTH + local_x
            ground_h = self._get_land_height(global_gx)

            for gy in range(WORLD_HEIGHT - 1, ground_h, -1):
                if gy == ground_h + 1:
                    chunk[gy][local_x] = BLOCK_GRASS
                    # Генерация декораций на поверхности
                    if random.random() < 0.15:
                        if random.random() < 0.4:
                            chunk[gy][local_x] = BLOCK_TALL_GRASS
                        else:
                            flower = random.choice([BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW, BLOCK_FLOWER_BLUE])
                            chunk[gy][local_x] = flower
                elif gy < ground_h + 6:
                    chunk[gy][local_x] = BLOCK_DIRT
                else:
                    r = random.random()
                    if r < 0.03 and gy > ground_h + 12:
                        chunk[gy][local_x] = BLOCK_GOLD_ORE
                    elif r < 0.06 and gy > ground_h + 10:
                        chunk[gy][local_x] = BLOCK_IRON_ORE
                    elif r < 0.10 and gy > ground_h + 7:
                        chunk[gy][local_x] = BLOCK_COPPER_ORE
                    elif r < 0.16 and gy > ground_h + 5:
                        chunk[gy][local_x] = BLOCK_COAL_ORE
                    else:
                        chunk[gy][local_x] = BLOCK_STONE

            # Деревья
            if random.random() < 0.12 and ground_h > 8:
                tree_h = random.randint(4, 6)
                for th in range(tree_h):
                    if ground_h - th >= 0:
                        chunk[ground_h - th][local_x] = BLOCK_WOOD
                top_y = ground_h - tree_h
                for lx in range(-2, 3):
                    for ly in range(-2, 2):
                        if abs(lx) == 2 and abs(ly) == 2:
                            continue
                        gx_leaf, gy_leaf = local_x + lx, top_y + ly
                        if 0 <= gx_leaf < CHUNK_WIDTH and 0 <= gy_leaf < WORLD_HEIGHT:
                            if chunk[gy_leaf][gx_leaf] == BLOCK_AIR:
                                chunk[gy_leaf][gx_leaf] = BLOCK_LEAVES
        return chunk

    def get_block(self, global_gx, gy):
        if gy < 0 or gy >= WORLD_HEIGHT:
            return BLOCK_AIR
        chunk = self.get_chunk(global_gx // CHUNK_WIDTH)
        return chunk[gy][global_gx % CHUNK_WIDTH]

    def set_block(self, global_gx, gy, block_type):
        if 0 <= gy < WORLD_HEIGHT:
            chunk_x = global_gx // CHUNK_WIDTH
            chunk = self.get_chunk(chunk_x)
            chunk[gy][global_gx % CHUNK_WIDTH] = block_type
            self.dirty_chunks.add(chunk_x)

    def get_chunk_surface(self, chunk_x):
        if chunk_x not in self.chunk_surfaces or chunk_x in self.dirty_chunks:
            self.chunk_surfaces[chunk_x] = self._render_chunk(chunk_x)
            self.dirty_chunks.discard(chunk_x)
        return self.chunk_surfaces[chunk_x]

    def _render_chunk(self, chunk_x):
        surf = pygame.Surface((CHUNK_WIDTH * BLOCK_SIZE, WORLD_HEIGHT * BLOCK_SIZE), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        chunk = self.get_chunk(chunk_x)
        for gy in range(WORLD_HEIGHT):
            for gx in range(CHUNK_WIDTH):
                b = chunk[gy][gx]
                if b != BLOCK_AIR:
                    rect = (gx * BLOCK_SIZE, gy * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                    pygame.draw.rect(surf, BLOCK_COLORS.get(b, (85, 85, 85)), rect)
                    if b not in (BLOCK_LEAVES, BLOCK_TALL_GRASS, BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW, BLOCK_FLOWER_BLUE):
                        pygame.draw.rect(surf, (20, 20, 20), rect, 1)
        return surf

    def clear(self):
        self.chunks.clear()
        self.chunk_surfaces.clear()
        self.dirty_chunks.clear()
        self.land_height_cache.clear()


class GamePlayer:
    """Управление игроком: физика с учётом dt, таймеры в секундах."""
    def __init__(self, world):
        self.world = world
        self.x, self.y = 0, 0
        self.vx, self.vy = 0, 0
        self.w, self.h = 22, 44
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

    def update(self, keys, dt):
        # Горизонтальное движение – скорость уже в пикселях/сек
        self.vx = 0
        if keys.get(pygame.K_a) or keys.get(pygame.K_LEFT):
            self.vx = -PLAYER_SPEED
            self.facing_right = False
        if keys.get(pygame.K_d) or keys.get(pygame.K_RIGHT):
            self.vx = PLAYER_SPEED
            self.facing_right = True

        # Прыжок – начальная скорость в пикселях/сек
        if (keys.get(pygame.K_w) or keys.get(pygame.K_SPACE) or keys.get(pygame.K_UP)) and self.is_grounded:
            self.vy = JUMP_FORCE
            self.is_grounded = False

        # Гравитация – ускорение в пикселях/сек²
        self.vy += GRAVITY * dt

        # Перемещение по X
        self.x += self.vx * dt
        if self._check_collision():
            self.x -= self.vx * dt

        # Перемещение по Y
        self.y += self.vy * dt
        if self._check_collision():
            if self.vy > 0:
                self.is_grounded = True
            self.y -= self.vy * dt
            self.vy = 0

        # Анимация (скорость анимации приводим к 60 Гц)
        if self.vx != 0:
            self.anim_frame += 0.35 * 60 * dt

        # Таймеры (уже в секундах)
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
            self.vy = -7 * 60  # пикселей/сек
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
            if len(self.mobs) < 7:
                offset = random.choice([-1, 1]) * random.randint(450, 750)
                sx = player_x + offset
                gx = int(sx // BLOCK_SIZE)
                sy = (self.world._get_land_height(gx) - 2) * BLOCK_SIZE
                if is_night:
                    r = random.random()
                    if r < 0.4:
                        self.mobs.append(Zombie(sx, sy))
                    elif r < 0.7:
                        self.mobs.append(DemonEye(sx, sy - 100))
                    else:
                        self.mobs.append(Skeleton(sx, sy))
                else:
                    if random.random() < 0.4:
                        self.mobs.append(Sheep(sx, sy))
                    else:
                        is_blue = random.random() < 0.35
                        self.mobs.append(Slime(sx, sy, is_blue))

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
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
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

        self.day_time = 3000
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

        # Облака
        self.clouds = []
        for _ in range(8):
            self.clouds.append({
                'x': random.randint(0, SCREEN_WIDTH * 2),
                'y': random.randint(-200, 100),
                'w': random.randint(200, 400),
                'h': random.randint(40, 80),
                'speed': random.uniform(10, 30)
            })

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
            global SCREEN_WIDTH, SCREEN_HEIGHT
            SCREEN_WIDTH, SCREEN_HEIGHT = info.current_w, info.current_h
        else:
            SCREEN_WIDTH, SCREEN_HEIGHT = 1100, 700
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    def toggle_inventory(self):
        if self.pause_menu_open:
            return
        self.inventory_open = not self.inventory_open

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
        if self.load_world():
            self.start_game(is_new=False)

    def reset_game_data(self):
        self.inventory_open = False
        self.pause_menu_open = False
        self.day_time = 3000
        self.save_notification_timer = 0.0
        self.keys.clear()
        self.world.clear()
        self.mob_manager.clear()
        self.inventory = GameInventory()
        self.player = GamePlayer(self.world)
        self.player.spawn()
        self.weather = WEATHER_CLEAR
        self.weather_timer = 0.0

    # ------------------- СОХРАНЕНИЕ / ЗАГРУЗКА -------------------
    def save_world(self):
        if not os.path.exists(APPDATA_PATH):
            os.makedirs(APPDATA_PATH)

        mobs_data, items_data = self.mob_manager.to_dict()
        chunks_data = {str(k): v for k, v in self.world.chunks.items()}

        save_data = {
            'player_x': self.player.x,
            'player_y': self.player.y,
            'hp': self.player.hp,
            'max_hp': self.player.max_hp,
            'day_time': self.day_time,
            'inventory': self.inventory.to_dict(),
            'selected_slot': self.inventory.selected_slot,
            'chunks': chunks_data,
            'mobs': mobs_data,
            'dropped_items': items_data
        }
        try:
            with open(SAVE_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            self.save_notification_timer = 2.0
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def load_world(self):
        if not os.path.exists(SAVE_FILE_PATH):
            return False
        try:
            with open(SAVE_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.player.x, self.player.y = data['player_x'], data['player_y']
            self.player.hp, self.player.max_hp = data['hp'], data['max_hp']
            self.day_time = data['day_time']
            self.inventory.from_dict(data['inventory'])
            self.inventory.selected_slot = data['selected_slot']
            self.world.chunks = {int(k): v for k, v in data['chunks'].items()}
            for cx in self.world.chunks:
                self.world.dirty_chunks.add(cx)
            self.mob_manager.from_dict(data['mobs'], data['dropped_items'])
            return True
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return False

    # ------------------- ОБНОВЛЕНИЕ (с dt) -------------------
    def update_physics(self, dt):
        if self.game_state != "game":
            return
        if self.inventory_open or self.pause_menu_open:
            return

        self.day_time = (self.day_time + 120 * dt) % 24000

        self.player.update(self.keys, dt)
        self.mob_manager.update(self.player.x, self.player.y, self.is_night(), self.player, dt)

        for item in self.mob_manager.dropped_items[:]:
            if math.hypot(self.player.x - item.x, self.player.y - item.y) < 28:
                if self.inventory.add_item(item.item_type, item.count):
                    self.mob_manager.dropped_items.remove(item)

        if self.save_notification_timer > 0:
            self.save_notification_timer -= dt

        # Обновление погоды
        self.weather_timer -= dt
        if self.weather_timer <= 0:
            self.weather = random.choice([WEATHER_CLEAR, WEATHER_RAIN, WEATHER_SNOW, WEATHER_FOG])
            self.weather_timer = random.uniform(30, 120)

        # Обновление облаков
        for cloud in self.clouds:
            cloud['x'] += cloud['speed'] * dt
            if cloud['x'] > SCREEN_WIDTH + 400:
                cloud['x'] = -400 - cloud['w']
                cloud['y'] = random.randint(-200, 100)
                cloud['w'] = random.randint(200, 400)
                cloud['h'] = random.randint(40, 80)
                cloud['speed'] = random.uniform(10, 30)

    # ------------------- РЕНДЕРИНГ -------------------
    def get_sky_color(self):
        t = self.day_time % 24000
        if t < 10000:
            return (92, 148, 252)
        elif t < 12000:
            return (224, 122, 95)
        elif t < 22000:
            return (5, 7, 20)
        else:
            return (244, 162, 97)

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

        self.screen.fill(self.get_sky_color())

        # Облака (под чанками)
        render_clouds(self.screen, self.clouds)

        cam_x = self.player.x - SCREEN_WIDTH / 2
        cam_y = self.player.y - SCREEN_HEIGHT / 2

        # Солнце
        t = self.day_time
        sun_angle = ((t % 24000) / 24000.0) * math.pi * 2 - math.pi / 2
        sun_x = SCREEN_WIDTH / 2 + math.cos(sun_angle) * (SCREEN_WIDTH * 0.45)
        sun_y = SCREEN_HEIGHT / 2 + math.sin(sun_angle) * (SCREEN_HEIGHT * 0.4)
        if sun_y < SCREEN_HEIGHT - 100:
            col = (255, 215, 0) if 0 <= t < 12000 else (236, 239, 241)
            pygame.draw.circle(self.screen, col, (int(sun_x), int(sun_y)), 22)

        # Чанки
        start_chunk = int(cam_x // (CHUNK_WIDTH * BLOCK_SIZE)) - 1
        end_chunk = int((cam_x + SCREEN_WIDTH) // (CHUNK_WIDTH * BLOCK_SIZE)) + 2
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

            # HP бар
            bar_w = 30
            hp_pct = max(0, mob.hp / mob.max_hp)
            pygame.draw.rect(self.screen, (50,50,50), (sx - bar_w//2, sy - mob.h//2 - 10, bar_w, 4))
            if hp_pct > 0:
                pygame.draw.rect(self.screen, (118, 255, 3), (sx - bar_w//2, sy - mob.h//2 - 10, bar_w * hp_pct, 4))

        # Игрок
        px, py = self.player.x - cam_x, self.player.y - cam_y
        self.draw_player(px, py)

        # HUD
        hp_x, hp_y = SCREEN_WIDTH - 220, 20
        hp_pct = max(0, self.player.hp / self.player.max_hp)
        pygame.draw.rect(self.screen, (28, 37, 65), (hp_x, hp_y, 180, 22), 0)
        pygame.draw.rect(self.screen, (58, 80, 107), (hp_x, hp_y, 180, 22), 2)
        if hp_pct > 0:
            pygame.draw.rect(self.screen, (230, 57, 70), (hp_x+2, hp_y+2, 176*hp_pct, 18))
        hp_text = self.font_small.render(f"HP: {self.player.hp} / {self.player.max_hp}", True, (255,255,255))
        self.screen.blit(hp_text, (hp_x+45, hp_y+4))

        fps_color = (118, 255, 3) if self.current_fps >= 30 else (255, 82, 82)
        pygame.draw.rect(self.screen, (11, 19, 43), (SCREEN_WIDTH // 2 - 45, 15, 90, 26), 0)
        pygame.draw.rect(self.screen, (58, 80, 107), (SCREEN_WIDTH // 2 - 45, 15, 90, 26), 2)
        fps_text = self.font_small.render(f"FPS: {self.current_fps}", True, fps_color)
        self.screen.blit(fps_text, (SCREEN_WIDTH // 2 - 25, 20))

        self.draw_hotbar()

        # Погода поверх всего, но под интерфейсом
        render_weather(self.screen, self.weather)

        if self.inventory_open:
            self.draw_inventory()
        if self.pause_menu_open:
            self.draw_pause()

        if self.save_notification_timer > 0:
            msg_surf = self.font_med.render("✓ Мир успешно сохранен!", True, (118, 255, 3))
            rect_w, rect_h = msg_surf.get_width() + 30, 36
            rect_x = SCREEN_WIDTH // 2 - rect_w // 2
            rect_y = SCREEN_HEIGHT - 60
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
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        s.set_alpha(180)
        s.fill((0,0,0))
        self.screen.blit(s, (0,0))

        box_w, box_h = 300, 270
        box_x = SCREEN_WIDTH // 2 - box_w // 2
        box_y = SCREEN_HEIGHT // 2 - box_h // 2
        pygame.draw.rect(self.screen, (11, 19, 43), (box_x, box_y, box_w, box_h))
        pygame.draw.rect(self.screen, (58, 80, 107), (box_x, box_y, box_w, box_h), 2)

        title = self.font_big.render("ПАУЗА", True, (255, 215, 0))
        self.screen.blit(title, (box_x + box_w // 2 - title.get_width() // 2, box_y + 20))

        self.pause_buttons = []
        btn_y = box_y + 75
        btn_texts = [
            ("Продолжить", self.toggle_pause, (46, 125, 50), (27, 94, 32)),
            ("Полный экран", self.toggle_fullscreen, (255, 183, 3), (251, 133, 0)),
            ("Сохранить мир", self.save_world, (21, 101, 192), (13, 71, 161)),
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
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))
        sub = self.font_small.render("Версия: 0.2", True, (141, 153, 174))
        self.screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 120))

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
                rect = pygame.Rect(SCREEN_WIDTH // 2 - 130, btn_y, 260, 30)
                is_hover = rect.collidepoint((self.mouse_x, self.mouse_y))
                self.menu_buttons.append((rect, action))
                txt = self.font_med.render(text, True, (76, 201, 240) if is_hover else (0, 180, 216))
                self.screen.blit(txt, (rect.x + (rect.width - txt.get_width()) // 2, rect.y + 4))
                btn_y += 40
            else:
                rect = pygame.Rect(SCREEN_WIDTH // 2 - 130, btn_y, 260, 42)
                is_hover = rect.collidepoint((self.mouse_x, self.mouse_y))
                self.menu_buttons.append((rect, action))
                draw_color = hover_color if is_hover else color
                pygame.draw.rect(self.screen, draw_color, rect, 0)
                pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)
                txt = self.font_med.render(text, True, (255, 255, 255))
                self.screen.blit(txt, (rect.x + (rect.width - txt.get_width()) // 2, rect.y + 9))
                btn_y += 52
        author = self.font_small.render("Автор: KIziName", True, (224, 225, 221))
        self.screen.blit(author, (SCREEN_WIDTH // 2 - author.get_width() // 2, SCREEN_HEIGHT - 35))

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
        cam_x = self.player.x - SCREEN_WIDTH / 2
        cam_y = self.player.y - SCREEN_HEIGHT / 2
        wx, wy = pos[0] + cam_x, pos[1] + cam_y

        if math.hypot(wx - self.player.x, wy - self.player.y) > BUILD_REACH:
            return

        if button == 1:
            self.player.swing_anim = 0.15
            slot = self.inventory.get_selected_item()

            # Зелья
            if slot['type'] in (ITEM_POTION, ITEM_BIG_POTION):
                heal = 40 if slot['type'] == ITEM_POTION else 80
                if self.player.hp < self.player.max_hp:
                    self.player.hp = min(self.player.max_hp, self.player.hp + heal)
                    slot['count'] -= 1
                    if slot['count'] <= 0:
                        slot['type'] = BLOCK_AIR
                return

            # Атака мобов
            dmg = self.player.get_weapon_damage(self.inventory)
            for mob in self.mob_manager.mobs[:]:
                if abs(mob.x - wx) < 30 and abs(mob.y - wy) < 30:
                    mob.hp -= dmg
                    mob.vy = -4.0 * 60  # пикселей/сек
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

            # Добыча блока
            gx, gy = int(wx // BLOCK_SIZE), int(wy // BLOCK_SIZE)
            b_type = self.world.get_block(gx, gy)
            if b_type != BLOCK_AIR:
                # Декоративные блоки сразу в инвентарь
                if b_type in (BLOCK_TALL_GRASS, BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW, BLOCK_FLOWER_BLUE):
                    self.inventory.add_item(b_type, 1)
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
                    self.world.set_block(gx, gy, slot['type'])
                    slot['count'] -= 1
                    if slot['count'] <= 0:
                        slot['type'] = BLOCK_AIR