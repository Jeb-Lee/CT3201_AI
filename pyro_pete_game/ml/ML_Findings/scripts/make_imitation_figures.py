"""Figures and the summary table for the imitation-learning experiments.

    python pyro_pete_game/ml/ML_Findings/scripts/make_imitation_figures.py

Reads imitation/<run>/ (epochs*.csv, rounds.csv, baseline.json, final_results.csv)
and writes figures/fig_imitation_*.png and data/imitation_summary.md. Every number
comes from those logs.
"""

import csv
import json
import os
import sys
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "..", "..")))
from ml.imitation_report import _epochs                           # noqa: E402
from ml.evaluation import wilson, summarise_group                  # noqa: E402
from ml.report import read_csv                                    # noqa: E402

IMIT, FIG, DATA = (os.path.join(BASE, d) for d in ("imitation", "figures", "data"))
RUNS = {"v1": os.path.join(IMIT, "imit_a_v1_local_view"),
        "v2": os.path.join(IMIT, "imit_b_v2_route_hints")}
LABEL = {"v1": "v1: local window only", "v2": "v2: A*'s information"}
COLOUR = {"v1": "#9ca3af", "v2": "#2563eb"}
TRAINED, UNSEEN = list(range(0, 7)), [7, 8, 9]                     # 0-based stages
OUTCOME_COLOURS = {"evacuated": "#3fb56b", "died": "#d9534f", "gave_up": "#f0ad4e", "timeout": "#5b8def"}
os.makedirs(FIG, exist_ok=True)
os.makedirs(DATA, exist_ok=True)


def results(run):
    """The 90 s-cap final test written by train_imitation.py (kept for comparison)."""
    return read_csv(os.path.join(RUNS[run], "final_results.csv"))


def rows240():
    """The 240 s-cap test (imitation_long_cap_test.py): the primary comparison, because the
    real game has no hard time limit and a short cap penalises whichever agent is slower."""
    return read_csv(os.path.join(DATA, "imitation_240s.csv"))


def subset(rows, agent, stages):
    return [r for r in rows if r["agent"] == agent and (r["stage"] in stages)]


def evac(rows):
    k = sum(1 for r in rows if r["outcome"] == "evacuated")
    lo, hi = wilson(k, len(rows))
    return k / len(rows), lo, hi


# ---------------------------------------------------------------- learning curves
def fig_epoch_vs_accuracy():
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(11, 11), sharex=True)
    for run, style in (("v1", "--"), ("v2", "-")):
        rows, marks = _epochs(RUNS[run])
        x = [r["epoch"] for r in rows]
        col = COLOUR[run]
        pick = lambda key: [(r["epoch"], 100 * r[key]) for r in rows if r.get(key) is not None]
        for key, name, alpha in (("val_seen_acc", "held-out episodes, trained stages", 1.0),
                                 ("val_unseen_acc", "UNSEEN stages", 0.55)):
            pts = pick(key)
            a1.plot([p[0] for p in pts], [p[1] for p in pts], style, color=col, alpha=alpha, lw=2,
                    label=f"{LABEL[run]} - {name}")
        for key, name, mk in (("game_seen_evac", "trained stages", "o"), ("game_unseen_evac", "UNSEEN stages", "^")):
            pts = pick(key)
            a2.plot([p[0] for p in pts], [p[1] for p in pts], style, color=col, marker=mk, lw=1.5,
                    alpha=1.0 if "seen" in key and "un" not in key else 0.6,
                    label=f"{LABEL[run]} - plays {name}")
        rounds = read_csv(os.path.join(RUNS[run], "rounds.csv"))
        ends = [30 + 12 * (i + 1) for i in range(len(rounds))]
        a2.plot(ends, [100 * r["game_seen_evac"] for r in rounds], "s", color=col, ms=6)
        a2.plot(ends, [100 * r["game_unseen_evac"] for r in rounds], "D", color=col, ms=5, alpha=0.6)
        a3.plot(x, [r["train_loss"] for r in rows], style, color=col, label=LABEL[run])
        for m in marks:
            for ax in (a1, a2, a3):
                ax.axvline(m, color="#6b7280", ls=":", lw=0.7, alpha=0.5)
    base = json.load(open(os.path.join(RUNS["v2"], "baseline.json")))
    a2.axhline(100 * base["seen_evac"], color="#111", ls="--", lw=1.2, label="A*, trained stages (same episodes)")
    a2.axhline(100 * base["unseen_evac"], color="#111", ls=":", lw=1.2, label="A*, unseen stages (same episodes)")
    a1.set_ylabel("action-match accuracy (%)\n(picks the move A* picks)")
    a1.set_ylim(60, 101)
    a1.set_title("Epoch vs accuracy: imitating A*, with and without A*'s information")
    a2.set_ylabel("episodes fully evacuated (%)\n(the network actually playing)")
    a2.set_ylim(-2, 102)
    a3.set_ylabel("training loss")
    a3.set_yscale("log")
    a3.set_xlabel("epoch  (dotted lines: a DAgger round begins; squares/diamonds: game test after each round)")
    for ax in (a1, a2, a3):
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7.5, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_imitation_epoch_vs_accuracy.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- headline bars
def led_out(rows):
    """Mean over episodes of (occupants led out / occupants in the stage): the same definition
    as the 'occupants led out' column of the tables."""
    return sum(r["victims_out"] / r["victims_total"] for r in rows) / len(rows)


def fig_headline():
    rows = rows240()
    groups = [("trained stages 1-7\n(70 episodes)", TRAINED), ("UNSEEN stages 8-10\n(30 episodes)", UNSEEN),
              ("all ten stages\n(100 episodes)", list(range(10)))]
    bars = [("A* (hand-written)", "astar", "#111827"),
            ("cloned, v2 (A*'s information), deterministic", "v2 deterministic", "#2563eb"),
            ("cloned, v2, sampled", "v2 sampled", "#93c5fd"),
            ("cloned, v1 (local window), deterministic", "v1 deterministic", "#6b7280"),
            ("best reinforcement-learning model", None, "#d9534f")]
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6), sharey=True)
    w = 0.16
    for ax, metric, title in ((axes[0], "evac", "evacuated EVERYONE (%)"),
                              (axes[1], "led", "occupants led out (% of all occupants)")):
        for i, (name, agent, colour) in enumerate(bars):
            xs, ys, lo, hi = [], [], [], []
            for g, (_, stages) in enumerate(groups):
                xs.append(g + (i - 2) * w)
                if agent is None:
                    ys.append(0.0); lo.append(0.0); hi.append(0.0)
                    continue
                sub = subset(rows, agent, stages)
                if metric == "evac":
                    p_, l, h = evac(sub)
                else:
                    p_ = led_out(sub)
                    l = h = p_
                ys.append(100 * p_); lo.append(100 * (p_ - l)); hi.append(100 * (h - p_))
            ax.bar(xs, ys, w, color=colour, label=name if ax is axes[0] else None,
                   yerr=[lo, hi] if metric == "evac" else None, capsize=2, error_kw=dict(lw=0.8))
            for x_, y_ in zip(xs, ys):
                ax.text(x_, y_ + 2.5, f"{y_:.0f}", ha="center", fontsize=7.5)
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels([g[0] for g in groups])
        ax.set_title(title)
        ax.set_ylim(0, 108)
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("%")
    fig.suptitle("FIRST test set (100 episodes), same episodes for every agent, 240 s cap; left-panel bars are 95% Wilson intervals. See the pooled figure for the fuller picture",
                 fontsize=10.5)
    fig.legend(loc="lower center", ncol=3, fontsize=8, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.text(0.5, -0.09, "The RL bar is 0 of 40 episodes on stages 1-4 (a different stage set; see FINDINGS F8).",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    fig.savefig(os.path.join(FIG, "fig_imitation_headline.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ by stage
def fig_by_stage():
    rows = rows240()
    fig, ax = plt.subplots(figsize=(12, 4.8))
    w = 0.27
    for i, (name, agent, colour) in enumerate([
            ("A*", "astar", "#111827"),
            ("cloned v2, deterministic", "v2 deterministic", "#2563eb"),
            ("cloned v1, deterministic", "v1 deterministic", "#9ca3af")]):
        ys, lo, hi = [], [], []
        for st in range(10):
            p, l, h = evac(subset(rows, agent, [st]))
            ys.append(100 * p); lo.append(100 * (p - l)); hi.append(100 * (h - p))
        ax.bar([s + (i - 1) * w for s in range(10)], ys, w, color=colour, label=name,
               yerr=[lo, hi], capsize=2, error_kw=dict(lw=0.7))
    ax.axvline(6.5, color="#d9534f", ls="--", lw=1.2)
    ax.text(6.6, 104, "never trained on  >", color="#d9534f", fontsize=9)
    ax.set_xticks(range(10))
    ax.set_xticklabels([str(s + 1) for s in range(10)])
    ax.set_xlabel("stage (10 episodes each)")
    ax.set_ylabel("episodes fully evacuated (%)")
    ax.set_ylim(0, 112)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title("Per stage: the clone tracks A* on the stages it trained on, and falls behind on the big unseen ones")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_imitation_by_stage.png"), dpi=110)
    plt.close(fig)


# ----------------------------------------------------------- how episodes end
def fig_outcomes():
    rows = rows240()
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), sharey=True)
    agents = [("A*", rows, "astar"), ("v2 det.", rows, "v2 deterministic"), ("v2 sampled", rows, "v2 sampled"),
              ("v1 det.", rows, "v1 deterministic"), ("v1 sampled", rows, "v1 sampled")]
    for ax, (title, stages) in zip(axes, (("trained stages 1-7", TRAINED), ("UNSEEN stages 8-10", UNSEEN))):
        for i, (name, rows, agent) in enumerate(agents):
            sub = subset(rows, agent, stages)
            bottom = 0.0
            for k in ("evacuated", "died", "gave_up", "timeout"):
                share = 100 * sum(1 for r in sub if r["outcome"] == k) / len(sub)
                ax.bar(i, share, bottom=bottom, color=OUTCOME_COLOURS[k],
                       label={"evacuated": "evacuated everyone", "died": "died", "gave_up": "gave up",
                              "timeout": "ran out of time"}[k] if i == 0 else None)
                bottom += share
        ax.set_xticks(range(len(agents)))
        ax.set_xticklabels([a[0] for a in agents])
        ax.set_title(title)
        ax.set_ylim(0, 100)
    axes[0].set_ylabel("how episodes ended (%)")
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("How episodes end (240 s cap): the v2 clone's failures are mostly giving up one occupant short, and dying", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_imitation_outcomes.png"), dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------- summary table
def summary_table():
    pct = lambda x: f"{100 * x:.0f}%"

    def table(rows, names, header=True):
        out = []
        if header:
            out += ["| agent | stages | n | evacuated everyone (95% CI) | died | gave up | ran out of time | occupants led out | mean score |",
                    "|---|---|---|---|---|---|---|---|---|"]
        for agent, label in names:
            for title, stages in (("trained 1-7", TRAINED), ("unseen 8-10", UNSEEN), ("all ten", list(range(10)))):
                sub = subset(rows, agent, stages)
                s_ = summarise_group(sub)
                lo, hi = s_["evacuated_ci"]
                out.append(f"| {label} | {title} | {s_['n']} | {pct(s_['evacuated'])} ({pct(lo)}-{pct(hi)}) | "
                           f"{pct(s_['died'])} | {pct(s_['gave_up'])} | {pct(s_['timeout'])} | "
                           f"{pct(s_['occupants_out'])} | {s_['score']:.0f} |")
        return out

    lines = ["## Primary: 240 s cap (the real game has no hard time limit)", ""]
    lines += table(rows240(), [("astar", "A*"), ("v2 deterministic", "v2 clone, deterministic"),
                               ("v2 sampled", "v2 clone, sampled"), ("v1 deterministic", "v1 clone, deterministic"),
                               ("v1 sampled", "v1 clone, sampled")])
    r2, r1 = results("v2"), results("v1")
    lines += ["", "## For comparison: the 90 s cap used during training", ""]
    lines += table(r2, [("astar", "A*"), ("cloned (deterministic)", "v2 clone, deterministic"),
                        ("cloned (sampled)", "v2 clone, sampled")])
    lines += table(r1, [("cloned (deterministic)", "v1 clone, deterministic"), ("cloned (sampled)", "v1 clone, sampled")],
                   header=False)

    rows = rows240()
    by = lambda a: {(r["stage"], r["seed"]): r for r in rows if r["agent"] == a}
    A, C = by("astar"), by("v2 deterministic")
    keys = sorted(set(A) & set(C))
    only_a = sum(A[k]["outcome"] == "evacuated" and C[k]["outcome"] != "evacuated" for k in keys)
    only_c = sum(C[k]["outcome"] == "evacuated" and A[k]["outcome"] != "evacuated" for k in keys)
    both = sum(A[k]["outcome"] == "evacuated" and C[k]["outcome"] == "evacuated" for k in keys)
    lines += ["", f"Paired, v2 deterministic vs A* on the same {len(keys)} episodes (240 s cap): both evacuated {both}, "
                  f"only A* {only_a}, only the clone {only_c}."]

    lines += ["", "## Where the give-ups come from", "",
              "Episodes that ended by giving up, and how many occupants were still inside:", ""]
    for agent in ("astar", "v2 deterministic", "v2 sampled"):
        g = [r for r in rows if r["agent"] == agent and r["outcome"] == "gave_up"]
        short = Counter(r["victims_total"] - r["victims_out"] for r in g)
        lines.append(f"* {agent}: {len(g)} of {sum(1 for r in rows if r['agent'] == agent)} episodes; "
                     f"occupants still inside: " + ", ".join(f"{n} left in {c}" for n, c in sorted(short.items())))
    with open(os.path.join(DATA, "imitation_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


# ------------------------------------------------------------ back-and-forth pacing
def fig_pingpong():
    import random as _r
    rows = read_csv(os.path.join(DATA, "oscillation.csv"))
    groups = [("A*", "astar", "evacuated"), ("A*", "astar", "died"), ("v2 clone", "v2", "evacuated"),
              ("v2 clone", "v2", "died"), ("v2 clone", "v2", "gave_up")]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    rng = _r.Random(3)
    for i, (label, agent, outcome) in enumerate(groups):
        ys = [r["longest_pingpong"] + 1 for r in rows if r["agent"] == agent and r["outcome"] == outcome]
        if not ys:
            continue
        ax.scatter([i + rng.uniform(-0.18, 0.18) for _ in ys], ys, s=22, alpha=0.6,
                   color=OUTCOME_COLOURS[outcome], edgecolor="none")
        ax.hlines(sorted(ys)[len(ys) // 2], i - 0.3, i + 0.3, color="#111", lw=2)
        ax.text(i, 0.62, f"n={len(ys)}", ha="center", fontsize=8)
    ax.axhline(7, color="#6b7280", ls=":", lw=1)
    ax.text(4.45, 7.6, "flagged: 6+ reversals in a row", ha="right", fontsize=8, color="#6b7280")
    ax.set_yscale("log")
    ax.set_ylim(0.5, 400)
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([f"{g[0]}\n{g[2].replace('_', ' ')}" for g in groups])
    ax.set_ylabel("longest back-and-forth run (reversals + 1, log scale)")
    ax.set_title("A* never paces between two tiles; every give-up by the clone contains a long run (black bar = median)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_imitation_pingpong.png"), dpi=110)
    plt.close(fig)


# ---------------------------------------------------- pooled 300 episodes (the fuller picture)
def fig_pooled():
    set1 = read_csv(os.path.join(DATA, "imitation_240s.csv"))
    set2 = read_csv(os.path.join(DATA, "confirmation_240s.csv"))
    agents = [("A*", "astar", "#111827"), ("v2: A*'s information", "v2 deterministic", "#2563eb"),
              ("v4: + full trail (deterministic)", "v4 deterministic", "#d97706"),
              ("v4: + full trail (sampled)", "v4 sampled", "#fbbf24")]
    groups = [("trained stages 1-7\n(210 episodes)", TRAINED), ("UNSEEN stages 8-10\n(90 episodes)", UNSEEN),
              ("all ten stages\n(300 episodes)", list(range(10)))]
    fig, ax = plt.subplots(figsize=(11, 5.2))
    w = 0.2
    for i, (name, agent, colour) in enumerate(agents):
        rows = [r for r in set1 if r["agent"] == agent] + [r for r in set2 if r["agent"] == agent]
        ys, lo, hi = [], [], []
        for _, stages in groups:
            p_, l, h = evac([r for r in rows if r["stage"] in stages])
            ys.append(100 * p_); lo.append(100 * (p_ - l)); hi.append(100 * (h - p_))
        xs = [g + (i - 1.5) * w for g in range(3)]
        ax.bar(xs, ys, w, color=colour, label=name, yerr=[lo, hi], capsize=2, error_kw=dict(lw=0.8))
        for x_, y_ in zip(xs, ys):
            ax.text(x_, y_ + 2.5, f"{y_:.0f}", ha="center", fontsize=8)
    ax.set_xticks(range(3))
    ax.set_xticklabels([g[0] for g in groups])
    ax.set_ylim(0, 108)
    ax.set_ylabel("episodes fully evacuated (%)")
    ax.set_title("Two independent test sets pooled (100 + 200 fresh episodes), 240 s cap; bars are 95% Wilson intervals")
    ax.legend(loc="lower left", fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.text(0.5, -0.01, "The clones are level with A* within a few points on trained stages and clearly behind on unseen ones.",
             ha="center", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_imitation_pooled.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------- memory: v2 vs v3 vs v4
MEM_RUNS = {"v2": "imit_b_v2_route_hints", "v3": "imit_c_v3_memory", "v4": "imit_d_v4_trail"}
MEM_LABEL = {"v2": "v2: no memory", "v3": "v3: short memory (last move + last 4 tiles)",
             "v4": "v4: full trail (visit counts, whole episode)"}
MEM_COLOUR = {"v2": "#2563eb", "v3": "#16a34a", "v4": "#d97706"}


def _have_memory_runs():
    return all(os.path.isfile(os.path.join(IMIT, f, "final_results.csv")) for f in MEM_RUNS.values()) \
        and os.path.isfile(os.path.join(DATA, "oscillation.csv"))


def fig_memory_headline():
    rows = rows240()
    osc = read_csv(os.path.join(DATA, "oscillation.csv"))
    groups = [("trained 1-7\n(70)", TRAINED), ("UNSEEN 8-10\n(30)", UNSEEN), ("all ten\n(100)", list(range(10)))]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={"width_ratios": [2.2, 1]})
    w = 0.2
    for i, (key, agent, colour) in enumerate([("A*", "astar", "#111827")] + [(k, f"{k} deterministic", MEM_COLOUR[k]) for k in MEM_RUNS]):
        ys, lo, hi = [], [], []
        for _, stages in groups:
            p_, l, h = evac(subset(rows, agent, stages))
            ys.append(100 * p_); lo.append(100 * (p_ - l)); hi.append(100 * (h - p_))
        xs = [g + (i - 1.5) * w for g in range(3)]
        a1.bar(xs, ys, w, color=colour, label="A*" if key == "A*" else MEM_LABEL[key], yerr=[lo, hi], capsize=2,
               error_kw=dict(lw=0.8))
        for x_, y_ in zip(xs, ys):
            a1.text(x_, y_ + 2.5, f"{y_:.0f}", ha="center", fontsize=7.5)
    a1.set_xticks(range(3))
    a1.set_xticklabels([g[0] for g in groups])
    a1.set_ylim(0, 108)
    a1.set_ylabel("episodes fully evacuated (%)")
    a1.set_title("Does memory help? FIRST test set (100 episodes), 240 s cap, deterministic")
    a1.legend(fontsize=8, loc="lower left")
    a1.grid(axis="y", alpha=0.25)
    names = [("A*", "astar", "#111827")] + [(k, k, MEM_COLOUR[k]) for k in MEM_RUNS]
    flagged = [sum(r["flagged"] for r in osc if r["agent"] == a) for _, a, _ in names]
    a2.bar(range(len(names)), flagged, color=[c for _, _, c in names])
    for i, f in enumerate(flagged):
        a2.text(i, f + 0.4, str(f), ha="center")
    a2.set_xticks(range(len(names)))
    a2.set_xticklabels([n for n, _, _ in names])
    a2.set_ylabel("episodes with long back-and-forth pacing\n(of 100)")
    a2.set_title("Pacing between two tiles")
    a2.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_imitation_memory.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


def fig_memory_epochs():
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)
    for key, folder in MEM_RUNS.items():
        rows, marks = _epochs(os.path.join(IMIT, folder))
        col = MEM_COLOUR[key]
        for ax, k, alpha, name in ((a1, "val_seen_acc", 1.0, "held-out episodes"), (a1, "val_unseen_acc", 0.5, "UNSEEN stages")):
            pts = [(r["epoch"], 100 * r[k]) for r in rows if r.get(k) is not None]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, alpha=alpha, lw=2,
                    label=f"{MEM_LABEL[key].split(':')[0]} - {name}")
        rounds = read_csv(os.path.join(IMIT, folder, "rounds.csv"))
        ends = [30 + 12 * (i + 1) for i in range(len(rounds))]
        a2.plot(ends, [100 * r["game_seen_evac"] for r in rounds], "s-", color=col, label=f"{key} plays trained stages")
        a2.plot(ends, [100 * r["game_unseen_evac"] for r in rounds], "D--", color=col, alpha=0.6, label=f"{key} plays UNSEEN stages")
        for m in marks:
            a1.axvline(m, color="#6b7280", ls=":", lw=0.6, alpha=0.5)
            a2.axvline(m, color="#6b7280", ls=":", lw=0.6, alpha=0.5)
    a1.set_ylabel("action-match accuracy (%)")
    a1.set_ylim(85, 100.5)
    a1.set_title("Epoch vs accuracy with and without memory")
    a2.set_ylabel("episodes evacuated in a game test after each DAgger round (%)")
    a2.set_ylim(-2, 102)
    a2.set_xlabel("epoch (dotted: a DAgger round begins)")
    for ax in (a1, a2):
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7.5, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_imitation_memory_epochs.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


def memory_summary():
    """The registered predictions (PREDICTIONS.md P7, P9), checked by code against the data."""
    rows = rows240()
    osc = read_csv(os.path.join(DATA, "oscillation.csv"))
    lines = ["| network | all-ten evacuated (deterministic, 240 s) | trained 1-7 | unseen 8-10 | flagged pacing episodes | one-short give-ups | median seconds |",
             "|---|---|---|---|---|---|---|"]
    stats = {}
    for key in MEM_RUNS:
        det = [r for r in rows if r["agent"] == f"{key} deterministic"]
        p_all, lo, hi = evac(det)
        p_tr = evac(subset(rows, f"{key} deterministic", TRAINED))[0]
        p_un = evac(subset(rows, f"{key} deterministic", UNSEEN))[0]
        fl = sum(r["flagged"] for r in osc if r["agent"] == key)
        short = sum(1 for r in det if r["outcome"] == "gave_up" and r["victims_total"] - r["victims_out"] == 1)
        secs = sorted(r["seconds"] for r in det)
        stats[key] = dict(p=p_all, fl=fl, short=short, un=p_un)
        lines.append(f"| {MEM_LABEL[key]} | {100 * p_all:.0f}% ({100 * lo:.0f}-{100 * hi:.0f}) | {100 * p_tr:.0f}% | "
                     f"{100 * p_un:.0f}% | {fl} of 100 | {short} | {secs[len(secs) // 2]:.0f} |")
    v2, v3, v4 = stats["v2"], stats["v3"], stats["v4"]
    lines += ["", "**Registered predictions, checked against the numbers above:**", "",
              f"* P7 (short memory): flagged episodes fall from {v2['fl']} to 6 or fewer: **{'HELD' if v3['fl'] <= 6 else 'FALSIFIED'}** "
              f"(v3 has {v3['fl']}). All-ten evacuation rises to 85% or more: "
              f"**{'HELD' if v3['p'] >= 0.85 else 'FALSIFIED'}** (v3: {100 * v3['p']:.0f}%, v2: {100 * v2['p']:.0f}%).",
              f"* P9 (full trail): flagged episodes no more than v3 and at most 6: "
              f"**{'HELD' if (v4['fl'] <= v3['fl'] and v4['fl'] <= 6) else 'FALSIFIED'}** (v4 has {v4['fl']}, v3 has {v3['fl']}). "
              f"Evacuation within 5 points of v3: **{'HELD' if abs(v4['p'] - v3['p']) <= 0.05 else 'FALSIFIED'}** "
              f"(v4: {100 * v4['p']:.0f}%, v3: {100 * v3['p']:.0f}%; a v4 that is worse by more than 5 points falsifies it).",
              f"* P8 (route damage) is not tested here. One-short give-ups: v2 {v2['short']}, v3 {v3['short']}, v4 {v4['short']}."]
    # paired: the same 100 episodes, who won what the other lost (deterministic policies, 240 s)
    def won(agent):
        return {(r["stage"], r["seed"]): r["outcome"] == "evacuated" for r in rows if r["agent"] == agent}
    lines += ["", "**Paired comparisons on the same 100 episodes** (evacuated everyone; deterministic, 240 s):", "",
              "| first | second | both | only first | only second |", "|---|---|---|---|---|"]
    for a, b in (("v2", "v3"), ("v2", "v4"), ("v3", "v4"), ("astar", "v4"), ("astar", "v3"), ("astar", "v2")):
        wa = won("astar" if a == "astar" else f"{a} deterministic")
        wb = won(f"{b} deterministic")
        keys = sorted(set(wa) & set(wb))
        both = sum(wa[k] and wb[k] for k in keys)
        oa = sum(wa[k] and not wb[k] for k in keys)
        ob = sum(wb[k] and not wa[k] for k in keys)
        lines.append(f"| {'A*' if a == 'astar' else a} | {b} | {both} | {oa} | {ob} |")
    with open(os.path.join(DATA, "memory_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    extra = (fig_memory_headline, fig_memory_epochs, memory_summary, fig_pooled) if _have_memory_runs() else ()
    for f in (fig_epoch_vs_accuracy, fig_headline, fig_by_stage, fig_outcomes, fig_pingpong, summary_table) + extra:
        try:
            f()
            print("ok", f.__name__)
        except Exception as exc:
            print("SKIPPED", f.__name__, "->", type(exc).__name__, exc)
