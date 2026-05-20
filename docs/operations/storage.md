# Atlas20 Storage Operations

## Growth expectations

`data/` grows with cached source snapshots, downloaded raw inputs, and the SQLite database. `reports/` grows with rendered research artifacts and console reruns, so it usually expands faster than `data/` during active analysis work.

Keep both directories on a volume with enough headroom for the largest expected research window plus several rerun cycles. For this batch, assume `reports/` is the first directory to pressure disk quotas.

## Backup retention

`make backup` runs `python -m atlas20.api.backup` and inherits the retention policy from `ATLAS20_BACKUP_RETENTION_DAYS` in Batch 7. The default window is 30 days, and archives older than that are purged after each backup run.

Backups include the SQLite database and `reports/app_runs/` when present.

## Disk probe

Use a simple cron probe to watch growth over time:

```bash
du -sh reports/ data/ | logger -t atlas20-disk
```

Pair the log line with your platform's retention rules so the storage trend stays visible without manual inspection.
