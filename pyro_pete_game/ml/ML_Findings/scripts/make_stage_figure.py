"""Figure for section 4.12 of IMITATION.md: A*, v4 and v5 stage by stage (data/stage_report.csv).

Left: share of episodes that evacuated everyone. Middle: mean clear time of the wins.
Right: share of the stage's floor tiles viewed when the agent gave up (stages with no give-up
have no bar).

    python pyro_pete_game/ml/ML_Findings/scripts/make_stage_figure.py
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
COLOUR = {"A*": "#444444", "v4": "#3f7fbf", "v5": "#d98c3f"}


def main():
    with open(os.path.join(BASE, "data", "stage_report.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    stages = list(range(1, 11))
    width = 0.27
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, title, ylabel in zip(
            axes, ("Evacuated everyone", "Clear time of the wins", "Map viewed when it gave up"),
            ("% of the 30 episodes per stage", "seconds", "% of the stage's floor tiles")):
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("stage (8-10 never trained on)")
        ax.set_xticks(stages)
        ax.axvline(7.5, color="grey", ls="--", lw=1)
    for i, agent in enumerate(("A*", "v4", "v5")):
        xs = [s + (i - 1) * width for s in stages]
        evac, time, view = [], [], []
        for s in stages:
            g = [r for r in rows if r["agent"] == agent and int(r["stage"]) == s]
            wins = [r for r in g if r["outcome"] == "evacuated"]
            gu = [r for r in g if r["outcome"] == "gave_up"]
            evac.append(100 * len(wins) / len(g))
            time.append(sum(float(r["seconds"]) for r in wins) / len(wins) if wins else 0)
            view.append(sum(float(r["viewed_pct"]) for r in gu) / len(gu) if gu else 0)
        axes[0].bar(xs, evac, width, label=agent, color=COLOUR[agent])
        axes[1].bar(xs, time, width, label=agent, color=COLOUR[agent])
        axes[2].bar(xs, view, width, label=agent, color=COLOUR[agent])
    axes[0].set_ylim(40, 112)
    axes[2].set_ylim(50, 100)
    axes[0].legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0), frameon=False)
    fig.tight_layout()
    out = os.path.join(BASE, "figures", "fig_stage_report.png")
    fig.savefig(out, dpi=140)
    print("wrote", out)


if __name__ == "__main__":
    main()
