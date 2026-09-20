# Predictions written down before the runs

*Recorded 2026-09-20, before experiments 03, 04 and 05 and before the seed-1/2
replicates had finished. What I had already seen when writing this: the two
seed-0 runs (exp01 and exp02) and the reward-accounting table
(`data/reward_accounting.md`). Nothing else. The point of writing predictions
first is that a result can then count as a test of the explanation instead of
being fitted to it afterwards. Outcomes are recorded next to each prediction in
[REWARD_EVOLUTION.md](REWARD_EVOLUTION.md).*

## The explanation being tested

> Under this game's reward, random exploration never saves anyone, so the
> optimiser never sees a positive outcome. All it can compare is *ways of
> failing*, and it learns to prefer the cheapest one. Changing the price of one
> failure moves the collapse to the next cheapest failure; it cannot produce a
> rescue, because nothing in the reward leads toward one.

Measured cost of each ending for a behaviour that never rescues anyone
(reward-accounting table, 30 episodes, stages 1-3, plain reward):

| ending | how it happens | return |
|---|---|---|
| give up | stand still 12 s | about -0.6 |
| die | wander into fire | about -142 |
| time out | keep moving safely until the limit (90 s) | about -4.5 (computed: 90 s x 0.05) |

So under the plain reward, standing still beats wandering by about 142 points,
and pacing safely until the time limit would beat both.

## Predictions

**P1 - replicates (exp01 plain, exp02 abandon-penalty, seeds 1 and 2, 100k steps).**
Every seed ends with 0% training accuracy and no occupant led out. Under the
plain reward, "gave up" is the majority ending by 100k steps in every seed
(>= 60% of the last 100 episodes). With the abandon penalty the collapse to
"gave up" is no larger than under the plain reward, because that penalty
charges standing still and dying the same amount.
*Falsified if:* any seed saves an occupant, or the plain-reward seeds do not
collapse to giving up.

**P2 - long run (exp03, abandon penalty 100, 500k steps, seed 0).**
Still no rescues. Held-out accuracy stays 0% and fewer than 5% of training
episodes lead any occupant out. More steps of the same reward do not fix it.
*Falsified if:* accuracy or occupants-out climbs meaningfully above zero.

**P3 - penalise giving up (exp04, `give_up = 200`, seeds 0 and 1, 100k steps).**
Standing still now costs about -200.6, worse than dying (-142). Prediction:
the "gave up" share falls to <= 10%, and it is replaced mostly by **timeouts**
(>= 50% of episodes end by the clock: the AI learns to pace safely), with 0
occupants led out.
*Falsified if:* giving up stays the majority ending, or if a rescue appears.

**P4 - penalise every non-fatal failure (exp05, `give_up = 200` and
`timeout = 200`, seed 0, 100k steps).**
Both cheap failures now cost more than dying. Prediction: the policy shifts to
**dying** (>= 70% of episodes end in death), still with 0 occupants led out.
The collapse just moves to the last ending left.
*Falsified if:* it keeps giving up or timing out, or if it starts rescuing.

## What a positive result would mean

If P3 or P4 instead produced rescues, the explanation is wrong and the reward
*was* leading toward success, only slowly. If all four predictions hold, the
supported conclusion is narrow: with this reward and a random-exploration
start, tuning failure penalties cannot work, and something that puts the agent
in contact with a success (a warm start from A*, a curriculum, or shaping) is
required. It is a claim about this setup, not about reinforcement learning in
general.

---

## Addendum, written after the 100k-step replicates and before experiment 06

*What I had seen when writing this: the six 100k-step runs (three seeds each of
exp01 and exp02). What I had not: any result from exp03-05, and anything from
the continuation run below.*

The replicates contradicted part of P1. Two of the three plain-reward seeds
**did** lead occupants out during training (seed 0 in 9 of 33 epochs, peak 1.8%
of occupants; seed 2 in 23 of 33 epochs, peak 8.5%), while the three
abandon-penalty seeds never did. Seed 2 also ended with a *positive* mean
return (+20, against about -1 for standing still): it looks like the one run
that has started to climb out of the standing-still trap.

**P5 - continue plain-reward seed 2 (exp06, `--resume` from exp01_plain_s2's
final model, 400k more steps, same settings).**
The share of occupants led out keeps rising above its 100k-step value (7.8%),
so the trap is not absolute for this seed. But it does **not** turn into a
competent rescuer within this budget: training-stage full-evacuation accuracy
stays below 20% at 500k total steps, and A* stays clearly ahead on the
held-out stage.
*Falsified if:* accuracy passes 20%, or if the rescue share falls back to
zero (the earlier rescues were a transient).

*Caveat recorded up front:* resuming discards the reward-normalisation
statistics (they are not saved with the model), so the first few epochs of the
continuation are not a perfectly clean continuation.

---

## Amendment: budget cut and one new prediction

*Written after seeing exp04 seed 0 (give-up penalty 200, 100k steps) and
before exp04 seed 1, exp05, or any long run.*

**What exp04 seed 0 showed, which I had not predicted:** giving up fell to 0%
(as P3 said), but the collapse did **not** move to timeouts: at 100k steps 83%
of episodes ended in death and 17% in timeouts (P3 said >= 50% timeouts), and
**7.2% of occupants were led out** (P3 said 0). So P3 is already partly
falsified by one seed; seed 1 will show whether it is a fluke.

**Budget.** Training ran at about 250 steps/s, not the 550 first measured, so
the queued long runs would have taken over an hour. Changes:

* exp06 (P5, continue plain seed 2): **+300k steps** instead of +400k.
* exp03 (P2, abandon penalty long run): **300k steps** instead of 500k, and it
  now runs last, so it may be cut short or dropped. If it is not run, P2 is
  reported as *untested*, not as held.
* **New: exp07, give-up penalty 200 for 300k steps (seed 0).** Chosen because it
  is the setting where a rescue signal is visibly alive.

**P6 - the give-up-penalty run keeps improving with more steps (exp07).**
The share of occupants led out at 300k is above its 100k value (7.2% in
exp04 seed 0), so this is not a plateau. Full evacuation on training stages
still stays under 20%, and A* stays clearly ahead on the held-out stage.
*Falsified if:* the rescue share is at or below 7% at 300k, or accuracy reaches
20% or more.

---

## Outcomes (added after all runs finished)

Details and numbers are in [REWARD_EVOLUTION.md](REWARD_EVOLUTION.md) and
[FINDINGS.md](FINDINGS.md) section 3. In short:

| prediction | outcome |
|---|---|
| **P1** replicates: no rescues; plain collapses to giving up; abandon no worse | **Partly falsified.** No full evacuation anywhere and plain seeds collapsed (91, 80, 74% gave up), abandon no worse (42-50%): held. But plain seeds 0 and 2 *did* lead occupants out (peak 1.8% and 8.5%): falsified. |
| **P2** long abandon run: still no rescues | **Held**, at 300k steps not 500k (0 rescues in 98 epochs). |
| **P3** give-up penalty: collapse moves to timeouts, no rescues | **Not supported.** Seed 0: gave up 0%, timeouts 17%, rescues 7.2%. Seed 1: gave up 30%, timeouts 23%, no rescues. |
| **P4** both penalties: collapse moves to dying | **Held as written** (87% died) but uninformative: dying is where training started; return fell below the random start. |
| **P5** continued plain seed 2 climbs but stays under 20% | **Held** (occupants 7.8% -> 13.5%; full evacuation <= 4%). Budget cut to +300k steps. |
| **P6** give-up penalty long run keeps improving, under 20% | **Held** (7.2% -> 22.9% of occupants; peak accuracy 5%). |

Predictions that were wrong were wrong in the specific clauses about rescues
and about where the collapse moves. The general claim under test, that
failure penalties cannot by themselves create a competent rescuer, was not
contradicted by anything here, but it is a claim about this setup and 100k-300k
steps, and one run (v3 long) shows a rescue skill growing under a failure
penalty, which the original wording ("cannot create a rescue") did not allow
for.

---

## Imitation follow-ups (registered 2026-09-20, before any run)

*What I had seen when writing this: the two imitation runs, the 240 s comparison, the
recordings, and the back-and-forth measurement in
[IMITATION.md](IMITATION.md) 4.6. Nothing from any experiment below.*

Both proposed changes obey the information-parity rule: a memory of the agent's own
past tiles is not more than A* has (A* itself carries a goal and a planned route
between decisions), and the route-damage figure is one A* computes.

**P7 - a short memory removes the pacing.** Version 3a = version 2 + the last four
tiles visited and the previous move as extra inputs. Same data, network, training and
test as `imit_b`.
*Prediction:* flagged (6+ reversals in a row) episodes fall from **19 of 100** to
**6 or fewer**, and all-ten deterministic evacuation at 240 s rises from **80%** to
**85% or more**, mostly on the unseen stages (from 60%).
*Falsified if:* flagged episodes stay above 10, or evacuation does not rise. If
pacing disappears but evacuation does not rise, then pacing was a symptom and not the
cause.

**P8 - the route damage fixes the endgame.** Version 3b = version 2 + the estimated
round-trip fire damage to the nearest unexplored area and the ratio to health (what A*
uses in `_worth_exploring`).
*Prediction:* the give-ups that end one occupant short fall from **9 of 100** to
**4 or fewer**, without changing the pacing count.
*Falsified if:* they stay at 7 or more, which would mean the endgame decision is not
what is missing.

**Interaction, stated in advance:** if both are true, version 3a+3b should reach the
A* level (about 91%) on the trained stages and within one interval of it on the unseen
ones. I do not expect it to *exceed* A*; nothing here suggests copying can.

---

## Amendment: a fuller memory (registered 2026-09-20, before any memory run)

*Prompted by the project owner asking whether it is fair for the model to remember
everything it walked and saw on the current map, starting empty and accumulating.
Answer, from A*'s code: yes, provided the memory starts empty each episode, holds only
the agent's own experience, and is nothing A* does not also hold. A* records the tiles it
has seen (`explored`), the occupants it has spotted (`known_victims`) and every tile it
has walked (`trail_cells`); it uses the first two to decide and only draws the third. So a
walked-tiles memory is within parity, and the learner already receives the first two
through the map window and the route hints.*

Two memory levels, both compared against `imit_b` (v2) with identical data, network,
seeds, DAgger schedule and test:

* **v3, short memory (P7 above, unchanged):** the last move and the last four tiles stood on.
* **v4, full trail:** v3 plus, for every tile in the 11 x 11 window, how many times the
  agent has stood on it this episode (capped at 5, scaled to 0-1), empty at the start.

**P9 - the full trail does at least as well as the short memory and removes the pacing.**
*Prediction:* flagged episodes (6+ reversals in a row) for v4 are **no more than for v3**
and at most **6 of 100**; all-ten deterministic evacuation at 240 s for v4 is **within 5
points of v3** (I do not expect a large extra gain, because the pacing is a short-horizon
loop that the last few tiles already reveal). *Falsified if:* v4 is worse than v3 by more
than 5 points (extra inputs hurting), or v4 flags more episodes than v3.

**Risk registered in advance:** A* almost never revisits tiles, so the demonstrations show
the network almost no looping states. The memory inputs will be nearly uninformative in the
cloning phase; whatever it learns to do with them has to come from the DAgger rounds, where
the network's own loops are labelled by A*. If memory helps at all, I expect it to be there.

*Unchanged from before:* I do not expect either version to exceed A*.

---

## Outcomes of P7 and P9, and a confirmation test (registered before it runs)

**Outcomes** (`data/memory_summary.md`, computed by code from the 240 s test, same 100
episodes): **P7 falsified on both clauses** (v3: 10 pacing episodes against a predicted
6 or fewer; evacuation 84% against a predicted 85% or more; the direction was right, the
size was not). **P9 held** (v4: 5 pacing episodes, no more than v3's 10 and at most 6; 87%
evacuation, within 5 points of v3's 84%). One thing the criteria did not capture: I
expected no *large* extra gain from the full trail, and on the unseen stages it gained 10
points over v3 (80% against 70%), more than I expected.

**Why a confirmation test.** Four network variants (v1 to v4) have now been evaluated on
the same 100 test episodes. The more variants tried on one test set, the more the
best-looking one is flattered by chance. So the final candidate is checked once more on
episodes nobody has used: 20 fresh episodes on each of the ten stages (seeds 190,000 and
up), for A*, v2 and v4.

**P10 (registered now, before running).** v4's all-ten deterministic evacuation on the
fresh episodes lies **inside the 95% interval it already had, 79-92%**; A* lies inside its
own earlier interval, 84-95%; and in the paired counts v4 wins **at least as many
episodes as v2 wins over it** (only-v4 >= only-v2).
*Falsified if:* v4 falls below 79%, or v2 beats v4 in the paired counts. If v4 falls below
79%, the memory gain was mostly the test set being reused.

**Outcome of P10 (fresh episodes, 200 per agent, seeds 190,000+).** **Falsified.** v4 scored
**76%** (70-82), below the 79% floor I set. A* scored 85% (79-89), inside its interval; in the
paired counts v4 won 8 episodes v2 lost and lost 5 (that clause held). By my own pre-stated
rule, the first test's memory gain was mostly the test set being reused: v4 beat v2 by 1
point on fresh episodes. Pooled over both sets (300 episodes) the gain is 3 points (77% to 80%,
paired p ~ 0.04). What did replicate is the reduction in back-and-forth pacing (v2 39 episodes,
v4 15, out of 200; A* 0) and the drop in deaths (12% to 8%). (`data/confirmation_240s.md`,
`data/pooled_300.md`, `data/oscillation_fresh.md`.)

**P11 (the project owner's hypothesis, tested after the fact, NOT registered in advance).**
After watching the v4 clips the owner said: the failures are mainly stalling; it is either
undecided between two paths or does not know what to do; it is mainly a higher-stage problem;
and removing it would raise success significantly. The test code was written before the results
were seen but the definition of "stall" (at most 3 different tiles among the last 16 entered,
10+ moments) is mine, so this is exploratory, not confirmatory.

**Outcome of P11 (300 episodes per agent).** *Mostly* supported, with two corrections.
(1) "Mainly stalling": v2 47% of failures contain a stall, v4 27%; v4's biggest failure class
is the non-stalling endgame give-up. (2) "Higher stages": stalling is 4% (v2) and 1% (v4) of
trained-stage episodes but 47% and 23% of stages 8-10; higher and unseen are confounded.
(3) "Undecided between paths": supported (77% of stalled moves change goal against 7% otherwise),
with a minority of lost moments. (4) "Significantly": +7 to +8 points for v2, only +2 to +3 for v4
(upper bound, borrowing A*). (`IMITATION.md` 4.9, `data/stall_analysis.md`,
`data/stall_counterfactual_{10,40,200}.md`.)

**P12 (registered now, before running).** On 200 episodes nobody has used (seeds 290,000+, 20 per
stage), A* with a mild far-side lean in its search order (`far_soft`: minimise distance-from-agent
minus 0.5 x distance-from-exit) **evacuates at least 2 points more than A*'s own nearest-frontier rule
and gives up less often**. It was 91% against 87% and 2% against 5% give-ups on the 300 episodes
where it was found, after four variants were tried there (forking paths).
*Falsified if:* far_soft evacuates less than nearest + 2 points on the fresh episodes, or its give-up
rate is not lower. The mean game score is *not* predicted to move (it was +2 points, indistinguishable
from 0). `far_hard` is tested too but only `far_soft` is the registered claim.

**Outcome of P12 (fresh episodes, 200, seeds 290,000+).** **Held.** far_soft evacuated **90%**
against nearest's **84%** (+6, needed +2) and gave up 2% against 5%; it won 13 episodes nearest lost
and lost 2. Pooled over both sets (500 episodes) 90.6% against 86.0%, won 31 / lost 8, sign test
p ~ 0.0003. Not predicted, and on the fresh set the other way from the first: far_soft's mean game
score was +18 (+2 to +34) higher there but +2 on the first set (pooled +8), so the score gain is
small and not settled. far_hard was 86% against 84% on the fresh set (not distinguishable; pooled
p ~ 0.05, mean score -3). Caveat: far_soft was picked as the best of four variants on the first set,
then confirmed once. (`IMITATION.md` 4.11, `data/frontier_variants*.md`.)

**P12 re-check with the corrected rule.** The far-side rule originally measured "distance from the
exit" with the locked door closed (spawn side missing, treated as 0). With the rule corrected to use the
static floor plan and run as a real agent option, on the same 200 fresh episodes: **90% against 84%**,
give-ups 2% against 5%, mean score 505 against 488. P12 still holds. (`data/teacher_variants_fresh.md`)

**Scorecard for the imitation follow-ups:** P7 falsified, P9 held on the first test set,
P10 falsified, P11 mostly supported (exploratory), P12 held. P8 (route damage) is still untested.
