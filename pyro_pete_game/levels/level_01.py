"""Level 1: small maze, lightly braided. Generated (not hand-authored) so
it's guaranteed solvable -- see mazegen.py. Fixed seed so the layout is
reproducible run to run.

BRAID > 0 knocks out some interior walls to add loops, so the floor plan
has real route choices: that's what makes the AI agent's A* an actual
decision (and the BFS/Dijkstra/A*/Greedy comparison in
tools/search_comparison.py show a difference) rather than every strategy
returning the one path a perfect maze allows.

Each level module follows the same shape (NAME, DIFFICULTY, build()) so
main.py can load any of them the same way -- a drop-in pattern for the
other planned maps, which scale difficulty via bigger cols/rows, less
braiding, and harsher hazard constants.
"""

from mazegen import generate_maze
from tilemap import TileMap

NAME = "Ground Floor"
DIFFICULTY = 1

SEED = 1337
COLS = 19
ROWS = 13
BRAID = 0.18


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell)
