"""Stalling: how common is it, what is the network doing when it stalls, and what is it worth?

Prompted by the project owner's reading of the v4 recordings: the failures look like the
network getting confused and pacing, either undecided between two paths or not knowing what
to do. Four claims, each tested here on the same seeded episodes (both 240 s test sets, 300
episodes per agent, deterministic policies):

  1. how many of the failures involve stalling?             (analyse)
  2. what is the network doing while it stalls?             (analyse)
       - undecided between goals: does the move it makes alternate between following
         different goals' route hints?
       - not knowing what to do: how confident is it, does it follow any hint at all,
         does it ever choose to stay?
  3. is stalling a higher-stage problem?                    (analyse, by stage)
  4. would eliminating it raise the success rate?           (counterfactual)
       - whenever the network stalls, A* takes the next few decisions. This borrows A*, so it is
         NOT a result for the network: it is an upper bound on what fixing stalling is worth.

Stall = in the last 16 tiles it entered, at most 3 different tiles (strict back-and-forth
between two tiles is the special case; small loops are caught too). An episode is *stalled*
if that held at 10 or more moments.

    python .../stall_analysis.py analyse
    python .../stall_analysis.py counterfactual
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
IMIT = os.path.join(BASE, "imitation")
MODELS = {"v2": "imit_b_v2_route_hints", "v4": "imit_d_v4_trail"}
CAP, DT = 240.0, 1 / 30
WINDOW, MAX_DISTINCT, FLAG_MOMENTS = 16, 3, 10
OVERRIDE_STEPS = int(os.environ.get("STALL_STEPS", "10"))
GOALS = ("exit", "occupant", "frontier", "key")
_POLICIES = {}


def _init():
    import torch
    torch.set_num_threads(1)
    from ml.policy import load_policy
    for key, folder in MODELS.items():
        _POLICIES[key] = load_policy(os.path.join(IMIT, folder, "final_model.zip"))


def stalled(cells):
    return len(cells) >= WINDOW and len(set(cells[-WINDOW:])) <= MAX_DISTINCT


class Recorder:
    """Wraps a policy: records, at each decision, what it did and how sure it was; optionally
    hands control to A* while the agent is stalled (the counterfactual)."""

    def __init__(self, inner, override=False):
        self.inner, self.override = inner, override
        self.obs_version = inner.obs_version
        self.agent = self.session = None
        self.log = []
        self.override_left = 0
        self.overrides = 0

    def act(self, observation, mask):
        import numpy as np
        import torch
        from ml.observation import OBS_SIZE, HINT_FIELDS, ACTION_STAY
        from ml.expert import expert_action
        a = self.agent
        hist = getattr(a, "cell_history", [])
        stall_now = stalled(hist)
        if self.override:
            if stall_now and self.override_left == 0:
                self.override_left = OVERRIDE_STEPS
                self.overrides += 1
            if self.override_left > 0:
                self.override_left -= 1
                return expert_action(a, self.session.victims)
        action = self.inner.act(observation, mask)
        model = self.inner.model
        with torch.no_grad():
            dist = model.policy.get_distribution(torch.as_tensor(observation, dtype=torch.float32).unsqueeze(0),
                                                 action_masks=np.asarray(mask).reshape(1, -1))
            probs = dist.distribution.probs[0].numpy()
        top = float(probs.max())
        entropy = float(-(probs[probs > 0] * np.log(probs[probs > 0])).sum())
        # which goals' best move is this action?
        n = len(HINT_FIELDS)
        hints = observation[OBS_SIZE:OBS_SIZE + n * len(GOALS)]
        agreed = []
        for g in range(len(GOALS)):
            block = hints[g * n:(g + 1) * n]
            if block[0] == 1.0:
                adv = block[1:5]
                best = int(np.argmax(adv)) + 1
                if action == best and adv.max() > 0:
                    agreed.append(g)
        self.log.append((stall_now, action == ACTION_STAY, top, entropy, tuple(agreed)))
        return action


def run_episode(job):
    agent_name, stage, seed, mode = job
    from ml import evaluation
    from ml.outcome import summarise
    import levels
    from main import GameSession
    evaluation._ensure_pygame()
    random.seed(seed)
    rec = None
    if agent_name == "astar":
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="astar", policy=None)
    else:
        rec = Recorder(_POLICIES[agent_name], override=(mode == "counterfactual"))
        s = GameSession(levels.get(stage), spectate=True, agent_visual="drone", stage_index=stage,
                        agent_brain="learned", policy=rec)
        rec.agent, rec.session = s.agent, s
    keys = evaluation._NoKeys()
    cells = [s.agent.current_cell]
    entries_stalled = 0
    while s.state == "playing" and s.agent_stats.elapsed < CAP:
        s.update(DT, keys)
        c = s.agent.current_cell
        if c != cells[-1]:
            cells.append(c)
            if stalled(cells):
                entries_stalled += 1
    summary = summarise(s)
    out = dict(agent=agent_name, stage=stage, seed=seed, outcome=summary["outcome"], out=summary["victims_out"],
               total=summary["victims_total"], seconds=summary["seconds"], stall_moments=entries_stalled,
               stalled=int(entries_stalled >= FLAG_MOMENTS), overrides=rec.overrides if rec else 0)
    # per-decision detail, split into stalled and not-stalled moments
    for label in ("stall", "normal"):
        rows = [r for r in (rec.log if rec else []) if r[0] == (label == "stall")]
        out[f"{label}_n"] = len(rows)
        out[f"{label}_stay"] = sum(1 for r in rows if r[1])
        out[f"{label}_conf"] = sum(r[2] for r in rows)
        out[f"{label}_entropy"] = sum(r[3] for r in rows)
        out[f"{label}_nogoal"] = sum(1 for r in rows if not r[4])
        out[f"{label}_multi"] = sum(1 for r in rows if len(r[4]) >= 2)
        pairs = [(a[4], b[4]) for a, b in zip(rows, rows[1:]) if len(a[4]) == 1 and len(b[4]) == 1]
        out[f"{label}_pairs"] = len(pairs)
        out[f"{label}_switch"] = sum(1 for x, y in pairs if x != y)
    return out


def episodes():
    jobs = []
    for base, per in ((90_000, 10), (190_000, 20)):
        for st in range(10):
            for i in range(per):
                jobs.append((st, base + 1000 * st + i))
    return jobs


def run_all(agents, mode):
    import multiprocessing
    jobs = [(a, st, seed, mode) for a in agents for st, seed in episodes()]
    with multiprocessing.get_context("spawn").Pool(8, initializer=_init) as pool:
        return pool.map(run_episode, jobs, chunksize=3)


def pct(k, n):
    return "n/a" if n == 0 else f"{100 * k / n:.0f}%"


def analyse():
    rows = run_all(["astar", "v2", "v4"], "analyse")
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "stall_analysis.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = [f"Stall = at most {MAX_DISTINCT} different tiles among the last {WINDOW} entered; an episode is stalled if that "
             f"held at {FLAG_MOMENTS}+ moments. 300 episodes per agent (both 240 s test sets), deterministic.", ""]

    lines += ["## 1. How many episodes stall, and how many failures involve a stall", "",
              "| agent | episodes | stalled | won | of the wins, stalled | failed | of the failures, **stalled** |",
              "|---|---|---|---|---|---|---|"]
    for a in ("astar", "v2", "v4"):
        sub = [r for r in rows if r["agent"] == a]
        won = [r for r in sub if r["outcome"] == "evacuated"]
        lost = [r for r in sub if r["outcome"] != "evacuated"]
        lines.append(f"| {'A*' if a == 'astar' else a} | {len(sub)} | {sum(r['stalled'] for r in sub)} ({pct(sum(r['stalled'] for r in sub), len(sub))}) "
                     f"| {len(won)} | {sum(r['stalled'] for r in won)} | {len(lost)} | "
                     f"**{sum(r['stalled'] for r in lost)} ({pct(sum(r['stalled'] for r in lost), len(lost))})** |")
    lines += ["", "Failures by kind, and whether they stalled (v4):", "", "| ending | episodes | stalled |", "|---|---|---|"]
    for kind in ("died", "gave_up"):
        sub = [r for r in rows if r["agent"] == "v4" and r["outcome"] == kind]
        lines.append(f"| {kind} | {len(sub)} | {sum(r['stalled'] for r in sub)} ({pct(sum(r['stalled'] for r in sub), len(sub))}) |")

    lines += ["", "## 2. What is the network doing while it stalls?", "",
              "| v4 | decisions | mean confidence (top probability) | mean entropy | chose to STAY | follows **no** goal's best move | switches goal from one move to the next |",
              "|---|---|---|---|---|---|---|"]
    v4 = [r for r in rows if r["agent"] == "v4"]
    for label, name in (("stall", "while stalled"), ("normal", "otherwise")):
        n = sum(r[f"{label}_n"] for r in v4)
        pairs = sum(r[f"{label}_pairs"] for r in v4)
        lines.append(f"| {name} | {n} | {sum(r[f'{label}_conf'] for r in v4) / max(1, n):.2f} | "
                     f"{sum(r[f'{label}_entropy'] for r in v4) / max(1, n):.2f} | "
                     f"{pct(sum(r[f'{label}_stay'] for r in v4), n)} | {pct(sum(r[f'{label}_nogoal'] for r in v4), n)} | "
                     f"{pct(sum(r[f'{label}_switch'] for r in v4), pairs)} (of {pairs} pairs) |")
    lines += ["", "Same, for v2:", "", "| v2 | decisions | mean confidence | mean entropy | chose to STAY | follows no goal's best move | switches goal |",
              "|---|---|---|---|---|---|---|"]
    v2 = [r for r in rows if r["agent"] == "v2"]
    for label, name in (("stall", "while stalled"), ("normal", "otherwise")):
        n = sum(r[f"{label}_n"] for r in v2)
        pairs = sum(r[f"{label}_pairs"] for r in v2)
        lines.append(f"| {name} | {n} | {sum(r[f'{label}_conf'] for r in v2) / max(1, n):.2f} | "
                     f"{sum(r[f'{label}_entropy'] for r in v2) / max(1, n):.2f} | {pct(sum(r[f'{label}_stay'] for r in v2), n)} | "
                     f"{pct(sum(r[f'{label}_nogoal'] for r in v2), n)} | {pct(sum(r[f'{label}_switch'] for r in v2), pairs)} (of {pairs}) |")

    lines += ["", "## 3. By stage: share of episodes that stall", "", "| stage | A* | v2 | v4 |", "|---|---|---|---|"]
    for st in range(10):
        cells = []
        for a in ("astar", "v2", "v4"):
            sub = [r for r in rows if r["agent"] == a and r["stage"] == st]
            cells.append(f"{sum(r['stalled'] for r in sub)}/{len(sub)}")
        lines.append(f"| {st + 1}{' (unseen)' if st >= 7 else ''} | " + " | ".join(cells) + " |")
    for title, stages in (("trained 1-7", range(7)), ("unseen 8-10", range(7, 10))):
        cells = []
        for a in ("astar", "v2", "v4"):
            sub = [r for r in rows if r["agent"] == a and r["stage"] in stages]
            cells.append(f"{sum(r['stalled'] for r in sub)}/{len(sub)} ({pct(sum(r['stalled'] for r in sub), len(sub))})")
        lines.append(f"| **{title}** | " + " | ".join(cells) + " |")
    text = "\n".join(lines) + "\n"
    with open(os.path.join(DATA, "stall_analysis.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


def counterfactual():
    base = run_all(["v2", "v4"], "analyse")
    fixed = run_all(["v2", "v4"], "counterfactual")
    from ml.evaluation import wilson
    lines = [f"Whenever the network stalls, A* takes the next {OVERRIDE_STEPS} decisions. This borrows A*, so it is an "
             "UPPER BOUND on what eliminating stalling is worth, not a result for the network. Same 300 episodes.", "",
             "| network | as trained | with stalls broken by A* | change | episodes A* had to step in | won only with the help | lost only with the help |",
             "|---|---|---|---|---|---|---|"]
    for a in ("v2", "v4"):
        b = {(r["stage"], r["seed"]): r for r in base if r["agent"] == a}
        f = {(r["stage"], r["seed"]): r for r in fixed if r["agent"] == a}
        wb = sum(r["outcome"] == "evacuated" for r in b.values())
        wf = sum(r["outcome"] == "evacuated" for r in f.values())
        gained = sum(f[k]["outcome"] == "evacuated" and b[k]["outcome"] != "evacuated" for k in b)
        lost = sum(b[k]["outcome"] == "evacuated" and f[k]["outcome"] != "evacuated" for k in b)
        helped = sum(1 for r in f.values() if r["overrides"] > 0)
        lo1, hi1 = wilson(wb, len(b))
        lo2, hi2 = wilson(wf, len(f))
        lines.append(f"| {a} | {pct(wb, len(b))} ({100 * lo1:.0f}-{100 * hi1:.0f}) | **{pct(wf, len(f))}** ({100 * lo2:.0f}-{100 * hi2:.0f}) | "
                     f"{100 * (wf - wb) / len(b):+.0f} points | {helped} | {gained} | {lost} |")
    a_star = read_astar_rate()
    lines += ["", f"For reference, A* on these 300 episodes: {a_star}."]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(DATA, f"stall_counterfactual_{OVERRIDE_STEPS}.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(os.path.join(DATA, f"stall_counterfactual_{OVERRIDE_STEPS}.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fixed[0]))
        w.writeheader()
        w.writerows(fixed)
    print(text)


def read_astar_rate():
    try:
        rows = [r for r in csv.DictReader(open(os.path.join(DATA, "stall_analysis.csv"), encoding="utf-8")) if r["agent"] == "astar"]
        k = sum(r["outcome"] == "evacuated" for r in rows)
        return f"{100 * k / len(rows):.0f}% ({k} of {len(rows)})"
    except OSError:
        return "see pooled_300.md (87%)"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "analyse"
    counterfactual() if mode == "counterfactual" else analyse()
