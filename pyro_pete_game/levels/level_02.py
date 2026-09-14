"""Stage 2: a wider floor plan, same hazards.

Same shape as every other stage module (NAME, DIFFICULTY, TUNING,
build()) -- see levels/level_01.py for what the fields mean and
levels/tuning.py for the difficulty knobs. Anything TUNING leaves unset
falls back to settings.py.
"""

from mazegen import generate_maze
from tilemap import TileMap
from levels.tuning import StageTuning

NAME = "Staff Canteen"
DIFFICULTY = 2

SEED = 2024
COLS = 21
ROWS = 13
BRAID = 0.17

TUNING = StageTuning(
    fire_seconds_to_exit=95,
    panel_count=3,
    debris_interval=8.6,
    debris_max_tiles=12,
    victim_count=3,
    agent_speed_scale=1.0,
)


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell)
