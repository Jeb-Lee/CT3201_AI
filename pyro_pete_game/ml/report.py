"""Training logs, the epoch-vs-accuracy chart, and the review page.

A training run lives in one folder (runs/<name>/):

    epochs.csv            one row per epoch -- the "epoch vs accuracy" log
    evaluations.csv       held-out / training-stage tests at each checkpoint,
                          plus the A* baseline on the same episodes
    epoch_vs_accuracy.png the chart drawn from those two files
    report.html           chart + tables + the recordings, for review
    videos/               screen recordings of the model playing
    checkpoints/, best_model.zip, final_model.zip, config.json

Words, because reinforcement learning has no fixed dataset to score against:

    epoch      one iteration of training: collect a batch of play with the
               current policy, then update the network from it. (Not to be
               confused with the optimiser's passes over that one batch,
               which stable-baselines3 also calls n_epochs.)
    accuracy   the share of episodes in which the AI got every occupant that
               was still alive out and survived itself ("evacuated").
    train accuracy       measured on the last N episodes played *while
                         learning* (the policy is still exploring, so it is
                         a pessimistic, noisy number)
    validation accuracy  measured at checkpoints by playing fixed, seeded
                         episodes with the deterministic policy, on training
                         stages and on stages the model never trained on.

This module has no stable-baselines3 dependency: it only reads the CSVs, so
it can be run on any finished (or still running) folder:

    python tools/plot_training.py runs/<name>
"""

import csv
import html
import json
import os

EPOCH_FIELDS = [
    "epoch", "timesteps", "wall_seconds", "episodes_total",
    "window_episodes", "train_accuracy", "died", "gave_up", "timeout",
    "occupants_out", "score", "reward", "episode_len",
    "epoch_episodes", "epoch_accuracy",
    "policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction",
    "explained_variance", "learning_rate", "steps_per_second",
]

EVAL_FIELDS = [
    "epoch", "timesteps", "agent", "split", "stages", "episodes",
    "accuracy", "accuracy_lo", "accuracy_hi", "died", "gave_up", "timeout",
    "occupants_out", "score", "score_ci", "seconds",
]

CHART = "epoch_vs_accuracy.png"
REPORT = "report.html"


class CsvLog:
    """Append-only CSV that is safe to read while training is running:
    every row is flushed immediately, and an existing file is continued."""

    def __init__(self, path, fields):
        self.path, self.fields = path, fields
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        new = not os.path.isfile(path) or os.path.getsize(path) == 0
        self._fh = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=fields, extrasaction="ignore")
        if new:
            self._writer.writeheader()
            self._fh.flush()

    def write(self, row):
        self._writer.writerow({k: _fmt(row.get(k)) for k in self.fields})
        self._fh.flush()

    def close(self):
        self._fh.close()


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if value != value:
            return ""
        return f"{value:.6g}"
    return value


def read_csv(path):
    """Rows as dicts with numbers converted; [] if the file isn't there."""
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            row = {}
            for key, val in raw.items():
                if val in ("", None):
                    row[key] = None
                    continue
                try:
                    row[key] = int(val)
                except ValueError:
                    try:
                        row[key] = float(val)
                    except ValueError:
                        row[key] = val
            rows.append(row)
    return rows


def last_epoch(run_dir):
    rows = read_csv(os.path.join(run_dir, "epochs.csv"))
    return int(rows[-1]["epoch"]) if rows else 0


# --------------------------------------------------------------------- chart
_COLOURS = {"train": "#3b82f6", "heldout": "#ef4444", "rolling": "#9ca3af"}


def _series(rows, key):
    xs = [r["epoch"] for r in rows if r.get(key) is not None]
    ys = [r[key] for r in rows if r.get(key) is not None]
    return xs, ys


def _legend(ax):
    """Legend to the right of the axes so it never sits on the data."""
    handles, _ = ax.get_legend_handles_labels()
    if handles:
        ax.legend(fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False)


def plot_run(run_dir):
    """Draw epoch_vs_accuracy.png from the CSVs. Returns the path, or None
    if matplotlib isn't installed / there is nothing to draw yet."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    epochs = read_csv(os.path.join(run_dir, "epochs.csv"))
    evals = read_csv(os.path.join(run_dir, "evaluations.csv"))
    if not epochs and not evals:
        return None

    fig, (ax_acc, ax_score, ax_loss) = plt.subplots(
        3, 1, figsize=(13, 11), sharex=True,
        gridspec_kw={"height_ratios": [3, 2, 2]})

    # ---- accuracy vs epoch
    xs, ys = _series(epochs, "train_accuracy")
    if xs:
        ax_acc.plot(xs, [100 * y for y in ys], color=_COLOURS["rolling"], lw=1.6,
                    label="train accuracy (rolling, while learning)")
    for split in ("train", "heldout"):
        rows = [r for r in evals if r["agent"] == "model" and r["split"] == split]
        if rows:
            # held-out points sit a hair to the right so the two never hide each other
            shift = 0.006 * max([r["epoch"] for r in evals] + [1]) if split == "heldout" else 0
            x = [r["epoch"] + shift for r in rows]
            y = [100 * r["accuracy"] for r in rows]
            lo = [100 * (r["accuracy"] - r["accuracy_lo"]) for r in rows]
            hi = [100 * (r["accuracy_hi"] - r["accuracy"]) for r in rows]
            name = "validation, training stages" if split == "train" \
                else "validation, HELD-OUT stages"
            ax_acc.errorbar(x, y, yerr=[lo, hi], color=_COLOURS[split], marker="o",
                            capsize=3, lw=1.8, label=name)
        base = [r for r in evals if r["agent"] == "astar" and r["split"] == split]
        if base:
            ax_acc.axhline(100 * base[0]["accuracy"], color=_COLOURS[split], ls="--",
                           lw=1, alpha=0.7,
                           label=f"A* on the same {'training' if split == 'train' else 'held-out'} episodes")
    ax_acc.set_ylabel("accuracy  (% episodes fully evacuated)")
    ax_acc.set_ylim(-3, 103)
    ax_acc.set_title("Epoch vs accuracy")
    ax_acc.grid(alpha=0.25)
    _legend(ax_acc)

    # ---- game score vs epoch
    xs, ys = _series(epochs, "score")
    if xs:
        ax_score.plot(xs, ys, color=_COLOURS["rolling"], lw=1.6, label="train score (rolling)")
    for split in ("train", "heldout"):
        rows = [r for r in evals if r["agent"] == "model" and r["split"] == split]
        if rows:
            ax_score.errorbar([r["epoch"] for r in rows], [r["score"] for r in rows],
                              yerr=[r["score_ci"] or 0 for r in rows],
                              color=_COLOURS[split], marker="o", capsize=3, lw=1.8,
                              label=f"validation score, {split}")
        base = [r for r in evals if r["agent"] == "astar" and r["split"] == split]
        if base:
            ax_score.axhline(base[0]["score"], color=_COLOURS[split], ls="--", lw=1,
                             alpha=0.7, label=f"A* ({split})")
    ax_score.set_ylabel("mean game score")
    ax_score.grid(alpha=0.25)
    _legend(ax_score)

    # ---- what the optimiser is doing
    for key, colour in (("policy_loss", "#8b5cf6"), ("entropy", "#10b981")):
        xs, ys = _series(epochs, key)
        if xs:
            ax_loss.plot(xs, ys, color=colour, lw=1.4, label=key.replace("_", " "))
    ax_loss.set_ylabel("policy loss / entropy")
    ax_loss.grid(alpha=0.25)
    xs, ys = _series(epochs, "value_loss")
    if xs:
        twin = ax_loss.twinx()
        twin.plot(xs, ys, color="#f59e0b", lw=1.2, alpha=0.9, label="value loss")
        twin.set_ylabel("value loss")
        twin.set_yscale("log")
        h1, l1 = ax_loss.get_legend_handles_labels()
        h2, l2 = twin.get_legend_handles_labels()
        ax_loss.legend(h1 + h2, l1 + l2, fontsize=8, loc="center left",
                       bbox_to_anchor=(1.07, 0.5), frameon=False)
    else:
        _legend(ax_loss)
    ax_loss.set_xlabel("epoch  (one epoch = one batch of play + one network update)")

    fig.tight_layout()
    path = os.path.join(run_dir, CHART)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return path


# -------------------------------------------------------------------- report
def _pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _eval_table(evals):
    if not evals:
        return "<p>No validation runs yet.</p>"
    rows = []
    for r in evals:
        agent = "A* (baseline)" if r["agent"] == "astar" else "model"
        split = {"train": "training stages", "heldout": "HELD-OUT stages"}.get(
            r["split"], r["split"])
        ci = ""
        if r.get("accuracy_lo") is not None:
            ci = f" ({_pct(r['accuracy_lo'])}&ndash;{_pct(r['accuracy_hi'])})"
        score = "n/a" if r.get("score") is None else f"{r['score']:.0f}"
        rows.append(
            f"<tr><td>{r['epoch']}</td><td>{r['timesteps']:,}</td><td>{agent}</td>"
            f"<td>{split}</td><td>{r['episodes']}</td>"
            f"<td><b>{_pct(r['accuracy'])}</b>{ci}</td><td>{_pct(r['died'])}</td>"
            f"<td>{_pct(r['gave_up'])}</td><td>{_pct(r['timeout'])}</td>"
            f"<td>{_pct(r['occupants_out'])}</td><td>{score}</td></tr>")
    return ("<table><tr><th>epoch</th><th>steps</th><th>agent</th><th>split</th>"
            "<th>n</th><th>accuracy (95% CI)</th><th>died</th><th>gave up</th>"
            "<th>timeout</th><th>occupants out</th><th>score</th></tr>"
            + "".join(rows) + "</table>")


def _videos(run_dir):
    vdir = os.path.join(run_dir, "videos")
    if not os.path.isdir(vdir):
        return "<p>No recordings yet.</p>"
    names = sorted(n for n in os.listdir(vdir) if n.lower().endswith((".mp4", ".gif")))
    if not names:
        return "<p>No recordings yet.</p>"
    cards = []
    for n in names:
        src = f"videos/{html.escape(n)}"
        media = (f'<img src="{src}" loading="lazy">' if n.lower().endswith(".gif")
                 else f'<video src="{src}" controls preload="none" muted></video>')
        cards.append(f'<figure>{media}<figcaption>{html.escape(n)}</figcaption></figure>')
    return '<div class="videos">' + "".join(cards) + "</div>"


def write_report(run_dir, live=False):
    """Rebuild report.html. live=True adds a 30-second auto-refresh so the
    page can stay open in a browser while training runs."""
    plot_run(run_dir)
    epochs = read_csv(os.path.join(run_dir, "epochs.csv"))
    evals = read_csv(os.path.join(run_dir, "evaluations.csv"))
    config = {}
    cfg_path = os.path.join(run_dir, "config.json")
    if os.path.isfile(cfg_path):
        with open(cfg_path, encoding="utf-8") as fh:
            config = json.load(fh)

    latest = ""
    if epochs:
        e = epochs[-1]
        latest = (f"epoch <b>{e['epoch']}</b> &middot; {e['timesteps']:,} steps &middot; "
                  f"train accuracy <b>{_pct(e.get('train_accuracy'))}</b> over the last "
                  f"{e.get('window_episodes')} episodes")
    chart = (f'<img class="chart" src="{CHART}?v={len(epochs)}_{len(evals)}">'
             if os.path.isfile(os.path.join(run_dir, CHART)) else
             "<p>(chart needs matplotlib: pip install matplotlib)</p>")
    cfg_rows = "".join(f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
                       for k, v in config.items())
    final = ""
    final_path = os.path.join(run_dir, "final_report.txt")
    if os.path.isfile(final_path):
        with open(final_path, encoding="utf-8") as fh:
            final = ("<h2>Final test (fresh seeds, held-out stages)</h2><pre>"
                     + html.escape(fh.read()) + "</pre>")
    refresh = '<meta http-equiv="refresh" content="30">' if live else ""
    page = f"""<!doctype html>
<html><head><meta charset="utf-8">{refresh}
<title>Training review - {html.escape(os.path.basename(os.path.abspath(run_dir)))}</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1f2430}}
 h1{{margin-bottom:0}} .sub{{color:#666;margin-top:4px}}
 table{{border-collapse:collapse;margin:8px 0;font-size:13px}}
 td,th{{border:1px solid #ddd;padding:3px 8px;text-align:right}} th{{background:#f3f4f6}}
 td:first-child,th:first-child{{text-align:left}}
 .chart{{width:100%;max-width:1000px}}
 .videos{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}}
 figure{{margin:0}} video,img{{width:100%;border-radius:6px;background:#000}}
 figcaption{{font-size:12px;color:#555}} pre{{background:#f6f7f9;padding:10px;overflow:auto;font-size:12px}}
 .note{{background:#fff8e1;border-left:4px solid #f5b400;padding:8px 12px;font-size:13px}}
</style></head><body>
<h1>Training review</h1>
<p class="sub">{html.escape(os.path.abspath(run_dir))}{' &middot; <i>live: refreshes every 30 s</i>' if live else ''}</p>
<p>{latest}</p>
{chart}
<div class="note"><b>Reading the chart.</b> Accuracy = the share of episodes where the AI
got everyone still alive out and survived. The grey line is measured on the episodes played
<i>while learning</i> (noisy: the policy is still exploring). Blue and red points are
<i>validation</i>: fixed seeded episodes, deterministic policy, on training stages (blue) and on
stages the model has never trained on (red, the honest one). Dashed lines are the A* AI on the
same episodes. Bars are 95% intervals; if they overlap, the difference is not established.</div>
<h2>Validation runs</h2>{_eval_table(evals)}
{final}
<h2>Recordings</h2>{_videos(run_dir)}
<h2>Settings</h2><table>{cfg_rows}</table>
<p class="sub">Data: epochs.csv (every epoch), evaluations.csv (every checkpoint).</p>
</body></html>"""
    path = os.path.join(run_dir, REPORT)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path
