Only the choice of *which unexplored area to search next* differs; A*'s benchmark code is untouched. 300 seeded episodes per variant, 240 s cap. 'paired' = the variant minus nearest on the same episode (mean, with 95% interval).

| variant | evacuated | died | gave up | occupants led out | mean score | paired score | mean seconds (evacuated) | paired seconds (both evacuated) |
|---|---|---|---|---|---|---|---|---|
| nearest | 87% | 8% | 5% | 92% | 505 | +0 (+0 to +0) | 41 | +0.0 s (+0.0 to +0.0, n=261) |
| far_soft | 91% | 7% | 2% | 93% | 507 | +2 (-13 to +17) | 43 | +1.9 s (+0.7 to +3.2, n=255) |
| far_hard | 91% | 7% | 2% | 92% | 502 | -3 (-19 to +13) | 43 | +2.4 s (+1.0 to +3.9, n=254) |
| far_first | 79% | 5% | 16% | 90% | 488 | -17 (-36 to +3) | 50 | +11.0 s (+8.5 to +13.4, n=212) |
| near_exit | 81% | 10% | 9% | 91% | 495 | -10 (-26 to +6) | 40 | -0.2 s (-1.6 to +1.2, n=237) |
