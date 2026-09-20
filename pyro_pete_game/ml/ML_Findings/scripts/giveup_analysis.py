"""Why do the agents give up with occupants still inside?

The owner's question: does the network decide that the last occupant is "not worth the
effort" and stop? This looks at the state each give-up ends in, for v4 and for A*, on the
300 seeded episodes used everywhere else (seeds 90,000+ x10/stage, 190,000+ x20/stage).

At the moment a give-up is declared it records:
  - the agent is standing on the exit or not, health left, occupants still idle
  - what A* (the teacher) would do from exactly that state (stay, or take a step = keep searching)
  - A*'s own cost-benefit rule (_worth_exploring: is the round trip to the nearest unexplored
    area within 60% of current health?) for that state

    python .../giveup_analysis.py        # writes data/giveup_analysis.md/.csv
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
V4 = os.path.join(BASE, "imitation", "imit_d_v4_trail", "final_model.zip")
CAP, DT = 240.0, 1 / 30
_POLICY = {}


def _init():
    import torch
    torch.set_num_threads(1)
    from ml.policy import load_policy
    _POLICY["v4"] = load_policy(V4)


def run(job):
    agent_name, stage, seed = job
    from ml import evaluation
    from ml.outcome import summarise
    from entities.rescue_agent import RescueAgent
    from pathfinding import astar_path
    from entities.victim import STATE_IDLE
    from pathfinding import weighted_distances
    import levels
    from main import GameSession
    evaluation._ensure_pygame()
    random.seed(seed)
    if agent_name == "astar":
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="astar", policy=None)
    else:
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="learned", policy=_POLICY["v4"])
    keys = evaluation._NoKeys()
    while s.state == "playing" and s.agent_stats.elapsed < CAP:
        s.update(DT, keys)
    summ = summarise(s)
    if summ["outcome"] != "gave_up":
        return None
    a = s.agent
    idle = sum(1 for v in s.victims if v.state == STATE_IDLE)
    spotted_idle = sum(1 for v in a.known_victims if v.state == STATE_IDLE)
    dist = weighted_distances(a.tilemap, a.current_cell, a._cost_fn())
    unexplored = a._nearest_unexplored(dist)
    worth = None if unexplored is None else bool(a._worth_exploring(unexplored))
    # not expert_action(): that returns STAY for any finished agent, which is always true here
    goal = RescueAgent._choose_goal_cell(a, s.victims)
    path = astar_path(a.tilemap, a.current_cell, goal, a._cost_fn())
    stays = int(not path or len(path) < 2)
    return dict(agent=agent_name, stage=stage, seed=seed, out=summ["victims_out"], total=summ["victims_total"],
                at_exit=int(a.current_cell == a.tilemap.exit_cell), health=round(a.health, 1), idle=idle,
                spotted_idle=spotted_idle, unexplored_left=int(unexplored is not None),
                worth_exploring="none" if worth is None else int(worth),
                astar_would_stay=stays, seconds=summ["seconds"])


def main():
    import multiprocessing
    jobs = []
    for name in ("astar", "v4"):
        for base, per in ((90_000, 10), (190_000, 20)):
            for st in range(10):
                for i in range(per):
                    jobs.append((name, st, base + 1000 * st + i))
    with multiprocessing.get_context("spawn").Pool(8, initializer=_init) as pool:
        rows = [r for r in pool.map(run, jobs, chunksize=3) if r]
    with open(os.path.join(DATA, "giveup_analysis.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = ["State at the moment each give-up was declared (300 episodes per agent, 240 s cap).", "",
             "| | give-ups | one occupant short | standing on the exit | A* would also stay | A*'s budget rule says the search is NOT worth it | an unexplored area is left | median health left |",
             "|---|---|---|---|---|---|---|---|"]
    for name in ("astar", "v4"):
        sub = [r for r in rows if r["agent"] == name]
        n = len(sub)
        if not n:
            continue
        one = sum(1 for r in sub if r["total"] - r["out"] == 1)
        ex = sum(r["at_exit"] for r in sub)
        st = sum(r["astar_would_stay"] for r in sub)
        nw = sum(1 for r in sub if r["worth_exploring"] == 0)
        ul = sum(r["unexplored_left"] for r in sub)
        hs = sorted(r["health"] for r in sub)
        lines.append(f"| {'A*' if name == 'astar' else name} | {n} | {one} | {ex} | {st} | {nw} | {ul} | {hs[n // 2]:.0f} |")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(DATA, "giveup_analysis.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
