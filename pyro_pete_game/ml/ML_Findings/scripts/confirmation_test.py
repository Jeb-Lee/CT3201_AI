"""Confirmation on fresh episodes: A*, the v2 clone and the v4 clone on seeds nobody has used.

Four network variants were compared on one 100-episode test set (seeds 90,000+); the more
variants tried on a test set, the more the best-looking one is flattered by chance. This
re-tests the final candidate on 200 fresh episodes (20 per stage, seeds 190,000+). The
prediction (PREDICTIONS.md, P10) was written before this was run.

    python pyro_pete_game/ml/ML_Findings/scripts/confirmation_test.py
Writes data/confirmation_240s.csv and data/confirmation_240s.md.
"""

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

from ml import evaluation                                         # noqa: E402

IMIT, DATA = os.path.join(BASE, "imitation"), os.path.join(BASE, "data")
TRAINED, UNSEEN = list(range(0, 7)), [7, 8, 9]


def main():
    v2 = os.path.join(IMIT, "imit_b_v2_route_hints", "final_model.zip")
    v4 = os.path.join(IMIT, "imit_d_v4_trail", "final_model.zip")
    specs = ["astar", f"model:{v2}", f"model:{v4}", f"sample:{v4}"]
    label = {specs[0]: "astar", specs[1]: "v2 deterministic", specs[2]: "v4 deterministic", specs[3]: "v4 sampled"}
    results = evaluation.evaluate(specs, list(range(10)), 20, base_seed=190_000, max_seconds=240.0, workers=8)
    for r in results:
        r["agent"] = label[r["agent"]]
    fields = ["agent", "stage", "seed", "outcome", "victims_out", "victims_total", "score", "seconds"]
    with open(os.path.join(DATA, "confirmation_240s.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow({k: r[k] for k in fields})
    pct = lambda x: f"{100 * x:.0f}%"
    lines = ["Fresh episodes (seeds 190,000+), 20 per stage, 240 s cap. The earlier 100-episode test gave: "
             "A* 91% (84-95), v2 80% (71-87), v4 87% (79-92).", "",
             "| agent | stages | n | evacuated (95% CI) | died | gave up | occupants led out | median seconds |",
             "|---|---|---|---|---|---|---|---|"]
    for name in ("astar", "v2 deterministic", "v4 deterministic", "v4 sampled"):
        for title, stages in (("trained 1-7", TRAINED), ("unseen 8-10", UNSEEN), ("all ten", list(range(10)))):
            sub = [r for r in results if r["agent"] == name and r["stage"] in stages]
            s = evaluation.summarise_group(sub)
            lo, hi = s["evacuated_ci"]
            secs = sorted(r["seconds"] for r in sub)
            lines.append(f"| {name} | {title} | {s['n']} | {pct(s['evacuated'])} ({pct(lo)}-{pct(hi)}) | {pct(s['died'])} | "
                         f"{pct(s['gave_up'])} | {pct(s['occupants_out'])} | {secs[len(secs) // 2]:.0f} |")
    won = lambda a: {(r["stage"], r["seed"]): r["outcome"] == "evacuated" for r in results if r["agent"] == a}
    lines += ["", "Paired on the same 200 episodes (evacuated everyone):", "", "| first | second | both | only first | only second |",
              "|---|---|---|---|---|"]
    for a, b in (("v2 deterministic", "v4 deterministic"), ("astar", "v4 deterministic"), ("astar", "v2 deterministic")):
        wa, wb = won(a), won(b)
        keys = sorted(set(wa) & set(wb))
        lines.append(f"| {a} | {b} | {sum(wa[k] and wb[k] for k in keys)} | {sum(wa[k] and not wb[k] for k in keys)} | "
                     f"{sum(wb[k] and not wa[k] for k in keys)} |")
    with open(os.path.join(DATA, "confirmation_240s.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
