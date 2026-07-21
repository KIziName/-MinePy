import pygame
import math
import random
from Blocks import *

class DroppedItem:
    def __init__(self, x, y, item_type, count=1):
        self.x, self.y = x, y
        self.item_type = item_type
        self.count = count
        self.vy = random.uniform(-2, -4)
        self.vx = random.uniform(-1.5, 1.5)
        self.bob_angle = random.uniform(0, 360)

    def update(self, player_x, player_y, get_block_func):
        self.bob_angle += 0.1
        dx, dy = player_x - self.x, player_y - self.y
        dist = math.hypot(dx, dy)

        if dist < 140:
            speed = 2.0 if dist > 30 else 4.0
            self.vx += (dx / dist) * speed
            self.vy += (dy / dist) * speed

        self.vy += GRAVITY * 0.4
        self.x += self.vx
        self.y += self.vy

        gx = int(self.x // BLOCK_SIZE)
        gy = int((self.y + 8) // BLOCK_SIZE)

        if get_block_func(gx, gy) != BLOCK_AIR:
            self.y = gy * BLOCK_SIZE - 8
            self.vy = 0
            self.vx *= 0.8

    def to_dict(self):
        return {'x': self.x, 'y': self.y, 'item_type': self.item_type, 'count': self.count}

    @staticmethod
    def from_dict(data):
        return DroppedItem(data['x'], data['y'], data['item_type'], data['count'])

class Slime:
    def __init__(self, x, y, is_blue=False):
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0
        self.w, self.h = 32, 24
        self.is_blue = is_blue
        self.hp = 25 if is_blue else 15
        self.max_hp = self.hp
        self.damage = 12 if is_blue else 7
        self.speed = 4.0 if is_blue else 3.2
        self.color = (30, 136, 229) if is_blue else (76, 175, 80)
        self.is_grounded = False
        self.jump_cooldown = random.randint(20, 50)

    def update(self, player_x, player_y, get_block_func):
        dist_x = player_x - self.x
        if self.jump_cooldown > 0: self.jump_cooldown -= 1

        if self.is_grounded and self.jump_cooldown <= 0 and abs(dist_x) < 450:
            self.vy = random.uniform(-8.5, -11.5)
            self.vx = self.speed if dist_x > 0 else -self.speed
            self.is_grounded = False
            self.jump_cooldown = random.randint(35, 75)

        self.vy += GRAVITY
        self.x += self.vx
        if self.check_collision(get_block_func):
            self.x -= self.vx
            self.vx = 0

        self.y += self.vy
        if self.check_collision(get_block_func):
            if self.vy > 0: self.is_grounded = True; self.vx = 0
            self.y -= self.vy
            self.vy = 0

    def check_collision(self, get_block_func):
        left, right = int((self.x - self.w/2) // BLOCK_SIZE), int((self.x + self.w/2) // BLOCK_SIZE)
        top, bottom = int((self.y - self.h/2) // BLOCK_SIZE), int((self.y + self.h/2) // BLOCK_SIZE)
        for gx in range(left, right+1):
            for gy in range(top, bottom+1):
                b = get_block_func(gx, gy)
                if b != BLOCK_AIR and b != BLOCK_LEAVES: return True
        return False

    def to_dict(self):
        return {'type': 'Slime', 'x': self.x, 'y': self.y, 'hp': self.hp, 'is_blue': self.is_blue}

class Zombie:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0
        self.w, self.h = 24, 44
        self.hp = 45; self.max_hp = 45; self.damage = 14; self.speed = 2.2
        self.is_grounded = False

    def update(self, player_x, player_y, get_block_func):
        dist_x = player_x - self.x
        if abs(dist_x) < 600: self.vx = self.speed if dist_x > 0 else -self.speed
        self.vy += GRAVITY
        self.x += self.vx
        if self.check_collision(get_block_func):
            self.x -= self.vx
            if self.is_grounded: self.vy = -9.5; self.is_grounded = False
        self.y += self.vy
        if self.check_collision(get_block_func):
            if self.vy > 0: self.is_grounded = True
            self.y -= self.vy; self.vy = 0

    def check_collision(self, get_block_func):
        left, right = int((self.x - self.w/2) // BLOCK_SIZE), int((self.x + self.w/2) // BLOCK_SIZE)
        top, bottom = int((self.y - self.h/2) // BLOCK_SIZE), int((self.y + self.h/2) // BLOCK_SIZE)
        for gx in range(left, right+1):
            for gy in range(top, bottom+1):
                b = get_block_func(gx, gy)
                if b != BLOCK_AIR and b != BLOCK_LEAVES: return True
        return False

    def to_dict(self): return {'type': 'Zombie', 'x': self.x, 'y': self.y, 'hp': self.hp}

class DemonEye:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0
        self.w, self.h = 28, 28
        self.hp, self.max_hp = 30, 30; self.damage = 12
        self.dash_timer = random.randint(40, 80)

    def update(self, player_x, player_y, get_block_func):
        dx, dy = player_x - self.x, player_y - self.y
        dist = math.hypot(dx, dy)
        self.dash_timer -= 1
        if self.dash_timer <= 0 and dist > 0:
            self.vx, self.vy = (dx / dist) * 8.0, (dy / dist) * 8.0
            self.dash_timer = random.randint(60, 100)
        else:
            self.vx *= 0.95; self.vy *= 0.95
            if dist > 0: self.vx += (dx / dist) * 0.2; self.vy += (dy / dist) * 0.2
        self.x += self.vx; self.y += self.vy

    def to_dict(self): return {'type': 'DemonEye', 'x': self.x, 'y': self.y, 'hp': self.hp}

class Skeleton:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0
        self.w, self.h = 22, 42
        self.hp, self.max_hp = 35, 35; self.damage = 18; self.speed = 2.8
        self.is_grounded = False

    def update(self, player_x, player_y, get_block_func):
        dist_x = player_x - self.x
        if abs(dist_x) < 550: self.vx = self.speed if dist_x > 0 else -self.speed
        self.vy += GRAVITY
        self.x += self.vx
        if self.check_collision(get_block_func):
            self.x -= self.vx
            if self.is_grounded: self.vy = -10.0; self.is_grounded = False
        self.y += self.vy
        if self.check_collision(get_block_func):
            if self.vy > 0: self.is_grounded = True
            self.y -= self.vy; self.vy = 0

    def check_collision(self, get_block_func):
        left, right = int((self.x - self.w/2) // BLOCK_SIZE), int((self.x + self.w/2) // BLOCK_SIZE)
        top, bottom = int((self.y - self.h/2) // BLOCK_SIZE), int((self.y + self.h/2) // BLOCK_SIZE)
        for gx in range(left, right+1):
            for gy in range(top, bottom+1):
                b = get_block_func(gx, gy)
                if b != BLOCK_AIR and b != BLOCK_LEAVES: return True
        return False

    def to_dict(self): return {'type': 'Skeleton', 'x': self.x, 'y': self.y, 'hp': self.hp}
    
