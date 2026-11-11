# Invalidated LS12 run: naive/UTC regime alignment

The first LS12 20bps diagnostic passed a naive `market.price` calendar into a
UTC-normalized BTC SMA series, so every regime lookup missed and the run fell
back to non-bear mode. That result is not evidence for or against LS12.

The runner now normalizes both the calendar and BTC close index to UTC. A
regression test covers the naive-calendar/UTC-price case. The candidate was
rerun from clean outputs after the fix.
