import os

# ------------------- КОНСТАНТЫ -------------------
SCREEN_WIDTH = 1100
SCREEN_HEIGHT = 700
BLOCK_SIZE = 32

CHUNK_WIDTH = 16
WORLD_HEIGHT = 60

MAX_STACK = 9999
BUILD_REACH = BLOCK_SIZE * 5.5

GRAVITY = 0.85
PLAYER_SPEED = 5.2
JUMP_FORCE = -11.5

TARGET_FPS = 60

APPDATA_DIR = os.environ.get('APPDATA', os.path.expanduser('~'))
APPDATA_PATH = os.path.join(APPDATA_DIR, 'MinePy')
SAVE_FILE_PATH = os.path.join(APPDATA_PATH, 'world_save.json')

# ------------------- БЛОКИ И ПРЕДМЕТЫ -------------------
BLOCK_AIR = 0
BLOCK_DIRT = 1
BLOCK_GRASS = 2
BLOCK_STONE = 3
BLOCK_WOOD = 4
BLOCK_LEAVES = 11
BLOCK_COPPER_ORE = 14
BLOCK_IRON_ORE = 15
BLOCK_GOLD_ORE = 26
BLOCK_COAL_ORE = 27

ITEM_SWORD_WOOD = 5
ITEM_SWORD_COPPER = 16
ITEM_SWORD_IRON = 17
ITEM_SWORD_GOLD = 28
ITEM_SWORD_DIAMOND = 29

ITEM_PICKAXE_WOOD = 6
ITEM_PICKAXE_COPPER = 18
ITEM_PICKAXE_IRON = 19
ITEM_PICKAXE_GOLD = 30

ITEM_GEL = 8
ITEM_POTION = 9
ITEM_BIG_POTION = 20
ITEM_COIN = 10
ITEM_LENS = 12
ITEM_TORCH = 13
ITEM_BONE = 21

ITEM_COPPER_INGOT = 22
ITEM_IRON_INGOT = 23
ITEM_GOLD_INGOT = 31
ITEM_COAL = 32
ITEM_DIAMOND = 33

ITEM_WOOD_SHIELD = 24
ITEM_IRON_ARMOR = 25

BLOCK_COLORS = {
    BLOCK_GRASS: (76, 175, 80),
    BLOCK_DIRT: (121, 85, 72),
    BLOCK_STONE: (96, 125, 139),
    BLOCK_WOOD: (93, 64, 55),
    BLOCK_LEAVES: (46, 125, 50),
    BLOCK_COPPER_ORE: (216, 112, 64),
    BLOCK_IRON_ORE: (176, 190, 197),
    BLOCK_GOLD_ORE: (255, 215, 0),
    BLOCK_COAL_ORE: (33, 33, 33)
}

ITEM_NAMES = {
    BLOCK_DIRT: "Земля", BLOCK_GRASS: "Трава", BLOCK_STONE: "Камень", BLOCK_WOOD: "Дерево",
    BLOCK_LEAVES: "Листва", BLOCK_COPPER_ORE: "Медн. руда", BLOCK_IRON_ORE: "Жел. руда",
    BLOCK_GOLD_ORE: "Зол. руда", BLOCK_COAL_ORE: "Угл. руда",
    ITEM_SWORD_WOOD: "Дер. меч", ITEM_SWORD_COPPER: "Медн. меч", ITEM_SWORD_IRON: "Жел. меч",
    ITEM_SWORD_GOLD: "Зол. меч", ITEM_SWORD_DIAMOND: "Алм. меч",
    ITEM_PICKAXE_WOOD: "Дер. кирка", ITEM_PICKAXE_COPPER: "Медн. кирка", ITEM_PICKAXE_IRON: "Жел. кирка",
    ITEM_PICKAXE_GOLD: "Зол. кирка", ITEM_GEL: "Гель", ITEM_POTION: "Зелье", ITEM_BIG_POTION: "Б. Зелье",
    ITEM_COIN: "Монета", ITEM_LENS: "Линза", ITEM_TORCH: "Факел", ITEM_BONE: "Кость",
    ITEM_COPPER_INGOT: "Медн. слиток", ITEM_IRON_INGOT: "Жел. слиток", ITEM_GOLD_INGOT: "Зол. слиток",
    ITEM_COAL: "Уголь", ITEM_DIAMOND: "Алмаз", ITEM_WOOD_SHIELD: "Дер. щит", ITEM_IRON_ARMOR: "Жел. броня"
}

CRAFTING_RECIPES = [
    ({'type': ITEM_TORCH, 'count': 4}, [(BLOCK_WOOD, 1), (ITEM_COAL, 1)]),
    ({'type': ITEM_POTION, 'count': 1}, [(ITEM_GEL, 2), (BLOCK_WOOD, 2)]),
    ({'type': ITEM_BIG_POTION, 'count': 1}, [(ITEM_POTION, 2), (ITEM_LENS, 1)]),
    ({'type': ITEM_COPPER_INGOT, 'count': 1}, [(BLOCK_COPPER_ORE, 3)]),
    ({'type': ITEM_IRON_INGOT, 'count': 1}, [(BLOCK_IRON_ORE, 3)]),
    ({'type': ITEM_GOLD_INGOT, 'count': 1}, [(BLOCK_GOLD_ORE, 3)]),
    ({'type': ITEM_SWORD_WOOD, 'count': 1}, [(BLOCK_WOOD, 7)]),
    ({'type': ITEM_SWORD_COPPER, 'count': 1}, [(ITEM_COPPER_INGOT, 5), (BLOCK_WOOD, 2)]),
    ({'type': ITEM_SWORD_IRON, 'count': 1}, [(ITEM_IRON_INGOT, 8), (BLOCK_WOOD, 2)]),
    ({'type': ITEM_SWORD_GOLD, 'count': 1}, [(ITEM_GOLD_INGOT, 8), (BLOCK_WOOD, 2)]),
    ({'type': ITEM_SWORD_DIAMOND, 'count': 1}, [(ITEM_DIAMOND, 5), (BLOCK_WOOD, 2)]),
    ({'type': ITEM_WOOD_SHIELD, 'count': 1}, [(BLOCK_WOOD, 10), (ITEM_BONE, 2)]),
    ({'type': ITEM_IRON_ARMOR, 'count': 1}, [(ITEM_IRON_INGOT, 12), (ITEM_COIN, 5)]),
]
