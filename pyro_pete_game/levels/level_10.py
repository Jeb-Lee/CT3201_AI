"""Stage 10: the last one: biggest map, worst of everything.

Same shape as every other stage module (NAME, DIFFICULTY, TUNING,
build()) -- see levels/level_01.py for what the fields mean and
levels/tuning.py for the difficulty knobs. Anything TUNING leaves unset
falls back to settings.py.
"""

from mazegen import generate_maze
from tilemap import TileMap
from levels.tuning import StageTuning

NAME = "Roof Plant"
DIFFICULTY = 10

SEED = 9999
COLS = 31
ROWS = 21
BRAID = 0.13

# Set dressing for this stage -- open sky, HVAC units, vents, ducts and aerials.
# Purely visual: props are drawn, never collided with, so this changes
# how the stage looks and not how it plays (see props.py).
THEME = "roof"

TUNING = StageTuning(
    fire_seconds_to_exit=285,
    fire_spread_interval=4.4,
    panel_count=8,
    debris_interval=5.4,
    debris_max_tiles=36,
    victim_count=6,
    agent_speed_scale=1.18,
)


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell, theme=THEME, seed=SEED)
