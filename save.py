import json
import os
from blocks import SAVE_FILE_PATH, APPDATA_PATH


class SaveManager:
    """Отвечает за сохранение и загрузку состояния игры."""
    def __init__(self, game):
        self.game = game

    def save(self):
        """Сохраняет текущее состояние в файл."""
        
        world = self.game.world
        player = self.game.player
        inventory = self.game.inventory
        mob_manager = self.game.mob_manager

        mobs_data, items_data = mob_manager.to_dict()
        chunks_data = {str(k): v for k, v in world.chunks.items()}

        save_data = {
            'player_x': player.x,
            'player_y': player.y,
            'hp': player.hp,
            'max_hp': player.max_hp,
            'day_time': self.game.day_time,
            'day_counter': self.game.day_counter,
            'inventory': inventory.to_dict(),
            'selected_slot': inventory.selected_slot,
            'chunks': chunks_data,
            'mobs': mobs_data,
            'dropped_items': items_data
        }

        # Создаём папку, если её нет
        if not os.path.exists(APPDATA_PATH):
            os.makedirs(APPDATA_PATH)

        # Запись 
        with open(SAVE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=None, separators=(',', ':'))

        self.game.save_notification_timer = 2.0

    def load(self):
        """Загружает состояние из файла. Возвращает True при успехе."""
        if not os.path.exists(SAVE_FILE_PATH):
            return False

        try:
            with open(SAVE_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Восстанавливаем игрока
            player = self.game.player
            player.x, player.y = data['player_x'], data['player_y']
            player.hp, player.max_hp = data['hp'], data['max_hp']
            self.game.day_time = data['day_time']
            self.game.day_counter = data.get('day_counter', 0)

            # Инвентарь
            inventory = self.game.inventory
            inventory.from_dict(data['inventory'])
            inventory.selected_slot = data['selected_slot']

            # Мир
            world = self.game.world
            world.chunks = {int(k): v for k, v in data['chunks'].items()}
            for cx in world.chunks:
                world.dirty_chunks.add(cx)   

            # Мобы и дроп
            mob_manager = self.game.mob_manager
            mob_manager.from_dict(data['mobs'], data['dropped_items'])

            # Перестроить фоновые поверхности
            self.game._build_background_surfaces()

            return True
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return False