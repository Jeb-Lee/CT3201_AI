"""One row per training run: the reward it used, what it ended up doing, and a
check that the measured price of each ending predicts its logged return.

    python pyro_pete_game/ml/ML_Findings/scripts/summarise_runs.py

Reads experiments/*/ (see collect_runs.py) and data/reward_accounting.csv.
Writes data/run_summary.csv and data/run_summary.md.

The consistency check: a run's logged mean return over its last 100 episodes
should be close to  sum(share of each ending x price of that ending),  where the
prices come from the independent reward-accounting measurement. If it is, the
price list really is what the optimiser was responding to.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "..", "..")))
from ml.report import read_csv                                   # noqa: E402
from make_figures import price_table                             # noqa: E402

EXP, DATA = os.path.join(BASE, "experiments"), os.path.join(BASE, "data")


def version_of(cfg):
    a, g, t = cfg["abandon_penalty"], cfg["give_up_penalty"], cfg["timeout_penalty"]
    if g and t:
        return "v4 give-up+timeout"
    if g:
        return "v3 give-up"
    if a:
        return "v2 abandon"
    return "v1 plain"


def prices_for(cfg, table):
    versions, _ = table
    lookup = {v[0]: v[1] for v in versions}
    key = {"v1 plain": "v1 plain", "v2 abandon": "v2 abandon 100",
           "v3 give-up": "v3 give-up 200", "v4 give-up+timeout": "v4 give-up+timeout 200"}
    return lookup[key[version_of(cfg)]]


def main():
    table = price_table()
    rows = []
    for name in sorted(os.listdir(EXP)):
        p = os.path.join(EXP, name)
        if not os.path.isfile(os.path.join(p, "epochs.csv")):
            continue
        cfg = json.load(open(os.path.join(p, "config.json"), encoding="utf-8"))
        ep = read_csv(os.path.join(p, "epochs.csv"))
        last = ep[-1]
        price = prices_for(cfg, table)
        implied = sum((last[k] or 0) * price[v] for k, v in
                      (("died", "died"), ("gave_up", "gave_up"), ("timeout", "timeout"),
                       ("train_accuracy", "evac")))
        ev = [r for r in read_csv(os.path.join(p, "evaluations.csv")) if r["agent"] == "model"]
        rows.append(dict(
            run=name, version=version_of(cfg), seed=cfg["seed"], steps=last["timesteps"],
            epochs=last["epoch"], died=last["died"], gave_up=last["gave_up"],
            timeout=last["timeout"], train_accuracy=last["train_accuracy"],
            occupants_out=last["occupants_out"], max_train_accuracy=max((r["train_accuracy"] or 0) for r in ep),
            max_occupants_out=max((r["occupants_out"] or 0) for r in ep),
            entropy=last["entropy"], logged_return=last["reward"], implied_return=round(implied, 1),
            val_accuracy_max=max((r["accuracy"] for r in ev), default=None)))
    if not rows:
        print("no runs collected yet")
        return
    with open(os.path.join(DATA, "run_summary.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    pct = lambda x: "-" if x is None else f"{100 * x:.0f}%"
    lines = ["| run | reward version | seed | steps | died | gave up | timed out | evacuated | occupants led out | entropy | logged return | implied by price list |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['run']} | {r['version']} | {r['seed']} | {r['steps']:,} | {pct(r['died'])} | "
                     f"{pct(r['gave_up'])} | {pct(r['timeout'])} | {pct(r['train_accuracy'])} | "
                     f"{100 * r['occupants_out']:.1f}% | {r['entropy']:.2f} | {r['logged_return']:.0f} | "
                     f"{r['implied_return']:.0f} |")
    with open(os.path.join(DATA, "run_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
