# Engine monthly starts

This directory keeps the aggregate evidence for the 12 true cash-start engine runs:

- `summary.csv`: baseline/candidate terminal, Sharpe, MDD, gross and liquidation checks by start;
- `summary.json`: gate booleans and counts;
- `report.md`: rendered audit table.

The full per-start equity, position, trade and funding ledgers were generated from the same frozen
runner and then pruned from git because they duplicated the primary 20bps run and added about 76 MiB.
The aggregate rows retain every gate input used by the report; the per-start runs are reproducible
with `scripts/run_h5_regime_short_router.py --evaluation-start <YYYY-MM-01>` and the frozen config.
