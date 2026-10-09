# Does PR2026-10-H5 buy after extreme runs, and what follows?

Hypothesis generation only: no rule changed, no trial registered.
Invested days: 874; trailing window: 21 days; buckets: 5.

`largest_trailing_21d` is the 21-day return of the largest holding on that day - the move
the momentum sleeves were chasing. Forward columns are the strategy's own subsequent
returns, so this measures the book's timing, not the coin's.

## Current position

Latest invested day: **2026-10-07**, largest holding `near` at 0.505 of capital, gross 0.505.
Its trailing 21-day return was +104.3%, in the **87% percentile** of every invested day in the sample; its largest single-day return over that window was +20.6% (62% percentile).

## Forward strategy returns by the run the book was chasing

| index | bucket | days | state_min | state_max | state_median | mean_forward_5d | median_forward_5d | hit_forward_5d | mean_forward_10d | median_forward_10d | hit_forward_10d | mean_forward_21d | median_forward_21d | hit_forward_21d | worst_21d_mdd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.0000 | 175.0000 | -0.3030 | 0.1302 | 0.0488 | 0.0101 | 0.0037 | 0.5486 | 0.0274 | 0.0073 | 0.5657 | 0.0533 | 0.0067 | 0.5600 | -0.2177 |
| 1 | 2.0000 | 175.0000 | 0.1309 | 0.3194 | 0.2229 | 0.0195 | -0.0046 | 0.4571 | 0.0176 | -0.0144 | 0.4343 | 0.0670 | -0.0072 | 0.4686 | -0.2102 |
| 2 | 3.0000 | 174.0000 | 0.3196 | 0.5018 | 0.4079 | 0.0285 | 0.0010 | 0.5115 | 0.0590 | 0.0034 | 0.5057 | 0.0833 | 0.0143 | 0.5172 | -0.2011 |
| 3 | 4.0000 | 175.0000 | 0.5047 | 0.8723 | 0.6789 | 0.0215 | 0.0051 | 0.5371 | 0.0406 | 0.0073 | 0.5314 | 0.1071 | 0.0563 | 0.6171 | -0.1934 |
| 4 | 5.0000 | 175.0000 | 0.8734 | 4.4014 | 1.1367 | 0.0094 | 0.0054 | 0.5314 | 0.0183 | 0.0063 | 0.5257 | 0.0178 | -0.0033 | 0.4286 | -0.1938 |

## Top-quintile run against everything else

The most chased quintile starts at a trailing 21-day return of +87%.

| index | horizon_days | extreme_days | rest_days | extreme_mean | rest_mean | difference | welch_t | extreme_hit_rate | rest_hit_rate | extreme_per_gross | rest_per_gross | difference_per_gross | welch_t_per_gross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 5.0000 | 170.0000 | 699.0000 | 0.0094 | 0.0199 | -0.0105 | -2.1982 | 0.5471 | 0.5136 | 0.0438 | 0.0409 | 0.0029 | 0.1870 |
| 1 | 10.0000 | 165.0000 | 699.0000 | 0.0183 | 0.0361 | -0.0178 | -2.5767 | 0.5576 | 0.5093 | 0.0735 | 0.0691 | 0.0045 | 0.2202 |
| 2 | 21.0000 | 159.0000 | 694.0000 | 0.0178 | 0.0774 | -0.0597 | -4.9872 | 0.4717 | 0.5447 | 0.0655 | 0.1486 | -0.0831 | -2.8309 |

## The same test with the MAX construct of the external literature

The crypto MAX-momentum result (Li and Urquhart et al., 2021, already source S6 of this
review) is the opposite of the equity MAX effect: coins with the largest single-day
return earn *higher* future returns. Here the same forward returns are bucketed by the
largest single-day return of the largest holding over the past 21 days.
The top quintile starts at +27.1%.

| index | bucket | days | state_min | state_max | state_median | mean_forward_5d | median_forward_5d | hit_forward_5d | mean_forward_10d | median_forward_10d | hit_forward_10d | mean_forward_21d | median_forward_21d | hit_forward_21d | worst_21d_mdd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 1.0000 | 186.0000 | 0.0223 | 0.1087 | 0.0893 | 0.0326 | 0.0066 | 0.5753 | 0.0473 | 0.0105 | 0.5591 | 0.0917 | 0.0268 | 0.6022 | -0.2177 |
| 1 | 2.0000 | 171.0000 | 0.1096 | 0.1403 | 0.1287 | 0.0197 | 0.0097 | 0.5673 | 0.0488 | 0.0133 | 0.5906 | 0.1257 | 0.0523 | 0.6140 | -0.1564 |
| 2 | 3.0000 | 181.0000 | 0.1404 | 0.2051 | 0.1811 | 0.0095 | -0.0068 | 0.4365 | 0.0107 | -0.0199 | 0.3370 | 0.0013 | -0.0476 | 0.3481 | -0.1938 |
| 3 | 4.0000 | 168.0000 | 0.2063 | 0.2707 | 0.2215 | 0.0117 | 0.0004 | 0.4881 | 0.0342 | 0.0103 | 0.5476 | 0.0712 | 0.0270 | 0.5119 | -0.2011 |
| 4 | 5.0000 | 168.0000 | 0.2723 | 0.7309 | 0.3569 | 0.0145 | 0.0015 | 0.5179 | 0.0225 | 0.0036 | 0.5357 | 0.0407 | 0.0030 | 0.5179 | -0.1934 |

Top quintile against the rest:

| index | horizon_days | extreme_days | rest_days | extreme_mean | rest_mean | difference | welch_t | extreme_hit_rate | rest_hit_rate | extreme_per_gross | rest_per_gross | difference_per_gross | welch_t_per_gross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 5.0000 | 178.0000 | 691.0000 | 0.0150 | 0.0186 | -0.0035 | -0.6229 | 0.5281 | 0.5181 | 0.0676 | 0.0342 | 0.0334 | 1.6817 |
| 1 | 10.0000 | 178.0000 | 686.0000 | 0.0274 | 0.0341 | -0.0067 | -0.7895 | 0.5562 | 0.5087 | 0.1075 | 0.0596 | 0.0479 | 1.8790 |
| 2 | 21.0000 | 178.0000 | 675.0000 | 0.0538 | 0.0696 | -0.0159 | -1.1729 | 0.5449 | 0.5274 | 0.1421 | 0.1297 | 0.0124 | 0.3706 |

## Reading

The most chased bucket (bucket 5) covers trailing 21-day returns of +87% to +440%; the least chased covers -30% to +13%.

Any difference here is in-sample and conditional on the strategy having chosen to hold
the coin at all. It is recorded to document what the specification's own timing looks
like after a large run; it is not a rule, and changing the entry rule would be a new
pre-registered trial.
