"""Compare AI agents fairly.

Runs each agent through the real game -- the same GameSession the player
sees -- on the same stages with the same occupant placements, and reports
outcome rates and score with 95% confidence intervals.

Agents are named by a short spec:

    astar         the hazard-weighted A* planner (the game's default AI)
    random        a learned-brain agent choosing uniformly among legal moves
    stay          a learned-brain agent that never moves (the floor)
    model         the trained model at ml/models/ai_policy.zip
    model:PATH    a trained model somewhere else
    sample:PATH   that model choosing by *sampling* instead of the most likely
                  action (how training acts; the game uses the deterministic one)

Why the statistics matter: an episode is noisy (occupants are placed
randomly, collapses are random), so a handful of runs can point either
way. Earlier in this project a change appeared to cut deaths from 9 to 7
in 80 runs, and that gap was noise. Every result here therefore carries a
Wilson interval for rates and a normal interval for means, and comparisons
between agents are *paired*: episode i of stage s uses the same seed for
every agent, so each agent faces the same occupant layout and the same
first collapses. (Later collapses and smoke draw from the same random
stream, so runs drift apart as agents behave differently -- pairing removes
the biggest source of luck, not all of it.)

Command line: tools/evaluate_agents.py
"""

import math
import multiprocessing
import os
import random
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame                                   # noqa: E402

import levels                                   # noqa: E402
from main import GameSession                    # noqa: E402
from settings import SCREEN_WIDTH, SCREEN_HEIGHT  # noqa: E402
from ml.outcome import OUTCOMES, summarise      # noqa: E402
from ml.policy import RandomPolicy, StayPolicy, load_policy, MODEL_PATH  # noqa: E402

DT = 1 / 30


class _NoKeys:
    def __getitem__(self, key):
        return False


def episode_seed(base_seed, stage_index, episode):
    """Same for every agent, so each faces the same layout."""
    return base_seed + 1000 * stage_index + episode


def resolve_agent(spec, seed=0):
    """spec -> (agent_brain, policy) for GameSession."""
    if spec == "astar":
        return "astar", None
    if spec == "random":
        return "learned", RandomPolicy(seed)
    if spec == "stay":
        return "learned", StayPolicy()
    if spec == "model":
        return "learned", load_policy(MODEL_PATH)
    if spec.startswith("model:"):
        return "learned", load_policy(spec.split(":", 1)[1])
    if spec.startswith("sample:"):
        # the same model, but choosing by sampling its action probabilities
        # (what training measures) instead of always taking the most likely
        # action (what the game does). The gap between the two can be large.
        import torch
        torch.manual_seed(seed)
        policy = load_policy(spec.split(":", 1)[1])
        policy.deterministic = False
        return "learned", policy
    raise ValueError(f"unknown agent {spec!r} (astar, random, stay, model, model:PATH, "
                     f"sample:PATH)")


def _ensure_pygame():
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))


def run_episode(spec, stage_index, seed, max_seconds=240.0, policy=None):
    """One AI-only run of one stage. Returns a flat result dict.

    `policy` runs a policy object directly (training evaluates the model it
    is in the middle of learning); `spec` is then only the label."""
    _ensure_pygame()
    if policy is not None:
        brain = "learned"
    else:
        brain, policy = resolve_agent(spec, seed)
    random.seed(seed)      # occupant placement + collapses use the global RNG
    session = GameSession(levels.get(stage_index), spectate=True, agent_visual="drone",
                          stage_index=stage_index, agent_brain=brain, policy=policy)
    keys = _NoKeys()
    frame_cap = int(max_seconds / DT) * 2
    frames = 0
    while (session.state == "playing" and session.agent_stats.elapsed < max_seconds
           and frames < frame_cap):
        session.update(DT, keys)
        frames += 1
    result = summarise(session)
    result.update(agent=spec, stage=stage_index, seed=seed)
    return result


# -------------------------------------------------------------- multiprocess
def _init_worker():
    _ensure_pygame()


def _task(args):
    return run_episode(*args)


def evaluate(specs, stages, episodes, base_seed=1000, max_seconds=240.0,
             workers=1, progress=None):
    """Every agent x stage x episode. Returns a list of result dicts."""
    tasks = [(spec, st, episode_seed(base_seed, st, i), max_seconds)
             for spec in specs for st in stages for i in range(episodes)]
    if workers <= 1:
        results = []
        for n, task in enumerate(tasks, 1):
            results.append(_task(task))
            if progress:
                progress(n, len(tasks))
        return results
    ctx = multiprocessing.get_context("spawn")
    results = []
    with ctx.Pool(workers, initializer=_init_worker) as pool:
        for n, res in enumerate(pool.imap_unordered(_task, tasks, chunksize=2), 1):
            results.append(res)
            if progress:
                progress(n, len(tasks))
    results.sort(key=lambda r: (specs.index(r["agent"]), r["stage"], r["seed"]))
    return results


# ------------------------------------------------------------------- stats
def wilson(k, n, z=1.96):
    """Wilson score interval for a proportion: (low, high). Behaves sensibly
    at 0% and 100%, where the textbook normal interval does not."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def mean_ci(values, z=1.96):
    """(mean, half-width of a normal 95% interval)."""
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"))
    mean = sum(values) / n
    if n < 2:
        return (mean, float("nan"))
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return (mean, z * math.sqrt(var / n))


def summarise_group(rows):
    n = len(rows)
    out = {"n": n}
    for name in OUTCOMES:
        k = sum(1 for r in rows if r["outcome"] == name)
        out[name] = k / n if n else float("nan")
        out[name + "_ci"] = wilson(k, n)
    occ = [r["victims_out"] / r["victims_total"] for r in rows if r["victims_total"]]
    out["occupants_out"] = sum(occ) / len(occ) if occ else float("nan")
    out["score"], out["score_ci"] = mean_ci([r["score"] for r in rows])
    out["seconds"] = mean_ci([r["seconds"] for r in rows])[0]
    return out


def paired_score_difference(results, a, b):
    """Mean of (score_b - score_a) over episodes that both agents ran, with
    a 95% interval, plus how many episodes each agent alone evacuated."""
    by_a = {(r["stage"], r["seed"]): r for r in results if r["agent"] == a}
    by_b = {(r["stage"], r["seed"]): r for r in results if r["agent"] == b}
    keys = sorted(set(by_a) & set(by_b))
    diffs = [by_b[k]["score"] - by_a[k]["score"] for k in keys]
    only_a = sum(1 for k in keys if by_a[k]["outcome"] == "evacuated"
                 and by_b[k]["outcome"] != "evacuated")
    only_b = sum(1 for k in keys if by_b[k]["outcome"] == "evacuated"
                 and by_a[k]["outcome"] != "evacuated")
    mean, half = mean_ci(diffs)
    return {"n": len(keys), "mean": mean, "half": half,
            "only_a_evacuated": only_a, "only_b_evacuated": only_b}


# ------------------------------------------------------------------ report
def _pct(x):
    return "  n/a" if x != x else f"{100 * x:4.0f}%"


def _row(label, stage_label, s):
    lo, hi = s["evacuated_ci"]
    ci = f"[{100 * lo:3.0f}-{100 * hi:3.0f}]"
    score = "n/a" if s["score"] != s["score"] else (
        f"{s['score']:6.0f}" + ("" if s["score_ci"] != s["score_ci"] else f" +/-{s['score_ci']:4.0f}"))
    return (f"{label:<12} {stage_label:>5} {s['n']:>4}  {_pct(s['evacuated'])} {ci:<11}"
            f"{_pct(s['died'])}  {_pct(s['gave_up'])}  {_pct(s['timeout'])}   "
            f"{_pct(s['occupants_out'])}   {score:<16} {s['seconds']:6.1f}")


def format_report(results, specs, per_stage=True):
    lines = []
    header = (f"{'agent':<12} {'stage':>5} {'n':>4}  {'evac':>5} {'95% CI':<11}"
              f"{'died':>5}  {'gaveup':>5}  {'tmout':>5}   {'occ.out':>5}   "
              f"{'score (mean)':<16} {'secs':>6}")
    lines += [header, "-" * len(header)]
    for spec in specs:
        rows = [r for r in results if r["agent"] == spec]
        if per_stage:
            for st in sorted({r["stage"] for r in rows}):
                lines.append(_row(spec, str(st + 1), summarise_group(
                    [r for r in rows if r["stage"] == st])))
        lines.append(_row(spec, "ALL", summarise_group(rows)))
        if per_stage:
            lines.append("")
    if len(specs) > 1:
        lines.append(f"Paired comparison against '{specs[0]}' "
                     f"(same stage + seed => same occupant layout):")
        for other in specs[1:]:
            d = paired_score_difference(results, specs[0], other)
            half = "n/a" if d["half"] != d["half"] else f"{d['half']:.1f}"
            verdict = ""
            if d["half"] == d["half"]:
                verdict = ("  -> clearly better" if d["mean"] - d["half"] > 0
                           else "  -> clearly worse" if d["mean"] + d["half"] < 0
                           else "  -> not distinguishable from noise")
            lines.append(
                f"  {other:<12} score {d['mean']:+.1f} +/- {half} over {d['n']} pairs;"
                f" evacuated alone: {specs[0]} {d['only_a_evacuated']}, "
                f"{other} {d['only_b_evacuated']}{verdict}")
    return "\n".join(lines)


def write_csv(results, path):
    import csv
    fields = ["agent", "stage", "seed", "outcome", "victims_out", "victims_total",
              "victims_lost", "score", "damage", "seconds"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: r[k] for k in fields})
