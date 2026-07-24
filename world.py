import pygame
import math
import random
from blocks import *

class GameWorld:
    """Отвечает за генерацию, хранение и рендеринг чанков."""
    def __init__(self):
        self.chunks = {}
        self.chunk_surfaces = {}
        self.dirty_chunks = set()
        self.land_height_cache = {}

    def _get_land_height(self, global_gx):
        if global_gx not in self.land_height_cache:
            h = int(LAND_HEIGHT_BASE
                    - (math.sin(global_gx * LAND_HEIGHT_FREQ) * LAND_HEIGHT_AMPLITUDE
                       + math.cos(global_gx * LAND_HEIGHT_FREQ2) * LAND_HEIGHT_AMPLITUDE2))
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

            # Цикл от низа до поверхности включительно (исправлено)
            for gy in range(WORLD_HEIGHT - 1, ground_h - 1, -1):
                if gy == ground_h:                     # поверхность – трава или декор
                    chunk[gy][local_x] = BLOCK_GRASS
                    if random.random() < DECORATION_CHANCE:
                        if random.random() < GRASS_CHANCE:
                            chunk[gy][local_x] = BLOCK_TALL_GRASS
                        else:
                            flower = random.choice(FLOWER_TYPES)
                            chunk[gy][local_x] = flower
                elif gy > ground_h - DIRT_LAYER_THICKNESS:   # слой земли под травой
                    chunk[gy][local_x] = BLOCK_DIRT
                else:                                      # камень с рудами
                    r = random.random()
                    if r < ORE_GOLD_CHANCE and gy > ground_h + ORE_GOLD_MIN_DEPTH:
                        chunk[gy][local_x] = BLOCK_GOLD_ORE
                    elif r < ORE_IRON_CHANCE and gy > ground_h + ORE_IRON_MIN_DEPTH:
                        chunk[gy][local_x] = BLOCK_IRON_ORE
                    elif r < ORE_COPPER_CHANCE and gy > ground_h + ORE_COPPER_MIN_DEPTH:
                        chunk[gy][local_x] = BLOCK_COPPER_ORE
                    elif r < ORE_COAL_CHANCE and gy > ground_h + ORE_COAL_MIN_DEPTH:
                        chunk[gy][local_x] = BLOCK_COAL_ORE
                    else:
                        chunk[gy][local_x] = BLOCK_STONE

            # Деревья
            if random.random() < TREE_CHANCE and ground_h > 8:
                tree_h = random.randint(TREE_MIN_HEIGHT, TREE_MAX_HEIGHT)
                for th in range(tree_h):
                    if ground_h - th >= 0:
                        chunk[ground_h - th][local_x] = BLOCK_WOOD
                top_y = ground_h - tree_h
                for lx in range(-TREE_LEAF_RADIUS, TREE_LEAF_RADIUS + 1):
                    for ly in range(-TREE_LEAF_RADIUS, TREE_LEAF_RADIUS):
                        if abs(lx) == TREE_LEAF_RADIUS and abs(ly) == TREE_LEAF_RADIUS:
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