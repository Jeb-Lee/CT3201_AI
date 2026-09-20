"""Figure for section 4.9 of IMITATION.md: where the networks stall, and what fixing it is worth.

Reads data/stall_analysis.csv and data/stall_counterfactual_{10,40,200}.csv (written by
stall_analysis.py) and writes figures/fig_stall.png.

    python pyro_pete_game/ml/ML_Findings/scripts/make_stall_figure.py
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
DATA, FIG = os.path.join(BASE, "data"), os.path.join(BASE, "figures")
COLOUR = {"v2": "#d98c3f", "v4": "#3f7fbf"}


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    rows = read("stall_analysis.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4))

    # left: share of episodes that stall, per stage
    width = 0.38
    for i, a in enumerate(("v2", "v4")):
        share = []
        for st in range(10):
            sub = [r for r in rows if r["agent"] == a and int(r["stage"]) == st]
            share.append(100 * sum(int(r["stalled"]) for r in sub) / len(sub))
        ax1.bar([s + (i - 0.5) * width for s in range(10)], share, width, label=a, color=COLOUR[a])
    ax1.axvline(6.5, color="grey", ls="--", lw=1)
    ax1.set_ylim(0, 70)
    ax1.text(6.6, 66, "never trained on", fontsize=8, color="grey")
    ax1.set_xticks(range(10))
    ax1.set_xticklabels([str(s + 1) for s in range(10)])
    ax1.set_xlabel("stage")
    ax1.set_ylabel("% of episodes that stall (A* = 0 on every stage)")
    ax1.set_title("Stalling by stage (30 episodes per stage)")
    ax1.legend()

    # right: success as trained vs with A* breaking each stall
    labels, values = ["as trained"], {"v2": [], "v4": []}
    for a in values:
        sub = [r for r in rows if r["agent"] == a]
        values[a].append(100 * sum(r["outcome"] == "evacuated" for r in sub) / len(sub))
    for n in (10, 40, 200):
        labels.append(f"A* breaks stalls\n({n} decisions)")
        fixed = read(f"stall_counterfactual_{n}.csv")
        for a in values:
            sub = [r for r in fixed if r["agent"] == a]
            values[a].append(100 * sum(r["outcome"] == "evacuated" for r in sub) / len(sub))
    astar = [r for r in rows if r["agent"] == "astar"]
    a_rate = 100 * sum(r["outcome"] == "evacuated" for r in astar) / len(astar)
    xs = range(len(labels))
    for i, a in enumerate(values):
        ax2.bar([x + (i - 0.5) * width for x in xs], values[a], width, label=a, color=COLOUR[a])
        for x, v in zip(xs, values[a]):
            ax2.text(x + (i - 0.5) * width, v + 0.4, f"{v:.0f}", ha="center", fontsize=8)
    ax2.axhline(a_rate, color="black", ls="--", lw=1)
    ax2.text(len(labels) - 0.5, a_rate + 0.5, f"A* {a_rate:.0f}%", ha="right", fontsize=8)
    ax2.set_ylim(70, 92)
    ax2.set_xticks(list(xs))
    ax2.set_xticklabels(labels, fontsize=8)
    ax2.set_ylabel("% of 300 episodes evacuated everyone")
    ax2.set_title("What removing the stalls is worth (upper bound: borrows A*)")
    ax2.legend(loc="lower right")

    fig.tight_layout()
    os.makedirs(FIG, exist_ok=True)
    out = os.path.join(FIG, "fig_stall.png")
    fig.savefig(out, dpi=140)
    print("wrote", out)


if __name__ == "__main__":
    main()
