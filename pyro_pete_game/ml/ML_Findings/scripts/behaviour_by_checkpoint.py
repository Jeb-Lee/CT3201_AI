"""Measure what each saved checkpoint actually *does*, with sampled actions.

Why this exists: the validation runs in training use the deterministic policy
(always the highest-probability action), which is what the game uses. But an
untrained network's highest-probability action is arbitrary -- in these runs
it is "stay" -- so the deterministic policy stands still at step 0 *and* at
step 100k, and the validation curve is flat zero for a trivial reason. It
cannot tell you whether learning is happening. Training itself acts by
*sampling*, so the collapse shows up there. This script replays each
checkpoint the way training saw it: sampling from the policy.

For every run in RUNS and its first, middle and last checkpoint in
runs/<name>/checkpoints:
  * 18 sampled episodes on stages 1-3 (6 per stage, fixed seeds)
  * how they ended, occupants led out, seconds
  * the fraction of decisions that were each action (stay/up/down/left/right)

    python pyro_pete_game/ml/ML_Findings/scripts/behaviour_by_checkpoint.py
Writes data/behaviour_by_checkpoint.csv. Needs runs/ (git-ignored) to exist.
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

import numpy as np                                            # noqa: E402
import torch                                                  # noqa: E402

from ml import evaluation                                     # noqa: E402
from ml.policy import load_policy                             # noqa: E402

RUNS = ["exp01_plain_s0", "exp02_abandon_s0", "exp04_giveup200_s0",
        "exp05_giveup200_timeout200_s0", "exp07_giveup200_long_s0",
        "exp06_plain_s2_continued", "exp03_abandon_long_s0"]
STAGES = [0, 1, 2]
PER_STAGE = 6
SEED_BASE = 80_000
MAX_SECONDS = 90.0
ACTIONS = ["stay", "up", "down", "left", "right"]


class Counting:
    """Wraps a policy and tallies the actions it chooses."""

    def __init__(self, inner):
        self.inner, self.counts = inner, np.zeros(5)

    def act(self, observation, action_mask):
        a = self.inner.act(observation, action_mask)
        self.counts[a] += 1
        return a


def main():
    # `python behaviour_by_checkpoint.py RUN [RUN ...]` measures just those runs and
    # writes data/_behaviour_<run>.csv (so runs can be measured in parallel);
    # `... --merge` joins them into behaviour_by_checkpoint.csv.
    args = sys.argv[1:]
    if args == ["--merge"]:
        merge()
        return
    rows = []
    for run in (args or RUNS):
        ckpt_dir = os.path.join(ROOT, "runs", run, "checkpoints")
        if not os.path.isdir(ckpt_dir):
            print("skip (no checkpoints):", run)
            continue
        files = sorted(f for f in os.listdir(ckpt_dir) if f.endswith(".zip"))
        files = sorted({files[0], files[len(files) // 2], files[-1]})
        for f in files:
            step = int(re.search(r"step_(\d+)", f).group(1))
            policy = load_policy(os.path.join(ckpt_dir, f))
            policy.deterministic = False
            results, counts = [], np.zeros(5)
            for st in STAGES:
                for i in range(PER_STAGE):
                    seed = SEED_BASE + 100 * st + i
                    torch.manual_seed(seed)
                    wrapped = Counting(policy)
                    results.append(evaluation.run_episode(run, st, seed, MAX_SECONDS,
                                                          policy=wrapped))
                    counts += wrapped.counts
            n = len(results)
            frac = counts / max(1, counts.sum())
            row = dict(run=run, step=step, episodes=n,
                       evacuated=sum(r["outcome"] == "evacuated" for r in results) / n,
                       died=sum(r["outcome"] == "died" for r in results) / n,
                       gave_up=sum(r["outcome"] == "gave_up" for r in results) / n,
                       timeout=sum(r["outcome"] == "timeout" for r in results) / n,
                       occupants_out=sum(r["victims_out"] for r in results)
                       / max(1, sum(r["victims_total"] for r in results)),
                       seconds=sum(r["seconds"] for r in results) / n)
            for name, p in zip(ACTIONS, frac):
                row["p_" + name] = round(float(p), 4)
            rows.append(row)
            print(f"{run:32s} step {step:>7,}  died {row['died']:.2f}  gave_up {row['gave_up']:.2f}  "
                  f"timeout {row['timeout']:.2f}  evac {row['evacuated']:.2f}  "
                  f"P(stay) {row['p_stay']:.2f}", flush=True)
    if rows and args:
        out = os.path.join(BASE, "data", "_behaviour_" + "_".join(args) + ".csv")
        _write(out, rows)
    elif rows:
        out = os.path.join(BASE, "data", "behaviour_by_checkpoint.csv")
        _write(out, rows)
        print("wrote", out)


def _write(out, rows):
    if True:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def merge():
    data = os.path.join(BASE, "data")
    parts = sorted(f for f in os.listdir(data) if f.startswith("_behaviour_"))
    rows = []
    for f in parts:
        with open(os.path.join(data, f), newline="", encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
        os.remove(os.path.join(data, f))
    order = {r: i for i, r in enumerate(RUNS)}
    rows.sort(key=lambda r: (order.get(r["run"], 99), int(r["step"])))
    _write(os.path.join(data, "behaviour_by_checkpoint.csv"), rows)
    print("merged", len(rows), "rows from", len(parts), "runs")


if __name__ == "__main__":
    main()
