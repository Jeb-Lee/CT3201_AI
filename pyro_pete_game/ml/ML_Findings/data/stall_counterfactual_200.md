Whenever the network stalls, A* takes the next 200 decisions. This borrows A*, so it is an UPPER BOUND on what eliminating stalling is worth, not a result for the network. Same 300 episodes.

| network | as trained | with stalls broken by A* | change | episodes A* had to step in | won only with the help | lost only with the help |
|---|---|---|---|---|---|---|
| v2 | 77% (72-81) | **84%** (80-88) | +8 points | 53 | 23 | 0 |
| v4 | 80% (75-84) | **83%** (78-87) | +3 points | 25 | 8 | 0 |

For reference, A* on these 300 episodes: 87% (261 of 300).
