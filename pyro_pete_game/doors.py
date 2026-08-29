"""One locked door + one key.

On a perfect maze there's a single corridor from spawn to exit, so a door
dropped on that corridor genuinely blocks the way through -- there's no
"go around". The key is placed on the spawn side of the door (found by
running BFS from spawn while the door is blocked, so we only ever pick a
cell that's actually reachable without a key).

Walking over the key -- Pete or the AI agent, whoever gets there -- picks
it up and unlocks the door for everyone. That makes "is the door in my
way? then the key is a sub-goal before my real goal" a routing decision
the AI has to make, instead of the map being a plain point-to-point
search.

Seeded off the level seed so door/key positions are reproducible.
"""

import random

import pygame

from settings import (
    LOCKED_DOOR_ENABLED, KEY_PICKUP_RADIUS, KEY_COLOR, LOCKED_DOOR_PANEL_COLOR,
)
from pathfinding import bfs_path, bfs_distances


class LockedDoorSystem:
    def __init__(self, tilemap, seed=None):
        """Picks the door + key cells straight away (needs only the maze),
        but does NOT block the door yet -- activate() does that. The gap
        lets panels/victims be placed on a doorless map first, so a victim
        can legitimately end up *beyond* the door (a 'fetch the key first'
        sub-goal) instead of being excluded from spawning there."""
        self.tilemap = tilemap
        self.enabled = LOCKED_DOOR_ENABLED
        self.doors = set()
        self.key_cell = None
        self.key_collected = False
        self.key_pos = None
        self._activated = False

        if not self.enabled:
            return

        corridor = bfs_path(tilemap, tilemap.spawn_cell, tilemap.exit_cell) or []
        inner = corridor[2:-2]  # not right next to spawn or exit
        if not inner:
            self.enabled = False
            return
        rng = random.Random(seed)

        # The maze may be braided (loops), so a random corridor cell can
        # have a way around it -- a "locked" door there would do nothing.
        # Walk the shortest path from the middle outward and take the first
        # cell that genuinely cuts spawn off from the exit when blocked.
        order = sorted(range(len(inner)), key=lambda i: abs(i - len(inner) // 2))
        door = None
        for i in order:
            cand = inner[i]
            tilemap.block_cell(cand, "door")
            cut = bfs_path(tilemap, tilemap.spawn_cell, tilemap.exit_cell) is None
            tilemap.unblock_cell(cand)
            if cut:
                door = cand
                break
        if door is None:
            self.enabled = False
            return
        self.doors.add(door)

        # key: reachable from spawn *with the door shut*, biased far from
        # spawn so it's a real detour.
        tilemap.block_cell(door, "door")
        try:
            reach = bfs_distances(tilemap, tilemap.spawn_cell)
        finally:
            tilemap.unblock_cell(door)
        options = [
            c for c, d in reach.items()
            if c not in self.doors and c not in (tilemap.spawn_cell, tilemap.exit_cell)
            and d >= 2
        ]
        options = options or [c for c in reach if c != tilemap.spawn_cell]
        options.sort(key=lambda c: -reach[c])
        self.key_cell = rng.choice(options[:max(1, len(options) // 2)])
        self.key_pos = tilemap.cell_center(*self.key_cell)

    def reserved_cells(self):
        """Cells other systems should avoid putting hazards / victims on."""
        cells = set(self.doors)
        if self.key_cell:
            cells.add(self.key_cell)
        return cells

    def activate(self):
        """Lock the door for real. Call after victims/panels are placed."""
        if self.enabled and not self._activated:
            self._activated = True
            for d in self.doors:
                self.tilemap.block_cell(d, "door")

    # ------------------------------------------------------------------
    def blocks(self, cell):
        return cell in self.doors and not self.key_collected

    def try_pickup(self, rect):
        """Pick the key up if `rect` overlaps it. Returns True on the
        frame it's first collected (so main can play a sound / flash)."""
        if not self.enabled or self.key_collected or self.key_cell is None:
            return False
        kx, ky = self.key_pos
        key_rect = pygame.Rect(0, 0, KEY_PICKUP_RADIUS * 2, KEY_PICKUP_RADIUS * 2)
        key_rect.center = (round(kx), round(ky))
        if rect.colliderect(key_rect):
            self.key_collected = True
            for d in self.doors:
                self.tilemap.unblock_cell(d)
            return True
        return False

    # ------------------------------------------------------------------
    def draw(self, surface, camera_offset):
        if not self.enabled:
            return
        ox, oy = camera_offset
        ts = self.tilemap.tile_size

        # door detail on top of the flat tile tilemap.draw() already laid
        # down (only while it's still locked)
        if not self.key_collected:
            for dc, dr in self.doors:
                x, y = dc * ts - ox, dr * ts - oy
                pygame.draw.rect(surface, LOCKED_DOOR_PANEL_COLOR,
                                 pygame.Rect(x + 8, y + 6, ts - 16, ts - 12))
                pygame.draw.rect(surface, (40, 28, 18),
                                 pygame.Rect(x + 8, y + 6, ts - 16, ts - 12), 2)
                pygame.draw.circle(surface, KEY_COLOR, (int(x + ts - 18), int(y + ts // 2)), 3)

        # the key
        if self.key_collected or self.key_cell is None:
            return
        cx, cy = self.key_pos
        x, y = cx - ox, cy - oy
        pygame.draw.polygon(surface, KEY_COLOR,
                            [(x, y - 9), (x + 7, y), (x, y + 9), (x - 7, y)])
        pygame.draw.polygon(surface, (30, 28, 20),
                            [(x, y - 9), (x + 7, y), (x, y + 9), (x - 7, y)], 2)
