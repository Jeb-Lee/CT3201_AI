Fresh episodes (seeds 190,000+), 20 per stage, 240 s cap. The earlier 100-episode test gave: A* 91% (84-95), v2 80% (71-87), v4 87% (79-92).

| agent | stages | n | evacuated (95% CI) | died | gave up | occupants led out | median seconds |
|---|---|---|---|---|---|---|---|
| astar | trained 1-7 | 140 | 84% (77%-89%) | 9% | 8% | 92% | 34 |
| astar | unseen 8-10 | 60 | 88% (78%-94%) | 5% | 7% | 94% | 57 |
| astar | all ten | 200 | 85% (79%-89%) | 8% | 8% | 92% | 38 |
| v2 deterministic | trained 1-7 | 140 | 79% (72%-85%) | 11% | 10% | 89% | 36 |
| v2 deterministic | unseen 8-10 | 60 | 65% (52%-76%) | 17% | 18% | 79% | 72 |
| v2 deterministic | all ten | 200 | 75% (69%-80%) | 12% | 12% | 86% | 40 |
| v4 deterministic | trained 1-7 | 140 | 81% (73%-86%) | 9% | 11% | 90% | 36 |
| v4 deterministic | unseen 8-10 | 60 | 67% (54%-77%) | 5% | 28% | 89% | 65 |
| v4 deterministic | all ten | 200 | 76% (70%-82%) | 8% | 16% | 90% | 40 |
| v4 sampled | trained 1-7 | 140 | 81% (74%-87%) | 8% | 11% | 90% | 36 |
| v4 sampled | unseen 8-10 | 60 | 68% (56%-79%) | 8% | 23% | 88% | 67 |
| v4 sampled | all ten | 200 | 78% (71%-83%) | 8% | 14% | 90% | 40 |

Paired on the same 200 episodes (evacuated everyone):

| first | second | both | only first | only second |
|---|---|---|---|---|
| v2 deterministic | v4 deterministic | 145 | 5 | 8 |
| astar | v4 deterministic | 152 | 18 | 1 |
| astar | v2 deterministic | 148 | 22 | 2 |
