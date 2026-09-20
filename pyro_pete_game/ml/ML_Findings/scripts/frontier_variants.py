"""Does the order in which A* searches matter? (owner's efficiency question)

A*'s search rule is "go to the nearest unexplored frontier cell" (greedy nearest-frontier, by
hazard-weighted distance). The owner asked whether it would be more efficient to search the far
side of the map first (relative to the exit) and collect what is convenient on the way back,
instead of always taking the nearest unseen area.

A* itself is NOT changed: the benchmark stays exactly as it is. Each variant here replaces only
`RescueAgent._nearest_unexplored` inside the worker processes of this script, so the game code
and the benchmark are untouched. Everything else is identical: same body, same health-budget rule
(`_worth_exploring`), same "chase the nearest spotted occupant first", same 300 seeded episodes
as every other test in this folder.

Variants (frontier = unexplored cell next to an explored one; d_agent = hazard-weighted distance
from the agent, d_exit = walking distance from the frontier to the exit):
  nearest      minimise d_agent                       (A*'s own rule)
  far_soft     minimise d_agent - 0.5 * d_exit        (lean towards the far side, but not at any price)
  far_hard     minimise d_agent - 1.0 * d_exit        (lean harder)
  far_first    maximise d_exit                        (always the frontier furthest from the exit)
  near_exit    minimise d_agent + 1.0 * d_exit        (sweep outwards from the exit)

    python .../frontier_variants.py        # writes data/frontier_variants.md and .csv
    python .../frontier_variants.py fresh  # confirmation: seeds 290,000+, 20/stage, three variants
"""

import csv
import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

DATA = os.path.join(BASE, "data")
CAP, DT = 240.0, 1 / 30
VARIANTS = {
    "nearest": None,
    "far_soft": ("lin", 0.5),
    "far_hard": ("lin", 1.0),
    "far_first": ("far", None),
    "near_exit": ("lin", -1.0),
}


def _patch(name):
    spec = VARIANTS[name]
    if spec is None:
        return
    from entities.rescue_agent import RescueAgent
    from pathfinding import bfs_distances

    def nearest_unexplored(self, dist):
        tm = self.tilemap
        d_exit = getattr(tm, "_exit_dist_cache", None)
        if d_exit is None:
            d_exit = tm._exit_dist_cache = bfs_distances(tm, tm.exit_cell)
        best, best_key = None, (math.inf, (0, 0))
        kind, w = spec
        for cell, d in dist.items():
            if cell in self.explored:
                continue
            if not any((cell[0] + dc, cell[1] + dr) in self.explored for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            e = d_exit.get(cell, 0)
            score = -e if kind == "far" else d - w * e
            if (score, cell) < best_key:
                best, best_key = cell, (score, cell)
        return best

    RescueAgent._nearest_unexplored = nearest_unexplored


def run(job):
    name, stage, seed = job
    _patch(name)
    from ml import evaluation
    from ml.outcome import summarise
    import levels
    from main import GameSession
    evaluation._ensure_pygame()
    random.seed(seed)
    s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                    agent_brain="astar", policy=None)
    keys = evaluation._NoKeys()
    while s.state == "playing" and s.agent_stats.elapsed < CAP:
        s.update(DT, keys)
    r = summarise(s)
    return dict(variant=name, stage=stage, seed=seed, outcome=r["outcome"], out=r["victims_out"],
                total=r["victims_total"], score=r["score"], damage=r["damage"], seconds=r["seconds"])


def main():
    import multiprocessing
    fresh = len(sys.argv) > 1 and sys.argv[1] == "fresh"
    names = ["nearest", "far_soft", "far_hard"] if fresh else list(VARIANTS)
    tag = "_fresh" if fresh else ""
    jobs = []
    for name in names:
        for base, per in (((290_000, 20),) if fresh else ((90_000, 10), (190_000, 20))):
            for st in range(10):
                for i in range(per):
                    jobs.append((name, st, base + 1000 * st + i))
    print(len(jobs), "episodes", flush=True)
    with multiprocessing.get_context("spawn").Pool(8) as pool:
        rows = pool.map(run, jobs, chunksize=4)
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, f"frontier_variants{tag}.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def by(name):
        return {(r["stage"], r["seed"]): r for r in rows if r["variant"] == name}
    base = by("nearest")
    lines = ["Only the choice of *which unexplored area to search next* differs; A*'s benchmark code is untouched. "
             f"{len(by('nearest'))} seeded episodes per variant, 240 s cap. 'paired' = the variant minus nearest on the same "
             "episode (mean, with 95% interval).", "",
             "| variant | evacuated | died | gave up | occupants led out | mean score | paired score | mean seconds (evacuated) | paired seconds (both evacuated) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name in names:
        sub = by(name)
        n = len(sub)
        ev = [r for r in sub.values() if r["outcome"] == "evacuated"]
        diffs = [sub[k]["score"] - base[k]["score"] for k in base]
        m = sum(diffs) / n
        sd = (sum((d - m) ** 2 for d in diffs) / (n - 1)) ** 0.5
        ci = 1.96 * sd / n ** 0.5
        both = [k for k in base if sub[k]["outcome"] == "evacuated" and base[k]["outcome"] == "evacuated"]
        td = [sub[k]["seconds"] - base[k]["seconds"] for k in both]
        tm_ = sum(td) / max(1, len(td))
        tsd = (sum((d - tm_) ** 2 for d in td) / max(1, len(td) - 1)) ** 0.5
        tci = 1.96 * tsd / max(1, len(td)) ** 0.5
        lines.append(
            f"| {name} | {100 * len(ev) / n:.0f}% | {100 * sum(r['outcome'] == 'died' for r in sub.values()) / n:.0f}% | "
            f"{100 * sum(r['outcome'] == 'gave_up' for r in sub.values()) / n:.0f}% | "
            f"{100 * sum(r['out'] / r['total'] for r in sub.values()) / n:.0f}% | {sum(r['score'] for r in sub.values()) / n:.0f} | "
            f"{m:+.0f} ({m - ci:+.0f} to {m + ci:+.0f}) | {sum(r['seconds'] for r in ev) / max(1, len(ev)):.0f} | "
            f"{tm_:+.1f} s ({tm_ - tci:+.1f} to {tm_ + tci:+.1f}, n={len(both)}) |")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(DATA, f"frontier_variants{tag}.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
