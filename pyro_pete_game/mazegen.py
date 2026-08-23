"""Perfect-maze generator (randomized recursive backtracker).

Produces a grid on the classic odd/even scheme: cells live at odd
(row, col) coordinates, even rows/cols are the wall lattice between them.
Because the algorithm carves a spanning tree over every cell, the result
is guaranteed fully connected -- any two floor cells have exactly one path
between them, so a spawn/exit pair is always solvable without needing to
validate it after the fact.

This also doubles as the natural data source for the course's graph-search
material later: each floor cell is a node, each carved passage is an edge,
which is exactly the "floor plan modeled as a graph" framing from the
Emergency Evacuation Routing exercise.
"""

import random

WALL = "#"
FLOOR = "."


def generate_maze(cols, rows, seed=None):
    """Returns a list of strings (rows), each character WALL or FLOOR.
    cols/rows are coerced up to the nearest odd number if needed.
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

    return ["".join(row) for row in grid], rows, cols
