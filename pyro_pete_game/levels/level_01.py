"""Level 1: small, easy maze. Generated (not hand-authored) so it's
guaranteed solvable -- see mazegen.py for why. Fixed seed so the layout
is reproducible run to run rather than reshuffling every launch.

Each level module follows the same shape (NAME, DIFFICULTY, build()) so
main.py can load any of them the same way, and so it's a drop-in pattern
for the other 9 planned maps -- difficulty for later levels can scale via
bigger cols/rows and eventually hazards, without changing this structure.
"""

from mazegen import generate_maze
from tilemap import TileMap

NAME = "Ground Floor"
DIFFICULTY = 1

SEED = 1337
COLS = 19
ROWS = 13


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell)
