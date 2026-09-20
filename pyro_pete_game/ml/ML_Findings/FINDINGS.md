# Learning to rescue: what a reinforcement-learning agent did with a faithful reward

*Pyro Pete: Emergency Evacuation -- machine-learning findings*
*Data collected 2026-09-20. All numbers trace to files in this folder.*

> **Correction, added the same day as the first version and after it was pushed.**
> These documents originally said the learned agent was "held to exactly what A\*
> is allowed to know". **That was false.** A* plans over the whole real map and
> the live hazard field everywhere; only the occupants' positions are hidden from
> it. The learned agent's observation (an 11 x 11 window of tiles it had walked
> near) gave it strictly *less*. What this changes:
>
> * **Unaffected:** everything about the reward and the optimiser: the price list
>   and its prediction of each run's return, the abandon-penalty arithmetic, the
>   collapse to standing still, the sampled-versus-deterministic gap, training
>   reproducibility, and the GPU finding. None of those depend on what the
>   observation contains.
> * **Reframed:** every learned-versus-A\* comparison is a *local-view learner
>   against a global-view planner*, so "0 of 40 vs 39 of 40" is not a like-for-like
>   contest. The explanations offered in F9 (partial map memorisation, no memory
>   of where other occupants are) are now confounded with the learner simply not
>   being able to see the layout A* plans over.
> * **Follow-up:** [IMITATION.md](IMITATION.md) measures how much of the gap this
>   accounts for, using an observation that adds A\*-equivalent route information.

## Abstract

We asked whether a neural network trained by reinforcement learning could
replace a hand-written A* planner as the AI rescuer in a burning-building
game, from a local view of the building (as I first described it, "the same
information the planner has"; that turned out to be wrong, see the correction
below). We built a Gymnasium environment over the real game, a local-view
observation, a
`MaskablePPO` learner, an evaluation harness with confidence intervals, and
tooling that logs every epoch and records the agent playing.

The learner did **not** learn to rescue. With a reward that mirrors the game
score, all three seeds learned to **stand still**: by 50,000 steps "give up"
overtook "die" as the most common ending, and by 100,000 steps 74-91% of
episodes ended that way, with no full evacuation in any run (A* evacuates 86%
of episodes). This is not a malfunction: we measured what each behaviour earns
and stand-still (about -1) beats wandering (about -142) by 142 points, while
random play never produced a rescue in 200 episodes. That price list predicted
each run's logged return to within about 3 points.

The interesting part is what happened next. A penalty for leaving occupants
inside, which I expected to fix this, did not: it lands equally on standing
still and on dying, leaving the gap between them **exactly unchanged**.
Pricing the other failures out (a penalty for giving up, then for timing out
too) did not move the collapse where I predicted. The agent did not slide to
the next cheapest ending; it kept dying, and in one of two seeds it kept
exploring and, over 300,000 steps, learned to lead about a fifth of the
occupants out: one person at a time, only on the stages it trained on, and
none on a stage it had not seen. A hypothesis I proposed for the remaining
standing still (freezing near fire) was tested and not supported; those
give-ups happen at the spawn tile. Most importantly for the game: in the form
it would use (the most likely action), **11 of 12 trained models stand still in
100% of fresh episodes and the twelfth dies or gives up**, and none evacuated
anyone: 0 of 40 episodes each, against 39 of 40 for A*. Two of my six
pre-registered predictions (P1 and P3) were wrong in some clause, and a third
(P4) held only trivially; all are reported that way.

The main lesson is about reward design rather than about this game: an
optimiser ranks the behaviours it can currently produce, and it will find the
cheapest failure. The full account is in
[REWARD_EVOLUTION.md](REWARD_EVOLUTION.md).

---

## 1. Question and setup

*Can a neural network trained with RL, from a local view of the building,
learn to lead occupants out of a burning building?* The learned agent is an
optional AI brain; A* stays the default and Pete is never ML-driven.

The learned agent shares the A* agent's body (health, damage, smoke, vision) so
both face identical rules; only the decision differs. It sees an 11 x 11 window
of explored tiles plus 13 scalars (1,102 numbers) and picks one of five moves.
Full details: [METHODS.md](METHODS.md).

Every training result here is for **stages 1-3, validated on stage 4, at
100,000 steps and three seeds per setting unless stated otherwise**.

## 2. Findings

Numbering: **F** = findings about learning; **E** = engineering findings.

### F1. The ceiling and the floor are well separated

| agent (20 episodes x 10 stages) | full evacuation | occupants led out |
|---|---|---|
| A* | **86%** (95% CI 81-91) | led someone out in 181 of 200 episodes |
| random legal moves | 0% (0-2) | **0 of 200** episodes |
| stand still | 0% (0-2) | 0 of 200 |

A* is weakest on stages 7 and 10 (55% and 65%). ![baselines](figures/fig_baselines.png)

### F2. The plain reward is gamed: the agent learns to do nothing

Three seeds, identical settings. The share of episodes ending in "gave up"
(stood still 12 s) overtook "died" at **epoch 19, 18 and 16** (49k-58k steps) and
reached **91%, 80% and 74%** by 100k steps. Full evacuation: **0%** in every
seed. Policy entropy had already dropped from 1.09 to below 0.6 by epochs
9-12, before the crossover: the network became decisive before it had found
anything to be decisive about. ![outcomes](figures/fig_reward_vs_behaviour.png)

### F3. The reward's price list predicts the run

Measured on 30 seeded episodes per behaviour (`data/reward_accounting.md`):
standing still returns **-0.6**, wandering **-142.3** (it always dies), A*
**+396.5**. Multiplying a run's outcome shares by those prices predicts its
logged return: **-5 vs -6, -7 vs -8** (plain seeds 0, 1) and **-405/-408/-411 vs
-405/-405/-408** (abandon seeds). The optimiser is responding to exactly this
list. ![prices](figures/fig_price_of_failure.png)

### F4. A penalty that lands equally on two failures does not separate them

The abandon penalty (100 per occupant inside at the end) shifted stand-still
from -0.6 to -333.9 and dying from -142.3 to -475.6: **the gap is 141.7 in
both**. My original reasoning (make giving up expensive, so the agent must
try) compared absolute costs; the optimiser compares differences. What the
penalty did change is the payoff of succeeding relative to standing still
(397 -> 717 points), which only matters if a success is ever sampled. Result: a
slower, partial collapse (42-50% stood still) and, in three seeds, **zero
rescues in 99 epochs**.

### F5. Rescues do occur under the plain reward, rarely, and they do not save the run

Contrary to my written prediction, two of three plain-reward seeds led
occupants out during training (seed 0: 9 of 33 epochs, peak 1.8% of
occupants; seed 2: 23 of 33 epochs, peak 8.5%). No seed ever produced a *full*
evacuation. So the picture is not "success is never seen" but "success is rare
and partial, and the penalties for trying are frequent and certain."

### F6. Pricing failures out did not move the collapse where I predicted

I predicted that a give-up penalty would move the collapse to timing out (the
next cheapest ending), and a give-up-plus-timeout penalty would move it to
dying. Neither happened as written ([REWARD_EVOLUTION.md](REWARD_EVOLUTION.md),
sections 6 and 7):

* **Give-up penalty 200 (2 seeds, 100k steps):** seed 0 stopped giving up (0%)
  but timed out only 17% (I predicted >= 50%) and led 7.2% of occupants out
  (I predicted 0); seed 1 still gave up in **30%** of episodes, timed out 23%
  and rescued nobody.
* **Both penalties (1 seed):** 87% died, 12% still gave up (the most expensive
  ending), and the mean return ended at **-151, below the random starting
  policy's -142**. Dying is where it started; it never left.

The refined reading: the optimiser goes to the cheapest failure *it can reach*.
Doing nothing is reachable at once; safe pacing needs a skill. That was
formed after seeing the data and is supported by the pattern, not by a direct
test.

### F7. More training

| run | steps | what happened |
|---|---|---|
| abandon penalty (v2) | 300k | **0 rescues in 98 epochs**; the outcome mix drifts (25-75% giving up) |
| plain reward, seed 2, continued | 100k -> 401k | still 62-98% giving up; occupants led out 7.8% -> 13.5%; full evacuation <= 4% |
| **give-up penalty (v3), seed 0** | 300k | occupants led out **7% -> 23%**, plateau near 20% from ~150k; full evacuation 1-5%; return -142 -> -29 |

Only the give-up-penalty run made sustained progress, and it is one seed.
![long runs](figures/fig_long_run.png)

### F8. The policy the game would use is not the policy that was trained

Training acts by sampling from the network's probabilities. The game (and the
validation curve) takes the most likely action. On identical fresh episodes
(stages 1-4, 10 each, `data/common_final_test.md`):

| | evacuated everyone | led any occupant out | stood still all episode |
|---|---|---|---|
| A* | **39 of 40 (98%)** | 98% of occupants | |
| 12 models, **deterministic** | **0 of 40 each** | 0% (all 12) | 11 models: 100%; the twelfth (v3 long) died 55%, gave up 35% |
| 12 models, **sampled** | **0 of 40 each** | 4 of 12 lead some out (6-11% of occupants) | |

A model that only rescues when sampling would look broken if installed in the
game. It also means that the near-flat validation curves during training were
not hiding progress in the early runs (E7); they were reporting the truth about
the *deployed* policy, which never rescued anyone.

### F9. Where the rescues happen, and what they are

For the four models that rescue anyone, on fresh seeds and sampling:

* **Only on trained stages, and on one or two of them.** Rescues were on stage 3
  for three models (22-40% of occupants there) and on stages 1 and 3 for v3 long
  (27% and 18%),
  and **never on stage 4, which none of them trained on (0 of 40 each; A* 90%)**.
  Each stage's maze is fixed, so the likely reading is partial map memorisation;
  it was not isolated.
* **One person, rarely two.** For the v3-long model, 9 rescuing episodes led out
  one occupant, 3 led out two, none three. In the recorded clip it led one
  occupant to the exit and then stayed near it until the fire killed it.
* **What changed inside the network:** the share of decisions that are "stay"
  went from 0.36 (untrained) to about 0.8 in every collapsed run, and back down
  to 0.49 and 0.55 in the two runs that made partial progress
  (`data/behaviour_by_checkpoint.csv`).

### F10. A hypothesis of mine that failed

I proposed that the standing still which survived a 200-point penalty was
*freezing near fire*. Tested on 30 sampled episodes per model: 71-100% of
give-ups never left the spawn tile, and fire was in view in 36-57% of them, which
a random walker also has (43%) after 12 s. **Not supported.** The give-ups are a
learned decision at the start of the episode.

### F11. Shown A*'s decisions and A*'s information, the network plays

The follow-up study ([IMITATION.md](IMITATION.md)) trains the same kind of network to copy A*
(behaviour cloning, then DAgger). With only a local window it evacuates **20%** of episodes; given
A*'s own information (parity enforced by tests) **77-80%** (A* 87% over the same 300 episodes);
adding a memory of its own path helps by a few points (v4: 80%, paired p ~ 0.04) and cuts
back-and-forth pacing (A* never does it), though a first-test gain of 7 points did **not**
replicate on fresh seeds (a registered prediction, P10, was falsified). It is roughly level with A*
on stages it trained on (84% vs 87%) and **clearly behind on unseen stages (71% vs 87%)**; it does
not match A* (25 episodes to 4, p ~ 0.0001). Unlike the RL models, **both its deterministic and
sampled policies work**. **This reframes F1-F10:** the RL learner had less information than A*
(see the correction box at the top), so those results compare a local-view learner against a
global-view planner, and the imitation study shows the information gap alone accounts for most of
the difference between 0% and about 80%.

### E-findings (engineering, each of which changed a decision)

* **E1. Eight trials per stage cannot resolve a small difference.** A change to
  A* appeared to cut deaths from 9 to 7 in 80 runs; that gap is noise. Every rate
  now carries a Wilson interval and comparisons are paired by seed. *(raw runs
  not preserved)*
* **E2. Non-reproducible A*.** Ties in `min()` over a set were broken by memory
  address, so one seeded episode could play out differently on a second
  attempt. Fixed with a `(distance, cell)` tie-break; guarded by a test.
* **E3. Throughput x3.0 from one cache.** 40% of environment time was
  re-reading sprite PNGs on every reset. 189 -> 575 steps/s.
  ![engineering](figures/fig_engineering.png)
* **E4. Reward scale.** Returns in the hundreds gave a value loss near 987;
  scaling rewards for the optimiser only brought it to about 8.
* **E5. A library name collision** (`info["episode"]`) that would have crashed
  return logging; found by reading the library rather than by a failure.
* **E6. Concurrency was slower in total.** Three runs at once got about 115
  steps/s each (345 total); one alone gets about 550. Runs were therefore
  executed one at a time.
* **E7. Deterministic validation is uninformative early.** An untrained
  network's highest-probability action is arbitrary, and here it is "stay",
  so the deterministic policy stands still at step 0 *and* at step 100k, and
  validation is flat zero for a trivial reason. The collapse is visible only
  with *sampled* actions, which is what training uses. Consequence: training
  curves and sampled behaviour, not early validation numbers, are the right
  evidence of what is being learned. `scripts/behaviour_by_checkpoint.py`
  measures behaviour with sampled actions.
* **E8. A process error.** Testing the `--install` option with a 40-second
  untrained run wrote a worthless model to the real model path. Noticed
  immediately, used once for a valid check (a real stable-baselines3 model
  loads and runs through the actual game menu), then deleted.

* **E9. A GPU would not help here.** The machine has an RTX 3050 (6 GB); the
  installed PyTorch is the CPU build. Timing four epochs split as: **87%
  collecting play** (the Python game simulation plus choosing actions), **11%
  the network update**, 1% other (measured while another run shared the CPU,
  so absolute times are inflated but the split is what matters). A GPU can
  only speed up that 11%, so even an infinitely fast one saves at most about a
  tenth, and for a network this small (two layers of 256) transfers to and from
  the GPU usually cost more than they save. Stable-baselines3's own guidance
  is to run MLP policies on the CPU. The real ceiling is the simulation, which
  is CPU-bound Python. A GPU would matter for a much bigger network (for
  example a convolutional one over a larger window) or for large supervised
  imitation datasets; `tools/train_agent.py --device cuda` is already
  supported if a CUDA build of PyTorch is installed.
* **E10. Training is exactly reproducible.** Experiment 07 uses the same seed
  and settings as experiment 04 seed 0, and its first 33 epochs match that run
  in all 12 logged columns, losses included (33 of 33 rows identical). Same
  seed, same machine, same code: same run, to the last logged digit. This is
  what makes a single-seed difference attributable to the seed rather than to
  noise in the tooling.

## 3. Predictions versus outcomes

Written before the runs ([PREDICTIONS.md](PREDICTIONS.md)). **A prediction that
was wrong is reported as wrong.**

| prediction | outcome |
|---|---|
| P1a: no seed leads an occupant out (100k, plain and abandon) | **Falsified for plain seeds 0 and 2.** Abandon seeds: held. |
| P1b: plain seeds end with >= 60% giving up | **Held** (91, 80, 74%) |
| P1c: abandon does not collapse to giving up more than plain | **Held** (42-50% vs 74-91%) |
| P1d: 0% full evacuation everywhere | **Held** |
| P2: long run, still no rescues | **Held**, at 300k steps rather than the planned 500k (0 rescues in 98 epochs) |
| P3: give-up penalty moves collapse from "gave up" to "timed out" (gave up <= 10%, timeouts >= 50%, 0 rescues) | **Not supported.** Seed 0: gave up 0% (held), timeouts 17% (failed), rescues 7.2% (failed). Seed 1: gave up 30% (failed), timeouts 23% (failed), rescues 0 (held). |
| P4: give-up + timeout penalties move it to "died" (>= 70%) | **Held as written** (87%), but uninformative: dying is where training started. Return fell to -151, below the random start. |
| P5: continued seed-2 run keeps rescuing more, accuracy stays under 20% | **Held** (7.8% -> 13.5% of occupants, peak 18%; full evacuation <= 4%; A* far ahead). Budget was +300k steps, not +400k. |
| P6: give-up-penalty run keeps improving to 300k, accuracy stays under 20% | **Held** (7.2% -> 22.9% of occupants; peak accuracy 5%; A* 98%). |

## 4. Threats to validity and limits

* **Small, easy setting.** Stages 1-3, 100k steps, one architecture, one
  algorithm, one observation design, three seeds (two for one setting, one for
  another). These are diagnostic experiments, not a tuned attempt at a strong
  agent.
* **Small validation sets.** 4 episodes per stage per checkpoint. Validation
  intervals are wide; the outcome mix over the last 100 *training* episodes is
  far better resolved.
* **Deterministic validation is degenerate early** (E7).
* **Randomness outside the seed.** Occupant placement, debris and smoke use
  Python's global generator; the harness seeds it per episode, so agents face
  the same starting layout, but events later in an episode diverge as behaviour
  diverges.
* **The pacing-timeout price is computed, not measured.** Give-up, die and A*
  prices are measured over 30 episodes each.
* **No hyperparameter search.** The learning rate, entropy coefficient and
  network size were fixed at reasonable defaults. A larger entropy coefficient
  could well delay the collapse; that is untested.
* **Resumed run (exp06)** loses the reward-normalisation statistics at the
  restart.
* **The observation itself may be too limited:** an 11 x 11 window with no
  memory. This has not been isolated as a cause.
* **Selection of what to report.** The experiment set was extended after
  seeing early results (replicates, then exp03-06). The predictions were fixed
  before each new set was run, and both the earlier and later results are
  reported.

## 5. What this does and does not show

**Supported:** in this setup, with random exploration as the starting point,
(a) a reward that mirrors the game score is optimised by standing still;
(b) the per-ending price list explains the behaviour quantitatively;
(c) an end-of-episode penalty that applies to all failures equally does not
change the ranking of failures; (d) pricing the cheap failures out did not
move the collapse to the next cheapest ending but left the agent exploring,
and in one of two seeds a partial rescue skill grew over 300,000 steps (about
a fifth of occupants, one at a time, only on trained stages); (e) none of that
survives into the policy the game would use (F8).

**Not shown:** that RL cannot solve this game, that PPO is unsuited to it, or
that any of the proposed remedies work. None of them was run.

## 6. Open questions and next experiments

1. **Imitation warm start from A\*: done**, see [IMITATION.md](IMITATION.md) (it
   works: 80% with A*'s information). What remains from this idea is the *RL fine-tune*
   from the clone, anchored to A*'s behaviour, which is the step that could go beyond A*.
2. **Curriculum** from an easier, fire-free map. *Prediction:* full evacuation
   appears within 100k steps on the easy map.
3. **Potential-based shaping** on distance to the exit or frontier
   (policy-invariant in theory). *Prediction:* rescues without the collapse.
4. **Larger entropy coefficient** and **memory** (recurrent policy). Cheap, and
   would separate "no signal" from "premature commitment".
5. A **larger sweep** (seeds, entropy, learning rate) to see how fragile the
   collapse timing is.

## 7. Related work and background

* Schulman et al., *Proximal Policy Optimization Algorithms* (2017),
  arXiv:1707.06347 -- the learning algorithm.
* Raffin et al., *Stable-Baselines3* (JMLR 2021); Towers et al., *Gymnasium*
  (2024), arXiv:2407.17032 -- the software.
* Huang and Ontanon, *A Closer Look at Invalid Action Masking in Policy
  Gradient Algorithms* (2020), arXiv:2006.14171 -- the action masking used.
* Ng, Harada and Russell, *Policy Invariance Under Reward Transformations*
  (ICML 1999) -- potential-based shaping.
* Amodei et al., *Concrete Problems in AI Safety* (2016), arXiv:1606.06565, and
  Krakovna et al., *Specification gaming* (DeepMind, 2020) -- reward
  hacking / specification gaming, of which F2 is a small instance.
* Henderson et al., *Deep Reinforcement Learning that Matters* (AAAI 2018),
  arXiv:1709.06560 -- why seeds and intervals matter.
* Ross, Gordon and Bagnell, *A Reduction of Imitation Learning...* (AISTATS
  2011), and Bengio et al., *Curriculum Learning* (ICML 2009) -- the proposed
  remedies.
* Wilson (1927), *J. Amer. Statist. Assoc.* 22 -- the interval used for
  proportions.

## 8. What is in this folder

See [README.md](README.md).
