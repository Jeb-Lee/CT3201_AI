"""How often does Greedy best-first take a costlier (more dangerous) route than A*?

tools/search_comparison.py compares the four searches on one snapshot of one stage, and on
that snapshot Greedy happens to tie with A*. This repeats the same comparison (spawn -> exit,
key collected, fire spread for a while) across every stage, three debris layouts and five
fire-spread times: 150 situations. It is the evidence behind the report's Section 6 verdict on
the AI's "use Greedy, it's faster" recommendation.

Run:  python tools/greedy_vs_astar_scan.py
"""

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "pyro_pete_game"))

import pygame  # noqa: needed before importing modules that touch pygame at import
pygame.init()
pygame.display.set_mode((1, 1))

import levels                                       # noqa: E402
from hazard_field import HazardField                # noqa: E402
from pathfinding import astar_path, bfs_path, greedy_path, path_cost   # noqa: E402

FIRE_SECONDS = (20, 40, 60, 80, 100)
LAYOUT_SEEDS = (0, 1, 2)          # debris placement uses the global random generator


def scan():
    rows = []
    for st in range(levels.STAGE_COUNT):
        for layout in LAYOUT_SEEDS:
            random.seed(layout)
            stage = levels.get(st)
            tm = stage.build()
            hz = HazardField(tm, seed=stage.SEED, protected_cells_fn=lambda: [tm.spawn_cell, tm.exit_cell],
                             occupied_cells_fn=lambda: [], tuning=getattr(stage, "TUNING", None))
            hz.doors.key_collected = True        # the door is a separate sub-problem, as in search_comparison
            for secs in FIRE_SECONDS:
                while hz.fire.elapsed < secs:
                    hz.update(1 / 60)
                cost = hz.entry_cost
                start, goal = tm.spawn_cell, tm.exit_cell
                pa, pg, pb = astar_path(tm, start, goal, cost), greedy_path(tm, start, goal, cost), bfs_path(tm, start, goal)
                if not pa or not pg:
                    continue
                hot = lambda p: sum(1 for cell in p[1:] if cost(cell) > 0)
                rows.append(dict(stage=st + 1, layout=layout, seconds=secs,
                                 astar=path_cost(pa, cost), greedy=path_cost(pg, cost),
                                 bfs=path_cost(pb, cost) if pb else None,
                                 astar_hot=hot(pa), greedy_hot=hot(pg)))
    return rows


def main():
    rows = scan()
    worse = [r for r in rows if r["greedy"] > r["astar"] + 1e-6]
    print(f"{len(rows)} situations; Greedy's route cost more than A*'s in {len(worse)} "
          f"({100 * len(worse) / len(rows):.0f}%). A* is never costlier (it is cost-optimal).\n")
    print("Largest gaps:")
    for r in sorted(worse, key=lambda r: r["greedy"] / r["astar"], reverse=True)[:8]:
        print(f"  stage {r['stage']:2d}, layout {r['layout']}, after {r['seconds']:3d} s of fire: "
              f"A* {r['astar']:6.1f} ({r['astar_hot']:2d} hazard tiles)   Greedy {r['greedy']:6.1f} "
              f"({r['greedy_hot']:2d} hazard tiles)")


if __name__ == "__main__":
    main()
