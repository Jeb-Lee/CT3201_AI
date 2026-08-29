"""Player-centered fog of war with memory.

Three states per tile:
  * never seen        -> pitch black
  * seen before       -> dim (FOG_EXPLORED_ALPHA) -- you remember the layout
  * currently in view  -> clear

"Currently in view" is a soft circle of VISIBILITY_RADIUS_TILES around
Pete, shrunk while he's in smoke (hazards.vision_multiplier). No wall
occlusion / raycasting -- the circle is the model.

Implementation: a full-screen fog surface, alpha 255 everywhere, then
  1. explored tiles get their alpha knocked down to FOG_EXPLORED_ALPHA
  2. a soft round hole is subtracted at Pete's position for the live view
The round hole shape is precomputed once with numpy (already a dep).
"""

import numpy as np
import pygame

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE,
    VISIBILITY_RADIUS_TILES, VISIBILITY_SOFT_EDGE_TILES, FOG_COLOR,
    FOG_EXPLORED_ALPHA,
)


def _make_hole_surface(radius_px, soft_px):
    outer = radius_px + soft_px
    size = max(2, int(outer * 2))
    center = size / 2

    yy, xx = np.mgrid[0:size, 0:size]
    dist = np.sqrt((xx - center) ** 2 + (yy - center) ** 2)

    if soft_px > 0:
        alpha = np.clip(255 * (1 - (dist - radius_px) / soft_px), 0, 255)
    else:
        alpha = np.where(dist <= radius_px, 255, 0)
    alpha = np.where(dist <= radius_px, 255, alpha).astype(np.uint8)

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    alpha_view = pygame.surfarray.pixels_alpha(surf)
    alpha_view[:, :] = alpha
    del alpha_view
    return surf, size


class VisibilitySystem:
    def __init__(self):
        self._base_radius_px = VISIBILITY_RADIUS_TILES * TILE_SIZE
        self._soft_px = VISIBILITY_SOFT_EDGE_TILES * TILE_SIZE
        self._hole, self._hole_size = _make_hole_surface(self._base_radius_px, self._soft_px)

        # reused every frame instead of reallocating a screen-sized surface
        self._overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._explored_dim = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self._explored_dim.fill((0, 0, 0, 255 - FOG_EXPLORED_ALPHA))

        self.explored = set()

    def reset(self):
        self.explored.clear()

    def update(self, player, hazards=None):
        """Fold whatever Pete can currently see into the explored set."""
        radius_tiles = VISIBILITY_RADIUS_TILES
        if hazards is not None:
            radius_tiles *= hazards.vision_multiplier(player.x, player.y)
        pc = player.x / TILE_SIZE, player.y / TILE_SIZE
        r = int(radius_tiles) + 1
        cc, cr = int(pc[0]), int(pc[1])
        for row in range(cr - r, cr + r + 1):
            for col in range(cc - r, cc + r + 1):
                if (col + 0.5 - pc[0]) ** 2 + (row + 0.5 - pc[1]) ** 2 <= radius_tiles ** 2:
                    self.explored.add((col, row))

    def draw(self, surface, player, camera_offset, hazards=None):
        ox, oy = camera_offset
        overlay = self._overlay
        overlay.fill((*FOG_COLOR, 255))

        # 1. lift explored tiles from black to dim
        ts = TILE_SIZE
        screen_w, screen_h = surface.get_size()
        for col, row in self.explored:
            x = col * ts - ox
            y = row * ts - oy
            if -ts < x < screen_w and -ts < y < screen_h:
                overlay.blit(self._explored_dim, (x, y), special_flags=pygame.BLEND_RGBA_SUB)

        # 2. subtract the live view hole (shrunk in smoke)
        radius_tiles = VISIBILITY_RADIUS_TILES
        if hazards is not None:
            radius_tiles *= hazards.vision_multiplier(player.x, player.y)
        hole, hole_size = self._hole, self._hole_size
        if abs(radius_tiles - VISIBILITY_RADIUS_TILES) > 0.05:
            hole, hole_size = _make_hole_surface(
                radius_tiles * TILE_SIZE, self._soft_px
            )
        px = player.x - ox - hole_size / 2
        py = player.y - oy - hole_size / 2
        overlay.blit(hole, (px, py), special_flags=pygame.BLEND_RGBA_SUB)

        surface.blit(overlay, (0, 0))
