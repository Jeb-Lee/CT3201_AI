"""What can the agent reach at spawn? (Why the key hint mattered.)

Every stage begins with the spawn area sealed behind a locked door. The exit, and
almost every occupant, are unreachable until the key is fetched. A* handles it by
heading for the key when its route to the goal is blocked; the first version of the
learner's observation had no notion of the key beyond a window of local tiles.

    python pyro_pete_game/ml/ML_Findings/scripts/spawn_reachability.py
Writes data/spawn_reachability.md.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "..", "..")))

from ml.env import EvacuationEnv                                  # noqa: E402
from pathfinding import weighted_distances, astar_path            # noqa: E402


def main():
    env = EvacuationEnv(max_sim_seconds=60.0)
    lines = ["Reachable ground at spawn, before the key is collected (5 seeds per stage, first seed shown for the map).", "",
             "| stage | door locked | tiles reachable | map tiles | exit reachable | occupants reachable | key reachable |",
             "|---|---|---|---|---|---|---|"]
    for st in range(10):
        rows = []
        for seed in range(5):
            env.reset(seed=seed, options={"stage": st})
            s = env._session
            a = s.agent
            tm = a.tilemap
            reach = weighted_distances(tm, a.current_cell, a._cost_fn())
            d = a.hazards.doors
            floor = sum(1 for c in range(tm.cols) for r in range(tm.rows) if tm.tile_at(c, r) != "#")
            rows.append((d.enabled and not d.key_collected, len(reach), floor, tm.exit_cell in reach,
                         sum(v.cell in reach for v in s.victims), len(s.victims),
                         d.key_cell in reach if d.key_cell else None))
        locked = all(r[0] for r in rows)
        lines.append(f"| {st + 1} | {'yes' if locked else 'no'} | {min(r[1] for r in rows)}-{max(r[1] for r in rows)} | "
                     f"{rows[0][2]} | {'no' if not any(r[3] for r in rows) else 'sometimes'} | "
                     f"{min(r[4] for r in rows)}-{max(r[4] for r in rows)} of {rows[0][5]} | "
                     f"{'yes' if all(r[6] for r in rows) else 'no'} |")
    text = "\n".join(lines)
    with open(os.path.join(BASE, "data", "spawn_reachability.md"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
