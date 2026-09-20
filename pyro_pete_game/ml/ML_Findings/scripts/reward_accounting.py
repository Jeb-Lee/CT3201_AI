"""What would each kind of behaviour actually earn under the training reward?

The training reward is what the optimiser sees, so if "stand still" earns more
than "try to rescue someone" the optimiser will (rationally) stand still.
This measures the mean episode return of three behaviours under both reward
settings used in the experiments:

    plain     abandon penalty 0     (reward mirrors the game score)
    abandon   abandon penalty 100   (plus a charge per occupant left inside)

    stay     the agent never moves           (played through the real env)
    random   uniformly random legal moves    (played through the real env)
    astar    the hand-written A* rescuer      (return computed from its game
                                              statistics with the same formula
                                              the env uses, because the env
                                              only steps the learned agent)

Stages 1-3, 10 seeded episodes each (30 per behaviour). Output:
    data/reward_accounting.csv   one row per episode
    data/reward_accounting.md    the summary table
Run:  python pyro_pete_game/ml/ML_Findings/scripts/reward_accounting.py
"""

import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))

import numpy as np                                             # noqa: E402

from ml import evaluation                                      # noqa: E402
from ml.env import EvacuationEnv, RewardConfig                 # noqa: E402

STAGES = [0, 1, 2]
EPISODES = 10
MAX_SECONDS = 90.0
SEED_BASE = 70_000
CONFIGS = {"plain": 0.0, "abandon": 100.0}


def mean_ci(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else float("nan")
    return m, 1.96 * sd / math.sqrt(n)


def env_return(policy, abandon, stage, seed):
    env = EvacuationEnv(stages=[stage], max_sim_seconds=MAX_SECONDS,
                        reward=RewardConfig(abandon=abandon))
    env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    total = 0.0
    while True:
        if policy == "stay":
            action = 0
        else:
            action = int(rng.choice(np.flatnonzero(env.action_masks())))
        _, r, term, trunc, info = env.step(action)
        total += r
        if term or trunc:
            return total, info["summary"]


def astar_return(abandon, summary):
    """Same terms as ml/env.py, evaluated from the finished episode."""
    r = summary["score"]                     # occupants*100 + exit + speed bonus - damage*0.4
    r -= 0.05 * summary["seconds"]           # time cost
    if summary["outcome"] == "died":
        r -= 100.0
    r -= abandon * (summary["victims_total"] - summary["victims_out"])
    return r


def main():
    rows = []
    for name, abandon in CONFIGS.items():
        for policy in ("stay", "random", "astar"):
            for st in STAGES:
                for i in range(EPISODES):
                    seed = SEED_BASE + 100 * st + i
                    if policy == "astar":
                        s = evaluation.run_episode("astar", st, seed, MAX_SECONDS)
                        ret = astar_return(abandon, s)
                    else:
                        ret, s = env_return(policy, abandon, st, seed)
                    rows.append(dict(reward=name, abandon=abandon, policy=policy, stage=st + 1,
                                     seed=seed, ret=round(ret, 2), outcome=s["outcome"],
                                     occupants_out=s["victims_out"],
                                     occupants_total=s["victims_total"],
                                     seconds=s["seconds"]))
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "reward_accounting.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    lines = ["| reward | behaviour | mean return (95% CI) | died | gave up | timeout | evacuated | episodes with >=1 occupant led out |",
             "|---|---|---|---|---|---|---|---|"]
    for name in CONFIGS:
        for policy in ("stay", "random", "astar"):
            sel = [r for r in rows if r["reward"] == name and r["policy"] == policy]
            m, h = mean_ci([r["ret"] for r in sel])
            n = len(sel)
            pct = lambda k: f"{100 * sum(1 for r in sel if r['outcome'] == k) / n:.0f}%"
            some = sum(1 for r in sel if r["occupants_out"] > 0)
            lines.append(f"| {name} | {policy} | {m:+.1f} +/- {h:.1f} | {pct('died')} | "
                         f"{pct('gave_up')} | {pct('timeout')} | {pct('evacuated')} | {some}/{n} |")
    with open(os.path.join(DATA, "reward_accounting.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
