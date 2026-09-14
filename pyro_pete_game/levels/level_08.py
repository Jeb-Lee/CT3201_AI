"""Stage 8: a long hall with the roof coming down.

Same shape as every other stage module (NAME, DIFFICULTY, TUNING,
build()) -- see levels/level_01.py for what the fields mean and
levels/tuning.py for the difficulty knobs. Anything TUNING leaves unset
falls back to settings.py.
"""

from mazegen import generate_maze
from tilemap import TileMap
from levels.tuning import StageTuning

NAME = "Turbine Hall"
DIFFICULTY = 8

SEED = 1618
COLS = 29
ROWS = 19
BRAID = 0.14

TUNING = StageTuning(
    fire_seconds_to_exit=245,
    fire_spread_interval=4.1,
    panel_count=6,
    debris_interval=6.2,
    debris_max_tiles=28,
    victim_count=6,
    agent_speed_scale=1.12,
)


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell)
