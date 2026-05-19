# Atlas20 Backup Operations

## Schedule

Run `python -m atlas20.api.backup` daily from operator-managed cron. Batch 14 will wire managed scheduling.

## Scope

Each archive includes the configured SQLite database file and `reports/app_runs/` when present.

The SQLite database is copied with `sqlite3.backup()` before it is archived, so backups are safe to run while the API is live.

## RPO

24 hours with the daily manual cron schedule.

## RTO

Minutes: stop the API, untar the selected archive into place, and restart the API.

Stopping the API before taking a backup is recommended for quiet operational windows, but it is not required for SQLite consistency.

## Retention

Archives older than `ATLAS20_BACKUP_RETENTION_DAYS` are removed after each backup run. The default retention window is 30 days.
