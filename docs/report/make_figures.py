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


# ---- data figures, drawn in one paper style that matches the diagrams --------------------------
# One colour per model in every figure (validated with the dataviz palette checker, light mode):
# A* violet, v2 blue, v4 orange, v5 aqua. v1 and v3 are neutral greys told apart by dash and
# position, because no five hues stay distinguishable when all five lines overlap.
AGENT = {"A*": "#4a3aa7", "v1": "#8b93a3", "v2": "#2a78d6", "v3": "#5b6472", "v4": "#eb6834", "v5": "#1baf7a"}
AGENT_DASH = {"v1": "-", "v3": (0, (3, 1.6))}
OUTCOME = {"died": "#e34948", "stood still": "#eda100", "kept moving": "#008300"}   # validated as a stack
TEXT2, RULE, GRID, UNSEEN = "#52514e", "#b9bcc2", "#ebebeb", "#f3f1ec"


def paper_axes(ax, ylabel=None, grid=True):
    """Recessive frame: no top/right spines, light rule, light horizontal grid, small grey ticks."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(RULE)
        ax.spines[side].set_linewidth(0.7)
    ax.tick_params(colors=TEXT2, labelsize=6.2, length=2.5, width=0.6)
    if grid:
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=6.6, color=INK)


def panel(ax, letter, text):
    ax.text(0.0, 1.035, "(%s)  %s" % (letter, text), transform=ax.transAxes, fontsize=6.8, color=INK,
            ha="left", va="bottom")


def unseen_band(ax, first=7.5, last=10.5):
    ax.axvspan(first, last, color=UNSEEN, zorder=0, lw=0)


def legend_above(ax, handles, ncol, y=1.13):
    ax.legend(handles=handles, fontsize=6.2, ncol=ncol, frameon=False, loc="lower left",
              bbox_to_anchor=(0.0, y), handlelength=1.6, columnspacing=1.2, borderaxespad=0)


def rl_outcomes():
    from matplotlib.patches import Patch
    with open(os.path.join(FINDINGS, "data", "run_summary.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    groups = [("plain\nscore", "exp01_"), ("+ abandon\npenalty", "exp02_"), ("+ give-up\npenalty", "exp04_"),
              ("+ give-up &\ntimeout", "exp05_")]
    series = [("died", "died"), ("gave_up", "stood still"), ("timeout", "kept moving")]
    means = []
    for _label, prefix in groups:
        sub = [r for r in rows if r["run"].startswith(prefix)]
        means.append({k: 100 * sum(float(r[k]) for r in sub) / len(sub) for k in ("died", "gave_up", "timeout")})
    fig, ax = plt.subplots(figsize=(3.3, 2.45))
    bottoms = [0.0] * len(groups)
    for key, name in series:
        vals = [m[key] for m in means]
        ax.bar(range(len(groups)), vals, 0.6, bottom=bottoms, color=OUTCOME[name], edgecolor="white", linewidth=0.8)
        for x, (b, v) in enumerate(zip(bottoms, vals)):
            if v >= 9:                           # values on the marks: relief for the lighter yellow
                ax.text(x, b + v / 2, "%.0f" % v, ha="center", va="center", fontsize=5.8,
                        color="white" if name != "stood still" else INK)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    paper_axes(ax, "% of the last 100 episodes")
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([g[0] for g in groups], fontsize=6)
    ax.set_xlabel("reward", fontsize=6.6, color=INK)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    legend_above(ax, [Patch(color=OUTCOME[n], label=n) for _k, n in series], ncol=3, y=1.03)
    fig.tight_layout(pad=0.35)
    fig.savefig(os.path.join(FIG, "fig_rl_outcomes.png"), dpi=240)
    plt.close(fig)


def epoch_accuracy():
    from matplotlib.lines import Line2D
    runs = [("v1", "imit_a_v1_local_view"), ("v2", "imit_b_v2_route_hints"), ("v3", "imit_c_v3_memory"),
            ("v4", "imit_d_v4_trail"), ("v5", "imit_e_v5_far_side")]
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.35), sharey=True)
    for name, folder in runs:
        d = os.path.join(FINDINGS, "imitation", folder)
        xs, seen, unseen = [], [], []
        for f in ["epochs.csv"] + ["epochs_round%d.csv" % k for k in range(1, 5)]:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    xs.append(len(xs) + 1)          # the round logs restart at 1: number epochs cumulatively
                    seen.append(100 * float(r["val_seen_acc"]))
                    unseen.append(100 * float(r["val_unseen_acc"]))
        style = dict(color=AGENT[name], lw=1.1 if name in AGENT_DASH else 1.3, ls=AGENT_DASH.get(name, "-"))
        axes[0].plot(xs, seen, **style)
        axes[1].plot(xs, unseen, **style)
        if name == "v1":                             # far from the rest: label it where it is
            for ax, ys in zip(axes, (seen, unseen)):
                ax.text(xs[-1] + 1, ys[-1], "v1", fontsize=6, color=TEXT2, va="center")
    for ax, letter, text in zip(axes, "ab", ("held-out episodes on the training stages 1–7",
                                             "stages never trained on (8–10)")):
        paper_axes(ax, None)
        for x in (30, 42, 54, 66):
            ax.axvline(x + 0.5, color=RULE, lw=0.6, ls=(0, (1, 2)))
        ax.text(48.5, 70.8, "DAgger rounds 1–4 begin at the dotted lines", fontsize=5.6, color=TEXT2, ha="center")
        ax.set_xlabel("epoch", fontsize=6.6, color=INK)
        ax.set_ylim(70, 100.5)
        ax.set_xlim(0, 84)
        panel(ax, letter, text)
    axes[0].set_ylabel("action-match accuracy (%)", fontsize=6.6, color=INK)
    handles = [Line2D([], [], color=AGENT[n], lw=1.3, ls=AGENT_DASH.get(n, "-"), label=n) for n, _f in runs]
    legend_above(axes[1], handles, ncol=5, y=1.16)
    fig.tight_layout(pad=0.35, w_pad=1.2)
    fig.savefig(os.path.join(FIG, "fig_epoch_accuracy_all.png"), dpi=240)
    plt.close(fig)


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return c - h, c + h


def pooled_compact():
    from matplotlib.patches import Patch
    # episodes fully evacuated out of (210 trained-stage, 90 unseen-stage) on sets 1 and 2 pooled
    counts = {"A*": (183, 78), "v2": (173, 57), "v4": (176, 64)}
    groups = [("trained stages\n1–7 (210)", 0, 210), ("unseen stages\n8–10 (90)", 1, 90), ("all ten\n(300)", None, 300)]
    fig, ax = plt.subplots(figsize=(3.3, 2.35))
    width = 0.27
    for i, (name, (tr, un)) in enumerate(counts.items()):
        for g, (_label, idx, n) in enumerate(groups):
            k = tr + un if idx is None else (tr, un)[idx]
            lo, hi = wilson(k, n)
            v = 100 * k / n
            x = g + (i - 1) * width
            ax.bar(x, v, width, color=AGENT[name], edgecolor="white", linewidth=0.8)
            ax.errorbar(x, v, yerr=[[v - 100 * lo], [100 * hi - v]], color=INK, lw=0.6, capsize=1.6, capthick=0.6)
            ax.text(x, 3, "%.0f" % v, ha="center", va="bottom", fontsize=5.6, color="white")
    paper_axes(ax, "% of episodes fully evacuated")
    ax.set_xticks(range(3))
    ax.set_xticklabels([g[0] for g in groups], fontsize=6)
    ax.set_ylim(0, 100)
    legend_above(ax, [Patch(color=AGENT[n], label=n) for n in counts], ncol=3, y=1.03)
    fig.tight_layout(pad=0.35)
    fig.savefig(os.path.join(FIG, "fig_pooled_compact.png"), dpi=240)
    plt.close(fig)


def stage_compact():
    from matplotlib.patches import Patch
    with open(os.path.join(FINDINGS, "data", "stage_report.csv"), encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    agents = ("A*", "v4", "v5")
    stages = list(range(1, 11))
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.2))
    for i, agent in enumerate(agents):
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
            ax.bar(xs, vals, 0.27, color=AGENT[agent], edgecolor="white", linewidth=0.5)
    texts = ("evacuated everyone (%)", "clear time of the wins (s)", "map viewed when it gave up (%)")
    for ax, letter, text in zip(axes, "abc", texts):
        paper_axes(ax, None)
        unseen_band(ax)
        ax.set_xticks(stages)
        ax.set_xlim(0.4, 10.6)
        ax.set_xlabel("stage", fontsize=6.6, color=INK)
        panel(ax, letter, text)
    axes[0].set_ylim(40, 103)
    axes[2].set_ylim(50, 100)
    legend_above(axes[2], [Patch(color=AGENT[a], label=a) for a in agents], ncol=3, y=1.16)
    fig.tight_layout(pad=0.35, w_pad=1.0)
    fig.savefig(os.path.join(FIG, "fig_stage_compact.png"), dpi=240)
    plt.close(fig)


def diamond(ax, cx, cy, w, h, text, size=6.2):
    from matplotlib.patches import Polygon
    ax.add_patch(Polygon([(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)], closed=True,
                         fc="#fbf1dc", ec=INK, lw=0.9))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=size, color=INK)


def line(ax, pts, head=True):
    xs, ys = zip(*pts)
    ax.plot(xs[:-1] if head else xs, ys[:-1] if head else ys, color=INK, lw=0.9, solid_capstyle="butt")
    if head:
        arrow(ax, xs[-2], ys[-2], xs[-1], ys[-1])
    elif len(pts) > 1:
        pass


def decision_loop():
    """Section V: the A* rescuer's sense-decide-act loop (replaces the text sketch of revision 1).
    Faithful to RescueAgent._choose_goal_cell: known waiting occupant, else an unexplored area worth
    the risk (the 60% health budget), else the exit; a locked door on the way makes the key the goal."""
    fig, ax = plt.subplots(figsize=(3.35, 4.55))
    ax.set_xlim(0, 10.3)
    ax.set_ylim(0, 14.6)
    ax.axis("off")
    cx, rx = 3.3, 8.05              # main spine, right-hand goals
    main_w, side_w = 4.5, 3.4

    box(ax, cx - main_w / 2, 13.2, main_w, 1.05, "Sense: tiles and occupants\nwithin 3.5 tiles", "#dfe7f3", size=6.3)
    diamond(ax, cx, 11.55, 4.9, 1.55, "Known occupant\nstill waiting?")
    box(ax, rx - side_w / 2, 11.05, side_w, 1.0, "Goal: nearest\nknown occupant", "#d6ecdf", size=6.2)
    diamond(ax, cx, 9.35, 4.9, 1.75, "Unexplored area\nreachable and worth\nthe risk?", size=5.9)
    box(ax, rx - side_w / 2, 8.85, side_w, 1.0, "Goal: nearest\nunexplored area", "#d6ecdf", size=6.2)
    box(ax, cx - 1.6, 7.25, 3.2, 0.8, "Goal: the exit", "#d6ecdf", size=6.2)
    diamond(ax, cx, 5.45, 4.9, 1.55, "Locked door in the\nway and no key?", size=6.0)
    box(ax, rx - side_w / 2, 4.95, side_w, 1.0, "Goal: fetch\nthe key first", "#f6d9d6", size=6.2)
    box(ax, cx - main_w / 2, 3.25, main_w, 0.95, "Plan the route with\nhazard-weighted A*", "#dfe7f3", size=6.3)
    box(ax, cx - main_w / 2, 1.85, main_w, 0.8, "Step one tile along it", "#dfe7f3", size=6.3)
    box(ax, cx - main_w / 2, 0.2, main_w, 1.05, "World changed? (fire, collapse,\ndoor) Re-plan, and every 0.25 s", "#eeeeee", size=5.9)

    lab = dict(fontsize=5.8, color=GREY, style="italic")
    arrow(ax, cx, 13.2, cx, 12.35)                                   # sense -> d1
    arrow(ax, cx + 2.45, 11.55, rx - side_w / 2, 11.55); ax.text(cx + 2.55, 11.87, "yes", **lab)
    arrow(ax, cx, 10.78, cx, 10.25); ax.text(cx + 0.15, 10.4, "no", **lab)
    arrow(ax, cx + 2.45, 9.35, rx - side_w / 2, 9.35); ax.text(cx + 2.55, 9.67, "yes", **lab)
    arrow(ax, cx, 8.47, cx, 8.05); ax.text(cx + 0.15, 8.12, "no", **lab)
    # the three goals merge above the door check
    bus = 10.1
    ax.plot([rx + side_w / 2, bus, bus], [11.55, 11.55, 6.75], color=INK, lw=0.9)
    ax.plot([rx + side_w / 2, bus], [9.35, 9.35], color=INK, lw=0.9)
    ax.plot([bus, cx], [6.75, 6.75], color=INK, lw=0.9)
    ax.plot([cx, cx], [7.25, 6.75], color=INK, lw=0.9)
    arrow(ax, cx, 6.75, cx, 6.23)
    arrow(ax, cx + 2.45, 5.45, rx - side_w / 2, 5.45); ax.text(cx + 2.55, 5.77, "yes", **lab)
    arrow(ax, cx, 4.68, cx, 4.2); ax.text(cx + 0.15, 4.33, "no", **lab)
    ax.plot([rx, rx, cx + main_w / 2 + 0.6], [4.95, 3.72, 3.72], color=INK, lw=0.9)
    arrow(ax, cx + main_w / 2 + 0.7, 3.72, cx + main_w / 2, 3.72)
    arrow(ax, cx, 3.25, cx, 2.65)
    arrow(ax, cx, 1.85, cx, 1.25)
    # the loop back to sensing
    ax.plot([cx - main_w / 2, 0.25, 0.25], [0.72, 0.72, 13.72], color=INK, lw=0.9)
    arrow(ax, 0.25, 13.72, cx - main_w / 2, 13.72)
    fig.tight_layout(pad=0.2)
    fig.savefig(os.path.join(FIG, "fig_decision_loop.png"), dpi=240)
    plt.close(fig)


def main():
    os.makedirs(FIG, exist_ok=True)
    decision_loop()
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
