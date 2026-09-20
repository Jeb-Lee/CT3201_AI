"""Pool the two independent 240 s test sets into one 300-episode comparison.

Set 1: 100 episodes (10 per stage, seeds 90,000+), on which four network variants were compared.
Set 2: 200 fresh episodes (20 per stage, seeds 190,000+), the confirmation test.
Only agents present in BOTH sets are pooled (A*, v2, v4). Writes data/pooled_300.md.

    python pyro_pete_game/ml/ML_Findings/scripts/pooled_summary.py
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "..", "..")))
from ml.evaluation import wilson                                  # noqa: E402
from ml.report import read_csv                                    # noqa: E402

DATA = os.path.join(BASE, "data")
TRAINED, UNSEEN = list(range(0, 7)), [7, 8, 9]


def sign_p(a, b):
    """Two-sided exact sign test on the discordant pairs."""
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    set1 = read_csv(os.path.join(DATA, "imitation_240s.csv"))
    set2 = read_csv(os.path.join(DATA, "confirmation_240s.csv"))
    names = ["astar", "v2 deterministic", "v4 deterministic", "v4 sampled"]
    rows = {n: [dict(r, _set=1) for r in set1 if r["agent"] == n] + [dict(r, _set=2) for r in set2 if r["agent"] == n]
            for n in names}
    lines = ["Two independent 240 s test sets pooled: 100 episodes (seeds 90,000+) + 200 fresh episodes "
             "(seeds 190,000+) = 300 per agent.", "",
             "| agent | stages | n | evacuated everyone (95% CI) | died | gave up | occupants led out |",
             "|---|---|---|---|---|---|---|"]
    pct = lambda x: f"{100 * x:.0f}%"
    for n in names:
        for title, stages in (("trained 1-7", TRAINED), ("unseen 8-10", UNSEEN), ("all ten", list(range(10)))):
            sub = [r for r in rows[n] if r["stage"] in stages]
            k = sum(r["outcome"] == "evacuated" for r in sub)
            lo, hi = wilson(k, len(sub))
            died = sum(r["outcome"] == "died" for r in sub) / len(sub)
            gave = sum(r["outcome"] == "gave_up" for r in sub) / len(sub)
            led = sum(r["victims_out"] / r["victims_total"] for r in sub) / len(sub)
            lines.append(f"| {n} | {title} | {len(sub)} | {pct(k / len(sub))} ({pct(lo)}-{pct(hi)}) | {pct(died)} | "
                         f"{pct(gave)} | {pct(led)} |")
    won = lambda n: {(r["_set"], r["stage"], r["seed"]): r["outcome"] == "evacuated" for r in rows[n]}
    lines += ["", "Paired on the same 300 episodes (evacuated everyone; exact sign test on the episodes only one won):", "",
              "| first | second | both | only first | only second | p |", "|---|---|---|---|---|---|"]
    for a, b in (("v2 deterministic", "v4 deterministic"), ("astar", "v4 deterministic"), ("astar", "v2 deterministic")):
        wa, wb = won(a), won(b)
        keys = sorted(set(wa) & set(wb))
        both = sum(wa[k] and wb[k] for k in keys)
        oa = sum(wa[k] and not wb[k] for k in keys)
        ob = sum(wb[k] and not wa[k] for k in keys)
        lines.append(f"| {a} | {b} | {both} | {oa} | {ob} | {sign_p(oa, ob):.4f} |")
    with open(os.path.join(DATA, "pooled_300.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
