# Experiment log

A chronological lab notebook: what was built or tried, what was expected, what
happened, including the mistakes and the things that turned out not to matter.
Entries 1-12 come from the development sessions; the raw runs behind entries 3
and 4 were not kept, so those numbers are as recorded at the time and are
marked *(not preserved)*. Entries from 13 on are backed by data in this folder.

## Build phase

**1. Scope decision.** The learned brain must be an *option for the AI player
only*; A* stays the default and Pete is never ML-driven. The menu entry is
hidden unless a trained model file exists, so a checkout without one plays
exactly as before.

**2. Observation design (and a later correction).** Before writing any learning
code, the observation was restricted to explored layout only, with hazards and
occupants visible within 3.5 tiles and the exit, head-count and fire countdown
always known, and a test was written to enforce it. I described this as "what A*
is allowed to know". **That was wrong**, found while planning the imitation
study: A* plans over the whole real map and the live hazard field everywhere
(only occupant positions are hidden), so this observation gave the learner
strictly less than A* has. The claim was in the docs pushed to GitHub and has
been corrected (METHODS section 2, the FINDINGS correction box). I made the
claim without reading the planner's code; I read it only when a poor
generalisation result made me check. Lesson: verify a claim about another
component in that component's source before writing it into a methods section.

**3. First harness run *(not preserved)*.** On stages 1-3, A* evacuated 90% of
episodes, a random-move agent 0%, and a stand-still agent 0% (100% gave up at
exactly 12.0 s). The paired comparison called both "clearly worse" than A*. This
established the floor and ceiling before any learning.

**4. A noise lesson *(not preserved)*.** An earlier change to A* appeared to cut
deaths from 9 to 7 in 80 runs. With 8 trials per stage that gap is within
noise. Result: every rate in the harness now carries a Wilson 95% interval, and
agent comparisons are paired by seed. (This is why the intervals appear
everywhere below.)

**5. A reproducibility bug in A*.** Running the same seeded episode twice in one
process gave different A* behaviour in some cases. Cause: `min()` over a `set`
of cells broke ties by memory address, so equal-cost targets were chosen
differently between runs. Fix: tie-break on `(distance, cell)`. Verified: 0 of 5
previously non-reproducible cases still differed over 8 repeats. Guarded by a
test (`test_astar_is_reproducible_under_a_seed`).

**6. The trainer.** Built `ml/training.py` (callbacks), `ml/report.py`
(epoch-vs-accuracy log, chart, review page), `ml/recording.py` (screen
recording) and `tools/train_agent.py`. Tested first against a stub model, then
against the real library.

**7. First real smoke run: 3,072 steps, 2 environments.** It worked end to end.
Three problems showed up immediately:

* value-network loss of about 860-990 (episode returns are in the hundreds);
* the chart legend covered the data;
* only 60-100 steps per second.

**8. Profiling.** A profile of the raw environment (189 steps/s) put about 40% of
the time in `pygame.image.load`: every reset re-read the same victim sprite
PNGs from disk. Caching the loaded sprite sets took it to **575 steps/s (3.0x)**
with no change in behaviour. (`fig_engineering.png`.)

**9. Reward scaling.** Added running-return normalisation of the reward for the
optimiser only (`VecNormalize(norm_obs=False, norm_reward=True)`). Logged
returns and scores stay in real game points. First-epoch value loss dropped
from about 987 to about 8. This does not change *which behaviour scores higher*,
only the scale the network has to fit.

**10. Naming collision.** The training wrapper writes `info["episode"]` itself,
which collided with the environment's own episode summary and would have
crashed the return logging. Renamed the environment's to `info["summary"]`.

## First experiments

**11. Experiment 01, plain reward, seed 0 (100k steps, stages 1-3).** The
network stopped dying (100% -> 3% of episodes) and scored zero. 91% of episodes
ended by standing still until the give-up rule. Details in
REWARD_EVOLUTION.md.

**12. Experiment 02, abandon penalty 100, seed 0.** Added a charge per occupant
left inside, expecting it to remove the incentive to stand still. Deaths fell
from 100% to 50% and giving up rose to 50%; still no occupant saved.

**A process mistake worth recording.** To test the `--install` option I ran a
40-second, untrained plain-PPO run with `--install`. That copied a worthless
model to the real `ml/models/ai_policy.zip`, which would have made the game
offer a "Learned model" entry backed by junk. I noticed in the output, used the
file for one useful check (a real stable-baselines3 model does load and run
through the actual game menu), then deleted it. Lesson applied since: test
`--install` against a temporary folder, never the real model path.

## Analysis phase

**13. Baselines** (`data/baselines_episodes.csv`, 600 episodes: 20 per stage x 10
stages x 3 agents). A* evacuates 86% (81-91) overall, weakest on stages 7 and 10
(55% and 65%). Random and stand-still: 0/200 each, and random play led **no**
occupant out in any of its 200 episodes.

**14. Reward accounting** (`data/reward_accounting.md`). Measured what each
kind of behaviour earns under the training reward. Result and the correction
it forced to entry 12 are in REWARD_EVOLUTION.md.

**15. A surprise in the recordings.** The checkpoint videos recorded with the
deterministic policy show the *untrained* network at step 0 standing still and
giving up at 12 s, exactly like the step-101k network. An untrained network's
highest-probability action is arbitrary and here happens to be "stay", so
deterministic validation is flat zero for a trivial reason. Fix: measure
behaviour with *sampled* actions, as training does
(`scripts/behaviour_by_checkpoint.py`).

**16. Predictions written down** before experiments 03-05 and before the seed 1
and 2 replicates had finished ([PREDICTIONS.md](PREDICTIONS.md)). Added opt-in
`give_up` and `timeout` penalties to the environment to test the explanation.

**17. Replicates (exp01, exp02: seeds 1 and 2).** Same settings, 100k steps. The
collapse to standing still replicated in all three plain seeds; the abandon
runs all landed near 50/50 died versus gave up, with return -405, -405, -408.
Checking my own prediction against the full logs (not just the last epoch)
showed that **two plain seeds had led occupants out during training**, which
P1 said would not happen. Recorded as falsified in PREDICTIONS.md.

**18. A useful accident: the price list predicts the return.** The abandon
seeds gave a 50/50 split at a mean return of -405. Multiplying the shares by
the measured prices gives 0.5 x (-333.9) + 0.5 x (-475.6) = -404.8. Turned
into a script (`scripts/summarise_runs.py`); it holds within about 3 points
for every run that has no rescues.

**19. exp04 (give-up penalty 200), seed 0.** Giving up fell to 0% as predicted
but timeouts stayed at 17% (predicted >= 50%) and 7.2% of occupants were led
out (predicted none). P3 partly falsified by one seed; the budget and queue
were changed and P6 written *before* running anything further
(PREDICTIONS.md, amendment).

**20. exp04 seed 1.** Same settings, different story: 30% still giving up, no
rescues, return -130. Two seeds of one setting disagreed by 30 points on the
main outcome, which is the argument for reporting every seed.

**21. exp05 (both penalties).** 87% died, 12% gave up, 1% timed out; return
-151, *worse* than the -142 random starting policy. Recorded as unexplained
rather than explained away. I proposed a freezing-near-fire hypothesis for the
remaining giving up (see 27).

**22. A scheduling mistake.** Three training runs at once each ran at about 115
steps/s (345 total), while one alone runs at about 550. I stopped them, deleted
the partial run folders so nothing would be appended to stale logs, and ran the
rest one at a time. Lost about ten minutes; recorded because "run more in
parallel" is the wrong instinct when a machine is already using its cores.

**23. The GPU question.** The machine has an RTX 3050; the installed PyTorch is
the CPU build. Timing four epochs: 87% of the time is the game simulation, 11%
the network update. A GPU could only speed up the 11%, so it was not installed.
Recorded as E9.

**24. exp07 (give-up penalty, 300k steps).** Reproduced exp04 seed 0 exactly for
33 epochs (all 12 logged columns identical), then the rescue share tripled to
about 22% and plateaued. Full evacuation peaked at 5%. Final test with the
deterministic policy: **0 occupants led out**, although the sampled policy leads
out about a fifth. This was the first sign that the deployed policy and the
trained policy differ (F8).

**25. exp06 (plain seed 2 continued) and exp03 (abandon, 300k).** exp06: still
62-98% giving up after 300k more steps, rescue share about 12%, deterministic
policy stands still in 40 of 40 episodes. exp03: 0 rescues in 98 epochs.
exp03's first 33 epochs are also identical to its 100k twin.

**26. Analysis pass on the finished runs.** Added a `sample:PATH` agent to the
harness so the same model can be tested by taking the most likely action (the
game) and by sampling (training) on identical episodes. Measured, with fresh
seeds: all 12 models stand still or die in deterministic mode; four rescue
anything when sampled, only on trained stages (0 of 40 on the unseen stage 4),
never more than two occupants in an episode. (`data/common_final_test.md`.)

**27. The freeze hypothesis, tested and rejected.** If the remaining standing
still were "freezing near fire", give-ups should happen with fire in view.
Measured (`data/freeze_diagnostic.md`): 71-100% of give-ups never left the spawn
tile, and fire was in view no more often than for a random walker (43%). Reward
evolution document, section 7a.

**Things I would do differently.** (1) Check the *full* log of a run, not its last
epoch, before writing a prediction about it (P1). (2) Measure what the deployed
policy does earlier; the deterministic-versus-sampled gap was visible from the
first recordings and I recorded it as a curiosity instead of a result. (3) Run
runs one at a time from the start. (4) Never point `--install` at the real
model path in a test.

## Imitation phase

**28. The questions that led here.** Three questions from the project owner shaped the
next study: what motivates the network to copy A* instead of standing still (answer:
in behaviour cloning the objective *is* agreement with A*; there is no reward to
prefer standing still to), whether this is transfer learning (closer to imitation
pretraining or distillation), and whether it could beat A* (cloning is capped by the
teacher; RL fine-tuning could in principle go beyond it, unproven).

**29. Checking the teacher first.** A* is a pure function of an agent's state
(goal choice, then hazard-weighted A*), so "what would A* do from here?" can be asked of
any agent anywhere. Before building anything, A* was played *through the network's
one-tile-step interface*: **88%** evacuated (n=100) against native A*'s 86% (n=200), so
the interface costs nothing. Labels: 1.1% stay, never illegal. 100 episodes collected in
8 s on 8 workers.

**30. First run (`imit_a`, local-window observation).** Cloning reached 90% action-match
on held-out episodes but only 76.6% on unseen stages, and in play evacuated 29% of
trained-stage episodes and **0% on unseen stages**. DAgger (4 rounds) did not move the
unseen accuracy at all (76-78% throughout). Final, 100 episodes, 90 s cap: 20% (13-29).

**31. Finding that my central claim was wrong.** The flat 76% made me read A*'s
planner. It plans over the whole real map and the live hazard field everywhere; only
occupant positions are hidden. My documents said the learner was "held to exactly what
A* is allowed to know". **False**, and already pushed to GitHub. I corrected every
mention (METHODS section 2, the FINDINGS correction box, this log's entry 2, the
main README, the code docstring) and stated which findings it does and does not
affect. The project owner then set the rule that governs the rest: *the model and A\*
must get the same conditions, or training will not work or the model gets God mode.*

**32. Parity made testable.** Wrote the rule into `ml/observation.py`, then tests: an
occupant the agent has not spotted can be moved anywhere without changing one number
it sees (nor A*'s decision), for both observation versions; a spotted one does show;
the learner and A* build the same map, key, exit, occupants, fires, speed and health from
the same seed.

**33. Every stage starts behind a locked door.** Writing the hint tests, the exit
hint was empty on every stage: the exit is unreachable at spawn on all ten (spawn pocket
3-45 tiles of 116-319 on nine); A* handles it by heading for the key. My first hints had
no key goal. Added it (a fourth goal, 24 hints in all) and measured it
(`data/spawn_reachability.md`). Found because my own tests failed.

**34. Second run (`imit_b`, A*'s information).** Same seeds, data, network and
hyperparameters as `imit_a`; only the observation differs. Action-match on unseen stages
76.6% -> 93.4% after cloning (97.2% after DAgger). In play, 90 s cap: 76% all ten (20%
before).

**35. Finding that my time cap was unfair.** The clone's failures looked like "ran out of
time". The game has **no hard time limit** (only a speed-bonus reference at 90 s); my 90 s
cap was an experimental convenience that penalises whichever agent is slower (A* never
needs over 78 s). Re-ran the identical episodes at 240 s: the clone rose to 80% (unseen
47% -> 60%; sampled 60% -> 73%) and every "ran out of time" became something
informative: died, or **gave up one occupant short (9 of 10)**. Made 240 s the primary
comparison and re-recorded all 21 clips.

**36. Recordings.** 21 clips (A*, v2 clone, v1 clone on stages 1, 3, 5, 7, 8, 9, 10; stages
8-10 unseen), stages and seeds fixed in advance, outcome in the file name; about half show
the clone failing.

**Things I would do differently (imitation).** (1) Read the teacher's code *before*
claiming parity with it; this is the same mistake as the RL study's, and cost a
correction to pushed documents. (2) Question my own evaluation cap as soon as a failure
was labelled "ran out of time", not after. (3) Run long jobs unbuffered from the start (a
progress monitor saw nothing for 30 minutes because Python buffers when writing to a
file; the run itself was fine).

**37. The back-and-forth pattern.** After the recordings, the project owner noticed that
wins look like "go in, search, rescue, leave" and failures look like the same until the
network gets confused, paces between two squares, and dies or gives up. Instead of
agreeing, I measured it: replayed the same 100 seeded episodes for A* and the v2
clone and counted runs of stepping back onto the tile just left. **A\* has none in 100
episodes; all 10 of the clone's give-ups contain one** (median 103 in a row, 47% of its
moves), against 3 of 10 deaths and 6 of 80 wins. One point in my first reading of the
result was wrong and is corrected in the document: the longest run begins before anyone
has been delivered in 9 of the 10 give-ups, so the pacing is a mid-episode event and the
one-occupant-short stall at the end is a separate one. Registered predictions for a
memory feature (P7) and a route-damage feature (P8) in PREDICTIONS.md *before* running
either. Attribution: the observation is the project owner's.

**38. Is it fair to give the network memory?** The project owner asked whether the model may
remember everything it walked and saw on the current map, starting empty. Checked against A*'s
code: A* records what it has seen (`explored`), the occupants it has spotted, and every tile it
has walked (`trail_cells`, used only for drawing), starting empty each episode. So a memory of the
agent's own experience is within parity, provided it starts empty each episode, holds only its own
experience, and is nothing A* lacks. Tests written for all three, including that memory is empty at
the start of every episode. Two levels tested: a short memory (last move + last four tiles) and
the full trail (visit counts, whole episode).

**39. Predictions registered, then the memory runs** (`imit_c`, `imit_d`). Same 65,787
demonstration decisions, network and schedule as `imit_b`. First 100-episode test (240 s):
v2 80%, v3 84%, v4 87%; pacing episodes 19, 10, 5 (A* 0). **P7 falsified on both clauses, P9
held.**

**40. The videos disagreed with the numbers, and that was informative.** On the seven fixed
recording episodes v3 and v4 were *not* better than v2 (v2 4 wins, v3 4, v4 3). Seven episodes
prove nothing either way, which is why the recordings table states it.

**41. Four variants on one test set: a confirmation on fresh seeds.** Wrote the prediction (P10)
*before* running 200 episodes nobody had used. **Falsified**: v4 76%, below the 79% floor, v2 75%.
A* moved from 91% to 85%, so seed sets swing by about 6 points. By my own pre-stated rule the
memory gain was mostly the test set being reused.

**42. What survived.** The pacing reduction replicated (v2 39, v4 15 of 200; A* 0), and deaths fell
(12% to 8%). Pooled over both sets (300 episodes) memory adds 3 points (77% to 80%, paired p ~ 0.04),
and A* still clearly beats v4 (25 episodes to 4, p ~ 0.0001), mainly on the unseen stages (87% vs
71%). A second overstatement of mine was corrected: "every give-up contains pacing" was 10 of 10 in the
first set but 15 of 25 (60%) on fresh episodes. The summaries in the README, the study and FINDINGS
were rewritten to the pooled numbers.

**43. Is stalling the failure? (owner's hypothesis, 300 episodes per agent).** Broadened the
pacing definition (at most 3 different tiles in the last 16 entered) and measured it. A* stalls in
0 of 300; v2 in 51, v4 in 24. Stalling is in 47% of v2's failures but 27% of v4's. It is
concentrated on stages 8-10 (v2 47%, v4 23% of episodes) against 4% and 1% on the trained stages,
though "higher" and "unseen" are confounded. While stalled, v4's moves change goal 77% of the
time (7% otherwise): undecided between goals rather than lost. Exploratory (P11).

**44. What removing stalls is worth (upper bound).** When a network stalls, A* takes the next
10 / 40 / 200 decisions. v2 77% to 83 / 84 / 84%; v4 80% to 82 / 82 / 83%; no episode was lost by the
help. So stalling is a large problem for v2 on unseen stages and only worth 2 to 3 points for v4,
whose remaining failures are mostly the endgame "one occupant short" give-up (20 of 22
non-stalling give-ups) and stage-7 deaths (10 of the 26 deaths left after stall-breaking).

**45. Do they give up because the last occupant "is not worth it"?** A* has that rule (health
budget 0.6); the network has no reward and only stands still for 12 s. Inspected the end state of
every give-up. A*: 16, all deliberate (on the exit, budget rule says stop). v4: 36; in 23-24 A*
would also stop (copied caution), in 13 A* would keep searching (real errors). First version of the
check reported "A* would also stay" for all 36 because `expert_action` returns stay for any finished
agent; caught by the 36/36 being suspicious, fixed by computing A*'s goal directly.

**46. Does the search order matter?** Patched only A*'s frontier choice inside the test workers (the
benchmark file is untouched); five orders on 300 episodes each. Unmodified rule reproduced 87%/505.
Mild far-side lean 91% (p ~ 0.02), forced far-first 79%, near-exit sweep 81%. Registered P12, then
confirmed on 200 fresh episodes: 90% vs 84% (held); pooled p ~ 0.0003. Score gain not settled.
Picked the best of four on one set, so the fresh run was essential.

**47. Teacher for v5, and a flaw in my far-side rule.** Turned the far-side search into a real agent
option (`frontier_lean`, default off: the benchmark is byte-for-byte the same) and added the owner's
fog-of-war corner rule (`frontier_min_reveal K`: skip a frontier that would reveal fewer than K unseen
floor tiles, so no special trip into a corner's last tiles). A test then found the flaw: I had measured
distance-from-exit once while the locked door was closed, so the spawn side had no distance. Stopped
the v5 run (14 epochs in), fixed it, re-measured everything (far side 91% vs 87%; fresh 90% vs 84%)
and restarted. Corner rule: skipping corners under 4 tiles costs nothing (91%, score 512); under 8
tiles evacuation falls to 81% (an occupant is sometimes in the corner) though it is faster (40 s vs
43 s) and scores the same; under 12 tiles, 60%. Deferring corners instead of skipping them (visit
only when nothing bigger is left) gave 85-87%, no better than A*. v5's teacher = far side + skip < 4.

**48. v5 trained and compared per stage.** Same recipe as v4, teacher = far side + skip corners < 4
(22 min). On 300 fresh episodes (seeds 950,000+): A* 85%, v5 84%, v4 81%; A*-v5 not distinguishable,
v5-v4 not established. Unseen stages 73% vs A*'s 87%; stage 7 the shared weak spot (v5 13 deaths of 30).
Recorded seven v5 clips on the v4 episodes.

**49. Game menu.** "Choose the AI's Brain" now lists A* (default), Learned v4 and Learned v5 whenever
their files are in `ml/models/` (`ai_v4.zip`, `ai_v5.zip`, each with a `.json` recording the search order
it was trained with). Shown in Watch AI Play only (Play vs AI keeps its A* rival and its old flow,
which a teammate's end-to-end key-driving test depends on). A model that fails to load falls back to
A*. 15 new tests (209 total).

**Things I would do differently (memory).** (1) Confirm on fresh seeds *before* writing a
headline, not after. (2) Never write "every X" from ten cases. (3) Pool independent test sets
early; a single 100-episode set carries a large swing.
