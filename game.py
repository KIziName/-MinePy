import pygame
import json
import math
import random
import os
import webbrowser
import time
import sys

from blocks import *
from renderer import draw_item_icon
from mobs import DroppedItem, Slime, Zombie, DemonEye, Skeleton

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
        self.chunks = {}
        self.mobs = []
        self.dropped_items = []
        self.save_notification_timer = 0
        
        self.reset_game_data()

        self.menu_buttons = []
        self.pause_buttons = []
        self.inventory_open = False
        self.pause_menu_open = False

    def init_fonts(self):
        font_name = pygame.font.match_font('arial') or pygame.font.match_font('dejavusans')
        self.font_small = pygame.font.Font(font_name, 13)
        self.font_med = pygame.font.Font(font_name, 18)
        self.font_big = pygame.font.Font(font_name, 32)
        self.font_huge = pygame.font.Font(font_name, 52)

    def reset_game_data(self):
        self.inventory_open = False
        self.pause_menu_open = False
        self.swing_anim = 0
        self.day_time = 3000

        self.fps_counter = 0
        self.current_fps = 0
        self.last_fps_time = time.time()

        self.inventory = [{'type': BLOCK_AIR, 'count': 0} for _ in range(40)]
        self.inventory[0] = {'type': ITEM_SWORD_WOOD, 'count': 1}
        self.inventory[1] = {'type': ITEM_PICKAXE_WOOD, 'count': 1}
        self.inventory[2] = {'type': BLOCK_DIRT, 'count': 20}

        self.selected_slot = 0
        self.dragged_slot = None
        self.mouse_x = 0
        self.mouse_y = 0

        self.hp = 100; self.max_hp = 100
        self.invulnerable_timer = 0

        self.player_x, self.player_y = 0, 0
        self.player_vx, self.player_vy = 0, 0
        self.player_w, self.player_h = 22, 44

        self.facing_right = True
        self.anim_frame = 0
        self.is_grounded = False

        self.keys = {}
        self.chunks.clear()
        self.mobs.clear()
        self.dropped_items.clear()
        self.spawn_timer = 0

    def save_world(self):
        if not os.path.exists(APPDATA_PATH):
            os.makedirs(APPDATA_PATH)

        mobs_data = [m.to_dict() for m in self.mobs]
        items_data = [i.to_dict() for i in self.dropped_items]
        chunks_data = {str(k): v for k, v in self.chunks.items()}

        save_data = {
            'player_x': self.player_x, 'player_y': self.player_y,
            'hp': self.hp, 'max_hp': self.max_hp, 'day_time': self.day_time,
            'inventory': self.inventory, 'selected_slot': self.selected_slot,
            'chunks': chunks_data, 'mobs': mobs_data, 'dropped_items': items_data
        }

        try:
            with open(SAVE_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            self.save_notification_timer = 120
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def load_world(self):
        if not os.path.exists(SAVE_FILE_PATH): return False
        try:
            with open(SAVE_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.player_x, self.player_y = data['player_x'], data['player_y']
            self.hp, self.max_hp = data['hp'], data['max_hp']
            self.day_time = data['day_time']
            self.inventory = data['inventory']
            self.selected_slot = data['selected_slot']
            self.chunks = {int(k): v for k, v in data['chunks'].items()}

            self.mobs.clear()
            for md in data['mobs']:
                m_type = md['type']
                if m_type == 'Slime': m = Slime(md['x'], md['y'], md.get('is_blue', False))
                elif m_type == 'Zombie': m = Zombie(md['x'], md['y'])
                elif m_type == 'DemonEye': m = DemonEye(md['x'], md['y'])
                elif m_type == 'Skeleton': m = Skeleton(md['x'], md['y'])
                else: continue
                m.hp = md['hp']
                self.mobs.append(m)

            self.dropped_items = [DroppedItem.from_dict(it) for it in data['dropped_items']]
            return True
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return False

    def is_night(self): return 11000 <= (self.day_time % 24000) <= 23000

    def get_land_height(self, global_gx):
        return int(40 - (math.sin(global_gx * 0.04) * 6 + math.cos(global_gx * 0.1) * 3))

    def get_chunk(self, chunk_x):
        if chunk_x in self.chunks: return self.chunks[chunk_x]
        chunk = [[BLOCK_AIR for _ in range(CHUNK_WIDTH)] for _ in range(WORLD_HEIGHT)]

        for local_x in range(CHUNK_WIDTH):
            global_gx = chunk_x * CHUNK_WIDTH + local_x
            ground_h = self.get_land_height(global_gx)

            for gy in range(WORLD_HEIGHT - 1, ground_h, -1):
                if gy == ground_h + 1: chunk[gy][local_x] = BLOCK_GRASS
                elif gy < ground_h + 6: chunk[gy][local_x] = BLOCK_DIRT
                else:
                    r = random.random()
                    if r < 0.03 and gy > ground_h + 12: chunk[gy][local_x] = BLOCK_GOLD_ORE
                    elif r < 0.06 and gy > ground_h + 10: chunk[gy][local_x] = BLOCK_IRON_ORE
                    elif r < 0.10 and gy > ground_h + 7: chunk[gy][local_x] = BLOCK_COPPER_ORE
                    elif r < 0.16 and gy > ground_h + 5: chunk[gy][local_x] = BLOCK_COAL_ORE
                    else: chunk[gy][local_x] = BLOCK_STONE

            if random.random() < 0.12 and ground_h > 8:
                tree_h = random.randint(4, 6)
                for th in range(tree_h):
                    if ground_h - th >= 0: chunk[ground_h - th][local_x] = BLOCK_WOOD
                top_y = ground_h - tree_h
                for lx in range(-2, 3):
                    for ly in range(-2, 2):
                        if abs(lx) == 2 and abs(ly) == 2: continue
                        gx_leaf, gy_leaf = local_x + lx, top_y + ly
                        if 0 <= gx_leaf < CHUNK_WIDTH and 0 <= gy_leaf < WORLD_HEIGHT:
                            if chunk[gy_leaf][gx_leaf] == BLOCK_AIR:
                                chunk[gy_leaf][gx_leaf] = BLOCK_LEAVES

        self.chunks[chunk_x] = chunk
        return chunk

    def get_block(self, global_gx, gy):
        if gy < 0 or gy >= WORLD_HEIGHT: return BLOCK_AIR
        chunk = self.get_chunk(global_gx // CHUNK_WIDTH)
        return chunk[gy][global_gx % CHUNK_WIDTH]

    def set_block(self, global_gx, gy, block_type):
        if 0 <= gy < WORLD_HEIGHT:
            chunk = self.get_chunk(global_gx // CHUNK_WIDTH)
            chunk[gy][global_gx % CHUNK_WIDTH] = block_type

    def add_to_inventory(self, item_type, count=1):
        for slot in self.inventory:
            if slot['type'] == item_type and slot['count'] < MAX_STACK:
                add = min(count, MAX_STACK - slot['count'])
                slot['count'] += add
                count -= add
                if count <= 0: return True

        for slot in self.inventory:
            if slot['type'] == BLOCK_AIR:
                slot['type'] = item_type
                slot['count'] = min(count, MAX_STACK)
                count -= slot['count']
                if count <= 0: return True
        return False

    def can_craft(self, ingredients):
        for itype, count in ingredients:
            total = sum(slot['count'] for slot in self.inventory if slot['type'] == itype)
            if total < count: return False
        return True

    def craft_item(self, result, ingredients):
        if not self.can_craft(ingredients): return
        for itype, count in ingredients:
            needed = count
            for slot in self.inventory:
                if slot['type'] == itype:
                    take = min(needed, slot['count'])
                    slot['count'] -= take
                    needed -= take
                    if slot['count'] <= 0: slot['type'] = BLOCK_AIR
                    if needed <= 0: break
        self.add_to_inventory(result['type'], result['count'])

    def get_player_weapon_damage(self):
        slot = self.inventory[self.selected_slot]
        itype = slot['type']
        if itype == ITEM_SWORD_WOOD: return 12
        if itype == ITEM_SWORD_COPPER: return 18
        if itype == ITEM_SWORD_IRON: return 28
        if itype == ITEM_SWORD_GOLD: return 38
        if itype == ITEM_SWORD_DIAMOND: return 55
        return 6

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        global SCREEN_WIDTH, SCREEN_HEIGHT
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            info = pygame.display.Info()
            SCREEN_WIDTH, SCREEN_HEIGHT = info.current_w, info.current_h
        else:
            SCREEN_WIDTH, SCREEN_HEIGHT = 1100, 700
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    def toggle_inventory(self):
        if self.pause_menu_open: return
        self.inventory_open = not self.inventory_open

    def toggle_pause(self):
        if self.inventory_open: self.inventory_open = False
        self.pause_menu_open = not self.pause_menu_open

    def open_github(self):
        webbrowser.open("https://github.com/KIziName/MinePy")

    def start_game(self, is_new=True):
        if is_new:
            self.reset_game_data()
            self.spawn_player()
        self.game_state = "game"
        self.inventory_open = False
        self.pause_menu_open = False

    def load_and_start_game(self):
        if self.load_world(): self.start_game(is_new=False)

    def spawn_player(self):
        self.player_x = 0
        ground_h = self.get_land_height(0)
        self.player_y = (ground_h - 2) * BLOCK_SIZE
        self.player_vx, self.player_vy = 0, 0

    def update_physics(self):
        if self.save_notification_timer > 0:
            self.save_notification_timer -= 1

        if self.inventory_open or self.pause_menu_open: return

        self.day_time = (self.day_time + 2) % 24000
        if self.swing_anim > 0: self.swing_anim -= 1

        self.player_vx = 0
        if self.keys.get(pygame.K_a) or self.keys.get(pygame.K_LEFT):
            self.player_vx = -PLAYER_SPEED
            self.facing_right = False
        if self.keys.get(pygame.K_d) or self.keys.get(pygame.K_RIGHT):
            self.player_vx = PLAYER_SPEED
            self.facing_right = True

        if (self.keys.get(pygame.K_w) or self.keys.get(pygame.K_SPACE) or self.keys.get(pygame.K_UP)) and self.is_grounded:
            self.player_vy = JUMP_FORCE
            self.is_grounded = False

        self.player_vy += GRAVITY
        self.player_x += self.player_vx
        if self.check_player_collision(): self.player_x -= self.player_vx

        self.player_y += self.player_vy
        if self.check_player_collision():
            if self.player_vy > 0: self.is_grounded = True
            self.player_y -= self.player_vy
            self.player_vy = 0

        if self.player_vx != 0: self.anim_frame += 0.35

        for mob in self.mobs[:]:
            mob.update(self.player_x, self.player_y, self.get_block)
            if self.invulnerable_timer == 0:
                if abs(self.player_x - mob.x) < 22 and abs(self.player_y - mob.y) < 26:
                    self.hp -= mob.damage
                    self.invulnerable_timer = 25
                    self.player_vy = -7
                    self.player_vx = 8 if self.player_x > mob.x else -8
                    if self.hp <= 0:
                        self.spawn_player()
                        self.hp = self.max_hp

        if self.invulnerable_timer > 0: self.invulnerable_timer -= 1

        for item in self.dropped_items[:]:
            item.update(self.player_x, self.player_y, self.get_block)
            if math.hypot(self.player_x - item.x, self.player_y - item.y) < 28:
                if self.add_to_inventory(item.item_type, item.count):
                    self.dropped_items.remove(item)

        self.spawn_timer += 1
        if self.spawn_timer > 120:
            self.spawn_timer = 0
            if len(self.mobs) < 7:
                offset = random.choice([-1, 1]) * random.randint(450, 750)
                sx = self.player_x + offset
                gx = int(sx // BLOCK_SIZE)
                sy = (self.get_land_height(gx) - 2) * BLOCK_SIZE

                if self.is_night():
                    r = random.random()
                    if r < 0.4: self.mobs.append(Zombie(sx, sy))
                    elif r < 0.7: self.mobs.append(DemonEye(sx, sy - 100))
                    else: self.mobs.append(Skeleton(sx, sy))
                else:
                    is_blue = random.random() < 0.35
                    self.mobs.append(Slime(sx, sy, is_blue))

    def check_player_collision(self):
        left, right = int((self.player_x - self.player_w/2) // BLOCK_SIZE), int((self.player_x + self.player_w/2) // BLOCK_SIZE)
        top, bottom = int((self.player_y - self.player_h/2) // BLOCK_SIZE), int((self.player_y + self.player_h/2) // BLOCK_SIZE)

        for gx in range(left, right+1):
            for gy in range(top, bottom+1):
                b = self.get_block(gx, gy)
                if b != BLOCK_AIR and b != BLOCK_LEAVES: return True
        return False

    def get_sky_color(self):
        t = self.day_time % 24000
        if t < 10000: return (92, 148, 252)
        elif t < 12000: return (224, 122, 95)
        elif t < 22000: return (5, 7, 20)
        else: return (244, 162, 97)

    def draw_player(self, px, py):
        if self.invulnerable_timer % 4 >= 2: return

        face_dir = 1 if self.facing_right else -1
        leg_step = math.sin(self.anim_frame) * 5 if self.is_grounded and self.player_vx != 0 else 0

        pygame.draw.rect(self.screen, (21, 101, 192), (px - 6 + leg_step, py + 8, 5, 14))
        pygame.draw.rect(self.screen, (13, 71, 161), (px + 1 - leg_step, py + 8, 5, 14))
        pygame.draw.rect(self.screen, (198, 40, 40), (px - 7, py - 8, 14, 16), 0, 2)
        pygame.draw.circle(self.screen, (255, 204, 128), (int(px), int(py - 14)), 8)
        pygame.draw.arc(self.screen, (121, 85, 72), (px - 8, py - 22, 16, 12), 0, math.pi, 4)

        eye_x = px + (3 * face_dir)
        pygame.draw.circle(self.screen, (33, 33, 33), (int(eye_x), int(py - 15)), 2)

        hand_x = px + (6 * face_dir)
        hand_y = py - 2
        
        swing_angle = (10 - self.swing_anim) * 8 if self.swing_anim > 0 else 0
        if not self.facing_right: swing_angle = -swing_angle

        curr_item = self.inventory[self.selected_slot]['type']
        if curr_item != BLOCK_AIR:
            item_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            draw_item_icon(item_surf, curr_item, 0, 0, size=32)
            if not self.facing_right:
                item_surf = pygame.transform.flip(item_surf, True, False)
            
            rotated_item = pygame.transform.rotate(item_surf, -swing_angle if self.facing_right else swing_angle)
            item_rect = rotated_item.get_rect(center=(hand_x + (8 * face_dir), hand_y))
            self.screen.blit(rotated_item, item_rect)

        pygame.draw.circle(self.screen, (255, 204, 128), (int(hand_x), int(hand_y)), 3)

    def render(self):
        if self.game_state != "game": return

        self.screen.fill(self.get_sky_color())
        cam_x = self.player_x - SCREEN_WIDTH / 2
        cam_y = self.player_y - SCREEN_HEIGHT / 2

        t = self.day_time
        sun_angle = ((t % 24000) / 24000.0) * math.pi * 2 - math.pi / 2
        sun_x = SCREEN_WIDTH / 2 + math.cos(sun_angle) * (SCREEN_WIDTH * 0.45)
        sun_y = SCREEN_HEIGHT / 2 + math.sin(sun_angle) * (SCREEN_HEIGHT * 0.4)

        if sun_y < SCREEN_HEIGHT - 100:
            col = (255, 215, 0) if 0 <= t < 12000 else (236, 239, 241)
            pygame.draw.circle(self.screen, col, (int(sun_x), int(sun_y)), 22)

        curr_cam_gx, curr_cam_gy = int(cam_x // BLOCK_SIZE), int(cam_y // BLOCK_SIZE)
        start_gx, end_gx = curr_cam_gx - 1, curr_cam_gx + int(SCREEN_WIDTH // BLOCK_SIZE) + 2
        start_gy, end_gy = max(0, curr_cam_gy - 1), min(WORLD_HEIGHT, curr_cam_gy + int(SCREEN_HEIGHT // BLOCK_SIZE) + 2)

        for gy in range(start_gy, end_gy):
            for gx in range(start_gx, end_gx):
                b_type = self.get_block(gx, gy)
                if b_type != BLOCK_AIR:
                    sx, sy = gx * BLOCK_SIZE - cam_x, gy * BLOCK_SIZE - cam_y
                    pygame.draw.rect(self.screen, BLOCK_COLORS.get(b_type, (85, 85, 85)), (sx, sy, BLOCK_SIZE, BLOCK_SIZE))
                    if b_type != BLOCK_LEAVES:
                        pygame.draw.rect(self.screen, (20, 20, 20), (sx, sy, BLOCK_SIZE, BLOCK_SIZE), 1)

        for item in self.dropped_items:
            sx = item.x - cam_x
            sy = item.y - cam_y + math.sin(item.bob_angle) * 4
            draw_item_icon(self.screen, item.item_type, int(sx - 12), int(sy - 12), size=24)

        for mob in self.mobs:
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

            bar_w = 30
            hp_pct = max(0, mob.hp / mob.max_hp)
            pygame.draw.rect(self.screen, (50,50,50), (sx - bar_w//2, sy - mob.h//2 - 10, bar_w, 4))
            if hp_pct > 0:
                pygame.draw.rect(self.screen, (118, 255, 3), (sx - bar_w//2, sy - mob.h//2 - 10, bar_w * hp_pct, 4))

        px, py = self.player_x - cam_x, self.player_y - cam_y
        self.draw_player(px, py)

        hp_x, hp_y = SCREEN_WIDTH - 220, 20
        hp_pct = max(0, self.hp / self.max_hp)
        pygame.draw.rect(self.screen, (28, 37, 65), (hp_x, hp_y, 180, 22), 0)
        pygame.draw.rect(self.screen, (58, 80, 107), (hp_x, hp_y, 180, 22), 2)
        if hp_pct > 0:
            pygame.draw.rect(self.screen, (230, 57, 70), (hp_x+2, hp_y+2, 176*hp_pct, 18))
        hp_text = self.font_small.render(f"HP: {self.hp} / {self.max_hp}", True, (255,255,255))
        self.screen.blit(hp_text, (hp_x+45, hp_y+4))

        fps_color = (118, 255, 3) if self.current_fps >= 30 else (255, 82, 82)
        pygame.draw.rect(self.screen, (11, 19, 43), (SCREEN_WIDTH // 2 - 45, 15, 90, 26), 0)
        pygame.draw.rect(self.screen, (58, 80, 107), (SCREEN_WIDTH // 2 - 45, 15, 90, 26), 2)
        fps_text = self.font_small.render(f"FPS: {self.current_fps}", True, fps_color)
        self.screen.blit(fps_text, (SCREEN_WIDTH // 2 - 25, 20))

        self.draw_hotbar()

        if self.inventory_open: self.draw_inventory()
        if self.pause_menu_open: self.draw_pause()

        if self.save_notification_timer > 0:
            msg_surf = self.font_med.render("✓ Мир успешно сохранен!", True, (118, 255, 3))
            rect_w, rect_h = msg_surf.get_width() + 30, 36
            rect_x = SCREEN_WIDTH // 2 - rect_w // 2
            rect_y = SCREEN_HEIGHT - 60
            
            pygame.draw.rect(self.screen, (11, 19, 43), (rect_x, rect_y, rect_w, rect_h), 0, 4)
            pygame.draw.rect(self.screen, (118, 255, 3), (rect_x, rect_y, rect_w, rect_h), 2, 4)
            self.screen.blit(msg_surf, (rect_x + 15, rect_y + 8))

        if self.dragged_slot is not None:
            item = self.inventory[self.dragged_slot]
            if item['type'] != BLOCK_AIR:
                draw_item_icon(self.screen, item['type'], self.mouse_x - 16, self.mouse_y - 16, size=32)

    def draw_hotbar(self):
        bar_x, bar_y = 15, 15
        for i in range(10):
            x, y = bar_x + i*48, bar_y
            item = self.inventory[i]
            color = (11, 19, 43) if i != self.selected_slot else (255, 215, 0)
            pygame.draw.rect(self.screen, color, (x, y, 44, 44), 0)
            pygame.draw.rect(self.screen, (58, 80, 107), (x, y, 44, 44), 2 if i != self.selected_slot else 3)
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
                item = self.inventory[idx]
                
                is_selected = (self.dragged_slot == idx)
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
            can_craft = self.can_craft(ingredients)
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
                        if event.key == pygame.K_0: self.selected_slot = 9
                        else: self.selected_slot = event.key - pygame.K_1
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

    def check_hotbar_click(self, pos):
        bar_x, bar_y = 15, 15
        for i in range(10):
            x = bar_x + i * 48
            rect = pygame.Rect(x, bar_y, 44, 44)
            if rect.collidepoint(pos):
                if self.inventory_open:
                    if self.dragged_slot is None:
                        if self.inventory[i]['type'] != BLOCK_AIR:
                            self.dragged_slot = i
                    else:
                        self.inventory[i], self.inventory[self.dragged_slot] = self.inventory[self.dragged_slot], self.inventory[i]
                        self.dragged_slot = None
                else:
                    self.selected_slot = i
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
        if self.check_hotbar_click(pos): return

        inv_x, inv_y = 15, 70
        for row in range(3):
            for col in range(10):
                idx = (row+1)*10 + col
                rect = pygame.Rect(inv_x + 12 + col*46, inv_y + 40 + row*46, 42, 42)
                if rect.collidepoint(pos):
                    if self.dragged_slot is None:
                        if self.inventory[idx]['type'] != BLOCK_AIR:
                            self.dragged_slot = idx
                    else:
                        self.inventory[idx], self.inventory[self.dragged_slot] = self.inventory[self.dragged_slot], self.inventory[idx]
                        self.dragged_slot = None
                    return

        craft_y = inv_y + 185
        for result, ingredients in CRAFTING_RECIPES:
            rect = pygame.Rect(inv_x + 12, craft_y, 466, 24)
            if rect.collidepoint(pos):
                self.craft_item(result, ingredients)
                return
            craft_y += 27

        if not (inv_x <= pos[0] <= inv_x + 490 and inv_y <= pos[1] <= inv_y + 360):
            self.toggle_inventory()

    def handle_game_click(self, pos, button=1):
        cam_x = self.player_x - SCREEN_WIDTH / 2
        cam_y = self.player_y - SCREEN_HEIGHT / 2
        wx, wy = pos[0] + cam_x, pos[1] + cam_y

        if math.hypot(wx - self.player_x, wy - self.player_y) > BUILD_REACH: return

        if button == 1:
            self.swing_anim = 8
            slot = self.inventory[self.selected_slot]

            if slot['type'] in (ITEM_POTION, ITEM_BIG_POTION):
                heal = 40 if slot['type'] == ITEM_POTION else 80
                if self.hp < self.max_hp:
                    self.hp = min(self.max_hp, self.hp + heal)
                    slot['count'] -= 1
                    if slot['count'] <= 0: slot['type'] = BLOCK_AIR
                return

            dmg = self.get_player_weapon_damage()
            for mob in self.mobs[:]:
                if abs(mob.x - wx) < 30 and abs(mob.y - wy) < 30:
                    mob.hp -= dmg
                    mob.vy = -4.0
                    if mob.hp <= 0:
                        drop_type = None
                        if isinstance(mob, Slime): drop_type, count = ITEM_GEL, random.randint(1,3)
                        elif isinstance(mob, Zombie): drop_type, count = ITEM_COIN, random.randint(1,4)
                        elif isinstance(mob, DemonEye): drop_type, count = ITEM_LENS, 1
                        elif isinstance(mob, Skeleton): drop_type, count = ITEM_BONE, random.randint(1,2)
                        if drop_type is not None:
                            self.dropped_items.append(DroppedItem(mob.x, mob.y, drop_type, count))
                        self.mobs.remove(mob)
                    return

            gx, gy = int(wx // BLOCK_SIZE), int(wy // BLOCK_SIZE)
            b_type = self.get_block(gx, gy)
            if b_type != BLOCK_AIR:
                self.set_block(gx, gy, BLOCK_AIR)
                drop_item = ITEM_COAL if b_type == BLOCK_COAL_ORE else b_type
                self.dropped_items.append(DroppedItem((gx+0.5)*BLOCK_SIZE, (gy+0.5)*BLOCK_SIZE, drop_item, 1))

        elif button == 3:
            gx, gy = int(wx // BLOCK_SIZE), int(wy // BLOCK_SIZE)
            slot = self.inventory[self.selected_slot]
            placeable = [BLOCK_DIRT, BLOCK_GRASS, BLOCK_STONE, BLOCK_WOOD,
                         BLOCK_LEAVES, BLOCK_COPPER_ORE, BLOCK_IRON_ORE,
                         BLOCK_GOLD_ORE, BLOCK_COAL_ORE]
            if slot['type'] in placeable and slot['count'] > 0:
                if self.get_block(gx, gy) == BLOCK_AIR:
                    self.set_block(gx, gy, slot['type'])
                    slot['count'] -= 1
                    if slot['count'] <= 0: slot['type'] = BLOCK_AIR

    def show_main_menu(self):
        self.game_state = "menu"
        self.inventory_open = False
        self.pause_menu_open = False
        self.chunks.clear(); self.mobs.clear(); self.dropped_items.clear()
