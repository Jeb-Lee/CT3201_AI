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

**2. Fair-information design.** Before writing any learning code, the observation
was restricted to what A* is allowed to know (explored layout only; hazards and
occupants within 3.5 tiles; exit, head-count and fire countdown always known),
and a test was written to enforce it. Rationale: an agent that can see the whole
burning building would beat A* by cheating, and the comparison would mean
nothing.

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
