"""Final test for the imitation-learned networks with a generous time cap (240 s).

The real game has no hard time limit (only a speed-bonus reference at 90 s and a fire that
reaches the exit after minutes). The experiments used a 90 s cap during training for speed,
and a cap penalises whichever agent is slower. This runs A* and the networks on the SAME
seeded episodes (seeds 90,000 + ...) with a 240 s cap, deterministic and sampled.

    python .../imitation_long_cap_test.py              # everything (A*, v1, v2, v3, v4)
    python .../imitation_long_cap_test.py v3 v4        # only these; merged into the existing csv

Writes data/imitation_240s.csv and data/imitation_240s.md.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

from ml import evaluation                                         # noqa: E402
from ml.report import read_csv                                    # noqa: E402

IMIT, DATA = os.path.join(BASE, "imitation"), os.path.join(BASE, "data")
CAP = 240.0
TRAINED, UNSEEN = list(range(0, 7)), [7, 8, 9]
MODELS = {"v1": "imit_a_v1_local_view", "v2": "imit_b_v2_route_hints",
          "v3": "imit_c_v3_memory", "v4": "imit_d_v4_trail"}
FIELDS = ["agent", "stage", "seed", "outcome", "victims_out", "victims_total", "victims_lost",
          "score", "damage", "seconds"]


def main():
    wanted = sys.argv[1:] or ["astar"] + list(MODELS)
    specs, label = [], {}
    if "astar" in wanted:
        specs.append("astar")
        label["astar"] = "astar"
    for k in [w for w in wanted if w in MODELS]:
        path = os.path.join(IMIT, MODELS[k], "final_model.zip")
        for prefix, mode in (("model", "deterministic"), ("sample", "sampled")):
            spec = f"{prefix}:{path}"
            specs.append(spec)
            label[spec] = f"{k} {mode}"
    print(f"{len(specs)} agents x 10 stages x 10 episodes, cap {CAP:.0f}s ...", flush=True)
    results = evaluation.evaluate(specs, list(range(10)), 10, base_seed=90_000, max_seconds=CAP, workers=8)
    for r in results:
        r["agent"] = label[r["agent"]]

    csv_path = os.path.join(DATA, "imitation_240s.csv")
    old = read_csv(csv_path) if os.path.isfile(csv_path) else []
    keep = [r for r in old if r["agent"] not in set(label.values())]
    rows = keep + results
    order = ["astar", "v1 deterministic", "v1 sampled", "v2 deterministic", "v2 sampled",
             "v3 deterministic", "v3 sampled", "v4 deterministic", "v4 sampled"]
    rows.sort(key=lambda r: (order.index(r["agent"]) if r["agent"] in order else 99, r["stage"], r["seed"]))
    os.makedirs(DATA, exist_ok=True)
    import csv
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in FIELDS})

    pct = lambda x: f"{100 * x:.0f}%"
    lines = [f"Time cap {CAP:.0f} s (the training-time final test used 90 s). Same seeded episodes for every agent.", "",
             "| agent | stages | n | evacuated (95% CI) | died | gave up | ran out of time | occupants led out | median seconds |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name in order:
        for title, stages in (("trained 1-7", TRAINED), ("unseen 8-10", UNSEEN), ("all ten", list(range(10)))):
            sub = [r for r in rows if r["agent"] == name and r["stage"] in stages]
            if not sub:
                continue
            s = evaluation.summarise_group(sub)
            lo, hi = s["evacuated_ci"]
            secs = sorted(r["seconds"] for r in sub)
            lines.append(f"| {name} | {title} | {s['n']} | {pct(s['evacuated'])} ({pct(lo)}-{pct(hi)}) | "
                         f"{pct(s['died'])} | {pct(s['gave_up'])} | {pct(s['timeout'])} | "
                         f"{pct(s['occupants_out'])} | {secs[len(secs) // 2]:.0f} |")
    a = [r for r in rows if r["agent"] == "astar"]
    over = sum(1 for r in a if r["outcome"] == "evacuated" and r["seconds"] > 90)
    lines += ["", f"A* episodes that evacuated but took longer than 90 s: {over} of "
                  f"{sum(1 for r in a if r['outcome'] == 'evacuated')} "
                  f"(longest {max(r['seconds'] for r in a if r['outcome'] == 'evacuated'):.0f} s)."]
    with open(os.path.join(DATA, "imitation_240s.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
