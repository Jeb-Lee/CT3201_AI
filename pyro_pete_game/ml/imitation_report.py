"""The epoch-vs-accuracy chart for an imitation run (needs matplotlib).

Reads a run folder written by tools/train_imitation.py:
    epochs.csv, epochs_round<k>.csv   one row per epoch (accuracy, loss, game outcomes)
    rounds.csv                        one row per DAgger round
    baseline.json                     A* on the same evaluation episodes

    python tools/plot_imitation.py runs/<name>
"""

import json
import os

from ml.report import read_csv

CHART = "imitation_epoch_vs_accuracy.png"


def _epochs(run_dir):
    """Every epoch of the run in order: the initial cloning epochs, then each
    DAgger round's epochs, numbered continuously."""
    rows = read_csv(os.path.join(run_dir, "epochs.csv"))
    marks = []
    k = 1
    while os.path.isfile(os.path.join(run_dir, f"epochs_round{k}.csv")):
        marks.append(rows[-1]["epoch"] if rows else 0)
        extra = read_csv(os.path.join(run_dir, f"epochs_round{k}.csv"))
        base = rows[-1]["epoch"] if rows else 0
        for r in extra:
            r = dict(r)
            r["epoch"] = base + (r["epoch"] - extra[0]["epoch"] + 1)
            rows.append(r)
        k += 1
    return rows, marks


def plot_imitation(run_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    rows, marks = _epochs(run_dir)
    if not rows:
        return None
    rounds = read_csv(os.path.join(run_dir, "rounds.csv"))
    base_path = os.path.join(run_dir, "baseline.json")
    base = json.load(open(base_path)) if os.path.isfile(base_path) else {}

    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(11, 11), sharex=True,
                                     gridspec_kw={"height_ratios": [3, 3, 2]})
    x = [r["epoch"] for r in rows]
    pct = lambda key: [None if r.get(key) is None else 100 * r[key] for r in rows]

    def line(ax, key, **kw):
        ys = pct(key)
        pts = [(a, b) for a, b in zip(x, ys) if b is not None]
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], **kw)

    line(a1, "train_acc", color="#9ca3af", lw=1.6, label="training data")
    line(a1, "val_seen_acc", color="#3b82f6", lw=2, label="held-out episodes, trained stages")
    line(a1, "val_unseen_acc", color="#ef4444", lw=2, label="episodes on UNSEEN stages")
    a1.set_ylabel("action-match accuracy (%)\n(picks the move A* picks)")
    a1.set_title("Epoch vs accuracy: imitating A*")
    a1.set_ylim(0, 102)

    line(a2, "game_seen_evac", color="#3b82f6", marker="o", lw=2, label="plays: trained stages")
    line(a2, "game_unseen_evac", color="#ef4444", marker="o", lw=2, label="plays: UNSEEN stages")
    for r in rounds:                      # one point per DAgger round, at the round's last epoch
        pass
    if rounds:
        xs = [m + (marks[i + 1] - m if i + 1 < len(marks) else (rows[-1]["epoch"] - m))
              for i, m in enumerate(marks)][:len(rounds)]
        a2.plot(xs, [100 * r["game_seen_evac"] for r in rounds], "s--", color="#1d4ed8", label="DAgger round: trained stages")
        a2.plot(xs, [100 * r["game_unseen_evac"] for r in rounds], "s--", color="#b91c1c", label="DAgger round: UNSEEN stages")
    if "seen_evac" in base:
        a2.axhline(100 * base["seen_evac"], color="#3b82f6", ls=":", lw=1.4, label="A* (same episodes, trained stages)")
    if "unseen_evac" in base:
        a2.axhline(100 * base["unseen_evac"], color="#ef4444", ls=":", lw=1.4, label="A* (same episodes, unseen stages)")
    a2.set_ylabel("episodes fully evacuated (%)\n(the network actually playing)")
    a2.set_ylim(-2, 102)

    line(a3, "train_loss", color="#9ca3af", lw=1.6, label="training loss")
    a3.set_ylabel("loss")
    a3.set_xlabel("epoch  (dashed lines: a DAgger round starts)")
    for ax in (a1, a2, a3):
        ax.grid(alpha=0.25)
        for m in marks:
            ax.axvline(m, color="#6b7280", ls="--", lw=0.8, alpha=0.6)
        ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)
    fig.tight_layout()
    path = os.path.join(run_dir, CHART)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path
