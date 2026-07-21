import pygame
import time
import sys
from blocks import TARGET_FPS
from Game import Game

def main():
    game = Game()
    
    while game.running:
        game.handle_events()

        game.fps_counter += 1
        now = time.time()
        if now - game.last_fps_time >= 1.0:
            game.current_fps = game.fps_counter
            game.fps_counter = 0
            game.last_fps_time = now

        if game.game_state == "game":
            game.update_physics()

        if game.game_state == "menu": 
            game.draw_menu()
        elif game.game_state == "game": 
            game.render()

        pygame.display.flip()
        game.clock.tick(TARGET_FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
