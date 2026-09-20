"""Draw the figures used in the findings, from the logged data only.

    python pyro_pete_game/ml/ML_Findings/scripts/make_figures.py

Reads experiments/*/epochs.csv, evaluations.csv, data/baselines_episodes.csv
and data/reward_accounting.csv; writes figures/*.png. Nothing here is typed in
by hand except the throughput measurements (see fig_engineering.png) and the
price-list arithmetic, which is derived from the reward accounting.
"""

import csv
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
EXP, DATA, FIG = (os.path.join(BASE, d) for d in ("experiments", "data", "figures"))
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "..", "..")))
from ml.report import read_csv                                    # noqa: E402

os.makedirs(FIG, exist_ok=True)
COL = {"died": "#d9534f", "gave_up": "#f0ad4e", "timeout": "#5b8def", "evac": "#3fb56b"}

# reward version -> (title, [run folders])
VERSIONS = [
    ("v1  plain game-score reward", ["exp01_plain_s0", "exp01_plain_s1", "exp01_plain_s2"]),
    ("v2  + abandon penalty (100 per occupant left)",
     ["exp02_abandon_s0", "exp02_abandon_s1", "exp02_abandon_s2"]),
    ("v3  + give-up penalty (200)", ["exp04_giveup200_s0", "exp04_giveup200_s1"]),
    ("v4  + give-up and timeout penalties (200 each)", ["exp05_giveup200_timeout200_s0"]),
]


def epochs(run):
    return read_csv(os.path.join(EXP, run, "epochs.csv"))


def have(run):
    return os.path.isfile(os.path.join(EXP, run, "epochs.csv"))


# ----------------------------------------------------------- outcome mix grid
def fig_outcomes():
    runs_present = [(t, [r for r in rs if have(r)]) for t, rs in VERSIONS]
    runs_present = [(t, rs) for t, rs in runs_present if rs]
    fig, axes = plt.subplots(len(runs_present), 3, figsize=(13, 2.6 * len(runs_present) + 0.9),
                             sharex=True, sharey=True, constrained_layout=True, squeeze=False)
    for r, (title, runs) in enumerate(runs_present):
        for c in range(3):
            ax = axes[r][c]
            if c >= len(runs):
                ax.axis("off")
                continue
            rows = epochs(runs[c])
            x = [row["epoch"] for row in rows]
            get = lambda k: [100 * (row[k] or 0) for row in rows]
            ax.stackplot(x, get("died"), get("gave_up"), get("timeout"), get("train_accuracy"),
                         colors=[COL["died"], COL["gave_up"], COL["timeout"], COL["evac"]],
                         labels=["died", "gave up (stood still)", "timed out (kept moving)",
                                 "EVACUATED (accuracy)"])
            ax.set_ylim(0, 100)
            ax.set_xlim(x[0], x[-1])
            ax.set_title(f"{title.split('  ')[0]} - seed {runs[c].split('_s')[-1]}"
                         + (f":  {title.split('  ', 1)[1]}" if c == 0 else ""),
                         fontsize=8, loc="left")
            ax.grid(alpha=0.2)
            if c == 0:
                ax.set_ylabel("% of last 100 episodes")
            if r == len(runs_present) - 1:
                ax.set_xlabel("epoch  (1 epoch = 3,072 steps)")
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=4, frameon=False, fontsize=9)
    fig.suptitle("How each episode ended, over training - by reward version and seed", fontsize=12)
    fig.savefig(os.path.join(FIG, "fig_reward_vs_behaviour.png"), dpi=110)
    plt.close(fig)


# --------------------------------------------------------- the price of endings
def price_table():
    """Return of each way an episode can end, under each reward version.
    give-up, die and A* are measured (reward_accounting.csv); the pacing
    timeout is computed (90 s of 0.05/s time cost, no damage, no rescue)."""
    rows = read_csv(os.path.join(DATA, "reward_accounting.csv"))

    def mean(reward, policy):
        xs = [r["ret"] for r in rows if r["reward"] == reward and r["policy"] == policy]
        return sum(xs) / len(xs)

    n_occ = -(mean("abandon", "stay") - mean("plain", "stay")) / 100.0     # ~3.33 occupants
    give, die, astar = mean("plain", "stay"), mean("plain", "random"), mean("plain", "astar")
    pace = -0.05 * 90
    versions = [
        ("v1 plain", dict(gave_up=give, died=die, timeout=pace, evac=astar)),
        ("v2 abandon 100", dict(gave_up=give - 100 * n_occ, died=die - 100 * n_occ,
                                timeout=pace - 100 * n_occ,
                                evac=mean("abandon", "astar"))),
        ("v3 give-up 200", dict(gave_up=give - 200, died=die, timeout=pace, evac=astar)),
        ("v4 give-up+timeout 200", dict(gave_up=give - 200, died=die, timeout=pace - 200,
                                        evac=astar)),
    ]
    return versions, n_occ


def fig_prices():
    versions, _ = price_table()
    fig, ax = plt.subplots(figsize=(11, 5.2))
    keys = ["gave_up", "died", "timeout"]
    names = {"gave_up": "give up (stand still)", "died": "die (wander into fire)",
             "timeout": "time out (pace safely)"}
    width = 0.26
    for i, k in enumerate(keys):
        xs = [j + (i - 1) * width for j in range(len(versions))]
        ys = [v[1][k] for v in versions]
        bars = ax.bar(xs, ys, width, color=COL[k], label=names[k])
        for x, y, (label, d) in zip(xs, ys, versions):
            cheapest = max(keys, key=lambda kk: d[kk]) == k
            ax.text(x, y - 12, f"{y:.0f}", ha="center", va="top", fontsize=8)
            if cheapest:
                ax.text(x, 12, "cheapest", ha="center", va="bottom", fontsize=8,
                        fontweight="bold", color="#222")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(len(versions)))
    ax.set_xticklabels([v[0] for v in versions])
    ax.set_ylabel("episode return for a policy that never rescues anyone")
    ax.set_title("The price of each way of failing, under each reward version\n"
                 "(the cheapest ending is marked; the optimiser is drawn to it)")
    fig.text(0.5, -0.01, "give-up, die: measured (30 episodes each, data/reward_accounting.md).  "
             "time out: computed as 90 s x 0.05/s time cost for a policy that paces safely.",
             ha="center", fontsize=8)
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    ax.set_ylim(min(min(v[1][k] for k in keys) for v in versions) - 60, 60)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_price_of_failure.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------- exploration collapse metrics
def fig_learning_signals():
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)
    palette = {"v1": "#d9534f", "v2": "#8e44ad", "v3": "#5b8def", "v4": "#16a085"}
    for (title, runs), key in zip(VERSIONS, palette):
        first = True
        for run in runs:
            if not have(run):
                continue
            rows = epochs(run)
            x = [r["epoch"] for r in rows]
            lab = title.split("  ")[0] + " " + title.split("  ", 1)[1] if first else None
            a1.plot(x, [r["entropy"] for r in rows], color=palette[key], alpha=0.8, label=lab)
            a2.plot(x, [r["reward"] for r in rows], color=palette[key], alpha=0.8)
            first = False
    a1.set_ylabel("policy entropy\n(how undecided it is)")
    a2.set_ylabel("mean episode return\n(last 100 episodes, raw game points)")
    a2.set_xlabel("epoch")
    a1.legend(fontsize=8)
    for a in (a1, a2):
        a.grid(alpha=0.25)
    a1.set_title("Policy entropy and mean return over training, every run")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_learning_signals.png"), dpi=110)
    plt.close(fig)


# -------------------------------------------------------------- long runs
LONG_RUNS = [("exp07_giveup200_long_s0", "v3: give-up penalty 200, 300k steps"),
             ("exp06_plain_s2_continued", "v1 plain, seed 2, continued to 401k steps"),
             ("exp03_abandon_long_s0", "v2: abandon penalty 100, 300k steps")]


def fig_long():
    runs = [(r, t) for r, t in LONG_RUNS if have(r)]
    if not runs:
        return
    fig, axes = plt.subplots(len(runs), 2, figsize=(14, 3.0 * len(runs) + 0.8), sharex=True,
                             constrained_layout=True, squeeze=False)
    for i, (run, title) in enumerate(runs):
        rows = epochs(run)
        x = [r["timesteps"] / 1000 for r in rows]
        get = lambda k: [100 * (r[k] or 0) for r in rows]
        a, b = axes[i]
        a.stackplot(x, get("died"), get("gave_up"), get("timeout"), get("train_accuracy"),
                    colors=[COL["died"], COL["gave_up"], COL["timeout"], COL["evac"]],
                    labels=["died", "gave up", "timed out", "EVACUATED"])
        a.set_ylim(0, 100)
        a.set_ylabel("% of last 100 episodes")
        a.set_title(title, fontsize=9, loc="left")
        b.plot(x, get("occupants_out"), color="#3fb56b", lw=2, label="occupants led out (%)")
        b.plot(x, get("train_accuracy"), color="#1b7f4b", lw=2, ls="--", label="full evacuations (%)")
        b.set_ylim(0, 50)
        b.set_title("rescue progress", fontsize=9, loc="left")
        for ax in (a, b):
            ax.grid(alpha=0.25)
        if i == 0:
            a.legend(ncol=4, fontsize=8, loc="upper center")
            b.legend(fontsize=8, loc="upper left")
    for ax in axes[-1]:
        ax.set_xlabel("training steps (thousands)")
    fig.suptitle("The long runs", fontsize=12)
    fig.savefig(os.path.join(FIG, "fig_long_run.png"), dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------- baselines
def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)


def fig_baselines():
    path = os.path.join(DATA, "baselines_episodes.csv")
    if not os.path.isfile(path):
        return
    rows = read_csv(path)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    agents = [("astar", "A* (hand-written)", "#3fb56b"), ("random", "random legal moves", "#d9534f"),
              ("stay", "stand still", "#f0ad4e")]
    w = 0.27
    for i, (a, label, colour) in enumerate(agents):
        ys, lo, hi = [], [], []
        for st in range(10):
            sel = [r for r in rows if r["agent"] == a and r["stage"] == st]
            k = sum(1 for r in sel if r["outcome"] == "evacuated")
            l, h = wilson(k, len(sel))
            ys.append(100 * k / len(sel))
            lo.append(100 * k / len(sel) - 100 * l)
            hi.append(100 * h - 100 * k / len(sel))
        ax.bar([s + (i - 1) * w for s in range(10)], ys, w, color=colour, label=label,
               yerr=[lo, hi], capsize=2, error_kw=dict(lw=0.8))
    ax.set_xticks(range(10))
    ax.set_xticklabels([str(s + 1) for s in range(10)])
    ax.set_xlabel("stage")
    ax.set_ylabel("accuracy: % of episodes fully evacuated")
    ax.set_title("Baselines, 20 episodes per stage per agent (bars: 95% Wilson interval)")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_baselines.png"), dpi=110)
    plt.close(fig)


# -------------------------------------------------------------- engineering
def fig_engineering():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.bar(["before\n(sprites re-read\nfrom disk each reset)", "after\n(sprite sets cached)"],
           [189, 575], color=["#d9534f", "#3fb56b"])
    for x, y in enumerate([189, 575]):
        a1.text(x, y + 10, f"{y} steps/s", ha="center")
    a1.set_ylabel("raw environment steps per second (1 process)")
    a1.set_title("Throughput: one cache, 3.0x")
    scaled = epochs("exp01_plain_s0")[0]["value_loss"]       # logged: first epoch, scaled reward
    unscaled = 987.3                                          # first smoke run, first epoch (typed in)
    a2.bar(["unscaled\nreward", "scaled\nreward"], [unscaled, scaled], color=["#d9534f", "#3fb56b"])
    a2.set_yscale("log")
    for x, y in enumerate([unscaled, scaled]):
        a2.text(x, y * 1.15, f"{y:.3g}", ha="center")
    a2.set_ylabel("value-network loss, first epoch (log scale)")
    a2.set_title("Reward scaling for the optimiser")
    fig.text(0.5, -0.02, "Measured during development (profile run and first smoke run); "
             "run folders for these two were not kept.", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "fig_engineering.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    for f in (fig_outcomes, fig_prices, fig_learning_signals, fig_long, fig_baselines,
              fig_engineering):
        try:
            f()
            print("ok", f.__name__)
        except Exception as exc:                      # a missing run must not block the rest
            print("SKIPPED", f.__name__, "->", type(exc).__name__, exc)
