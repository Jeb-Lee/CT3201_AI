Two independent 240 s test sets pooled: 100 episodes (seeds 90,000+) + 200 fresh episodes (seeds 190,000+) = 300 per agent.

| agent | stages | n | evacuated everyone (95% CI) | died | gave up | occupants led out |
|---|---|---|---|---|---|---|
| astar | trained 1-7 | 210 | 87% (82%-91%) | 8% | 5% | 93% |
| astar | unseen 8-10 | 90 | 87% (78%-92%) | 8% | 6% | 91% |
| astar | all ten | 300 | 87% (83%-90%) | 8% | 5% | 92% |
| v2 deterministic | trained 1-7 | 210 | 82% (77%-87%) | 10% | 8% | 90% |
| v2 deterministic | unseen 8-10 | 90 | 63% (53%-73%) | 17% | 20% | 79% |
| v2 deterministic | all ten | 300 | 77% (72%-81%) | 12% | 12% | 87% |
| v4 deterministic | trained 1-7 | 210 | 84% (78%-88%) | 9% | 8% | 91% |
| v4 deterministic | unseen 8-10 | 90 | 71% (61%-79%) | 7% | 22% | 89% |
| v4 deterministic | all ten | 300 | 80% (75%-84%) | 8% | 12% | 90% |
| v4 sampled | trained 1-7 | 210 | 85% (79%-89%) | 7% | 8% | 91% |
| v4 sampled | unseen 8-10 | 90 | 71% (61%-79%) | 10% | 19% | 88% |
| v4 sampled | all ten | 300 | 81% (76%-85%) | 8% | 11% | 90% |

Paired on the same 300 episodes (evacuated everyone; exact sign test on the episodes only one won):

| first | second | both | only first | only second | p |
|---|---|---|---|---|---|
| v2 deterministic | v4 deterministic | 225 | 5 | 15 | 0.0414 |
| astar | v4 deterministic | 236 | 25 | 4 | 0.0001 |
| astar | v2 deterministic | 226 | 35 | 4 | 0.0000 |
