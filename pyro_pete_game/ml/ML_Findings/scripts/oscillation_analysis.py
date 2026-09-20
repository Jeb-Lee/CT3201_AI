"""Do the clone's failures involve walking back and forth between two tiles?

Prompted by watching the recordings: wins look like "go in, search, rescue, leave";
failures look like normal play until, at some point, the agent paces between two
squares and then dies or gives up. This measures it instead of trusting an
impression: replay the same 100 seeded episodes (the seeds of the 240 s final
test) for A* and the v2 clone, log every tile the agent enters, and count
*reversals* (stepping back onto the tile it just left).

  ping-pong run   consecutive reversals, i.e. A,B,A,B,A... (4 reversals = 2.5 round trips)
  flagged         an episode whose longest ping-pong run is at least 6 reversals
  onset           when the first flagged run began, and how many occupants were out then

    python pyro_pete_game/ml/ML_Findings/scripts/oscillation_analysis.py
Writes data/oscillation.md and data/oscillation.csv.
"""

import csv
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pyro_pete_game"))

DATA = os.path.join(BASE, "data")
MODELS = {"v2": "imit_b_v2_route_hints", "v3": "imit_c_v3_memory", "v4": "imit_d_v4_trail"}
CAP, DT, FLAG_AT = 240.0, 1 / 30, 6
_POLICIES = {}
FRESH = "fresh" in sys.argv[1:]                       # the confirmation episodes (seeds 190,000+, 20 per stage)
SEED_BASE, EPS, SUFFIX = (190_000, 20, "_fresh") if FRESH else (90_000, 10, "")


def _init():
    import torch
    torch.set_num_threads(1)
    from ml.policy import load_policy
    for key, folder in MODELS.items():
        path = os.path.join(BASE, "imitation", folder, "final_model.zip")
        if os.path.isfile(path):
            _POLICIES[key] = load_policy(path)


def run(job):
    """One episode; returns the outcome and the reversal statistics."""
    agent_name, stage, seed = job
    from ml import evaluation
    from ml.outcome import summarise
    import levels
    from main import GameSession
    evaluation._ensure_pygame()
    random.seed(seed)
    if agent_name == "astar":
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="astar", policy=None)
    else:
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="learned", policy=_POLICIES[agent_name])
    keys = evaluation._NoKeys()
    cells = [s.agent.current_cell]
    times = [0.0]
    out_then = [0]
    while s.state == "playing" and s.agent_stats.elapsed < CAP:
        s.update(DT, keys)
        c = s.agent.current_cell
        if c != cells[-1]:
            cells.append(c)
            times.append(s.agent_stats.elapsed)
            out_then.append(s.victims_out)
    summary = summarise(s)
    # reversals: entering the tile it had just left
    rev = [1 if i >= 2 and cells[i] == cells[i - 2] else 0 for i in range(len(cells))]
    longest = cur = 0
    onset = long_start = None
    for i, r in enumerate(rev):
        cur = cur + 1 if r else 0
        if cur > longest:
            longest = cur
            long_start = i - cur + 1
        if cur == FLAG_AT and onset is None:
            onset = i - FLAG_AT + 1
    moves = max(1, len(cells) - 1)
    return dict(agent=agent_name, stage=stage, seed=seed, outcome=summary["outcome"],
                out=summary["victims_out"], total=summary["victims_total"], seconds=summary["seconds"],
                moves=moves, reversal_share=sum(rev) / moves, longest_pingpong=longest,
                flagged=int(longest >= FLAG_AT),
                onset_frac=(times[onset] / max(summary["seconds"], 1e-9)) if onset is not None else "",
                out_at_onset=out_then[onset] if onset is not None else "",
                long_onset_frac=(times[long_start] / max(summary["seconds"], 1e-9)) if longest >= FLAG_AT else "",
                out_at_longest=out_then[long_start] if longest >= FLAG_AT else "")


def main():
    import multiprocessing
    names = ["astar"] + [k for k in MODELS if os.path.isfile(os.path.join(BASE, "imitation", MODELS[k], "final_model.zip"))]
    if FRESH:
        names = [n for n in names if n in ("astar", "v2", "v4")]
    jobs = [(a, st, SEED_BASE + 1000 * st + i) for a in names for st in range(10) for i in range(EPS)]
    with multiprocessing.get_context("spawn").Pool(8, initializer=_init) as pool:
        rows = pool.map(run, jobs, chunksize=2)
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, f"oscillation{SUFFIX}.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def med(xs):
        xs = sorted(xs)
        return xs[len(xs) // 2] if xs else float("nan")

    lines = [f"Same {10 * EPS} seeded episodes per agent (240 s cap), deterministic clones. A back-and-forth run is "
             f"consecutive reversals; an episode is *flagged* if its longest run is at least {FLAG_AT} reversals.", "",
             "| agent | outcome | episodes | flagged (long ping-pong) | median longest run | median reversal share of moves |",
             "|---|---|---|---|---|---|"]
    for name in names:
        for outcome in ("evacuated", "died", "gave_up"):
            sub = [r for r in rows if r["agent"] == name and r["outcome"] == outcome]
            if not sub:
                continue
            fl = sum(r["flagged"] for r in sub)
            lines.append(f"| {'A*' if name == 'astar' else name + ' clone'} | {outcome} | {len(sub)} | "
                         f"{fl} ({100 * fl / len(sub):.0f}%) | {med([r['longest_pingpong'] for r in sub])} | "
                         f"{100 * med([r['reversal_share'] for r in sub]):.0f}% |")
    lines += ["", "Episodes flagged as long back-and-forth pacing (6+ reversals in a row): " +
              ", ".join(f"{('A*' if n == 'astar' else n)}: {sum(r['flagged'] for r in rows if r['agent'] == n)}"
                        for n in names) + f" (of {10 * EPS} each)."]
    fl_rows = [r for r in rows if r["agent"] == "v2" and r["flagged"] and r["onset_frac"] != ""]
    if fl_rows:
        lines += ["", "Flagged v2 episodes: the first long ping-pong began, on median, "
                      f"{100 * med([r['onset_frac'] for r in fl_rows]):.0f}% of the way through the episode, "
                      f"with a median of {med([r['out_at_onset'] for r in fl_rows])} occupants already out; "
                      f"{sum(1 for r in fl_rows if r['out_at_onset'] > 0)} of {len(fl_rows)} had already rescued someone."]
    gu = [r for r in rows if r["agent"] == "v2" and r["outcome"] == "gave_up" and r["out_at_longest"] != ""]
    if gu:
        short = [r["total"] - r["out_at_longest"] for r in gu]
        lines += ["", "The v2 clone's give-up episodes, at the start of their LONGEST back-and-forth run: "
                      f"median {100 * med([r['long_onset_frac'] for r in gu]):.0f}% of the way through; "
                      "occupants still to be delivered at that point: " +
                      ", ".join(f"{k} in {sum(1 for x in short if x == k)}" for k in sorted(set(short))) +
                      "; occupants out at the end: " +
                      ", ".join(f"{r['out']}/{r['total']}" for r in gu) + "."]
    with open(os.path.join(DATA, f"oscillation{SUFFIX}.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
