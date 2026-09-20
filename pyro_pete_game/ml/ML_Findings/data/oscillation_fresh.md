Same 200 seeded episodes per agent (240 s cap), deterministic clones. A back-and-forth run is consecutive reversals; an episode is *flagged* if its longest run is at least 6 reversals.

| agent | outcome | episodes | flagged (long ping-pong) | median longest run | median reversal share of moves |
|---|---|---|---|---|---|
| A* | evacuated | 170 | 0 (0%) | 1 | 3% |
| A* | died | 15 | 0 (0%) | 1 | 3% |
| A* | gave_up | 15 | 0 (0%) | 1 | 3% |
| v2 clone | evacuated | 150 | 15 (10%) | 1 | 4% |
| v2 clone | died | 25 | 9 (36%) | 1 | 4% |
| v2 clone | gave_up | 25 | 15 (60%) | 10 | 9% |
| v4 clone | evacuated | 153 | 3 (2%) | 1 | 4% |
| v4 clone | died | 15 | 0 (0%) | 1 | 3% |
| v4 clone | gave_up | 32 | 12 (38%) | 3 | 9% |

Episodes flagged as long back-and-forth pacing (6+ reversals in a row): A*: 0, v2: 39, v4: 15 (of 200 each).

Flagged v2 episodes: the first long ping-pong began, on median, 45% of the way through the episode, with a median of 0 occupants already out; 10 of 39 had already rescued someone.

The v2 clone's give-up episodes, at the start of their LONGEST back-and-forth run: median 48% of the way through; occupants still to be delivered at that point: 1 in 7, 2 in 1, 3 in 1, 6 in 6; occupants out at the end: 2/3, 3/5, 4/5, 4/5, 5/6, 5/6, 5/6, 5/6, 5/6, 4/6, 5/6, 5/6, 5/6, 3/6, 5/6.
