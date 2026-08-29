"""Tile grid: collision, rendering, and pixel/tile coordinate conversion.

Tile art doesn't exist yet, so walls/floor/exit are drawn as flat colored
rectangles for now -- swap draw() for real tile sprites later without
touching the collision or camera code, since those only care about the
grid of tile types, not how each tile is drawn.
"""

import pygame

from settings import (
    TILE_SIZE, WALL_COLOR, FLOOR_COLOR, EXIT_COLOR, GRID_LINE_COLOR,
    DEBRIS_COLOR, LOCKED_DOOR_COLOR,
)

WALL = "#"
FLOOR = "."
EXIT = "E"


class TileMap:
    def __init__(self, rows, spawn_cell, exit_cell):
        """rows: list of strings (each char WALL/FLOOR). spawn_cell/exit_cell
        are (col, row) tile coordinates."""
        self.rows_text = rows
        self.rows = len(rows)
        self.cols = len(rows[0])
        self.tile_size = TILE_SIZE

        self.grid = [list(r) for r in rows]
        ex_c, ex_r = exit_cell
        self.grid[ex_r][ex_c] = EXIT

        self.spawn_cell = spawn_cell
        self.exit_cell = exit_cell

        # Cells that are floor in `grid` but currently impassable because a
        # hazard system put something there -- fallen debris, a locked
        # door. Kept separate from `grid` so it can be cleared on restart
        # without regenerating the maze, and so systems can own their own
        # cells. Maps cell -> render tag ("debris" / "door") for draw().
        self.dynamic_blocked = {}

    def block_cell(self, cell, tag):
        self.dynamic_blocked[cell] = tag

    def unblock_cell(self, cell):
        self.dynamic_blocked.pop(cell, None)

    def clear_dynamic_blocks(self):
        self.dynamic_blocked.clear()

    @property
    def pixel_width(self):
        return self.cols * self.tile_size

    @property
    def pixel_height(self):
        return self.rows * self.tile_size

    def spawn_pos(self):
        c, r = self.spawn_cell
        return self.cell_center(c, r)

    def cell_center(self, col, row):
        return (col * self.tile_size + self.tile_size / 2,
                row * self.tile_size + self.tile_size / 2)

    def tile_at(self, col, row):
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.grid[row][col]
        return WALL

    def is_walkable(self, col, row):
        """Static walls AND anything a hazard system has dropped in
        (debris, a locked door) block movement."""
        if self.tile_at(col, row) == WALL:
            return False
        return (col, row) not in self.dynamic_blocked

    def tiles_overlapping(self, rect):
        """Yield every (col, row) a pixel rect touches. One place for the
        rect->tile-range math the walkable / exit / hazard checks share."""
        ts = self.tile_size
        for row in range(rect.top // ts, (rect.bottom - 1) // ts + 1):
            for col in range(rect.left // ts, (rect.right - 1) // ts + 1):
                yield col, row

    def rect_walkable(self, rect):
        """True if a pixel rect doesn't overlap any wall/blocked tile."""
        return all(self.is_walkable(c, r) for c, r in self.tiles_overlapping(rect))

    def is_exit_rect(self, rect):
        return any(self.tile_at(c, r) == EXIT for c, r in self.tiles_overlapping(rect))

    def draw(self, surface, camera_offset):
        ox, oy = camera_offset
        screen_w, screen_h = surface.get_size()

        first_col = max(0, int(ox // self.tile_size))
        first_row = max(0, int(oy // self.tile_size))
        last_col = min(self.cols, int((ox + screen_w) // self.tile_size) + 1)
        last_row = min(self.rows, int((oy + screen_h) // self.tile_size) + 1)

        for row in range(first_row, last_row):
            for col in range(first_col, last_col):
                tile = self.grid[row][col]
                color = WALL_COLOR if tile == WALL else (
                    EXIT_COLOR if tile == EXIT else FLOOR_COLOR)
                block = self.dynamic_blocked.get((col, row))
                if block == "debris":
                    color = DEBRIS_COLOR
                elif block == "door":
                    color = LOCKED_DOOR_COLOR
                x = col * self.tile_size - ox
                y = row * self.tile_size - oy
                rect = pygame.Rect(x, y, self.tile_size, self.tile_size)
                pygame.draw.rect(surface, color, rect)
                pygame.draw.rect(surface, GRID_LINE_COLOR, rect, 1)
