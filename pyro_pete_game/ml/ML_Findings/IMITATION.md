# Imitation learning: teaching the network to play like A*

*Data collected 2026-09-20, after the reinforcement-learning study in
[REWARD_EVOLUTION.md](REWARD_EVOLUTION.md) and [FINDINGS.md](FINDINGS.md).
Every number below traces to a file in this folder.*

## Summary

Reinforcement learning from scratch never produced a network that rescued
anyone in the form the game uses (0 of 40 fresh episodes). This study asks the
next question: **if the network is shown A\*'s own decisions, how close can it
get?** It depends on whether the network sees what A* sees, and, to a smaller
extent, on whether it can remember where it has been.

Deterministic policies (what the game uses), 240 s cap, ten stages, fully evacuated:

| | first test, 100 episodes | fresh test, 200 episodes | **pooled, 300 episodes** |
|---|---|---|---|
| **A\*** (hand-written) | 91% (84-95) | 85% (79-89) | **87%** (83-90) |
| v4: A*'s information + full-episode memory | 87% (79-92) | 76% (70-82) | **80%** (75-84) |
| v3: + short memory | 84% (76-90) | not tested | |
| v2: A*'s information, no memory | 80% (71-87) | 75% (69-80) | **77%** (72-81) |
| v1: only a local window | 20% (13-29) | not tested | |
| best reinforcement-learning model | 0 of 40 (stages 1-4) | | |

* **Information was the biggest factor, and it is robust.** Same everything else, giving
  the network A*'s own information moved it from 20% to 80% (v1 to v2).
* **Memory helps, modestly.** Long back-and-forth pacing between two tiles (which A*
  never does) fell from 19 to 5 episodes of 100, and from 39 to 15 of 200 on fresh
  episodes: **that replicated**. Evacuation rose by less: +7 points on the first test,
  **+1 on the fresh one**, +3 pooled (v4 won 15 episodes v2 lost, and lost 5; sign test
  p ~ 0.04). The fresh test also **falsified a prediction I registered before running it**
  (P10); see 4.8.
* **On the stages it trained on the clones are roughly 3-5 points below A\*, not clearly
  distinguishable** (pooled: v4 84% against A*'s 87%). **On the three unseen stages they
  are clearly behind**: v4 71% (61-79) against 87% (78-92).
* **It does not match A\*.** Over the same 300 episodes A* won 25 that v4 lost and v4 won 4
  that A* lost (p ~ 0.0001).
* **Where the remaining gap is:** memory turned pacing deaths into give-ups. v4 dies less
  (8% against 12%) and leads out more occupants (90% against 87%), but gives up as often
  (12%), mostly one occupant short. That endgame stall, not pacing, is now the main loss.

![Pooled](figures/fig_imitation_pooled.png)

*Two independent test sets pooled (300 episodes). The chart below is the first 100-episode test only.*

![Headline, first test set](figures/fig_imitation_headline.png)

## 1. Why imitation, and what was asked

The RL runs collapsed because random exploration never found a rescue, so the
reward never taught anything about succeeding. Imitation removes that problem:
the training example is "what the agent saw" and the answer is "the tile A*
stepped to", scored by **action-match accuracy**, a real accuracy in the usual
sense, logged every epoch. There is no reward to prefer standing still to; A*
stands still in only 1.1% of its decisions, so the data does not teach it.

## 2. The rule that governs everything: the learner and A* get the same conditions

The requirement, stated by the project owner: *the model and A\* must get the same
conditions, or training will not work, or the model will have God mode.* Both
halves are real. If the learner sees less than A*, the teacher's move is not a
function of what the student sees, so it cannot be learned. If it sees more, the
comparison is meaningless.

### 2.1 What A* actually knows (read from the code, after I first got it wrong)

| | A* |
|---|---|
| the maze layout | **all of it**: it plans over the whole real map |
| fire, smoke, sparking panels, a pending collapse | **all of it, live, everywhere**: its route costs read the live hazard field |
| where the exit and the key are; how many occupants there are | all of it (the HUD shows a human the exit direction and head-count) |
| where an occupant is | **only within 3.5 tiles**; once spotted, remembered |
| its "explored" set | used **only** to choose which unseen area to search next |

**Correction.** Earlier documents in this folder said the learner was "held to
exactly what A\* is allowed to know". That was false: the original observation
(version 1) showed only an 11 x 11 window of tiles the agent had walked near. It
is corrected in METHODS.md and in the FINDINGS correction box. I made the claim
without reading A*'s planner, and read it only when the poor unseen-stage result
made me check.

### 2.2 Version 2 of the observation, and how parity is enforced

Version 2 = version 1 + **24 route hints**: for each of A*'s four candidate goals
(the exit; the nearest spotted, not-yet-rescued occupant; the nearest unexplored
frontier; the key, while a locked door is in the way) the hazard-weighted path
cost from the agent, how much each of the four moves shortens it, and whether the
goal exists. They are computed with **A*'s own path costs from A*'s own inputs**.
The network still has to decide *which goal to pursue and when*.

Parity is enforced by tests (`tests/test_imitation.py`), not just stated:

| test | what it proves |
|---|---|
| `test_moving_an_occupant_the_agent_has_not_spotted_changes_nothing_it_sees` (v1 and v2) | **no God mode**: relocating an occupant the agent has not spotted changes no number in the observation, and not A*'s own decision |
| `test_spotting_an_occupant_does_change_what_the_learner_sees` | **no less than A\***: once spotted, it shows |
| `test_the_hints_read_only_agent_knowledge_not_the_list_of_all_occupants` | the hints ignore the list of all occupants |
| `test_the_learner_and_a_star_share_one_body_and_one_game` | same stage seed gives the same map, key, exit, occupants, fires, speed, health, spawn |
| `test_the_exit_hint_points_the_way_a_star_would_step` | a hint agrees with A*'s real first step |
| `test_every_stage_starts_behind_a_locked_door_so_the_key_is_the_first_goal` | the key hint exists because A* needs it |
| `test_best_epoch_is_chosen_on_seen_stages_not_unseen` | model selection never peeks at the unseen stages |

### 2.3 The other conditions

* **Same game and body.** One `GameSession`, one agent body class (health,
  damage, smoke slowdown, speed, 3.5-tile vision); only the decision differs.
* **Same episodes.** Every comparison uses identical seeded episodes (same map,
  occupants, hazards), paired.
* **Same decision opportunity.** The clone acts in one-tile steps; A* replans
  continuously. Checked: A* playing *through the network's own interface*
  evacuates **88%** (n=100) against native A*'s **86%** (81-91, n=200), so the
  interface loses nothing.
* **Same time cap: a correction.** My experiments used a 90 s cap for speed. **The
  real game has no hard time limit** (only a speed-bonus reference at 90 s and a
  fire that reaches the exit after minutes). A cap penalises the slower agent:
  A* never needs more than 78 s (median 39), the clone is slower. Re-running the
  identical episodes at 240 s lifted the clone (deterministic, unseen stages
  47% to 60%; sampled 60% to 73%) and turned every "ran out of time" ending into
  something more informative (section 4.5). **The 240 s numbers are primary
  throughout;** the 90 s ones are in `data/imitation_summary.md`.
* **One remaining asymmetry, small.** A* may end a stage early at the exit when
  searching further is "not worth the health"; the learner instead idles at the
  exit for 12 s and is scored as giving up. Both count as "not everyone out".
  A* does it in 1 of 100 episodes; the clone's give-ups are analysed in 4.5.

### 2.4 Every stage starts behind a locked door

Measured in `data/spawn_reachability.md`: on **all ten stages the exit is
unreachable at spawn**, and on nine the spawn pocket is only 3-45 tiles out of
116-319. The key is always reachable inside it. The first job on every stage is
fetching the key. Version 1 had to find it through a small window; that is a large
part of why it failed.

## 3. Method

* **Demonstrations.** A* plays 120 episodes on each of stages 1-7 through the
  network's own one-tile-step interface (840 episodes); every decision is
  recorded as (observation, the move A* chose). Only the episodes where A*
  evacuated everyone are imitated (83%). Labels are stay/up/down/left/right =
  1.1 / 17 / 30 / 16 / 37%, and never an illegal move.
* **Held-out data.** 20 further episodes per training stage (do the network's
  moves match A*'s on new episodes of familiar mazes?) and 30 per stage on **stages
  8-10, which it never trains on**.
* **Network.** The same MaskablePPO policy the RL runs use: two hidden layers of
  256, five actions with illegal moves masked. Cross-entropy on A*'s labels, Adam
  (learning rate 1e-3 falling to 5e-5), batch 512, 30 epochs.
* **DAgger, 4 rounds.** A network that only ever saw A*'s states can drift into
  states A* never visited. Each round lets the *network* drive (A* drives with
  probability 0.5, 0.3, 0.1, then 0), has A* label every state reached, adds them
  (18-29k states per round), and trains 12 more epochs.
* **Two runs, identical except for the observation:** `imit_a` (v1, local window)
  and `imit_b` (v2, route hints). Same seeds, data, network, hyperparameters.
* **Final test:** 10 fresh episodes on each of the ten stages (seeds nobody
  trained or validated on), A* and each network on the same episodes, both the
  deterministic policy and a sampled one.
* **Hardware:** CPU. Training a network this small takes seconds per epoch; the
  cost is the game simulation. A GPU was not needed (FINDINGS E9).

## 4. Results

### 4.1 Epoch versus accuracy

![Epoch vs accuracy](figures/fig_imitation_epoch_vs_accuracy.png)

*Top: how often the network picks the move A\* picks. Middle: how often the network
actually evacuates everyone when it plays (small samples; the dashed lines are A\*
on the same episodes). Bottom: training loss. Dotted lines mark DAgger rounds.*

| | v1 (local window) | **v2 (A\*'s information)** |
|---|---|---|
| action match, held-out episodes, epoch 5 | 87.3% | **95.2%** |
| ... unseen stages, epoch 5 | 76.8% | **90.0%** |
| after cloning (epoch 30): training / held-out / **unseen** | 97.1 / 90.1 / **76.6** | 99.9 / 96.9 / **93.4** |
| after DAgger (epoch 78): training / held-out / **unseen** | 96.7 / 92.0 / **76.1** | 100.0 / 99.3 / **97.2** |

Two things to notice. v1's accuracy on unseen stages is **flat at about 76-78%
for the whole run**: more training and DAgger cannot supply information the
network cannot see. And v2's unseen-stage accuracy (97%) is close to its
trained-stage accuracy (99%), so what it learned transfers.

### 4.2 Accuracy of the network *playing* (240 s cap, primary)

| | trained 1-7 (n=70) | unseen 8-10 (n=30) | all ten (n=100) |
|---|---|---|---|
| A* | 94% (86-98) | 83% (66-93) | 91% (84-95) |
| **v2 clone, deterministic** | **89%** (79-94) | **60%** (42-75) | **80%** (71-87) |
| v2 clone, sampled | 90% (81-95) | 73% (56-86) | 85% (77-91) |
| v1 clone, deterministic | 29% (19-40) | 0% (0-11) | 20% (13-29) |
| v1 clone, sampled | 37% (27-49) | 0% (0-11) | 26% (18-35) |

Occupants led out: A* 94 / 86 / 92%; v2 deterministic 93 / 79 / 89%; v2 sampled
92 / 89 / 91%. Full table with deaths and give-ups: `data/imitation_summary.md`.

*These are the first test set (100 episodes). A fresh 200-episode confirmation gave A* 85%, v2 75%, v4 76%; see 4.8.*

The information ablation is the clean comparison: **v1 to v2, everything else
identical, moves the all-ten deterministic rate from 20% to 80%.**

### 4.3 By stage

![By stage](figures/fig_imitation_by_stage.png)

| stage | A* | v2 deterministic | v2 sampled |
|---|---|---|---|
| 1 | 10/10 | 10/10 | 10/10 |
| 2 | 10/10 | 10/10 | 10/10 |
| 3 | 10/10 | 8/10 | 9/10 |
| 4 | 9/10 (36/40 led out) | 9/10 (**39/40** led out) | 9/10 |
| 5 | 9/10 | 8/10 | 9/10 |
| 6 | 10/10 | 9/10 | 9/10 |
| 7 | 8/10 | 8/10 | 7/10 |
| 8 (unseen) | 9/10 | 6/10 | 8/10 |
| 9 (unseen) | 9/10 | 7/10 | 8/10 |
| 10 (unseen) | 7/10 (42/60 led out) | 5/10 | 6/10 (**50/60** led out) |

On stages 1-2 the clone is A*. The gap opens on the large unseen mazes. On stage
4 (deterministic) and stage 10 (sampled) the clone leads out *more* occupants
than A* did on those episodes, but these are 10-episode counts and I do not read
anything into them.

### 4.4 DAgger

For v2, the network's own play (on training-stage seeds, A* labelling) evacuated
86%, 79%, 83% and 88% of episodes across the four rounds while A*'s help dropped
from 50% of the decisions to none: the clone holds up when it drives alone. For v1
the same measure **fell** as A* let go: 77%, 55%, 45%, 32%. Game tests after each
round (28 and 18 episodes, wide intervals) went 57% to 82% on trained stages for
v2 after the first round, and stayed near 80%.

### 4.5 Where the clone still fails

![Outcomes](figures/fig_imitation_outcomes.png)

On unseen stages the deterministic v2 clone ends 60% evacuated, 17% dead, 23%
gave up, 0% ran out of time. **The gave-up endings are almost all one occupant
short:**

| | gave up | occupants still inside |
|---|---|---|
| A* | 1 of 100 | 1 left in 1 |
| v2 deterministic | 10 of 100 | 1 left in **9**, 2 left in 1 |
| v2 sampled | 8 of 100 | 1 left in **7**, 2 left in 1 |

The clone rescues everyone it finds, then stops before finding the last person.
That is the **endgame decision**: A* decides whether searching further is worth
the fire damage it would cost (`_worth_exploring`: the round-trip damage of the
route against a share of its health). **That number is not in the observation.**
The hints give the *path cost* to the nearest unexplored area, but not the
*damage* along it, so the clone cannot compute A*'s call and errs toward
"go and wait at the exit". This is a **hypothesis from the pattern (9 of 10), not
tested**; the natural test is a version 3 that adds the estimated route damage
and health-budget ratio as features, which are A* inputs and so consistent with
the parity rule.

Before the cap was corrected these episodes were recorded as "ran out of time":
the clone was slower, not stuck, and the difference matters.

**It is also slower, and the fire is a clock.** Median seconds to finish an episode
(240 s cap, `data/imitation_240s.md`):

| | trained 1-7 | unseen 8-10 | all ten |
|---|---|---|---|
| A* | 34 | **53** | 39 |
| v2 clone, deterministic | 35 | **76** | 42 |
| v2 clone, sampled | 35 | **72** | 42 |

On familiar mazes it is as fast as A*; on the large unseen ones it takes about
40% longer, and the spreading fire punishes that: it dies in 17% of unseen-stage
episodes against A*'s 13%. In the recorded stage 9 episode A* finished in 73.6 s
while the clone died at 98 s with nobody out.

### 4.6 The back-and-forth pattern (found by watching the recordings)

*This section exists because of an observation by the project owner, made while
watching the clips: when the network wins it does the normal thing (go in, search,
rescue, leave); when it fails it does the same thing until, at some point, it gets
confused, paces between two squares, and then dies or gives up. I measured it
rather than trust the impression* (`scripts/oscillation_analysis.py`,
`data/oscillation.md`).

Method: replay the same 100 seeded episodes for A* and the v2 clone, log every
tile entered, and count *reversals* (stepping back onto the tile just left). An
episode is flagged if it contains 6 or more reversals in a row.

![Pacing](figures/fig_imitation_pingpong.png)

| | episodes | flagged | median longest run | reversals as a share of moves |
|---|---|---|---|---|
| A* (91 won, 8 died, 1 gave up) | 100 | **0** | 1 | 3% |
| v2 clone, evacuated | 80 | 6 (8%) | 1 | 4% |
| v2 clone, died | 10 | 3 (30%) | 1 | 4% |
| **v2 clone, gave up** | 10 | **10 (100%)** | **103** | **47%** |

* **A\* never does it.** Not once in 100 episodes.
* **All ten of the clone's give-ups in this set contain a long run**, a median of 103
  reversals in a row and nearly half of all its moves (**but see the replication below: on
  fresh episodes it is 60%, not 100%**). Deaths less so (3 of 10), and 6 of 80 wins
  contain a run the clone got out of.
* **Timing.** The longest run begins about 45% of the way through the episode, and
  in **9 of the 10 give-ups nobody had been delivered yet** when it began (in the tenth,
  5 of 6 were out). So it happens during the search-and-collect phase, and lasts 16 to
  244 reversals. The clone nevertheless goes on to deliver 3 to 5 occupants in every one of
  them, so it *does* escape the loop, and then stalls short of the last one (one occupant
  short in nine of the ten, two in one; 4.5). The pacing and the endgame stall are
  therefore two separate events in the same episodes.
* **Pacing is not the give-up itself.** It consists of successful steps, so it
  cannot trigger the 12-second idle rule. What it costs is time, and the fire is
  a clock (4.5): it explains much of why the clone is about 40% slower on the big
  mazes. The give-up comes after, when the clone finally stands still.

**Reading, as a hypothesis.** The network has no memory (it is a plain feed-forward
network, see the architecture note). At tile A the picture says "go to B"; at B, with
the fire and the goals shifted a little, it says "go back to A". A* does not do this
because it commits to a route. That the *sampled* clone does better on unseen
stages (73% against 60%) is consistent with this, since randomness breaks a loop,
but it is not a test.

**Limits.** Ten give-ups; one training run; the association is strong for
give-ups and weak for deaths (7 of 10 deaths contain no long run). Whether the
ping-pong *causes* the failures is untested: the test is to give the network a short
memory and see whether the failures go away. That prediction is written down in
[PREDICTIONS.md](PREDICTIONS.md) before any such run.

**Replication on fresh episodes** (`data/oscillation_fresh.md`, 200 episodes per
agent, seeds nobody had used). A*: **0** episodes with a long run. v2 clone: **39** (19.5%).
Of v2's 25 give-ups, **15 (60%)** contain a long run. So "every give-up contains
pacing" was an overstatement from ten episodes; pooled it is 25 of 35 (about 70%). What
holds up is the contrast: the clone paces in a fifth of all its episodes and in most of
its give-ups, and A* never does.

### 4.7 Deterministic versus sampled

Sampling from the network's probabilities does better on the unseen stages (73%
against 60%) and the same on trained stages. With 30 episodes the intervals
overlap, so treat it as a lead. In the RL study the sampled policy was the one
that worked and the deterministic one was useless; here both work, and sampling
is somewhat better.

### 4.8 Does memory help? (predictions P7 and P9, registered before the runs)

**Why.** Section 4.6 found the clone paces between two tiles in every give-up while A*
never does, and suggested the network, being a plain feed-forward network with no
memory, cannot tell it is looping. The project owner then asked whether it would be fair
to let it remember everything it walked and saw on the current map, starting empty.
Checked against A*'s code: A* records the tiles it has seen (`explored`), the occupants
it has spotted (`known_victims`) and every tile it has walked (`trail_cells`), and it
starts empty each episode, so a memory of the agent's own experience is within the
information-parity rule. Tests check that it starts empty every episode, holds only
tiles the agent actually stood on, and that hidden occupants still change nothing the
agent sees (for all four observation versions).

**Two levels, one change each, everything else identical to `imit_b`** (same 65,787
demonstration decisions, network, seeds, DAgger schedule and test):

* **v3, short memory:** the last move and the last four tiles it stood on (17 numbers).
* **v4, full trail:** v3 plus, for each tile in the 11 x 11 window, how many times it has
  stood there this episode (121 numbers), empty at the start.

| deterministic, 240 s, same 100 episodes | v2 no memory | v3 short | v4 full trail | A\* |
|---|---|---|---|---|
| evacuated everyone, all ten | 80% (71-87) | 84% (76-90) | **87%** (79-92) | 91% (84-95) |
| trained stages 1-7 | 89% | 90% | 90% | 94% |
| **unseen stages 8-10** | 60% (42-75) | 70% (52-83) | **80%** (63-90) | 83% (66-93) |
| **episodes with long back-and-forth pacing** | 19 | 10 | **5** | **0** |
| gave up (of which one occupant short) | 10 (9) | 5 (5) | 4 (4) | 1 (1) |
| median seconds, unseen stages | 76 | 71 | 62 | 53 |

![Memory](figures/fig_imitation_memory.png)

*Left: evacuation by group; right: episodes with a long back-and-forth run. Bars on the left
are 95% Wilson intervals.* The epoch-vs-accuracy curves for the three networks are in
`figures/fig_imitation_memory_epochs.png`.

**Predictions against outcomes** (graded by code in `scripts/make_imitation_figures.py`,
`data/memory_summary.md`):

| prediction | outcome |
|---|---|
| **P7** short memory cuts pacing episodes from 19 to 6 or fewer, and lifts evacuation to 85% or more | **Falsified on both clauses**: 10 pacing episodes and 84%. The direction was right; the size fell short. |
| **P9** full trail: pacing no more than v3's and at most 6; evacuation within 5 points of v3 | **Held**: 5 pacing episodes, 87% against 84%. I had expected no *large* extra gain; on the unseen stages it gained 10 points over v3, which I did not expect. |

**Paired on the same episodes** (evacuated everyone; only-first / only-second):
v2 vs v3 2 / 6 (not significant), **v2 vs v4 0 / 7 (sign test p ~ 0.016)**, v3 vs v4 1 / 4 (not
significant), A* vs v4 7 / 3 (p ~ 0.34, not distinguishable from A*).

**Reading.**

* **On this first test set**, memory helped and more memory helped more: the pacing nearly
  disappeared (19 to 5, A* 0), and of v4's four give-ups only one contains a long run. It also
  got faster (median on unseen stages 76 s to 62 s; A* 53 s). Only v2 against v4 was
  individually significant here.
* **What survived the fresh test is narrower** (next section): the pacing reduction, yes; a
  large evacuation gain, no.

**The videos are a caution about small samples.** On the seven hand-fixed episodes in
section 5, v3 and v4 are *not* better than v2: on stage 5 v2 evacuated while v3 and v4 both
died with 4 of 5 out, and on stage 9 v3 evacuated while v4 died. Seven episodes are
not evidence; the 100-episode test is.

**Limits.**

* Four variants were evaluated on the same 100 test episodes, so the best-looking one is
  flattered by chance. The fresh-episode confirmation below is the check.
* One training run per variant, no seed sweep.
* v3 and v4 differ in both how much memory and how it is represented (17 numbers against
  138), so "more memory helps more" is not cleanly separated from "a different
  representation helps more".
* A* records where it has walked but does not use it to decide, so the full trail gives the
  network something A* has and ignores. That is within information parity, but it means a
  fully informed learner is *allowed* an edge.

#### Confirmation on fresh episodes (prediction P10, registered before running)

Because four variants had been tried on one test set, the final candidate (v4), with v2 and
A*, was re-tested on **200 episodes nobody had used** (20 per stage, seeds 190,000+;
`data/confirmation_240s.md`).

| deterministic, 240 s, all ten stages | first test (100) | **fresh test (200)** |
|---|---|---|
| A* | 91% (84-95) | **85%** (79-89) |
| v2, no memory | 80% (71-87) | **75%** (69-80) |
| v4, full trail | 87% (79-92) | **76%** (70-82) |

**P10 was falsified.** I predicted v4 would land inside its earlier interval, 79-92%; it got 76%.
The clause I wrote in advance applies: *the memory gain was mostly the test set being
reused.* (The other two clauses held: A* at 85% is inside its interval, and in the paired
counts v4 won 8 episodes v2 lost against 5 the other way.)

* **Seed sets differ a lot.** A* itself moved from 91% to 85%. Comparing agents on the same
  episodes is what makes any of this readable, and single test sets of 100 episodes carry
  roughly a 6-point swing.
* **The pacing result replicated** (v2 39, v4 15 of 200; A* 0), and v4 died less (8% against
  12%) and led out more occupants (90% against 86%).
* **The evacuation gain mostly did not.** 75% against 76%. The pacing deaths turned into
  give-ups: v4 gave up in 16% of fresh episodes against v2's 12%, and only 12 of v4's 32
  give-ups contain a long run, so most are the endgame stall (4.5), not pacing.

**Pooled over both sets, 300 episodes per agent** (`data/pooled_300.md`):

| | trained 1-7 (210) | unseen 8-10 (90) | all ten (300) |
|---|---|---|---|
| A* | 87% (82-91) | 87% (78-92) | **87%** (83-90) |
| v4 deterministic | 84% (78-88) | 71% (61-79) | **80%** (75-84) |
| v4 sampled | 85% (79-89) | 71% (61-79) | 81% (76-85) |
| v2 deterministic | 82% (77-87) | 63% (53-73) | 77% (72-81) |

Paired on the same 300 episodes: **v4 won 15 that v2 lost, v2 won 5 that v4 lost** (sign test
p ~ 0.04); **A* won 25 that v4 lost, v4 won 4 that A* lost (p ~ 0.0001)**. So the best
estimate is that memory adds a few points, and that the clone is still clearly behind A*,
mostly on the unseen stages (71% against 87%) and roughly level, within a few points, on the
stages it trained on.

### 4.9 Is stalling the failure? (the project owner's hypothesis, tested on all 300 episodes)

After watching the v4 recordings the project owner proposed that the later versions still fail
mainly by pacing (stalling); that when confused the network is either *undecided between two
paths* or *does not know what to do*; that this shows up mainly on higher stages; and that
**eliminating stalling would raise the success rate significantly.** These are four separate
claims, so each was tested on the same 300 seeded episodes per agent (both 240 s test sets;
`scripts/stall_analysis.py`, `scripts/make_stall_figure.py`). This test was *not* registered
in advance; the analysis was written before the numbers were seen, but the definitions below
were my choice (see P11 in `PREDICTIONS.md`).

**Definition.** Section 4.6 counted strict back-and-forth between two tiles. This section uses
a broader one so that small loops are caught too: a *stall* is at most 3 different tiles among
the last 16 tiles entered, and an episode is *stalled* if that held at 10 or more moments.

![Stalling by stage, and what removing it is worth](figures/fig_stall.png)

**Claim 1, "the failures are mostly stalling": partly.** A* never stalls (0 of 300).

| | episodes that stall | failures | failures that contain a stall |
|---|---|---|---|
| v2 | 51 (17%) | 70 | **33 (47%)** |
| v4 | 24 (8%) | 60 | **16 (27%)** |

For v4, stalling is in 14 of 36 give-ups (39%) but only 2 of 24 deaths (8%). It is also not
fatal by itself: 8 of v4's 24 stalled episodes still evacuated everyone. The other 44 v4
failures (22 died, 22 gave up) do not stall. Twenty of those 22 give-ups are *one occupant
short* (the endgame stall of section 4.5, which is standing still, not pacing), and 10 of the
26 deaths that remain after the stalls are removed (below) are on stage 7, a stage it trained
on.

**Claim 3, "it is mainly a higher-stage problem": yes, but the data cannot say which
part of that it is.** Stalled episodes: stages 1-7 (trained): v2 9 of 210 (4%), v4 3 of 210
(1%). Stages 8-10: v2 42 of 90 (47%), v4 21 of 90 (23%). Stage 9 is worst (v2 18 of 30, v4 10
of 30). But stages 8-10 are both the highest *and* the ones the networks never trained on, so
"higher stage" and "unseen stage" are confounded in this design. My reading is that it is the
unseen part (the network stalls where its training data thins out) but the tests cannot
separate them.

**Claim 2, "undecided between two paths, or does not know what to do":** the evidence favours
*undecided between goals*. The observation carries four route hints (exit, occupant, frontier,
key); at every decision I checked which goals' best move the network actually chose.

| v4 | mean confidence (top probability) | chose to stay | followed no goal's best move | changed goal from one move to the next |
|---|---|---|---|---|
| while stalled | 0.83 | 12% | 17% | **77%** |
| otherwise | 0.99 | 3% | 4% | 7% |

v2 is the same shape (98% goal changes while stalled against 12%). So when it stalls, most
moves still follow *some* goal's route, but consecutive moves follow *different* goals: it
flips between, for example, "go for the occupant" and "go for the exit". It is less sure
(0.83 against 0.99) but it is not lost: it stays still on 12% of stalled decisions and follows
no goal on 17%. That gives a minority of "does not know what to do" moments inside a mostly
"undecided between two goals" pattern. Caveat: a reversal on one goal is impossible while that
goal's route is consistent, so some goal-flipping is built into any two-tile loop. I did not
break the flips down by *which* two goals compete; that is the obvious next measurement.

**Claim 4, "eliminating stalling raises success significantly": true for v2, modest for v4.**
This is an upper bound, not a result for the network. Whenever a network stalls, A* takes the
next N decisions and then hands control back (same episodes, same conditions).

| network | as trained | A* breaks stalls, 10 decisions | 40 | 200 | episodes only won with the help | lost with the help |
|---|---|---|---|---|---|---|
| v2 | 77% | 83% | 84% | 84% | 20-23 | 0 |
| v4 | 80% | 82% | 82% | 83% | 7-8 | 0 |
| A* | 87% | | | | | |

For v2 the gain is real (+7 to +8 points). For v4 it is +2 to +3 points, because memory had
already removed most of the stalling (section 4.8), and even a very long takeover does not lift
it past about 83%. By stage group, v4 with stalls broken is unchanged on the trained stages
(176 to 177 of 210) and improves on the unseen ones (64 to 71 of 90, 71% to 79%); v2 improves
from 57 to 75 of 90 (63% to 83%) on the unseen stages, close to A*'s 87% there.

**Conclusion.** Stalling is the dominant failure of the network *without memory* on the unseen
stages, and fixing it would recover most of the gap there. For the network *with* memory it is
a second-order problem: about a quarter of its failures, worth 2 to 3 points at best. The
larger remaining share is the endgame "one occupant short" stall and the stage-7 deaths, which
need a different fix (route damage, prediction P8).

**What a real fix could be, and what it must not be.** The counterfactual above borrows A*, so
it is not a legitimate agent. Fixes that respect the same-information rule use only what the
agent itself has seen: (a) DAgger rounds seeded from stall states, which are exactly the states
the clone visits and A* never does; (b) a commitment feature (which goal it chose last and how
long ago) in the observation; (c) a plain anti-stall rule on the agent's own trail, which would
make the agent "network plus rule" rather than a pure network. None of these is run yet.

### 4.10 Do they give up because the last occupant "is not worth it"? (owner's question)

A* has exactly such a rule: when no occupant is known and the round trip to the nearest
unexplored area would cost more than 60% of its current health (`AGENT_EXPLORE_HEALTH_BUDGET`,
`_worth_exploring`), it stops searching, walks to the exit and waits. That ends as `gave_up`.
The network has no such rule and no notion of points: it has no reward at all, only labels copied
from A*. It gives up only by standing still for 12 s (`IDLE_GIVE_UP_SECONDS`). So the question
is whether its give-ups are copies of A*'s stop decision. `scripts/giveup_analysis.py` inspects
the state at the moment each give-up was declared (300 episodes per agent):

| | give-ups | one occupant short | on the exit | A*'s budget rule says "not worth it" | A* would keep searching from that state |
|---|---|---|---|---|---|
| A* | 16 | 15 | 16 | 16 (all) | 0 |
| v4 | 36 | 32 | 35 | 24 | 13 |

Reading: **about two-thirds of v4's give-ups (23-24 of 36) end in a state where A* itself would
stop**, so the network is reproducing A*'s cautious decision (with more of them, 36 against 16,
probably because it reaches those states damaged or late). The other 13 are real errors: A*
would go on searching and the network did not. Caveat: this shows what A* would do from the end
state, not why the network stood still. The network has no route-damage input, so it can only
approximate the rule from correlated cues, which is what prediction P8 is about.

A side effect worth noting for the research: the success metric ("evacuated everyone") counts
A*'s deliberate caution as a failure. Its game score can still be positive: saving the last
occupant is worth +100, and a round trip costing up to 60% of its remaining health costs
roughly 0.4 points per health point lost, so the rule protects survival, not score.
(`data/giveup_analysis.md`)

### 4.11 Does the search order matter? (owner's efficiency question; A* itself is unchanged)

A* searches by always going to the **nearest** unexplored frontier (greedy nearest-frontier by
hazard-weighted distance, `_nearest_unexplored`); it is neither BFS nor DFS. The owner asked if it
would be more efficient to lean towards the far side of the map (relative to the exit) and pick up
what is convenient on the way back. `scripts/frontier_variants.py` replaces *only* that choice,
inside its own worker processes, and leaves the benchmark and the game code untouched. The
unmodified rule reproduces A*'s 87% and score of 505, so the harness is faithful.

> **Correction, found while building v5.** The first version of this experiment (a patch inside
> `scripts/frontier_variants.py`) measured "distance from the exit" once, at the agent's first planning
> step, while the locked door was still closed. The spawn side of every stage is behind that door, so
> those cells had no distance and were treated as 0: the far-side lean did nothing there. A new test
> (a frontier cell with no exit distance) exposed it. The rule now measures over the static floor plan
> and is a real agent option (`frontier_lean`); re-measured with it (`scripts/teacher_variants.py`):
> **300 episodes: 91% against A*'s 87%, score 509 against 505; 200 fresh episodes (seeds 290,000+):
> 90% against 84%, score 505 against 488.** The conclusion is unchanged. The other rows of the table
> below (far_hard, far_first, near_exit) were **not re-run** and carry the flaw; treat them as
> indicative only.

| search order (300 episodes) | evacuated | gave up | mean score | seconds (evacuated) |
|---|---|---|---|---|
| **nearest (A*'s own rule)** | 87% | 5% | 505 | 41 |
| far_soft: distance from agent minus 0.5 x distance from exit | **91%** | 2% | 507 | 43 |
| far_hard: minus 1.0 x | 91% | 2% | 502 | 43 |
| far_first: always the frontier furthest from the exit | 79% | 16% | 488 | 50 |
| near_exit: sweep outwards from the exit | 81% | 9% | 495 | 40 |

**Prediction P12** (registered before the fresh run): far_soft beats nearest by at least 2 points
and gives up less. On 200 fresh episodes: **90% against 84%, give-ups 2% against 5%. It held**;
pooled over 500 episodes 90.6% against 86.0% (won 31 / lost 8, p ~ 0.0003). The two extremes are
worse: searching *only* the far side (far_first) is clearly slower (+11 s) and gives up in 16%, and
sweeping outwards from the exit (near_exit) is worse too.

Reading, for the "veer, do not force" idea: **a mild lean towards the far side helps; forcing it does
not.** The gain is in *finishing* (fewer one-occupant-short give-ups, more occupants led out: 93%
against 92% and 89% on the two sets), not in speed (it is about 2 s slower) and not in points (+2 on
the first set, +18 on the fresh set, pooled +8, not settled). My hypothesis for why, **untested**:
searching the far side first, while healthy, leaves the cheap frontiers near the exit for last,
where A*'s "is the round trip within 60% of my health" rule still says yes, so it is less often
forced to abandon the last occupant.

Two consequences. (1) It is a *teacher* improvement: cloning from a 90% teacher rather than an
87% one raises the ceiling for the network, which more training on the current labels cannot do.
(2) The benchmark is left as it was; this table does not change any other number in this folder.
(`data/frontier_variants.md`, `data/frontier_variants_fresh.md`)

### 4.12 v5: a clone of the far-side searcher, and the per-stage comparison with A* and v4

**What v5 is.** Same network, observation (version 4: A*'s information plus the full trail) and training
recipe as v4 (`imit_e`, 120 demonstrations per training stage, 30 epochs, four DAgger rounds); only the
**teacher** changed to A* with two search-order settings that exist as opt-in agent options
(`frontier_lean 0.5`, `frontier_min_reveal 4`; A*'s default behaviour is untouched). The "frontier" route
hint the network sees is computed by the same rule, so the learner and its teacher still share one
observation. The options travel with the model in `final_model.json`, so the game applies them
automatically.

**The corner rule you asked for** ("near a corner, no occupant found: do not make a special trip into it
just to finish looking at every tile"; fog of war unchanged) is `frontier_min_reveal K`: skip a frontier
whose trip would reveal fewer than K unseen floor tiles. Measured on the teacher over 300 episodes
(`data/teacher_variants.md`):

| teacher | evacuated | gave up | score | seconds (wins) |
|---|---|---|---|---|
| A* (benchmark) | 87% | 5% | 505 | 41 |
| far side | 91% | 2% | 509 | 43 |
| **far side + skip corners < 4 tiles (v5's teacher)** | **91%** | 3% | **512** | 42 |
| far side + skip corners < 8 tiles | 81% | 13% | 507 | 40 |
| far side + skip corners < 12 tiles | 60% | 38% | 487 | 33 |
| far side + defer corners < 8 (visit them only if nothing else is left) | 87% | 7% | 507 | 41 |

Reading: **skipping only tiny corner remnants costs nothing; skipping bigger ones is faster but loses
occupants** (an occupant is sometimes in the corner, and once one is missing the corner is the *only*
place left), so the evacuation rate falls 10 points while the score stays level. I shipped the mild
version. I did **not** measure how often the *network itself* makes corner trips, only the teacher's
effect on outcomes. Whether to trade evacuations for speed with the stronger setting is your call.

**Per-stage results.** 300 fresh episodes per agent (30 per stage, seeds 950,000+, never used to train,
select the model or choose the teacher), 240 s cap, identical episodes for all three agents. Full tables,
including give-up detail per stage: `data/stage_report.md` and `.csv`.

![A*, v4 and v5 by stage](figures/fig_stage_report.png)

| stage | A* evacuated | v4 | v5 | A* clear time | v4 | v5 | A* score (wins) | v4 | v5 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 93% | 93% | 93% | 22 s | 23 s | 25 s | 395 | 395 | 393 |
| 2 | 90% | 90% | 93% | 35 s | 35 s | 31 s | 382 | 381 | 385 |
| 3 | 93% | 93% | 97% | 28 s | 29 s | 32 s | 480 | 479 | 478 |
| 4 | 83% | 87% | 90% | 36 s | 40 s | 46 s | 478 | 474 | 467 |
| 5 | 73% | 80% | 87% | 40 s | 42 s | 38 s | 577 | 574 | 580 |
| 6 | 97% | 97% | 100% | 42 s | 44 s | 41 s | 574 | 573 | 574 |
| 7 | 60% | 60% | 57% | 53 s | 54 s | 56 s | 665 | 666 | 666 |
| 8 (unseen) | 93% | 70% | 80% | 62 s | 69 s | 60 s | 651 | 648 | 650 |
| 9 (unseen) | 90% | 83% | 83% | 49 s | 62 s | 64 s | 670 | 660 | 658 |
| 10 (unseen) | 77% | 60% | 57% | 66 s | 73 s | 68 s | 650 | 649 | 651 |
| **all ten** | **85%** | **81%** | **84%** | 43 s | 45 s | 44 s | 546 | 538 | 538 |

When it gave up (all stages pooled): A* 15 give-ups had found 72% of the occupants (3.9 of 5.3, all of them
saved) and viewed 88% of the floor tiles; v4 had 18, found 81%, saved 4.5 of 5.8, viewed 83%; **v5 had 14,
found 79%, saved 4.4 of 5.6, viewed 88%**. Mean game score over all 300 episodes: A* 494, v5 477, v4 472;
occupants led out: 90%, 88%, 87%.

Paired on the same 300 episodes (evacuated everyone): **A\* against v5: A\* won 22, v5 won 18, p = 0.64:
not distinguishable.** A* against v4: 19 against 8, p = 0.052. **v5 against v4: 24 against 17, p = 0.35: v5's
gain over v4 is not established.** By stage group: trained stages 1-7: A* 84% (177 of 210), v4 86%, **v5 88%
(185)**; unseen stages 8-10: **A\* 87% (78 of 90), v4 71%, v5 73% (66)**.

What this says. (1) v5 plays level with A* overall and is nominally ahead on the trained stages, but the
comparison cannot separate them. (2) The far-side search order did not close the **unseen-stage gap**
(73% against 87%): that gap is about generalising to new mazes, not about search order, which is why v4
and v5 look alike there. (3) **Stage 7 is the shared weak spot** (A* 60%, v4 60%, v5 57%); v5 died 13 times
there against A*'s 7 and v4's 9 (it is a trained stage and the deaths are hazard deaths, not stalls). (4)
Wins are equally fast and equally scored for all three (43 to 45 s, 538 to 546). (5) v5 was not
pre-registered; the choice of teacher was made on other episodes and confirmed on fresh ones (90% against
84%), and this evaluation is on a third, untouched set.

**Recordings.** Seven clips of v5 on the same seven episodes as v4 (`media/imitation/*_v5_*.mp4`): stages
1, 3, 5, 8, 9 evacuated; stage 7 (seed 1001) and stage 10 (seed 1001) died with nobody out. As always, seven
episodes prove nothing either way.

## 5. Recordings

All recordings are of the *same seeded episode* for A*, the v2 clone and the v1
clone, at a 240 s cap, played at 4x with a caption bar (agent, stage, health,
occupants out, score). Stages and seeds were fixed in advance
(`scripts/record_imitation.py`); the outcome is in each file name. The three
stages 8-10 are ones the networks never trained on.

Files are in [`media/imitation/`](media/imitation/) as `stage<NN>_seed<S>_<agent>_<outcome>.mp4`
(`astar`, `v2` = clone with A*'s information, `v1` = clone with a local window), each
with a `_sheet.png` contact sheet of eight stills.

| stage, seed | A* | v2 clone (A*'s information) | v1 clone (local window) | what it shows |
|---|---|---|---|---|
| 1, 1000 | evacuated 3/3, 34.2 s | evacuated 3/3, **34.2 s** | gave up, 2/3 out, 78.6 s | on this episode the v2 clone takes the same time as A* to the second; v1 stops one short |
| 3, 1000 | evacuated 4/4, 13.5 s | evacuated 4/4, 14.2 s | evacuated 4/4, 14.2 s | a short stage all three finish |
| 5, 1000 | evacuated 5/5, 30.4 s | evacuated 5/5, **68.9 s** | evacuated 5/5, 29.2 s | the v2 clone succeeds but takes over twice as long here |
| 7, 1001 | **died** 0/6, 43.4 s | **gave up, 5/6 out**, 152.2 s | died 0/6, 154.3 s | a hard episode (A* dies): the v2 clone rescues five, then stops one short. [GIF](media/imitation/stage07_seed1001_v2_gave_up.gif) |
| **8, 1000 (unseen)** | evacuated 6/6, 57.0 s | **evacuated 6/6**, 65.9 s | died 0/6, 58.8 s | **success on a stage it never trained on**, where the v1 network dies. [GIF v2](media/imitation/stage08_seed1000_v2_evacuated.gif), [GIF v1](media/imitation/stage08_seed1000_v1_died.gif) |
| **9, 1000 (unseen)** | evacuated 6/6, 73.6 s | **died** 0/6, 98.0 s | died 0/6, 129.4 s | **failure on an unseen stage**: A* finishes in 73.6 s; the clone is slower and the fire gets it first. [GIF](media/imitation/stage09_seed1000_v2_died.gif) |
| 10, 1001 (unseen) | died 0/6, 67.6 s | died 0/6, 98.5 s | died 0/6, 120.9 s | the hardest stage; nobody gets out on this episode |

**The memory networks on the same seven episodes** (`_v3_` and `_v4_` files in the same folder):

| stage, seed | v2 (no memory) | v3 (short memory) | v4 (full trail) |
|---|---|---|---|
| 1, 1000 | evacuated, 34.2 s | evacuated, 34.2 s | evacuated, 34.2 s |
| 3, 1000 | evacuated, 14.2 s | evacuated, 14.2 s | evacuated, 14.2 s |
| 5, 1000 | evacuated, 68.9 s | **died**, 4/5 out, 53.4 s | **died**, 4/5 out, 53.4 s |
| 7, 1001 | gave up, 5/6, 152.2 s | died, 5/6, 107.9 s | gave up, 5/6, 119.0 s |
| 8, 1000 (unseen) | evacuated, 65.9 s | evacuated, 65.9 s | evacuated, 62.9 s |
| 9, 1000 (unseen) | died, 0/6, 98.0 s | **evacuated**, 6/6, 101.0 s | died, 0/6, 99.1 s |
| 10, 1001 (unseen) | died, 0/6, 98.5 s | died, 0/6, 72.6 s | died, 0/6, 205.3 s |

On these seven the memory networks are not better than v2 (v2 evacuates 4, v3 4, v4 3); see the
caution in 4.8.

All at the 240 s cap, played at 4x speed. Stages and seeds were fixed in advance
and were not chosen for how they look; roughly half of these show the clone
failing. An earlier set recorded with the 90 s cap was replaced because the cap
cut slower runs off (see section 2.3).

## 6. What this does and does not show

**Shows**

* Showing the network A*'s decisions makes it play: from 0 of 40 (RL) and 20%
  (v1) to 80% (v2) on all ten stages.
* The two runs differ *only* in the observation, so **the information gap was
  the dominant cause of v1's failure**, which reframes the reinforcement-learning
  study as a comparison of a local-view learner against a global-view planner.
* On stages it trained on, the clone is indistinguishable from A*.
* It leads out 89% of occupants overall against A*'s 92%; with memory, 91%.
* **Memory reduces pacing** (19 to 5 episodes of 100, then 39 to 15 of 200 on fresh episodes) and
  improves evacuation modestly: pooled over 300 episodes 77% to 80%, paired p ~ 0.04. Most of the
  first test's apparent +7 points did not replicate.

**Does not show**

* **That it can beat A\*.** It does not (both evacuated 78, only A* 13, only the
  clone 2). Cloning is capped by the teacher; beating A* would need a further
  step.
* **That it has learned to plan.** Version 2 hands it A*'s own route
  computations, so what it learns is mostly *which goal to pursue and how to
  follow the hint*. That is a far easier problem than learning from a raw view,
  and the result should not be read as "a network learned to solve the maze".
* **Robustness.** One training run per observation version, 10 episodes per stage,
  wide intervals. No seed sweep.
* **Generalisation beyond these mazes.** The unseen stages are three larger mazes
  from the same generator.
* **Anything about the endgame hypothesis** in 4.5; it is a pattern, not a test.
* **A large memory gain.** The first test suggested +7 points; fresh episodes showed +1, pooled +3.
* **That it matches A\\*.** Over 300 episodes A* won 25 that v4 lost and v4 won 4 (p ~ 0.0001), mainly
  on the unseen stages (87% against 71%).

**Predictions.** Unlike the RL study, these were not written into a file before
the runs. What I expected in conversation was that cloning would get near A* and
not beyond it, and that it would generalise worse to unseen stages; both held. I
did not predict that the information gap would matter as much as it did, or that
the time cap would.

## 7. Mistakes and corrections made along the way

1. **The information claim** (2.1): wrote that the learner had A*'s information
   without reading A*'s planner.
2. **The time cap** (2.3): evaluated with a cap the game does not have, which
   understated the clone until I re-ran at 240 s.
3. **The key** (2.4): my first hints had no key goal, so on every stage the exit
   hint was empty at spawn. Found because my own tests failed.
4. **Buffered output**: I launched the first run without unbuffered output, so the
   progress monitor saw nothing for 30 minutes; the run itself was fine.
5. **Two definitions of "led out"**: a figure pooled occupants across episodes
   while the table averaged per episode (a point or two apart); unified.

## 8. Next experiments

1. **The missing endgame information** (route damage and the health budget; prediction P8 in
   PREDICTIONS.md). Memory did not remove the one-occupant-short give-ups (4 remain against A*'s 1),
   so this is the natural next feature. Prediction: they fall to 2 or fewer.
2. **More and different training stages**, holding out fewer, to test whether the
   unseen-stage gap is about coverage.
3. **Seeds.** Several training runs per observation version.
4. **Reinforcement learning from the clone** (with an anchor to A*'s behaviour so
   it does not drift back to standing still). This is the step that could go
   *beyond* A*; nothing here shows it will.
5. **Install and play it in the game**, which the code already supports
   (`--install`), and watch it as the AI opponent.

## 9. Reproducing

```bash
python tools/train_imitation.py --name imit_b --obs-version 2       # cloning + DAgger + final test
python tools/train_imitation.py --name imit_a --obs-version 1       # the local-window ablation
python pyro_pete_game/ml/ML_Findings/scripts/imitation_long_cap_test.py   # 240 s comparison
python pyro_pete_game/ml/ML_Findings/scripts/make_imitation_figures.py    # figures + tables
python pyro_pete_game/ml/ML_Findings/scripts/record_imitation.py          # the recordings
python pyro_pete_game/ml/ML_Findings/scripts/spawn_reachability.py        # section 2.4
python tools/train_imitation.py --name imit_c --obs-version 3       # + short memory
python tools/train_imitation.py --name imit_d --obs-version 4       # + full trail
python pyro_pete_game/ml/ML_Findings/scripts/oscillation_analysis.py      # back-and-forth counts
python pyro_pete_game/ml/ML_Findings/scripts/confirmation_test.py         # fresh-episode check
```

Files: `imitation/imit_a_v1_local_view/`, `imit_b_v2_route_hints/`, `imit_c_v3_memory/` and `imit_d_v4_trail/`
(config, `epochs*.csv` = the epoch-vs-accuracy log, `rounds.csv`, `baseline.json`,
`final_report.txt`, `final_results.csv`, the chart, and the trained model);
`data/imitation_240s.csv`, `data/imitation_summary.md`, `data/spawn_reachability.md`.
