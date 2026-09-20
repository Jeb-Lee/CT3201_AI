Same 100 seeded episodes (240 s cap) for A* and the v2 clone (deterministic). A back-and-forth run is consecutive reversals; an episode is *flagged* if its longest run is at least 6 reversals.

| agent | outcome | episodes | flagged (long ping-pong) | median longest run | median reversal share of moves |
|---|---|---|---|---|---|
| A* | evacuated | 91 | 0 (0%) | 1 | 3% |
| A* | died | 8 | 0 (0%) | 1 | 3% |
| A* | gave_up | 1 | 0 (0%) | 1 | 2% |
| v2 clone | evacuated | 80 | 6 (8%) | 1 | 4% |
| v2 clone | died | 10 | 3 (30%) | 1 | 4% |
| v2 clone | gave_up | 10 | 10 (100%) | 103 | 47% |
| v3 clone | evacuated | 84 | 3 (4%) | 1 | 4% |
| v3 clone | died | 11 | 2 (18%) | 1 | 3% |
| v3 clone | gave_up | 5 | 5 (100%) | 76 | 29% |
| v4 clone | evacuated | 87 | 3 (3%) | 1 | 4% |
| v4 clone | died | 9 | 1 (11%) | 1 | 4% |
| v4 clone | gave_up | 4 | 1 (25%) | 1 | 19% |

Episodes flagged as long back-and-forth pacing (6+ reversals in a row): A*: 0, v2: 19, v3: 10, v4: 5.

Flagged v2 episodes: the first long ping-pong began, on median, 45% of the way through the episode, with a median of 0 occupants already out; 0 of 19 had already rescued someone.

The v2 clone's give-up episodes, at the start of their LONGEST back-and-forth run: median 45% of the way through; occupants still to be delivered at that point: 1 in 1, 4 in 1, 5 in 2, 6 in 6; occupants out at the end: 3/4, 3/5, 4/5, 5/6, 5/6, 5/6, 5/6, 5/6, 5/6, 5/6.
