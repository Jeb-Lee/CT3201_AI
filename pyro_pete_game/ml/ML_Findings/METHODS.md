# Methods

How the learned agent, the environment, the training runs and the evaluation
are set up, so that every number in [FINDINGS.md](FINDINGS.md) and
[REWARD_EVOLUTION.md](REWARD_EVOLUTION.md) can be checked and reproduced.

## 1. The task

*Pyro Pete: Emergency Evacuation* is a top-down game with ten stages of
increasing difficulty. Occupants are trapped in a burning maze. Fire spreads,
smoke slows movement and hides tiles, electrical panels spark, ceilings
collapse, and one stage element is a locked door with a key. A rescuer leads
occupants to the exit. In *Watch AI Play* mode an AI rescuer plays alone.

The AI already had a working player: a hazard-weighted A* planner
(`entities/rescue_agent.py`). The research question is whether a *learned*
policy can do the same job, as an optional second brain that never replaces
A*:

> Can a neural network trained by reinforcement learning, seeing only what the
> A* agent is allowed to see, learn to lead occupants out of the burning
> building?

A stage ends when everyone still alive is out, or nobody alive can act (the
game's own rules, unchanged). An episode of the environment is one stage played
by the AI alone.

## 2. Agents

| | A* rescuer (default) | Learned rescuer (`entities/learned_agent.py`) |
|---|---|---|
| decides | plans a route with hazard-weighted A*, replans every 0.25 s | asks a neural network which way to step |
| body | health, fire damage, smoke slowdown, vision, sprites | **the same class**, so identical rules |
| knows the map | only tiles it has explored | only tiles it has explored |
| knows hazards / occupants | within vision radius (3.5 tiles) | within vision radius (3.5 tiles) |
| knows head-count, exit, fire countdown | yes (all on the human's HUD) | yes |
| gives up | when its search is not worth the risk | after 12 s without a successful step |

**Fair information.** The learned agent is held to what A* is allowed to know.
Unexplored tiles are flagged as unexplored and show nothing else (a test checks
this, `tests/test_ml.py`). Only Pete is human-driven; the learned brain never
controls Pete.

## 3. Observation and actions

A flat `float32` vector of 1,102 numbers:

* **Window**: 11 x 11 tiles centred on the agent, 9 channels each: wall,
  blocked, unexplored, fire, smoke, panel, exit, occupant, key.
* **13 scalar features**: health, share of occupants escorted / out / unclaimed
  / lost / spotted, exit direction (dx, dy) and path distance, fire countdown,
  whether the exit is on fire, whether a key is still needed, elapsed time.

**Actions** are five discrete moves: stay, up, down, left, right. A move walks
to the adjacent tile with the game's own movement (about 12 simulation frames;
smoke slows it); "stay" lasts 8 frames. Choosing a wall is a wasted step and
costs a little reward. Illegal moves are masked out for `MaskablePPO`.

## 4. Environment

`ml/env.py`: a Gymnasium environment stepping the real `GameSession` (nothing
is re-implemented). It passes `gymnasium.utils.env_checker.check_env`, and the
same seed gives the same episode. Simulation step 1/30 s. Episode cap: 90 s of
game time in these experiments (the default in the code is 240 s).

The reward function is the subject of its own document,
[REWARD_EVOLUTION.md](REWARD_EVOLUTION.md).

## 5. Learner

| setting | value |
|---|---|
| algorithm | `MaskablePPO` (sb3-contrib 2.9.0 on stable-baselines3 2.9.0) |
| network | MLP, two hidden layers of 256 (separate policy and value heads) |
| parallel environments | 6 (separate processes) |
| steps per environment per epoch | 512, so **3,072 steps per epoch** |
| minibatch / optimiser passes | 256 / 4 |
| learning rate, discount, GAE lambda | 3e-4 (constant), 0.995, 0.95 |
| entropy coefficient | 0.01 |
| clip range | 0.2 (library default) |
| reward scaling | running-return normalisation of the *reward only* (`VecNormalize`); observations untouched, so a saved model needs no extra state |
| device | CPU |

An **epoch** in this project is one iteration: collect a batch (3,072 steps) with
the current policy, then update the network. (Stable-baselines3 also uses
"epochs" for the optimiser's passes over that one batch; those are the
"4" above.)

Stages: experiments 01-07 **train on stages 1-3 and validate on stage 4**. This is
a deliberately small, easy setting so each run takes a few minutes; the
script's default is train 1-7, held-out 8-10.

## 6. Evaluation

* **Accuracy** = the share of episodes that end `evacuated`: the AI survived and
  everyone still alive got out. Other endings: `died`, `gave_up` (stood still
  12 s), `timeout` (the clock ran out while still moving).
* **Train accuracy** is measured on the last 100 episodes played *while
  learning*, with the sampled (exploring) policy.
* **Validation accuracy** is measured at checkpoints on fixed, seeded episodes
  with the *deterministic* policy (highest-probability action), on training
  stages and on held-out stages, beside A* on the identical episodes.
* Intervals: Wilson 95% for proportions (well behaved at 0% and 100%), normal
  95% for means. Comparisons between agents are paired by seed.
* Seed bases, all different: validation 50,000; run-level final test 90,000;
  sampled behaviour 80,000; reward accounting 70,000; freeze diagnostic 60,000;
  common final test 90,000 (stages 1-4, 10 episodes each); baselines 1,000.
  Episode seed = base + 1000 x stage + episode (some scripts use 100 x stage).
* Two ways to act with the same network: **deterministic** (always the most
  likely action; what the game and the validation curve use) and **sampled**
  (choose by the network's probabilities; what training acts like). The
  harness agent specs are `model:PATH` and `sample:PATH`. The gap between them
  turned out to matter a great deal (FINDINGS F8).

**Known limits of this measurement**

* Occupant placement, debris and smoke use Python's global random generator.
  The harness seeds it per episode, so two agents face the same *starting*
  layout; later random events drift apart as the agents behave differently.
  Pairing removes the largest source of luck, not all of it.
* The deterministic validation policy of a barely-trained network is
  degenerate (see Finding E7 in FINDINGS.md), so early validation numbers say
  nothing about whether learning is happening.
* Selecting the best checkpoint on held-out episodes makes that number
  slightly optimistic; the run script therefore finishes with a test on fresh
  seeds.

## 7. Software and hardware

Python 3.13.14, pygame 2.6.1, numpy 2.5.2, gymnasium 1.3.0,
stable-baselines3 2.9.0, sb3-contrib 2.9.0, torch 2.14.0 (CPU), matplotlib
3.11.2, ffmpeg 2025-02-06 (recordings). Windows 11, 12 logical CPUs, an RTX 3050
laptop GPU that was **not used** (the CPU build of PyTorch is installed; see
FINDINGS E9: 87% of a training epoch is game simulation). Training speed about
550-650 steps/s with 6 environments when a run has the machine to itself,
and about 115-360 steps/s per run when runs overlap (and less in total).

## 8. Reproducing

```bash
pip install -r requirements.txt -r requirements-ml.txt
python tools/evaluate_agents.py --agents astar,random,stay --episodes 20 --workers 4 --csv baselines.csv
python tools/train_agent.py --runs-dir runs --name exp01_plain_s0 --seed 0 \
   --timesteps 100000 --n-envs 6 --eval-every 25000 --eval-episodes 4 \
   --train-stages 1-3 --heldout-stages 4 --max-seconds 90 --record-stages 1 --record-every 2
# abandon / give-up / timeout variants: --abandon-penalty 100, --give-up-penalty 200, --timeout-penalty 200
python pyro_pete_game/ml/ML_Findings/scripts/collect_runs.py     # copy curated run files here
python pyro_pete_game/ml/ML_Findings/scripts/make_figures.py     # redraw every figure from the CSVs
```

Exact settings for every run are in `experiments/<run>/config.json`.
