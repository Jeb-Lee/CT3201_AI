## Primary: 240 s cap (the real game has no hard time limit)

| agent | stages | n | evacuated everyone (95% CI) | died | gave up | ran out of time | occupants led out | mean score |
|---|---|---|---|---|---|---|---|---|
| A* | trained 1-7 | 70 | 94% (86%-98%) | 6% | 0% | 0% | 94% | 473 |
| A* | unseen 8-10 | 30 | 83% (66%-93%) | 13% | 3% | 0% | 86% | 568 |
| A* | all ten | 100 | 91% (84%-95%) | 8% | 1% | 0% | 92% | 502 |
| v2 clone, deterministic | trained 1-7 | 70 | 89% (79%-94%) | 7% | 4% | 0% | 93% | 462 |
| v2 clone, deterministic | unseen 8-10 | 30 | 60% (42%-75%) | 17% | 23% | 0% | 79% | 520 |
| v2 clone, deterministic | all ten | 100 | 80% (71%-87%) | 10% | 10% | 0% | 89% | 480 |
| v2 clone, sampled | trained 1-7 | 70 | 90% (81%-95%) | 7% | 3% | 0% | 92% | 459 |
| v2 clone, sampled | unseen 8-10 | 30 | 73% (56%-86%) | 7% | 20% | 0% | 89% | 584 |
| v2 clone, sampled | all ten | 100 | 85% (77%-91%) | 7% | 8% | 0% | 91% | 496 |
| v1 clone, deterministic | trained 1-7 | 70 | 29% (19%-40%) | 66% | 6% | 0% | 34% | 158 |
| v1 clone, deterministic | unseen 8-10 | 30 | 0% (0%-11%) | 97% | 3% | 0% | 6% | 33 |
| v1 clone, deterministic | all ten | 100 | 20% (13%-29%) | 75% | 5% | 0% | 25% | 121 |
| v1 clone, sampled | trained 1-7 | 70 | 37% (27%-49%) | 60% | 3% | 0% | 44% | 199 |
| v1 clone, sampled | unseen 8-10 | 30 | 0% (0%-11%) | 100% | 0% | 0% | 0% | 0 |
| v1 clone, sampled | all ten | 100 | 26% (18%-35%) | 72% | 2% | 0% | 31% | 139 |

## For comparison: the 90 s cap used during training

| agent | stages | n | evacuated everyone (95% CI) | died | gave up | ran out of time | occupants led out | mean score |
|---|---|---|---|---|---|---|---|---|
| A* | trained 1-7 | 70 | 94% (86%-98%) | 6% | 0% | 0% | 94% | 473 |
| A* | unseen 8-10 | 30 | 83% (66%-93%) | 13% | 3% | 0% | 86% | 568 |
| A* | all ten | 100 | 91% (84%-95%) | 8% | 1% | 0% | 92% | 502 |
| v2 clone, deterministic | trained 1-7 | 70 | 89% (79%-94%) | 6% | 4% | 1% | 92% | 459 |
| v2 clone, deterministic | unseen 8-10 | 30 | 47% (30%-64%) | 10% | 3% | 40% | 49% | 327 |
| v2 clone, deterministic | all ten | 100 | 76% (67%-83%) | 7% | 4% | 13% | 79% | 419 |
| v2 clone, sampled | trained 1-7 | 70 | 90% (81%-95%) | 7% | 1% | 1% | 92% | 458 |
| v2 clone, sampled | unseen 8-10 | 30 | 60% (42%-75%) | 7% | 0% | 33% | 65% | 424 |
| v2 clone, sampled | all ten | 100 | 81% (72%-87%) | 7% | 1% | 11% | 84% | 448 |
| v1 clone, deterministic | trained 1-7 | 70 | 29% (19%-40%) | 39% | 3% | 30% | 32% | 147 |
| v1 clone, deterministic | unseen 8-10 | 30 | 0% (0%-11%) | 40% | 0% | 60% | 3% | 17 |
| v1 clone, deterministic | all ten | 100 | 20% (13%-29%) | 39% | 2% | 39% | 23% | 108 |
| v1 clone, sampled | trained 1-7 | 70 | 36% (26%-47%) | 27% | 0% | 37% | 43% | 194 |
| v1 clone, sampled | unseen 8-10 | 30 | 0% (0%-11%) | 60% | 0% | 40% | 0% | 0 |
| v1 clone, sampled | all ten | 100 | 25% (18%-34%) | 37% | 0% | 38% | 30% | 136 |

Paired, v2 deterministic vs A* on the same 100 episodes (240 s cap): both evacuated 78, only A* 13, only the clone 2.

## Where the give-ups come from

Episodes that ended by giving up, and how many occupants were still inside:

* astar: 1 of 100 episodes; occupants still inside: 1 left in 1
* v2 deterministic: 10 of 100 episodes; occupants still inside: 1 left in 9, 2 left in 1
* v2 sampled: 8 of 100 episodes; occupants still inside: 1 left in 7, 2 left in 1
