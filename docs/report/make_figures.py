"""Figures for the learned-agent section of the IEEE report (revision 2).

Draws the figures at report size (7.3 in wide, 6-7 pt text) into docs/report/figures/, so the report
folder is self-contained and nothing has to be shrunk after the fact:

  fig_architecture.png        the network the game runs (drawn here)
  fig_rl_outcomes.png         how RL episodes ended, per reward version (data/run_summary.csv)
  fig_epoch_accuracy_all.png  epoch versus action-match accuracy for v1-v5 (imitation/*/epochs*.csv)
  fig_pooled_compact.png      A*, v2, v4 on 300 pooled episodes (Wilson intervals computed here)
  fig_stage_compact.png       A*, v4, v5 stage by stage on 300 fresh episodes (data/stage_report.csv)

    python docs/report/make_figures.py
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
FINDINGS = os.path.abspath(os.path.join(HERE, "..", "..", "pyro_pete_game", "ml", "ML_Findings"))

INK, BLUE, ORANGE, GREY, GREEN, RED = "#1b2333", "#3f7fbf", "#d98c3f", "#8b93a3", "#3aa06b", "#d9534f"


def box(ax, x, y, w, h, text, fc, ec=INK, size=7, weight="normal", color=INK, style="round,pad=0.02,rounding_size=0.06"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, weight=weight, color=color)


def arrow(ax, x0, y0, x1, y1, ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=9, lw=1.0, color=INK, ls=ls))


def architecture():
    fig, ax = plt.subplots(figsize=(7.3, 3.0))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 7.6)
    ax.axis("off")

    ax.text(2.85, 7.25, "Observation: 1,264 numbers (v4, v5)", ha="center", fontsize=7.4, weight="bold")
    parts = [("11 x 11 window x 9 channels (1089)", "#dfe7f3", "v1"), ("13 scalar features", "#dfe7f3", "v1"),
             ("24 route hints (A*'s own inputs)", "#cfe3d4", "v2"), ("17 memory: last move, last 4 tiles", "#f3e3c8", "v3"),
             ("121 nearby-tile visit counts", "#f3e3c8", "v4")]
    y = 6.75
    for text, fc, tag in parts:
        ax.add_patch(FancyBboxPatch((0.1, y - 0.85), 5.5, 0.8, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=INK, lw=0.9))
        ax.text(0.35, y - 0.45, text, ha="left", va="center", fontsize=6.3, color=INK)
        ax.text(5.35, y - 0.45, tag, ha="right", va="center", fontsize=6.3, color=GREY, weight="bold")
        y -= 1.0
    ax.text(2.85, 0.95, "each version adds one block (v1 = first two rows)", ha="center", fontsize=6.0, style="italic", color=GREY)

    ax.text(10.9, 7.25, "Policy network (what the game runs)", ha="center", fontsize=7.4, weight="bold")
    xs = [6.5, 9.0, 11.5]
    for x, lab in zip(xs, ["Linear\n1264 -> 256\ntanh", "Linear\n256 -> 256\ntanh", "Linear\n256 -> 5\naction logits"]):
        box(ax, x, 4.2, 2.2, 2.3, lab, "#dfe7f3", size=6.5)
    arrow(ax, 5.65, 5.35, 6.45, 5.35)
    arrow(ax, 8.72, 5.35, 8.98, 5.35)
    arrow(ax, 11.22, 5.35, 11.48, 5.35)
    box(ax, 14.3, 4.5, 2.6, 1.7, "action mask\nillegal move -> -inf", "#f6d9d6", size=6.2)
    arrow(ax, 13.72, 5.35, 14.28, 5.35)
    box(ax, 17.4, 4.5, 2.4, 1.7, "argmax\n(in the game)", "#d6ecdf", size=6.4)
    arrow(ax, 16.92, 5.35, 17.38, 5.35)
    ax.text(18.6, 4.3, "stay / up / down\n/ left / right", ha="center", va="top", fontsize=5.9, color=GREY)

    ax.text(6.5, 3.5, "Value network (reinforcement learning only; not used by cloning or by the game)", ha="left",
            fontsize=6.3, style="italic", color=GREY)
    for x, lab in zip(xs, ["Linear\n1264 -> 256\ntanh", "Linear\n256 -> 256\ntanh", "Linear\n256 -> 1\nvalue"]):
        box(ax, x, 1.35, 2.2, 1.8, lab, "#f0f0f0", ec=GREY, size=5.8, color="#555555")
    arrow(ax, 5.65, 4.4, 6.45, 2.4, ls="--")
    arrow(ax, 8.72, 2.25, 8.98, 2.25, ls="--")
    arrow(ax, 11.22, 2.25, 11.48, 2.25, ls="--")

    ax.text(10.9, 0.35, "390,917 parameters on the acting path, 780,806 with the value network; one flat vector in, five moves out",
            ha="center", fontsize=6.2, color=INK)
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(FIG, "fig_architecture.png"), dpi=220)
    plt.close(fig)


def rl_outcomes():
    with open(os.path.join(FINDINGS, "data", "run_summary.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    groups = [("v1 plain\nreward", "exp01_"), ("v2 + abandon\npenalty", "exp02_"), ("v3 + give-up\npenalty", "exp04_"),
              ("v4 + give-up &\ntimeout penalty", "exp05_")]
    fig, ax = plt.subplots(figsize=(3.45, 2.7))
    bottoms = [0] * len(groups)
    series = [("died", "died", RED), ("gave_up", "stood still", "#eeae4a"), ("timeout", "kept moving", BLUE)]
    means = []
    for label, prefix in groups:
        sub = [r for r in rows if r["run"].startswith(prefix)]
        means.append({k: 100 * sum(float(r[k]) for r in sub) / len(sub) for k in ("died", "gave_up", "timeout")})
    for key, name, colour in series:
        vals = [m[key] for m in means]
        ax.bar(range(len(groups)), vals, 0.62, bottom=bottoms, color=colour, label=name)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([g[0] for g in groups], fontsize=6)
    ax.set_ylabel("% of the last 100 episodes", fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylim(0, 128)
    ax.set_yticks([0, 25, 50, 75, 100])
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=c, label=n) for _k, n, c in series] + [Patch(color=GREEN, label="evacuated: 0% in every run")],
              fontsize=5.8, ncol=2, loc="upper center", frameon=False)
    ax.set_title("How reinforcement-learning episodes ended (100k steps)", fontsize=7.2)
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(FIG, "fig_rl_outcomes.png"), dpi=220)
    plt.close(fig)


def epoch_accuracy():
    runs = [("v1", "imit_a_v1_local_view", GREY), ("v2", "imit_b_v2_route_hints", BLUE), ("v3", "imit_c_v3_memory", GREEN),
            ("v4", "imit_d_v4_trail", ORANGE), ("v5", "imit_e_v5_far_side", RED)]
    fig, axes = plt.subplots(1, 2, figsize=(7.3, 2.6), sharey=True)
    for name, folder, colour in runs:
        d = os.path.join(FINDINGS, "imitation", folder)
        xs, seen, unseen = [], [], []
        files = ["epochs.csv"] + ["epochs_round%d.csv" % k for k in range(1, 5)]
        for f in files:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    xs.append(len(xs) + 1)          # the round logs restart at 1: number epochs cumulatively
                    seen.append(100 * float(r["val_seen_acc"]))
                    unseen.append(100 * float(r["val_unseen_acc"]))
        axes[0].plot(xs, seen, color=colour, lw=1.3, label=name)
        axes[1].plot(xs, unseen, color=colour, lw=1.3, label=name)
    for ax, title in zip(axes, ("held-out episodes on the training stages (1-7)", "stages never trained on (8-10)")):
        for x in (30, 42, 54, 66):
            ax.axvline(x + 0.5, color="#bbbbbb", lw=0.7, ls=":")
        ax.set_title(title, fontsize=7.2)
        ax.set_xlabel("epoch (dotted lines: a DAgger round starts)", fontsize=6.6)
        ax.tick_params(labelsize=6.5)
        ax.grid(alpha=0.25)
        ax.set_ylim(70, 100.5)
    axes[0].set_ylabel("action-match accuracy (%)\n(picks the move A* picks)", fontsize=6.8)
    axes[1].legend(fontsize=6.4, ncol=5, loc="lower right", frameon=False)
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(FIG, "fig_epoch_accuracy_all.png"), dpi=220)
    plt.close(fig)


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return c - h, c + h


def pooled_compact():
    # episodes fully evacuated out of (210 trained-stage, 90 unseen-stage, 300 all) on sets 1 and 2 pooled
    counts = {"A*": (183, 78), "v2": (173, 57), "v4": (176, 64)}
    colours = {"A*": INK, "v2": BLUE, "v4": ORANGE}
    groups = [("trained stages 1-7 (210)", 0, 210), ("unseen stages 8-10 (90)", 1, 90), ("all ten (300)", None, 300)]
    fig, ax = plt.subplots(figsize=(3.6, 2.5))
    width = 0.26
    for i, (name, (tr, un)) in enumerate(counts.items()):
        xs, vals, lo, hi = [], [], [], []
        for g, (label, idx, n) in enumerate(groups):
            k = tr + un if idx is None else (tr, un)[idx]
            l, h = wilson(k, n)
            xs.append(g + (i - 1) * width)
            vals.append(100 * k / n)
            lo.append(100 * k / n - 100 * l)
            hi.append(100 * h - 100 * k / n)
        ax.bar(xs, vals, width, yerr=[lo, hi], color=colours[name], label=name, error_kw=dict(lw=0.7, capsize=1.5))
        for x, v in zip(xs, vals):
            ax.text(x, 3, "%.0f" % v, ha="center", fontsize=5.6, color="white", weight="bold")
    ax.set_xticks(range(3))
    ax.set_xticklabels([g[0] for g in groups], fontsize=5.6)
    ax.set_ylim(0, 105)
    ax.set_ylabel("% of episodes fully evacuated", fontsize=6.4)
    ax.tick_params(axis="y", labelsize=6)
    ax.legend(fontsize=5.8, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False)
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(FIG, "fig_pooled_compact.png"), dpi=220)
    plt.close(fig)


def stage_compact():
    with open(os.path.join(FINDINGS, "data", "stage_report.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    colour = {"A*": INK, "v4": BLUE, "v5": ORANGE}
    stages = list(range(1, 11))
    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.3))
    titles = ("evacuated everyone (%)", "clear time of the wins (s)", "map viewed when it gave up (%)")
    for i, agent in enumerate(("A*", "v4", "v5")):
        ev, tm, vw = [], [], []
        for s in stages:
            g = [r for r in rows if r["agent"] == agent and int(r["stage"]) == s]
            wins = [r for r in g if r["outcome"] == "evacuated"]
            gu = [r for r in g if r["outcome"] == "gave_up"]
            ev.append(100 * len(wins) / len(g))
            tm.append(sum(float(r["seconds"]) for r in wins) / len(wins) if wins else 0)
            vw.append(sum(float(r["viewed_pct"]) for r in gu) / len(gu) if gu else 0)
        xs = [s + (i - 1) * 0.27 for s in stages]
        for ax, vals in zip(axes, (ev, tm, vw)):
            ax.bar(xs, vals, 0.27, color=colour[agent], label=agent)
    for ax, title in zip(axes, titles):
        ax.set_title(title, fontsize=6.8)
        ax.set_xticks(stages)
        ax.tick_params(labelsize=5.8)
        ax.set_xlabel("stage (8-10 unseen)", fontsize=6)
        ax.axvline(7.5, color="grey", ls="--", lw=0.7)
    axes[0].set_ylim(40, 112)
    axes[2].set_ylim(50, 100)
    axes[0].legend(fontsize=6, ncol=3, loc="upper center", frameon=False)
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(FIG, "fig_stage_compact.png"), dpi=220)
    plt.close(fig)


def main():
    os.makedirs(FIG, exist_ok=True)
    for old in ("fig_imitation_pooled.png", "fig_stage_report.png", "fig_stall.png"):
        path = os.path.join(FIG, old)
        if os.path.isfile(path):
            os.remove(path)               # earlier copies, drawn for a larger page
    architecture()
    rl_outcomes()
    epoch_accuracy()
    pooled_compact()
    stage_compact()
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
