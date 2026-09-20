"""Screen-record what training-time behaviour looks like, per reward version.

Recordings made during training use the deterministic policy (see the note in
behaviour_by_checkpoint.py), which stands still at every checkpoint of these
runs. This records the *sampled* policy instead -- how the network acts while
it is being trained -- for the first, middle and last checkpoint of the
plain-reward run and the last checkpoint of each other reward version, on
stage 1 with two fixed seeds. Nothing is chosen for how it looks: the outcome
is put in the file name after the fact.

    python pyro_pete_game/ml/ML_Findings/scripts/record_sampled_behaviour.py
Output: media/reward_versions/<run>_step<N>_seed<S>_<outcome>.mp4
Needs runs/<name>/checkpoints (git-ignored).
"""

import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

import torch                                                  # noqa: E402

from ml.policy import load_policy                             # noqa: E402
from ml.recording import record_episode                       # noqa: E402

OUT = os.path.join(BASE, "media", "reward_versions")
SEEDS = [1000, 1001]
JOBS = [("exp01_plain_s0", ["first", "mid", "last"]), ("exp02_abandon_s0", ["last"]),
        ("exp04_giveup200_s0", ["last"]), ("exp05_giveup200_timeout200_s0", ["last"]),
        ("exp07_giveup200_long_s0", ["last"]), ("exp06_plain_s2_continued", ["last"])]
LABEL = {"exp01_plain_s0": "v1 plain", "exp02_abandon_s0": "v2 abandon 100",
         "exp04_giveup200_s0": "v3 give-up 200", "exp05_giveup200_timeout200_s0": "v4 give-up+timeout 200",
         "exp07_giveup200_long_s0": "v3 give-up 200, 300k steps",
         "exp06_plain_s2_continued": "v1 plain seed 2, 400k steps"}


def main():
    os.makedirs(OUT, exist_ok=True)
    for run, picks in JOBS:
        ckpt_dir = os.path.join(ROOT, "runs", run, "checkpoints")
        if not os.path.isdir(ckpt_dir):
            print("skip (no checkpoints):", run)
            continue
        files = sorted(f for f in os.listdir(ckpt_dir) if f.endswith(".zip"))
        chosen = {"first": files[0], "mid": files[len(files) // 2], "last": files[-1]}
        for pick in picks:
            f = chosen[pick]
            step = int(re.search(r"step_(\d+)", f).group(1))
            policy = load_policy(os.path.join(ckpt_dir, f))
            policy.deterministic = False
            for seed in SEEDS:
                torch.manual_seed(seed)
                tmp = os.path.join(OUT, "_tmp.mp4")
                res = record_episode(run, 0, seed, tmp, policy=policy, speed=3.0, max_seconds=90,
                                     caption=f"{LABEL[run]}  |  step {step:,}  |  SAMPLED actions")
                name = f"{run}_step{step:07d}_seed{seed}_{res['outcome']}.mp4"
                shutil.move(res["video"], os.path.join(OUT, name))
                print(f"{name}: {res['outcome']}, {res['victims_out']}/{res['victims_total']} out, "
                      f"{res['seconds']}s", flush=True)


if __name__ == "__main__":
    main()
