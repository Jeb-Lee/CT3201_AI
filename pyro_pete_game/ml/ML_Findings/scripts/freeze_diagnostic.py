"""Where do the "gave up" endings happen?

Hypothesis (REWARD_EVOLUTION.md, v4): the standing still that survives even a
200-point penalty is not a global decision to do nothing but *freezing near
fire*, because damage is charged continuously while the give-up penalty comes
once, up to 12 s later. If that is right, most give-ups should happen with
fire in view. If instead the policy simply never moves, they should happen at
the spawn tile, whatever is around.

For each final model, sample episodes (sampled actions, as in training) on
stages 1-3. For every episode that ends "gave_up", record:
  * was the agent still on its spawn tile?
  * was any burning tile within the vision radius (3.5 tiles)?
  * how many tiles had it explored?
As a yardstick, the same "fire within vision" measure is taken at the end of
every *random-walk* episode's first 12 seconds (an agent that is not freezing).

    python pyro_pete_game/ml/ML_Findings/scripts/freeze_diagnostic.py
Writes data/freeze_diagnostic.csv and data/freeze_diagnostic.md.
"""

import csv
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

import numpy as np                                            # noqa: E402
import torch                                                  # noqa: E402

import levels                                                 # noqa: E402
from main import GameSession                                  # noqa: E402
from ml import evaluation                                     # noqa: E402
from ml.outcome import classify                               # noqa: E402
from ml.policy import load_policy, RandomPolicy               # noqa: E402
from settings import AGENT_VISION_TILES                       # noqa: E402

EXP, DATA = os.path.join(BASE, "experiments"), os.path.join(BASE, "data")
RUNS = ["exp01_plain_s0", "exp01_plain_s1", "exp01_plain_s2", "exp04_giveup200_s0",
        "exp04_giveup200_s1", "exp05_giveup200_timeout200_s0", "exp07_giveup200_long_s0",
        "exp06_plain_s2_continued"]
STAGES = [0, 1, 2]
PER_STAGE = 10
SEED_BASE = 60_000
DT = 1 / 30


def fire_in_view(session):
    a = session.agent
    cc, cr = a.current_cell
    r = AGENT_VISION_TILES
    return sum(1 for (c, rr) in session.hazards.fire.burning
               if (c - cc) ** 2 + (rr - cr) ** 2 <= r * r)


def play(stage, seed, policy, max_seconds=90.0, stop_at=None):
    evaluation._ensure_pygame()
    random.seed(seed)
    s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                    agent_brain="learned", policy=policy)
    keys = evaluation._NoKeys()
    while s.state == "playing" and s.agent_stats.elapsed < max_seconds:
        s.update(DT, keys)
        if stop_at and s.agent_stats.elapsed >= stop_at:
            break
    return s


def main():
    rows = []
    # yardstick: a random walker, sampled at 12 s (the time a freeze would take to trigger)
    base = []
    for st in STAGES:
        for i in range(PER_STAGE):
            s = play(st, SEED_BASE + 100 * st + i, RandomPolicy(i), stop_at=12.0)
            base.append(fire_in_view(s) > 0)
    for run in RUNS:
        path = os.path.join(EXP, run, "final_model.zip")
        if not os.path.isfile(path):
            continue
        policy = load_policy(path)
        policy.deterministic = False
        n = gave = at_spawn = fire = 0
        explored = []
        for st in STAGES:
            for i in range(PER_STAGE):
                seed = SEED_BASE + 100 * st + i
                torch.manual_seed(seed)
                s = play(st, seed, policy)
                n += 1
                if classify(s) != "gave_up":
                    continue
                gave += 1
                at_spawn += s.agent.current_cell == s.tilemap.spawn_cell
                fire += fire_in_view(s) > 0
                explored.append(len(s.agent.explored))
        rows.append(dict(run=run, episodes=n, gave_up=gave,
                         gave_up_at_spawn=at_spawn, gave_up_with_fire_in_view=fire,
                         median_tiles_explored=int(np.median(explored)) if explored else None))
        print(rows[-1], flush=True)
    base_rate = sum(base) / len(base)
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "freeze_diagnostic.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [f"Yardstick: a random walker has fire within vision after 12 s in "
             f"{100 * base_rate:.0f}% of episodes ({sum(base)}/{len(base)}).", "",
             "| run | episodes | ended gave-up | of those: still on spawn tile | of those: fire in view | median tiles explored |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        g = r["gave_up"]
        pc = lambda k: "-" if not g else f"{r[k]} ({100 * r[k] / g:.0f}%)"
        lines.append(f"| {r['run']} | {r['episodes']} | {g} | {pc('gave_up_at_spawn')} | "
                     f"{pc('gave_up_with_fire_in_view')} | {r['median_tiles_explored']} |")
    with open(os.path.join(DATA, "freeze_diagnostic.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
