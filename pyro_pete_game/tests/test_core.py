"""Fast, no-pygame checks for the parts a wrong answer would quietly
break: maze connectivity, the search functions, hazard placement rules,
and the debris safety guarantee.

Run:  python -m pytest        (from pyro_pete_game/)
  or: python tests/test_core.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mazegen import generate_maze, FLOOR
from tilemap import TileMap
from pathfinding import (
    bfs_path, bfs_distances, astar_path, weighted_distances, greedy_path, path_cost,
)


def _map(seed=1337, cols=19, rows=13):
    grid, ar, ac = generate_maze(cols, rows, seed=seed)
    return TileMap(grid, (1, 1), (ac - 2, ar - 2))


# ---------------------------------------------------------------- maze
def test_maze_is_fully_connected():
    for seed in range(6):
        tm = _map(seed=seed)
        reach = bfs_distances(tm, tm.spawn_cell)
        floors = {
            (c, r)
            for r in range(tm.rows) for c in range(tm.cols)
            if tm.grid[r][c] in (FLOOR, "E")
        }
        assert floors <= set(reach), f"seed {seed}: {len(floors - set(reach))} floor cells unreachable"


def test_spawn_and_exit_connected():
    tm = _map()
    assert bfs_path(tm, tm.spawn_cell, tm.exit_cell) is not None


# ---------------------------------------------------------------- search
def test_bfs_path_shortest_and_valid():
    tm = _map()
    path = bfs_path(tm, tm.spawn_cell, tm.exit_cell)
    assert path[0] == tm.spawn_cell and path[-1] == tm.exit_cell
    for a, b in zip(path, path[1:]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1  # single steps
        assert tm.is_walkable(*b)
    # BFS distance to the exit == path length - 1
    assert bfs_distances(tm, tm.spawn_cell)[tm.exit_cell] == len(path) - 1


def test_bfs_returns_none_when_unreachable():
    tm = _map()
    # wall off the exit
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        tm.block_cell((tm.exit_cell[0] + dc, tm.exit_cell[1] + dr), "debris")
    assert bfs_path(tm, tm.spawn_cell, tm.exit_cell) is None


def test_astar_matches_bfs_with_no_hazards():
    tm = _map()
    a = astar_path(tm, tm.spawn_cell, tm.exit_cell)
    b = bfs_path(tm, tm.spawn_cell, tm.exit_cell)
    assert path_cost(a) == path_cost(b)  # same cost (perfect maze -> same path)


def test_astar_routes_around_a_costed_tile():
    # a 1-row-tall maze would have no detour; use an open room instead
    grid = [
        "#####",
        "#...#",
        "#.#.#",
        "#...#",
        "#####",
    ]
    tm = TileMap(grid, (1, 1), (3, 3))
    hot = (2, 3)

    def cost(cell):
        return 50.0 if cell == hot else 0.0

    path = astar_path(tm, (1, 1), (3, 3), cost)
    assert hot not in path  # detoured around the expensive tile
    assert astar_path(tm, (1, 1), (3, 3)) is not None


def test_greedy_can_be_worse_than_astar_on_cost():
    grid = [
        "#######",
        "#.....#",
        "#.###.#",
        "#.....#",
        "#######",
    ]
    tm = TileMap(grid, (1, 1), (5, 1))
    # make the straight top row expensive; A* should take the long way,
    # greedy (heuristic-only) barrels along the top
    hot = {(2, 1), (3, 1), (4, 1)}

    def cost(cell):
        return 20.0 if cell in hot else 0.0

    a = astar_path(tm, (1, 1), (5, 1), cost)
    g = greedy_path(tm, (1, 1), (5, 1), cost)
    assert path_cost(a, cost) <= path_cost(g, cost)


def test_weighted_distances_penalises_hazard():
    grid = ["#####", "#...#", "#...#", "#...#", "#####"]
    tm = TileMap(grid, (1, 1), (3, 3))
    plain = weighted_distances(tm, (1, 1))
    costly = weighted_distances(tm, (1, 1), lambda c: 10.0 if c == (2, 2) else 0.0)
    assert costly[(2, 2)] > plain[(2, 2)]


# ---------------------------------------------------------------- hazards
def test_fire_never_ignites_on_spawn():
    from hazards import FireSystem
    for seed in range(4):
        tm = _map(seed=seed)
        fs = FireSystem(tm)
        assert fs.ignition_cell != tm.spawn_cell


def test_spark_panels_avoid_reserved_and_spawn():
    from panels import SparkPanelSystem
    tm = _map()
    sp = SparkPanelSystem(tm, exclude_cells=[(5, 5)], seed=1)
    assert tm.spawn_cell not in sp.panels
    assert tm.exit_cell not in sp.panels
    assert (5, 5) not in sp.panels


def test_locked_door_key_reachable_with_door_shut():
    from doors import LockedDoorSystem
    tm = _map()
    d = LockedDoorSystem(tm, seed=3)
    if not d.enabled:
        return
    d.activate()
    reach = bfs_distances(tm, tm.spawn_cell)
    assert d.key_cell in reach, "key spawned on the wrong side of the door"
    # ...and the exit is genuinely blocked without it
    assert bfs_path(tm, tm.spawn_cell, tm.exit_cell) is None


def test_debris_never_isolates_a_protected_cell():
    from debris import DebrisSystem
    tm = _map()
    protected = [tm.spawn_cell, tm.exit_cell, (9, 5)]
    ds = DebrisSystem(tm, lambda: protected, lambda: [])
    for _ in range(400):
        ds.update(0.1)
    reach = bfs_distances(tm, tm.spawn_cell)
    for p in protected:
        assert p in reach, f"{p} got walled off by debris"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
