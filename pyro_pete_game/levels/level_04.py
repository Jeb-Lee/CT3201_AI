"""Stage 4: tight aisles and more live equipment.

Same shape as every other stage module (NAME, DIFFICULTY, TUNING,
build()) -- see levels/level_01.py for what the fields mean and
levels/tuning.py for the difficulty knobs. Anything TUNING leaves unset
falls back to settings.py.
"""

from mazegen import generate_maze
from tilemap import TileMap
from levels.tuning import StageTuning

NAME = "Server Room"
DIFFICULTY = 4

SEED = 8080
COLS = 23
ROWS = 15
BRAID = 0.16

# Set dressing for this stage -- server racks, cable trays and cooling plant.
# Purely visual: props are drawn, never collided with, so this changes
# how the stage looks and not how it plays (see props.py).
THEME = "server"

TUNING = StageTuning(
    fire_seconds_to_exit=135,
    fire_spread_interval=3.8,
    panel_count=4,
    debris_interval=7.8,
    debris_max_tiles=16,
    victim_count=4,
    agent_speed_scale=1.04,
)


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell, theme=THEME, seed=SEED)
