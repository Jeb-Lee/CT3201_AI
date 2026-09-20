Only the choice of *which unexplored area to search next* differs; A*'s benchmark code is untouched. 200 seeded episodes per variant, 240 s cap. 'paired' = the variant minus nearest on the same episode (mean, with 95% interval).

| variant | evacuated | died | gave up | occupants led out | mean score | paired score | mean seconds (evacuated) | paired seconds (both evacuated) |
|---|---|---|---|---|---|---|---|---|
| nearest | 84% | 10% | 5% | 89% | 488 | +0 (+0 to +0) | 42 | +0.0 s (+0.0 to +0.0, n=169) |
| far_soft | 90% | 8% | 2% | 93% | 507 | +18 (+2 to +34) | 44 | +1.2 s (-0.2 to +2.5, n=167) |
| far_hard | 86% | 12% | 2% | 89% | 485 | -3 (-24 to +17) | 45 | +3.3 s (+1.7 to +5.0, n=161) |
