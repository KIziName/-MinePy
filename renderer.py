import pygame
import random
from blocks import *

def draw_item_icon(surface, item_type, x, y, size=32):
    """Детализированная отрисовка предметов (включая мечи и кирки)"""
    if item_type in BLOCK_COLORS:
        if item_type == BLOCK_TALL_GRASS:
            pygame.draw.rect(surface, (76, 175, 80), (x+6, y+4, 20, 24))
            pygame.draw.line(surface, (50, 120, 50), (x+8, y+20), (x+16, y+4), 2)
            pygame.draw.line(surface, (50, 120, 50), (x+16, y+20), (x+24, y+4), 2)
            return
        elif item_type in (BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW, BLOCK_FLOWER_BLUE):
            col = BLOCK_COLORS[item_type]
            cx, cy = x + size//2, y + size//2
            pygame.draw.circle(surface, col, (cx, cy-4), 6)
            pygame.draw.line(surface, (50, 150, 50), (cx, cy+2), (cx, cy+10), 2)
            return
        pygame.draw.rect(surface, BLOCK_COLORS[item_type], (x + 2, y + 2, size - 4, size - 4))
        pygame.draw.rect(surface, (20, 20, 20), (x + 2, y + 2, size - 4, size - 4), 1)
        return

    cx, cy = x + size // 2, y + size // 2
    
    if item_type in (ITEM_SWORD_WOOD, ITEM_SWORD_COPPER, ITEM_SWORD_IRON, ITEM_SWORD_GOLD, ITEM_SWORD_DIAMOND):
        colors = {
            ITEM_SWORD_WOOD: (141, 110, 99), ITEM_SWORD_COPPER: (216, 112, 64),
            ITEM_SWORD_IRON: (220, 235, 245), ITEM_SWORD_GOLD: (255, 215, 0),
            ITEM_SWORD_DIAMOND: (0, 229, 255)
        }
        col = colors.get(item_type, (255, 255, 255))
        pygame.draw.line(surface, col, (x + 8, y + size - 8), (x + size - 5, y + 5), 4)
        pygame.draw.line(surface, (255, 255, 255), (x + 10, y + size - 10), (x + size - 7, y + 7), 1)
        pygame.draw.line(surface, (100, 100, 100), (x + 7, y + size - 13), (x + 13, y + size - 7), 3)
        pygame.draw.line(surface, (121, 85, 72), (x + 5, y + size - 5), (x + 8, y + size - 8), 3)
        pygame.draw.circle(surface, (200, 200, 200), (x + 4, y + size - 4), 2)

    elif item_type in (ITEM_PICKAXE_WOOD, ITEM_PICKAXE_COPPER, ITEM_PICKAXE_IRON, ITEM_PICKAXE_GOLD):
        colors = {
            ITEM_PICKAXE_WOOD: (141, 110, 99), ITEM_PICKAXE_COPPER: (216, 112, 64),
            ITEM_PICKAXE_IRON: (220, 235, 245), ITEM_PICKAXE_GOLD: (255, 215, 0)
        }
        col = colors.get(item_type, (255, 255, 255))
        pygame.draw.line(surface, (101, 67, 33), (x + 5, y + size - 5), (x + size - 8, y + 8), 3)
        head_pts = [(x + size - 16, y + 4), (x + size - 4, y + 4), (x + size - 4, y + 16)]
        pygame.draw.lines(surface, col, False, head_pts, 4)
        pygame.draw.circle(surface, col, (x + size - 4, y + 4), 3)

    elif item_type in (ITEM_POTION, ITEM_BIG_POTION):
        col = (229, 57, 53) if item_type == ITEM_POTION else (156, 39, 176)
        pygame.draw.circle(surface, col, (cx, cy + 3), 7)
        pygame.draw.rect(surface, (200, 200, 200), (cx - 3, cy - 8, 6, 5))

    elif item_type in (ITEM_COPPER_INGOT, ITEM_IRON_INGOT, ITEM_GOLD_INGOT):
        colors = {ITEM_COPPER_INGOT: (216, 112, 64), ITEM_IRON_INGOT: (207, 216, 220), ITEM_GOLD_INGOT: (255, 215, 0)}
        pygame.draw.polygon(surface, colors[item_type], [(x+6, y+20), (x+10, y+10), (x+22, y+10), (x+26, y+20)])

    elif item_type == ITEM_GEL:
        pygame.draw.circle(surface, (66, 165, 245), (cx, cy), 7)
    elif item_type == ITEM_COIN:
        pygame.draw.circle(surface, (255, 215, 0), (cx, cy), 6)
    elif item_type == ITEM_COAL:
        pygame.draw.circle(surface, (33, 33, 33), (cx, cy), 7)
    elif item_type == ITEM_DIAMOND:
        pygame.draw.polygon(surface, (0, 229, 255), [(cx, y+6), (x+24, cy), (cx, y+26), (x+8, cy)])
    elif item_type == ITEM_TORCH:
        pygame.draw.rect(surface, (121, 85, 72), (cx-2, cy-2, 4, 12))
        pygame.draw.circle(surface, (255, 112, 67), (cx, cy-4), 4)
    else:
        pygame.draw.circle(surface, (180, 180, 180), (cx, cy), 6)


# ------------------- НОВЫЕ ФУНКЦИИ ДЛЯ ПОГОДЫ И ОБЛАКОВ -------------------

def render_clouds(screen, clouds):
    """Рисует облака на экране."""
    for cloud in clouds:
        x = cloud['x']
        y = cloud['y']
        w = cloud['w']
        h = cloud['h']
        pygame.draw.ellipse(screen, (255, 255, 255), (x, y, w, h))
        pygame.draw.ellipse(screen, (255, 255, 255), (x + w*0.2, y - h*0.3, w*0.6, h*0.8))
        pygame.draw.ellipse(screen, (255, 255, 255), (x - w*0.1, y + h*0.1, w*0.3, h*0.6))


def render_weather(screen, weather):
    """Рисует эффекты погоды (дождь, снег, туман)."""
    if weather == WEATHER_RAIN:
        for _ in range(80):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            pygame.draw.line(screen, (180, 200, 255), (x, y), (x-3, y+12), 1)
    elif weather == WEATHER_SNOW:
        for _ in range(60):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), 3)
    elif weather == WEATHER_FOG:
        fog = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fog.set_alpha(80)
        fog.fill((200, 200, 200))
        screen.blit(fog, (0, 0))