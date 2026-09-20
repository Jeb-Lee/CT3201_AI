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
