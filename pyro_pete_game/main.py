"""Pyro Pete: Emergency Evacuation - tilemap/maze prototype.

Loads a generated maze level, drops Pete at the spawn point, and lets you
walk him through it with wall collision to the exit tile. No victims or
hazards yet -- this proves out the tilemap + camera + collision layer on
its own before those get added.
"""

import sys
import pygame

from settings import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from entities.player import Player
from camera import Camera
from levels import level_01

FONT_COLOR = (230, 230, 230)


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Pyro Pete - Emergency Evacuation (maze prototype)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 28)

    tilemap = level_01.build()
    camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, tilemap.pixel_width, tilemap.pixel_height)

    spawn_x, spawn_y = tilemap.spawn_pos()
    player = Player(spawn_x, spawn_y)

    reached_exit = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    # quick restart, mostly useful once "reached_exit" matters
                    spawn_x, spawn_y = tilemap.spawn_pos()
                    player = Player(spawn_x, spawn_y)
                    reached_exit = False

        keys = pygame.key.get_pressed()
        player.update(dt, keys, tilemap=tilemap)

        if not reached_exit and tilemap.is_exit_rect(player.get_collision_rect()):
            reached_exit = True

        camera.update(player.x, player.y)

        tilemap.draw(screen, camera.offset)
        player.draw(screen, camera.offset)

        if reached_exit:
            text = font.render("Reached the exit! (R to restart)", True, FONT_COLOR)
            screen.blit(text, (16, 16))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
