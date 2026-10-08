# Do any state variables mark PR2026-10-H5's worst months?

Crash months are the calendar months with a return at or below -8%.
Months in the sample: 53; crash months: 9.

## Crash versus rest

`diff_over_rest_std` is the difference in means divided by the rest-months' standard
deviation. It is a standardised difference for comparison, not a significance test.

| index | crash_mean | rest_mean | difference | rest_std | diff_over_rest_std | months_of_data |
| --- | --- | --- | --- | --- | --- | --- |
| gate_open | 0.6498 | 0.4987 | 0.1511 | 0.4361 | 0.3464 | 9.0000 |
| breadth | 0.3698 | 0.4799 | -0.1101 | 0.2946 | -0.3737 | 9.0000 |
| disp_ratio | 0.7506 | 0.9426 | -0.1920 | 0.5109 | -0.3757 | 9.0000 |
| mkt_vol | 0.7176 | 0.7054 | 0.0122 | 0.2133 | 0.0570 | 9.0000 |
| own63_before | 0.2172 | 0.1220 | 0.0952 | 0.2651 | 0.3589 | 9.0000 |
| gross | 0.3101 | 0.2657 | 0.0444 | 0.2489 | 0.1784 | 9.0000 |

## Worst months and the state they started in

| index | ret | gate_open | breadth | disp_ratio | mkt_vol | own63_before | gross |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2023-04-30 00:00:00 | -0.1929 | 1.0000 | 0.6500 | 0.5927 | 1.0756 | -0.0579 | 0.9007 |
| 2024-04-30 00:00:00 | -0.1896 | 1.0000 | 0.3133 | 0.6878 | 0.7727 | 0.4609 | 0.3427 |
| 2022-11-30 00:00:00 | -0.1288 | 0.1000 | 0.3150 | 1.1292 | 0.8108 | 0.0000 | 0.0343 |
| 2023-07-31 00:00:00 | -0.1139 | 1.0000 | 0.8032 | 1.6640 | 0.5714 | 0.2816 | 0.3400 |
| 2024-01-31 00:00:00 | -0.1063 | 1.0000 | 0.4935 | 0.7036 | 0.6014 | 1.3066 | 0.4054 |
| 2025-02-28 00:00:00 | -0.0966 | 0.5714 | 0.0714 | 0.5265 | 0.8249 | -0.0503 | 0.2092 |
| 2023-08-31 00:00:00 | -0.0893 | 0.5484 | 0.2000 | 0.5242 | 0.4717 | 0.1807 | 0.2283 |
| 2024-06-30 00:00:00 | -0.0878 | 0.4667 | 0.3300 | 0.5016 | 0.6207 | -0.0450 | 0.2047 |
| 2024-08-31 00:00:00 | -0.0877 | 0.1613 | 0.1516 | 0.4256 | 0.7089 | -0.1219 | 0.1257 |
| 2023-03-31 00:00:00 | -0.0707 | 1.0000 | 0.2726 | 0.5039 | 0.7523 | 0.3816 | 0.5226 |
| 2024-07-31 00:00:00 | -0.0604 | 0.4516 | 0.3500 | 0.4415 | 0.6100 | 0.0351 | 0.3385 |
| 2023-05-31 00:00:00 | -0.0599 | 0.9355 | 0.1306 | 0.4264 | 1.3524 | -0.2654 | 0.4619 |

## Reading

A state variable only supports a new overlay if the crash months look different from
the rest. Any separation here is in-sample hypothesis generation: it would still have
to be pre-registered and confirmed out of sample before it could change a rule.
