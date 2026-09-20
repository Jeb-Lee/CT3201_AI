"""Stage 5: big room, five occupants, ceiling going early.

Same shape as every other stage module (NAME, DIFFICULTY, TUNING,
build()) -- see levels/level_01.py for what the fields mean and
levels/tuning.py for the difficulty knobs. Anything TUNING leaves unset
falls back to settings.py.
"""

from mazegen import generate_maze
from tilemap import TileMap
from levels.tuning import StageTuning

NAME = "Chemical Store"
DIFFICULTY = 5

SEED = 1550
COLS = 25
ROWS = 17
BRAID = 0.15

# Set dressing for this stage -- drums, crates and hazard signage.
# Purely visual: props are drawn, never collided with, so this changes
# how the stage looks and not how it plays (see props.py).
THEME = "chemical"

TUNING = StageTuning(
    fire_seconds_to_exit=160,
    fire_spread_interval=3.7,
    panel_count=5,
    debris_interval=7.4,
    debris_max_tiles=19,
    victim_count=5,
    agent_speed_scale=1.06,
)


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell, theme=THEME, seed=SEED)
