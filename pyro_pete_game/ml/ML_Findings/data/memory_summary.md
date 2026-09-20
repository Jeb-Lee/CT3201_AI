| network | all-ten evacuated (deterministic, 240 s) | trained 1-7 | unseen 8-10 | flagged pacing episodes | one-short give-ups | median seconds |
|---|---|---|---|---|---|---|
| v2: no memory | 80% (71-87) | 89% | 60% | 19 of 100 | 9 | 42 |
| v3: short memory (last move + last 4 tiles) | 84% (76-90) | 90% | 70% | 10 of 100 | 5 | 42 |
| v4: full trail (visit counts, whole episode) | 87% (79-92) | 90% | 80% | 5 of 100 | 4 | 42 |

**Registered predictions, checked against the numbers above:**

* P7 (short memory): flagged episodes fall from 19 to 6 or fewer: **FALSIFIED** (v3 has 10). All-ten evacuation rises to 85% or more: **FALSIFIED** (v3: 84%, v2: 80%).
* P9 (full trail): flagged episodes no more than v3 and at most 6: **HELD** (v4 has 5, v3 has 10). Evacuation within 5 points of v3: **HELD** (v4: 87%, v3: 84%; a v4 that is worse by more than 5 points falsifies it).
* P8 (route damage) is not tested here. One-short give-ups: v2 9, v3 5, v4 4.

**Paired comparisons on the same 100 episodes** (evacuated everyone; deterministic, 240 s):

| first | second | both | only first | only second |
|---|---|---|---|---|
| v2 | v3 | 78 | 2 | 6 |
| v2 | v4 | 80 | 0 | 7 |
| v3 | v4 | 83 | 1 | 4 |
| A* | v4 | 84 | 7 | 3 |
| A* | v3 | 83 | 8 | 1 |
| A* | v2 | 78 | 13 | 2 |
