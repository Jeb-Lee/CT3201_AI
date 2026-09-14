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
from collections import deque

import pygame

from settings import (
    SPARK_PANEL_COUNT, SPARK_PANEL_MIN_SPAWN_DISTANCE,
    SPARK_PANEL_DAMAGE_PER_SECOND, SPARK_PANEL_TILE_COST,
    SPARK_PANEL_COLOR, SPARK_PANEL_CORE_COLOR, SPARK_PANEL_BOX_COLOR,
)
from pathfinding import bfs_distances


def _route_exists_avoiding(tilemap, blocked):
    """Is there a spawn->exit path that never crosses `blocked`? Plain
    BFS over walkable tiles with those cells treated as walls."""
    start, goal = tilemap.spawn_cell, tilemap.exit_cell
    if start in blocked or goal in blocked:
        return False
    seen = {start}
    queue = deque([start])
    while queue:
        col, row = queue.popleft()
        if (col, row) == goal:
            return True
        for dc, dr in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nxt = (col + dc, row + dr)
            if (nxt not in seen and nxt not in blocked
                    and tilemap.is_walkable(*nxt)):
                seen.add(nxt)
                queue.append(nxt)
    return False


class SparkPanelSystem:
    def __init__(self, tilemap, exclude_cells=(), seed=None, count=None):
        """count overrides SPARK_PANEL_COUNT for this stage."""
        self.tilemap = tilemap
        count = SPARK_PANEL_COUNT if count is None else count
        rng = random.Random(seed)
        dist = bfs_distances(tilemap, tilemap.spawn_cell)
        banned = set(exclude_cells) | {tilemap.spawn_cell, tilemap.exit_cell}
        candidates = [
            c for c, d in dist.items()
            if c not in banned and d >= SPARK_PANEL_MIN_SPAWN_DISTANCE
        ]
        rng.shuffle(candidates)
        self.panels = self._place_leaving_a_clean_route(candidates, count)
        self._t = 0.0

    def _place_leaving_a_clean_route(self, candidates, count):
        """Take panels from `candidates` one at a time, skipping any that
        would seal off every panel-free route from spawn to exit.

        Without this the later campaign stages were unwinnable: with eight
        or more panels on a lightly-braided map, the seeded layout could
        sit across the only corridor, and both Pete and the AI had to walk
        through 34 dps to get anywhere. The cost surcharge in the A* only
        helps if an alternative exists -- this is what guarantees one.
        """
        chosen = set()
        for cell in candidates:
            if len(chosen) >= count:
                break
            if _route_exists_avoiding(self.tilemap, chosen | {cell}):
                chosen.add(cell)
        return chosen

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
