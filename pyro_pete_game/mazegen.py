"""Maze generator: randomized recursive backtracker, optionally braided.

Produces a grid on the classic odd/even scheme: cells live at odd
(row, col) coordinates, even rows/cols are the wall lattice between them.
The backtracker carves a spanning tree over every cell, so the result is
always fully connected.

`braid` (0.0-1.0) then knocks out that fraction of the *interior* walls
that have floor on both sides, adding loops. braid=0 is a perfect maze
(exactly one path between any two cells); braid>0 gives genuine route
choices -- which is what makes A* vs Greedy vs Dijkstra a real comparison
on this map rather than all four returning the identical single path
(see tools/search_comparison.py).

Each floor cell is a node, each carved passage an edge -- the "floor plan
modeled as a graph" framing from the Emergency Evacuation Routing
exercise.
"""

import random

WALL = "#"
FLOOR = "."


def generate_maze(cols, rows, seed=None, braid=0.0):
    """Returns (rows, actual_rows, actual_cols). `rows` is a list of
    strings, each character WALL or FLOOR. cols/rows are coerced up to the
    nearest odd number. `braid` in [0,1] is the fraction of removable
    interior walls to knock out for loops.
    """
    if cols % 2 == 0:
        cols += 1
    if rows % 2 == 0:
        rows += 1

    rng = random.Random(seed)
    grid = [[WALL] * cols for _ in range(rows)]

    def cell_neighbors(r, c):
        dirs = [(-2, 0), (2, 0), (0, -2), (0, 2)]
        rng.shuffle(dirs)
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 1 <= nr < rows - 1 and 1 <= nc < cols - 1:
                yield nr, nc, dr, dc

    start = (1, 1)
    grid[1][1] = FLOOR
    visited = {start}
    stack = [start]

    while stack:
        r, c = stack[-1]
        advanced = False
        for nr, nc, dr, dc in cell_neighbors(r, c):
            if (nr, nc) not in visited:
                grid[r + dr // 2][c + dc // 2] = FLOOR  # knock down the wall between
                grid[nr][nc] = FLOOR
                visited.add((nr, nc))
                stack.append((nr, nc))
                advanced = True
                break
        if not advanced:
            stack.pop()

    if braid > 0:
        # candidate walls: even-lattice cells with floor on the two
        # opposite sides (so removing one joins two corridors into a loop)
        candidates = []
        for r in range(1, rows - 1):
            for c in range(1, cols - 1):
                if grid[r][c] != WALL:
                    continue
                if grid[r - 1][c] == FLOOR and grid[r + 1][c] == FLOOR and \
                        grid[r][c - 1] == WALL and grid[r][c + 1] == WALL:
                    candidates.append((r, c))
                elif grid[r][c - 1] == FLOOR and grid[r][c + 1] == FLOOR and \
                        grid[r - 1][c] == WALL and grid[r + 1][c] == WALL:
                    candidates.append((r, c))
        rng.shuffle(candidates)
        for r, c in candidates[:int(len(candidates) * braid)]:
            grid[r][c] = FLOOR

    return ["".join(row) for row in grid], rows, cols
