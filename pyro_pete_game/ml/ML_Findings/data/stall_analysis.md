Stall = at most 3 different tiles among the last 16 entered; an episode is stalled if that held at 10+ moments. 300 episodes per agent (both 240 s test sets), deterministic.

## 1. How many episodes stall, and how many failures involve a stall

| agent | episodes | stalled | won | of the wins, stalled | failed | of the failures, **stalled** |
|---|---|---|---|---|---|---|
| A* | 300 | 0 (0%) | 261 | 0 | 39 | **0 (0%)** |
| v2 | 300 | 51 (17%) | 230 | 18 | 70 | **33 (47%)** |
| v4 | 300 | 24 (8%) | 240 | 8 | 60 | **16 (27%)** |

Failures by kind, and whether they stalled (v4):

| ending | episodes | stalled |
|---|---|---|
| died | 24 | 2 (8%) |
| gave_up | 36 | 14 (39%) |

## 2. What is the network doing while it stalls?

| v4 | decisions | mean confidence (top probability) | mean entropy | chose to STAY | follows **no** goal's best move | switches goal from one move to the next |
|---|---|---|---|---|---|---|
| while stalled | 2615 | 0.83 | 0.36 | 12% | 17% | 77% (of 1998 pairs) |
| otherwise | 37701 | 0.99 | 0.02 | 3% | 4% | 7% (of 10543 pairs) |

Same, for v2:

| v2 | decisions | mean confidence | mean entropy | chose to STAY | follows no goal's best move | switches goal |
|---|---|---|---|---|---|---|
| while stalled | 8270 | 0.86 | 0.31 | 5% | 16% | 98% (of 5952) |
| otherwise | 36624 | 0.99 | 0.03 | 3% | 4% | 12% (of 9774) |

## 3. By stage: share of episodes that stall

| stage | A* | v2 | v4 |
|---|---|---|---|
| 1 | 0/30 | 1/30 | 0/30 |
| 2 | 0/30 | 0/30 | 0/30 |
| 3 | 0/30 | 1/30 | 1/30 |
| 4 | 0/30 | 0/30 | 1/30 |
| 5 | 0/30 | 4/30 | 0/30 |
| 6 | 0/30 | 1/30 | 0/30 |
| 7 | 0/30 | 2/30 | 1/30 |
| 8 (unseen) | 0/30 | 10/30 | 6/30 |
| 9 (unseen) | 0/30 | 18/30 | 10/30 |
| 10 (unseen) | 0/30 | 14/30 | 5/30 |
| **trained 1-7** | 0/210 (0%) | 9/210 (4%) | 3/210 (1%) |
| **unseen 8-10** | 0/90 (0%) | 42/90 (47%) | 21/90 (23%) |
