"""Sparking electrical panels: a stationary, non-spreading hazard.

Placed once at level build time on floor tiles that aren't spawn, exit, a
victim cell or the fire's ignition cell, and at least
SPARK_PANEL_MIN_SPAWN_DISTANCE cells from spawn. A shorted panel arcs
across its tile -- standing on it drains health fast
(SPARK_PANEL_DAMAGE_PER_SECOND, higher than open fire), but unlike fire
it never grows, so it's a fixed obstacle to route around rather than a
timer. Passable in an emergency; the AI's A* gives it a heavy surcharge
(SPARK_PANEL_TILE_COST) so it only crosses one if the detour is worse.

Seeded off the level seed so the layout is reproducible run to run, the
same way the maze and fire ignition are.
"""

import random

import pygame

from settings import (
    SPARK_PANEL_COUNT, SPARK_PANEL_MIN_SPAWN_DISTANCE,
    SPARK_PANEL_DAMAGE_PER_SECOND, SPARK_PANEL_TILE_COST,
    SPARK_PANEL_COLOR, SPARK_PANEL_CORE_COLOR, SPARK_PANEL_BOX_COLOR,
)
from pathfinding import bfs_distances


class SparkPanelSystem:
    def __init__(self, tilemap, exclude_cells=(), seed=None):
        self.tilemap = tilemap
        rng = random.Random(seed)
        dist = bfs_distances(tilemap, tilemap.spawn_cell)
        banned = set(exclude_cells) | {tilemap.spawn_cell, tilemap.exit_cell}
        candidates = [
            c for c, d in dist.items()
            if c not in banned and d >= SPARK_PANEL_MIN_SPAWN_DISTANCE
        ]
        rng.shuffle(candidates)
        self.panels = set(candidates[:SPARK_PANEL_COUNT])
        self._t = 0.0

    def update(self, dt):
        self._t += dt

    def damage_rect(self, rect):
        cells = self.tilemap.tiles_overlapping(rect)
        return SPARK_PANEL_DAMAGE_PER_SECOND if any(c in self.panels for c in cells) else 0.0

    def tile_cost(self, cell):
        return SPARK_PANEL_TILE_COST if cell in self.panels else 0.0

    def draw(self, surface, camera_offset):
        ox, oy = camera_offset
        ts = self.tilemap.tile_size
        arcing = (int(self._t * 9) % 3 != 0)  # on 2 beats out of 3
        for col, row in self.panels:
            x, y = col * ts - ox, row * ts - oy
            # dark housing bolted to the wall
            box = pygame.Rect(x + 10, y + 8, ts - 20, ts - 16)
            pygame.draw.rect(surface, SPARK_PANEL_BOX_COLOR, box)
            pygame.draw.rect(surface, (90, 84, 64), box, 2)
            if arcing:
                cx = x + ts // 2
                # jagged bolt down the tile + a soft glow ring
                glow = pygame.Surface((ts, ts), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*SPARK_PANEL_COLOR, 70), (ts // 2, ts // 2), ts // 2 - 6)
                surface.blit(glow, (x, y))
                jitter = random.Random(int(self._t * 30) + col * 7 + row)
                pts = [(cx, y + 12)]
                for i in range(1, 5):
                    pts.append((cx + jitter.randint(-9, 9), y + 12 + i * (ts - 24) / 4))
                pygame.draw.lines(surface, SPARK_PANEL_CORE_COLOR, False, pts, 2)
