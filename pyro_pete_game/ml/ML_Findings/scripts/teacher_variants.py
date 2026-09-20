"""Choosing the teacher for v5: far-side search, with and without the "no corner trips" rule.

Uses the real agent options (`frontier_lean`, `frontier_min_reveal`, see
entities/rescue_agent.py), not a patch. The default agent is unchanged; the first row is the
unmodified A* and must reproduce the benchmark (87%, score 505 on these 300 episodes) or
something is wrong.

  frontier_lean 0.5          lean the search towards the far side of the map (section 4.11)
  frontier_defer_small       with K: visit a small corner only when nothing bigger is left
  frontier_min_reveal K      never make a trip to a frontier that would reveal fewer than K unseen
                             floor tiles (a corner's last few tiles). Fog of war is unchanged: it
                             only uses the layout, the exit and its own explored set.

    python .../teacher_variants.py          # 300 episodes, all variants
    python .../teacher_variants.py fresh    # 200 fresh episodes (seeds 290,000+), three variants
"""

import csv
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
    "A* (benchmark)": {},
    "far side (lean 0.5)": {"frontier_lean": 0.5},
    "far side + skip corners < 4 tiles": {"frontier_lean": 0.5, "frontier_min_reveal": 4},
    "far side + skip corners < 8 tiles": {"frontier_lean": 0.5, "frontier_min_reveal": 8},
    "far side + skip corners < 12 tiles": {"frontier_lean": 0.5, "frontier_min_reveal": 12},
    "nearest + skip corners < 8 tiles": {"frontier_min_reveal": 8},
    "far side + defer corners < 8 tiles": {"frontier_lean": 0.5, "frontier_min_reveal": 8, "frontier_defer_small": True},
    "far side + defer corners < 12 tiles": {"frontier_lean": 0.5, "frontier_min_reveal": 12, "frontier_defer_small": True},
    "nearest + defer corners < 8 tiles": {"frontier_min_reveal": 8, "frontier_defer_small": True},
}


def run(job):
    name, stage, seed = job
    from ml import evaluation
    from ml.outcome import summarise
    import levels
    from main import GameSession
    evaluation._ensure_pygame()
    random.seed(seed)
    s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                    agent_brain="astar", policy=None, agent_options=VARIANTS[name])
    keys = evaluation._NoKeys()
    while s.state == "playing" and s.agent_stats.elapsed < CAP:
        s.update(DT, keys)
    r = summarise(s)
    return dict(variant=name, stage=stage, seed=seed, outcome=r["outcome"], out=r["victims_out"],
                total=r["victims_total"], score=r["score"], seconds=r["seconds"])


def main():
    import multiprocessing
    fresh = len(sys.argv) > 1 and sys.argv[1] == "fresh"
    names = ["A* (benchmark)", "far side (lean 0.5)", "far side + skip corners < 4 tiles"] if fresh else list(VARIANTS)
    tag = "_fresh" if fresh else ""
    sets = ((290_000, 20),) if fresh else ((90_000, 10), (190_000, 20))
    jobs = [(n, st, base + 1000 * st + i) for n in names for base, per in sets
            for st in range(10) for i in range(per)]
    print(len(jobs), "episodes", flush=True)
    with multiprocessing.get_context("spawn").Pool(8) as pool:
        rows = pool.map(run, jobs, chunksize=4)
    with open(os.path.join(DATA, f"teacher_variants{tag}.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [f"{len(jobs) // len(names)} seeded episodes per row ("
             + ("fresh seeds 290,000+" if fresh else "the two test sets pooled") + "), 240 s cap.", "",
             "| teacher | evacuated | died | gave up | occupants led out | mean score | mean seconds (evacuated) |",
             "|---|---|---|---|---|---|---|"]
    for name in names:
        sub = [r for r in rows if r["variant"] == name]
        n = len(sub)
        ev = [r for r in sub if r["outcome"] == "evacuated"]
        lines.append(f"| {name} | {100 * len(ev) / n:.0f}% | {100 * sum(r['outcome'] == 'died' for r in sub) / n:.0f}% | "
                     f"{100 * sum(r['outcome'] == 'gave_up' for r in sub) / n:.0f}% | "
                     f"{100 * sum(r['out'] / r['total'] for r in sub) / n:.0f}% | {sum(r['score'] for r in sub) / n:.0f} | "
                     f"{sum(r['seconds'] for r in ev) / max(1, len(ev)):.0f} |")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(DATA, f"teacher_variants{tag}.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
