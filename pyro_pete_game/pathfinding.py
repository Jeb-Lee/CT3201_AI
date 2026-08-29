"""Shared graph-search helpers over the tilemap.

The maze (mazegen.py) is a perfect maze -- a spanning tree over the floor
cells -- so for *unweighted* routing there's exactly one path between any
two cells and plain BFS is already optimal. That's still true for the fire
spread timing (bfs_distances below).

Once hazards enter the picture the routing problem stops being trivial:
fire, smoke and sparking panels make some tiles *expensive but passable*
and debris/locked doors make some *impassable*, so "shortest" is no longer
"fewest tiles". weighted_distances (Dijkstra) and astar_path handle that
case -- they take a cost_fn(cell) -> float giving the extra cost of
entering a cell (0.0 = clear, math.inf = blocked). This is the single
place the tile grid is walked as a graph, so every consumer (fire
placement, the rescue-agent AI, connectivity checks) searches the same
representation.
"""

import heapq
import math
from collections import deque

NEIGHBOR_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))

# Base cost of stepping into any walkable tile, before hazard surcharges.
STEP_COST = 1.0


def bfs_distances(tilemap, start_cell):
    """Distance in cells from start_cell to every floor cell reachable
    from it, walking only through tilemap.is_walkable() tiles. Unweighted
    -- used for fire-spread ring counting and connectivity tests."""
    dist = {start_cell: 0}
    queue = deque([start_cell])
    while queue:
        col, row = queue.popleft()
        for dc, dr in NEIGHBOR_STEPS:
            n_col, n_row = col + dc, row + dr
            if (n_col, n_row) in dist:
                continue
            if tilemap.is_walkable(n_col, n_row):
                dist[(n_col, n_row)] = dist[(col, row)] + 1
                queue.append((n_col, n_row))
    return dist


def bfs_path(tilemap, start_cell, goal_cell):
    """Shortest sequence of cells from start_cell to goal_cell inclusive.
    Returns None if goal_cell isn't reachable. Unweighted -- see
    astar_path for hazard-aware routing."""
    if start_cell == goal_cell:
        return [start_cell]

    came_from = {start_cell: None}
    queue = deque([start_cell])
    while queue:
        col, row = queue.popleft()
        if (col, row) == goal_cell:
            break
        for dc, dr in NEIGHBOR_STEPS:
            n_col, n_row = col + dc, row + dr
            if (n_col, n_row) in came_from:
                continue
            if tilemap.is_walkable(n_col, n_row):
                came_from[(n_col, n_row)] = (col, row)
                queue.append((n_col, n_row))

    if goal_cell not in came_from:
        return None

    path = []
    cell = goal_cell
    while cell is not None:
        path.append(cell)
        cell = came_from[cell]
    path.reverse()
    return path


def _zero_cost(_cell):
    return 0.0


def weighted_distances(tilemap, start_cell, cost_fn=None, max_cost=math.inf):
    """Dijkstra: least-cost distance from start_cell to every reachable
    cell, where entering `cell` costs STEP_COST + cost_fn(cell). Cells
    whose cost_fn is math.inf (blocked -- debris, locked doors) are never
    expanded. Stops expanding past max_cost. Used to pick the nearest
    victim by *effort* rather than by tile count."""
    cost_fn = cost_fn or _zero_cost
    best = {start_cell: 0.0}
    pq = [(0.0, start_cell)]
    while pq:
        d, cell = heapq.heappop(pq)
        if d > best.get(cell, math.inf):
            continue
        col, row = cell
        for dc, dr in NEIGHBOR_STEPS:
            nxt = (col + dc, row + dr)
            if not tilemap.is_walkable(*nxt):
                continue
            surcharge = cost_fn(nxt)
            if surcharge == math.inf:
                continue
            nd = d + STEP_COST + surcharge
            if nd < best.get(nxt, math.inf) and nd <= max_cost:
                best[nxt] = nd
                heapq.heappush(pq, (nd, nxt))
    return best


def astar_path(tilemap, start_cell, goal_cell, cost_fn=None):
    """Least-cost path from start to goal using A* with a Manhattan
    heuristic (admissible: 4-connected grid, min step cost STEP_COST=1,
    hazard surcharges only add). Entering `cell` costs
    STEP_COST + cost_fn(cell); math.inf means blocked. Returns the list
    of cells inclusive, or None if the goal is unreachable given the
    current blocks."""
    cost_fn = cost_fn or _zero_cost
    if start_cell == goal_cell:
        return [start_cell]

    gx, gy = goal_cell

    def h(cell):
        return abs(cell[0] - gx) + abs(cell[1] - gy)

    g = {start_cell: 0.0}
    came_from = {start_cell: None}
    pq = [(h(start_cell), 0.0, start_cell)]
    while pq:
        _, gc, cell = heapq.heappop(pq)
        if cell == goal_cell:
            path = []
            while cell is not None:
                path.append(cell)
                cell = came_from[cell]
            path.reverse()
            return path
        if gc > g.get(cell, math.inf):
            continue
        col, row = cell
        for dc, dr in NEIGHBOR_STEPS:
            nxt = (col + dc, row + dr)
            if not tilemap.is_walkable(*nxt):
                continue
            surcharge = cost_fn(nxt)
            if surcharge == math.inf:
                continue
            ng = gc + STEP_COST + surcharge
            if ng < g.get(nxt, math.inf):
                g[nxt] = ng
                came_from[nxt] = cell
                heapq.heappush(pq, (ng + h(nxt), ng, nxt))
    return None


def greedy_path(tilemap, start_cell, goal_cell, cost_fn=None):
    """Greedy best-first: always expand the frontier cell closest to the
    goal by the Manhattan heuristic, ignoring cost-so-far. Fast but NOT
    cost-optimal -- kept here specifically so the project can compare it
    against astar_path on a hazard-weighted map (see docs/ai_critique.md).
    Still respects blocked cells (cost_fn == inf)."""
    cost_fn = cost_fn or _zero_cost
    if start_cell == goal_cell:
        return [start_cell]
    gx, gy = goal_cell

    def h(cell):
        return abs(cell[0] - gx) + abs(cell[1] - gy)

    came_from = {start_cell: None}
    pq = [(h(start_cell), start_cell)]
    while pq:
        _, cell = heapq.heappop(pq)
        if cell == goal_cell:
            path = []
            while cell is not None:
                path.append(cell)
                cell = came_from[cell]
            path.reverse()
            return path
        col, row = cell
        for dc, dr in NEIGHBOR_STEPS:
            nxt = (col + dc, row + dr)
            if nxt in came_from or not tilemap.is_walkable(*nxt):
                continue
            if cost_fn(nxt) == math.inf:
                continue
            came_from[nxt] = cell
            heapq.heappush(pq, (h(nxt), nxt))
    return None


def path_cost(path, cost_fn=None):
    """Total traversal cost of a path (STEP_COST per step + surcharge of
    each entered cell). Handy for the search-strategy comparison."""
    if not path or len(path) < 2:
        return 0.0
    cost_fn = cost_fn or _zero_cost
    return sum(STEP_COST + cost_fn(cell) for cell in path[1:])
