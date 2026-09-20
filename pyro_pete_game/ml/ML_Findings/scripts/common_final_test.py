"""Every run's final model on the same fresh episodes, next to A*.

Each training run reports its own final test, but with different sizes and
stages. This puts all final models on identical ground: stages 1-4, 10
episodes per stage, seeds nobody trained or validated on (90,000 + ...), each
model twice -- the deterministic policy (always the most likely action; what
the game would use) and the sampled policy (what training acts like) -- and A*
on the very same episodes.

    python pyro_pete_game/ml/ML_Findings/scripts/common_final_test.py
Writes data/common_final_test.csv and data/common_final_test.md.
"""

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

from ml import evaluation                                         # noqa: E402

EXP, DATA = os.path.join(BASE, "experiments"), os.path.join(BASE, "data")
STAGES = [0, 1, 2, 3]
EPISODES = 10
SEED_BASE = 90_000
MAX_SECONDS = 90.0


def main():
    runs = sorted(n for n in os.listdir(EXP)
                  if os.path.isfile(os.path.join(EXP, n, "final_model.zip")))
    specs, label, order = ["astar"], {"astar": "astar"}, ["astar"]
    for n in runs:
        path = os.path.join(EXP, n, "final_model.zip")
        for prefix, mode in (("model", "deterministic"), ("sample", "sampled")):
            spec = f"{prefix}:{path}"
            specs.append(spec)
            label[spec] = f"{n} ({mode})"
            order.append(label[spec])
    print(f"{len(runs)} models x 2 modes x {len(STAGES)} stages x {EPISODES} episodes ...", flush=True)
    results = evaluation.evaluate(specs, STAGES, EPISODES, base_seed=SEED_BASE,
                                  max_seconds=MAX_SECONDS, workers=6)
    for r in results:
        r["agent"] = label[r["agent"]]
    os.makedirs(DATA, exist_ok=True)
    evaluation.write_csv(results, os.path.join(DATA, "common_final_test.csv"))

    pct = lambda x: f"{100 * x:.0f}%"
    lines = ["| agent | episodes | evacuated (95% CI) | died | gave up | timed out | occupants led out | mean score |",
             "|---|---|---|---|---|---|---|---|"]
    for name in order:
        s = evaluation.summarise_group([r for r in results if r["agent"] == name])
        lo, hi = s["evacuated_ci"]
        lines.append(f"| {name} | {s['n']} | {pct(s['evacuated'])} ({pct(lo)}-{pct(hi)}) | {pct(s['died'])} | "
                     f"{pct(s['gave_up'])} | {pct(s['timeout'])} | {pct(s['occupants_out'])} | {s['score']:.0f} |")
    text = "\n".join(lines)
    with open(os.path.join(DATA, "common_final_test.md"), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
