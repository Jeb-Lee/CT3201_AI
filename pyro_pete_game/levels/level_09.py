"""Stage 9: seven occupants, barely a loop in the place.

Same shape as every other stage module (NAME, DIFFICULTY, TUNING,
build()) -- see levels/level_01.py for what the fields mean and
levels/tuning.py for the difficulty knobs. Anything TUNING leaves unset
falls back to settings.py.
"""

from mazegen import generate_maze
from tilemap import TileMap
from levels.tuning import StageTuning

NAME = "Reactor Annex"
DIFFICULTY = 9

SEED = 6626
COLS = 29
ROWS = 21
BRAID = 0.13

# Set dressing for this stage -- coolant tanks, shielding blocks and control consoles.
# Purely visual: props are drawn, never collided with, so this changes
# how the stage looks and not how it plays (see props.py).
THEME = "reactor"

TUNING = StageTuning(
    fire_seconds_to_exit=270,
    fire_spread_interval=4.3,
    panel_count=7,
    debris_interval=5.8,
    debris_max_tiles=32,
    victim_count=6,
    agent_speed_scale=1.15,
)


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell, theme=THEME, seed=SEED)
