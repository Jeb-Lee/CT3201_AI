"""Per-stage performance of A*, v4 and v5, on episodes nobody has used before.

For every stage 1-10 and every agent it reports
  * how often it evacuated everyone, the clear time and the game score of those wins;
  * when it gave up: how many occupants it had found (spotted) and how many it had saved;
  * when it gave up: how much of the map it had viewed, in tiles.
"Viewed" = floor tiles inside the agent's fog-of-war "explored" set (everything it has been
within 3.5 tiles of) out of all floor tiles of the stage. Walls are not counted.

Episodes: seeds 950,000 + 1000 x stage + episode, 30 per stage per agent, 240 s cap, the same
episode for every agent. These seeds are separate from every set used to train, to select the
model, or to choose v5's teacher.

Models are the ones the game menu offers: ml/models/ai_v4.zip and ai_v5.zip (a model's own JSON
file tells the game which search order it was trained with).

    python .../stage_report.py [episodes_per_stage]      # writes data/stage_report.md and .csv
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
MODEL_DIR = os.path.join(ROOT, "pyro_pete_game", "ml", "models")
CAP, DT, SEED_BASE = 240.0, 1 / 30, 950_000
AGENTS = ("A*", "v4", "v5")
FILES = {"v4": "ai_v4.zip", "v5": "ai_v5.zip"}
_POLICY = {}


def _init():
    import torch
    torch.set_num_threads(1)
    from ml.policy import load_policy
    for name, file in FILES.items():
        path = os.path.join(MODEL_DIR, file)
        if os.path.isfile(path):
            _POLICY[name] = load_policy(path)


def run(job):
    agent, stage, seed = job
    from ml import evaluation
    from ml.outcome import summarise
    import levels
    from main import GameSession
    evaluation._ensure_pygame()
    random.seed(seed)
    if agent == "A*":
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="astar", policy=None)
    else:
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="learned", policy=_POLICY[agent])
    keys = evaluation._NoKeys()
    while s.state == "playing" and s.agent_stats.elapsed < CAP:
        s.update(DT, keys)
    r = summarise(s)
    tm = s.tilemap
    floor = [(c, rw) for rw in range(tm.rows) for c in range(tm.cols) if tm.tile_at(c, rw) != "#"]
    seen = sum(1 for cell in floor if cell in s.agent.explored)
    return dict(agent=agent, stage=stage + 1, seed=seed, outcome=r["outcome"], total=r["victims_total"],
                found=len(s.agent.known_victims), saved=r["victims_out"], score=r["score"],
                seconds=r["seconds"], floor_tiles=len(floor), viewed_tiles=seen,
                viewed_pct=round(100 * seen / len(floor), 1))


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def fmt(x, spec="{:.0f}"):
    return "-" if x is None else spec.format(x)


def report(rows, per_stage):
    lines = [f"{per_stage} episodes per stage per agent ({10 * per_stage} per agent), 240 s cap, identical episodes "
             f"for every agent (seeds {SEED_BASE:,}+). Give-up = the agent stopped with occupants still inside. "
             "'Found' = occupants it had spotted; 'saved' = led out; 'viewed' = share of the stage's floor tiles "
             "inside its explored set.", ""]
    for agent in AGENTS:
        sub = [r for r in rows if r["agent"] == agent]
        if not sub:
            continue
        lines += [f"## {agent}", "",
                  "| stage | episodes | evacuated | **clear time** (wins) | **score** (wins) | died | gave up | "
                  "**found** (give-ups) | **saved** (give-ups) | **map viewed** (give-ups) | map viewed (wins) |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        groups = [(str(st), [r for r in sub if r["stage"] == st]) for st in range(1, 11)]
        groups.append(("**all**", sub))
        for name, g in groups:
            wins = [r for r in g if r["outcome"] == "evacuated"]
            gu = [r for r in g if r["outcome"] == "gave_up"]
            died = [r for r in g if r["outcome"] == "died"]
            lines.append(
                f"| {name} | {len(g)} | {len(wins)} ({100 * len(wins) / len(g):.0f}%) | "
                f"{fmt(mean(r['seconds'] for r in wins), '{:.0f} s')} | {fmt(mean(r['score'] for r in wins))} | "
                f"{len(died)} | {len(gu)} | "
                f"{fmt(mean(r['found'] / r['total'] * 100 for r in gu), '{:.0f}%') if gu else '-'} "
                f"({fmt(mean(r['found'] for r in gu), '{:.1f}')} of {fmt(mean(r['total'] for r in gu), '{:.1f}')}) | "
                f"{fmt(mean(r['saved'] for r in gu), '{:.1f}') if gu else '-'} | "
                f"{fmt(mean(r['viewed_pct'] for r in gu), '{:.0f}%')} | "
                f"{fmt(mean(r['viewed_pct'] for r in wins), '{:.0f}%')} |")
        lines.append("")
    # side by side
    lines += ["## Side by side", "",
              "| stage | " + " | ".join(f"{a} evacuated" for a in AGENTS) + " | "
              + " | ".join(f"{a} clear time" for a in AGENTS) + " | " + " | ".join(f"{a} score" for a in AGENTS) + " |",
              "|---|" + "---|" * (3 * len(AGENTS))]
    for st in list(range(1, 11)) + ["all"]:
        cells_w, cells_t, cells_s = [], [], []
        for a in AGENTS:
            g = [r for r in rows if r["agent"] == a and (st == "all" or r["stage"] == st)]
            wins = [r for r in g if r["outcome"] == "evacuated"]
            cells_w.append(f"{100 * len(wins) / len(g):.0f}%" if g else "-")
            cells_t.append(fmt(mean(r["seconds"] for r in wins), "{:.0f} s"))
            cells_s.append(fmt(mean(r["score"] for r in wins)))
        lines.append(f"| {'**all**' if st == 'all' else st} | " + " | ".join(cells_w + cells_t + cells_s) + " |")
    return "\n".join(lines) + "\n"


def main():
    import multiprocessing
    per_stage = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    agents = [a for a in AGENTS if a == "A*" or os.path.isfile(os.path.join(MODEL_DIR, FILES[a]))]
    jobs = [(a, st, SEED_BASE + 1000 * st + i) for a in agents for st in range(10) for i in range(per_stage)]
    print(len(jobs), "episodes", flush=True)
    with multiprocessing.get_context("spawn").Pool(8, initializer=_init) as pool:
        rows = pool.map(run, jobs, chunksize=3)
    with open(os.path.join(DATA, "stage_report.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    text = report(rows, per_stage)
    with open(os.path.join(DATA, "stage_report.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
