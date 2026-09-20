Time cap 240 s (the training-time final test used 90 s). Same seeded episodes for every agent.

| agent | stages | n | evacuated (95% CI) | died | gave up | ran out of time | occupants led out | median seconds |
|---|---|---|---|---|---|---|---|---|
| astar | trained 1-7 | 70 | 94% (86%-98%) | 6% | 0% | 0% | 94% | 34 |
| astar | unseen 8-10 | 30 | 83% (66%-93%) | 13% | 3% | 0% | 86% | 53 |
| astar | all ten | 100 | 91% (84%-95%) | 8% | 1% | 0% | 92% | 39 |
| v1 deterministic | trained 1-7 | 70 | 29% (19%-40%) | 66% | 6% | 0% | 34% | 59 |
| v1 deterministic | unseen 8-10 | 30 | 0% (0%-11%) | 97% | 3% | 0% | 6% | 99 |
| v1 deterministic | all ten | 100 | 20% (13%-29%) | 75% | 5% | 0% | 25% | 71 |
| v1 sampled | trained 1-7 | 70 | 37% (27%-49%) | 60% | 3% | 0% | 44% | 68 |
| v1 sampled | unseen 8-10 | 30 | 0% (0%-11%) | 100% | 0% | 0% | 0% | 76 |
| v1 sampled | all ten | 100 | 26% (18%-35%) | 72% | 2% | 0% | 31% | 74 |
| v2 deterministic | trained 1-7 | 70 | 89% (79%-94%) | 7% | 4% | 0% | 93% | 35 |
| v2 deterministic | unseen 8-10 | 30 | 60% (42%-75%) | 17% | 23% | 0% | 79% | 76 |
| v2 deterministic | all ten | 100 | 80% (71%-87%) | 10% | 10% | 0% | 89% | 42 |
| v2 sampled | trained 1-7 | 70 | 90% (81%-95%) | 7% | 3% | 0% | 92% | 35 |
| v2 sampled | unseen 8-10 | 30 | 73% (56%-86%) | 7% | 20% | 0% | 89% | 72 |
| v2 sampled | all ten | 100 | 85% (77%-91%) | 7% | 8% | 0% | 91% | 42 |
| v3 deterministic | trained 1-7 | 70 | 90% (81%-95%) | 9% | 1% | 0% | 91% | 35 |
| v3 deterministic | unseen 8-10 | 30 | 70% (52%-83%) | 17% | 13% | 0% | 84% | 71 |
| v3 deterministic | all ten | 100 | 84% (76%-90%) | 11% | 5% | 0% | 89% | 42 |
| v3 sampled | trained 1-7 | 70 | 91% (83%-96%) | 7% | 1% | 0% | 92% | 35 |
| v3 sampled | unseen 8-10 | 30 | 77% (59%-88%) | 10% | 13% | 0% | 88% | 64 |
| v3 sampled | all ten | 100 | 87% (79%-92%) | 8% | 5% | 0% | 91% | 42 |
| v4 deterministic | trained 1-7 | 70 | 90% (81%-95%) | 9% | 1% | 0% | 92% | 35 |
| v4 deterministic | unseen 8-10 | 30 | 80% (63%-90%) | 10% | 10% | 0% | 88% | 62 |
| v4 deterministic | all ten | 100 | 87% (79%-92%) | 9% | 4% | 0% | 91% | 42 |
| v4 sampled | trained 1-7 | 70 | 91% (83%-96%) | 6% | 3% | 0% | 94% | 35 |
| v4 sampled | unseen 8-10 | 30 | 77% (59%-88%) | 13% | 10% | 0% | 88% | 62 |
| v4 sampled | all ten | 100 | 87% (79%-92%) | 8% | 5% | 0% | 92% | 42 |

A* episodes that evacuated but took longer than 90 s: 0 of 91 (longest 78 s).
