300 seeded episodes per row (the two test sets pooled), 240 s cap.

| teacher | evacuated | died | gave up | occupants led out | mean score | mean seconds (evacuated) |
|---|---|---|---|---|---|---|
| A* (benchmark) | 87% | 8% | 5% | 92% | 505 | 41 |
| far side (lean 0.5) | 91% | 6% | 2% | 93% | 509 | 43 |
| far side + skip corners < 4 tiles | 91% | 6% | 3% | 93% | 512 | 42 |
| far side + skip corners < 8 tiles | 81% | 6% | 13% | 91% | 507 | 40 |
| far side + skip corners < 12 tiles | 60% | 3% | 38% | 86% | 487 | 33 |
| nearest + skip corners < 8 tiles | 81% | 5% | 14% | 91% | 510 | 38 |
| far side + defer corners < 8 tiles | 87% | 7% | 7% | 92% | 507 | 41 |
| far side + defer corners < 12 tiles | 85% | 7% | 8% | 91% | 497 | 43 |
| nearest + defer corners < 8 tiles | 86% | 7% | 7% | 92% | 509 | 40 |
