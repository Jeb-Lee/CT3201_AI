"""Stage 1: small maze, lightly braided. Generated (not hand-authored) so it's guaranteed
solvable -- see mazegen.py. Fixed seed so the layout is reproducible run
to run.

BRAID > 0 knocks out some interior walls to add loops, so the floor plan
has real route choices: that's what makes the AI agent's A* an actual
decision (and the BFS/Dijkstra/A*/Greedy comparison in
tools/search_comparison.py show a difference) rather than every strategy
returning the one path a perfect maze allows.

Each level module follows the same shape (NAME, DIFFICULTY, TUNING,
build()) so main.py can load any of them the same way. Difficulty across
the campaign scales through bigger cols/rows, more occupants to find,
and the harsher hazard constants in TUNING.

Braiding stays roughly constant (0.18 down to 0.13) rather than dropping
away on the later stages. Starving a big map of loops looked like a
difficulty lever and was really a bug: with only one corridor between
two points, a fire across it leaves no route that isn't through flame,
and the AI died on those stages every run rather than playing them
badly. Loops are also the whole reason the A* comparison is meaningful,
so removing them removes the point of the map.

Note on the fire timer: TUNING.fire_seconds_to_exit *grows* down the
campaign, because a bigger building takes longer to cross. What tightens
is the time per tile -- see the difficulty test in
tests/test_campaign.py, which is what that curve is actually checked
against.
"""

from mazegen import generate_maze
from tilemap import TileMap
from levels.tuning import StageTuning

NAME = "Ground Floor"
DIFFICULTY = 1

SEED = 1337
COLS = 19
ROWS = 13
BRAID = 0.18

# Stage 1 is the original level, so it deliberately overrides
# nothing -- it plays exactly as it did before the campaign.
TUNING = StageTuning()


def build():
    rows, actual_rows, actual_cols = generate_maze(COLS, ROWS, seed=SEED, braid=BRAID)
    spawn_cell = (1, 1)
    exit_cell = (actual_cols - 2, actual_rows - 2)
    return TileMap(rows, spawn_cell, exit_cell)
