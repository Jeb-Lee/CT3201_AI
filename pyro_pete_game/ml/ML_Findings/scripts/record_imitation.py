"""Screen-record the imitation-learned agents playing, with A* on the same episode.

For each chosen (stage, seed) it records, on the identical episode:
    A*                     the hand-written planner
    v2 cloned              the network with A*-equivalent information (deterministic
                           policy: what the game would use)
    v1 cloned              the network with only a local window (for the contrast)
Stages include ones the networks never trained on. Nothing is chosen for how it
looks: stages and seeds are fixed here, the outcome goes in the file name. The cap is 240 s
(the real game has no hard limit; a 90 s cap would cut off slower agents).

    python pyro_pete_game/ml/ML_Findings/scripts/record_imitation.py
Output: media/imitation/<stage>_<seed>_<agent>_<outcome>.mp4   (needs runs/imit_a and runs/imit_b)
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

from ml.policy import load_policy                             # noqa: E402
from ml.recording import record_episode                       # noqa: E402

OUT = os.path.join(BASE, "media", "imitation")
# 1-based stage, seed. Stages 8-10 were never trained on.
EPISODES = [(1, 1000), (3, 1000), (5, 1000), (7, 1001), (8, 1000), (9, 1000), (10, 1001)]
AGENTS = [("astar", None, "A*"),
          ("v2", os.path.join(ROOT, "runs", "imit_b", "final_model.zip"), "cloned, A*-equivalent information (v2)"),
          ("v1", os.path.join(ROOT, "runs", "imit_a", "final_model.zip"), "cloned, local view only (v1)"),
          ("v3", os.path.join(ROOT, "runs", "imit_c", "final_model.zip"), "cloned, A*'s information + short memory (v3)"),
          ("v4", os.path.join(ROOT, "runs", "imit_d", "final_model.zip"), "cloned, A*'s information + full trail (v4)"),
          ("v5", os.path.join(ROOT, "runs", "imit_e", "final_model.zip"), "cloned from the far-side-first searcher + full trail (v5)")]


def main():
    os.makedirs(OUT, exist_ok=True)
    loaded = {}
    only = sys.argv[1:]                      # e.g. `record_imitation.py v3 v4` records just those
    for stage, seed in EPISODES:
        for key, path, label in AGENTS:
            if only and key not in only:
                continue
            if path and not os.path.isfile(path):
                print("skip (no model):", key)
                continue
            policy = None
            if path:
                loaded.setdefault(key, load_policy(path))
                policy = loaded[key]
            unseen = " (UNSEEN stage)" if stage >= 8 else ""
            tmp = os.path.join(OUT, "_tmp.mp4")
            res = record_episode(key, stage - 1, seed, tmp, policy=policy, speed=4.0, max_seconds=240,
                                 caption=f"{label}{unseen}")
            name = f"stage{stage:02d}_seed{seed}_{key}_{res['outcome']}.mp4"
            shutil.move(res["video"], os.path.join(OUT, name))
            print(f"{name}: {res['outcome']}, {res['victims_out']}/{res['victims_total']} out, {res['seconds']}s",
                  flush=True)


if __name__ == "__main__":
    main()
