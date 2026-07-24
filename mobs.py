import math
import random
from blocks import *

# ------------------- БАЗОВЫЙ КЛАСС МОБА -------------------
class Mob:
    def __init__(self, x, y, w, h, hp, damage, speed=0):
        self.x, self.y = x, y
        self.vx, self.vy = 0.0, 0.0
        self.w, self.h = w, h
        self.hp = hp
        self.max_hp = hp
        self.damage = damage
        self.speed = speed
        self.is_grounded = False

    def check_collision(self, get_block_func):
        left = int((self.x - self.w/2) // BLOCK_SIZE)
        right = int((self.x + self.w/2) // BLOCK_SIZE)
        top = int((self.y - self.h/2) // BLOCK_SIZE)
        bottom = int((self.y + self.h/2) // BLOCK_SIZE)
        for gx in range(left, right+1):
            for gy in range(top, bottom+1):
                b = get_block_func(gx, gy)
                if b != BLOCK_AIR and b not in (BLOCK_LEAVES, BLOCK_TALL_GRASS,
                                                BLOCK_FLOWER_RED, BLOCK_FLOWER_YELLOW,
                                                BLOCK_FLOWER_BLUE):
                    return True
        return False

    def apply_gravity(self, dt, gravity_mult=1.0):
        self.vy += GRAVITY * gravity_mult * dt

    def move_x(self, dt, get_block_func):
        self.x += self.vx * dt
        if self.check_collision(get_block_func):
            self.x -= self.vx * dt
            self.vx = 0

    def move_y(self, dt, get_block_func):
        self.y += self.vy * dt
        if self.check_collision(get_block_func):
            if self.vy > 0:
                self.is_grounded = True
            self.y -= self.vy * dt
            self.vy = 0

    def update(self, player_x, player_y, get_block_func, dt):
        self.update_ai(player_x, player_y, get_block_func, dt)
        self.apply_gravity(dt)
        self.move_x(dt, get_block_func)
        self.move_y(dt, get_block_func)

    def update_ai(self, player_x, player_y, get_block_func, dt):
        pass

    def to_dict(self):
        return {
            'type': self.__class__.__name__,
            'x': self.x,
            'y': self.y,
            'hp': self.hp
        }

    @classmethod
    def from_dict(cls, data):
        raise NotImplementedError("from_dict должен быть переопределён в дочернем классе")


# ------------------- СЛАЙМ -------------------
class Slime(Mob):
    def __init__(self, x, y, is_blue=False):
        w, h = SLIME_WIDTH, SLIME_HEIGHT
        hp = SLIME_HP_BLUE if is_blue else SLIME_HP_GREEN
        damage = SLIME_DAMAGE_BLUE if is_blue else SLIME_DAMAGE_GREEN
        super().__init__(x, y, w, h, hp, damage)
        self.is_blue = is_blue
        self.speed = SLIME_SPEED_BLUE if is_blue else SLIME_SPEED_GREEN
        self.color = (30, 136, 229) if is_blue else (76, 175, 80)
        self.jump_cooldown = random.uniform(SLIME_JUMP_COOLDOWN_MIN, SLIME_JUMP_COOLDOWN_MAX)

    def update_ai(self, player_x, player_y, get_block_func, dt):
        dist_x = player_x - self.x
        if self.jump_cooldown > 0:
            self.jump_cooldown -= dt

        if self.is_grounded and self.jump_cooldown <= 0 and abs(dist_x) < SLIME_AGGRO_RANGE:
            self.vy = random.uniform(SLIME_JUMP_FORCE_MIN, SLIME_JUMP_FORCE_MAX)
            self.vx = self.speed if dist_x > 0 else -self.speed
            self.is_grounded = False
            self.jump_cooldown = random.uniform(SLIME_JUMP_COOLDOWN_AFTER, SLIME_JUMP_COOLDOWN_AFTER_MAX)

    def to_dict(self):
        d = super().to_dict()
        d['is_blue'] = self.is_blue
        return d

    @classmethod
    def from_dict(cls, data):
        slime = cls(data['x'], data['y'], data.get('is_blue', False))
        slime.hp = data['hp']
        return slime


# ------------------- ЗОМБИ -------------------
class Zombie(Mob):
    def __init__(self, x, y):
        super().__init__(x, y, ZOMBIE_WIDTH, ZOMBIE_HEIGHT, ZOMBIE_HP, ZOMBIE_DAMAGE)
        self.speed = ZOMBIE_SPEED

    def update_ai(self, player_x, player_y, get_block_func, dt):
        dist_x = player_x - self.x
        if abs(dist_x) < ZOMBIE_AGGRO_RANGE:
            self.vx = self.speed if dist_x > 0 else -self.speed
        else:
            self.vx = 0

    def move_x(self, dt, get_block_func):
        self.x += self.vx * dt
        if self.check_collision(get_block_func):
            self.x -= self.vx * dt
            if self.is_grounded:
                self.vy = ZOMBIE_JUMP_FORCE
                self.is_grounded = False
            self.vx = 0

    @classmethod
    def from_dict(cls, data):
        z = cls(data['x'], data['y'])
        z.hp = data['hp']
        return z


# ------------------- ГЛАЗ ДЕМОНА -------------------
class DemonEye(Mob):
    def __init__(self, x, y):
        super().__init__(x, y, DEMON_EYE_WIDTH, DEMON_EYE_HEIGHT, DEMON_EYE_HP, DEMON_EYE_DAMAGE)
        self.dash_timer = random.uniform(DEMON_EYE_DASH_TIMER_MIN, DEMON_EYE_DASH_TIMER_MAX)

    def update_ai(self, player_x, player_y, get_block_func, dt):
        dx, dy = player_x - self.x, player_y - self.y
        dist = math.hypot(dx, dy)

        self.dash_timer -= dt
        if self.dash_timer <= 0 and dist > 0:
            speed = DEMON_EYE_DASH_SPEED
            self.vx = (dx / dist) * speed
            self.vy = (dy / dist) * speed
            self.dash_timer = random.uniform(DEMON_EYE_DASH_COOLDOWN_MIN, DEMON_EYE_DASH_COOLDOWN_MAX)
        else:
            self.vx *= 0.95
            self.vy *= 0.95
            if dist > 0:
                accel = DEMON_EYE_ACCEL
                self.vx += (dx / dist) * accel * dt
                self.vy += (dy / dist) * accel * dt

    def apply_gravity(self, dt, gravity_mult=1.0):
        pass

    def move_y(self, dt, get_block_func):
        self.y += self.vy * dt

    @classmethod
    def from_dict(cls, data):
        d = cls(data['x'], data['y'])
        d.hp = data['hp']
        return d


# ------------------- СКЕЛЕТ -------------------
class Skeleton(Mob):
    def __init__(self, x, y):
        super().__init__(x, y, SKELETON_WIDTH, SKELETON_HEIGHT, SKELETON_HP, SKELETON_DAMAGE)
        self.speed = SKELETON_SPEED

    def update_ai(self, player_x, player_y, get_block_func, dt):
        dist_x = player_x - self.x
        if abs(dist_x) < SKELETON_AGGRO_RANGE:
            self.vx = self.speed if dist_x > 0 else -self.speed
        else:
            self.vx = 0

    def move_x(self, dt, get_block_func):
        self.x += self.vx * dt
        if self.check_collision(get_block_func):
            self.x -= self.vx * dt
            if self.is_grounded:
                self.vy = SKELETON_JUMP_FORCE
                self.is_grounded = False
            self.vx = 0

    @classmethod
    def from_dict(cls, data):
        s = cls(data['x'], data['y'])
        s.hp = data['hp']
        return s


# ------------------- ОВЦА -------------------
class Sheep(Mob):
    def __init__(self, x, y):
        super().__init__(x, y, SHEEP_WIDTH, SHEEP_HEIGHT, SHEEP_HP, SHEEP_DAMAGE)
        self.color = (255, 255, 255)
        self.move_timer = random.uniform(0, 2)

    def update_ai(self, player_x, player_y, get_block_func, dt):
        self.move_timer -= dt
        if self.move_timer <= 0:
            self.vx = random.uniform(SHEEP_SPEED_MIN, SHEEP_SPEED_MAX)
            self.move_timer = random.uniform(SHEEP_MOVE_TIMER_MIN, SHEEP_MOVE_TIMER_MAX)

    def apply_gravity(self, dt, gravity_mult=1.0):
        self.vy += GRAVITY * SHEEP_GRAVITY_MULT * dt

    @classmethod
    def from_dict(cls, data):
        sh = cls(data['x'], data['y'])
        sh.hp = data['hp']
        return sh


# ------------------- ВЫПАВШИЙ ПРЕДМЕТ -------------------
class DroppedItem:
    def __init__(self, x, y, item_type, count=1):
        self.x, self.y = x, y
        self.item_type = item_type
        self.count = count
        self.vy = random.uniform(-2, -4) * 60
        self.vx = random.uniform(-1.5, 1.5) * 60
        self.bob_angle = random.uniform(0, 360)

    def update(self, player_x, player_y, get_block_func, dt):
        self.bob_angle += 0.1 * 60 * dt

        dx, dy = player_x - self.x, player_y - self.y
        dist = math.hypot(dx, dy)

        if dist < DROPPED_ITEM_PULL_RADIUS and dist > 0:
            speed = (2.0 if dist > 30 else 4.0) * 60
            self.vx += (dx / dist) * speed * dt
            self.vy += (dy / dist) * speed * dt

        self.vy += GRAVITY * 0.4 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        gx = int(self.x // BLOCK_SIZE)
        gy = int((self.y + 8) // BLOCK_SIZE)

        if get_block_func(gx, gy) != BLOCK_AIR:
            self.y = gy * BLOCK_SIZE - 8
            self.vy = 0
            self.vx *= 0.8

    def to_dict(self):
        return {
            'type': 'DroppedItem',
            'x': self.x,
            'y': self.y,
            'item_type': self.item_type,
            'count': self.count
        }

    @classmethod
    def from_dict(cls, data):
        return cls(data['x'], data['y'], data['item_type'], data['count'])