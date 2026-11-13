# LS103 compact evidence

This directory keeps the audit-sized evidence for the LS103 candidate-selection study.

- `*/summary.json`: engine metrics and risk counters for one scenario.
- `*/daily_returns.csv`: daily equity returns from the same run.
- `*/profit_lock_audit.csv`: profit-lock decision log for LS23/LS45/LS54/LS57 runs.
- `ls45_gross125_proxy_20bps/` and `ls57_gross125_proxy_20bps/`: selected base runs,
  including trades, funding events and short attribution.

The full hourly equity, gross-exposure, position and funding ledgers were intentionally
not retained because they are reproducible and approximately 95 MB. Recreate them with
the commands in `../report.md` and the corresponding frozen trial IDs.

`comparison.csv` at the parent level is the normalized scenario summary.
