# Atlas20 Storage Operations

## Growth expectations

`data/` grows with cached source snapshots, downloaded raw inputs, and the SQLite database. `reports/` grows with rendered research artifacts and console reruns, so it usually expands faster than `data/` during active analysis work.

Keep both directories on a volume with enough headroom for the largest expected research window plus several rerun cycles. For this batch, assume `reports/` is the first directory to pressure disk quotas.

## Backup retention

`make backup` runs `python -m atlas20.api.backup` and inherits the retention policy from `ATLAS20_BACKUP_RETENTION_DAYS` in Batch 7. The default window is 30 days, and archives older than that are purged after each backup run.

Backups include the SQLite database and `reports/app_runs/` when present.

## Disk probe

Use the built-in probe from cron or systemd timers:

```bash
ATLAS20_REPORT_STORAGE_WARN_BYTES=53687091200 \
ATLAS20_DATA_STORAGE_WARN_BYTES=107374182400 \
python -m atlas20.api.storage | logger -t atlas20-disk
```

The probe emits one JSON line for `reports` and one for `data`. A threshold of `0` disables alerting for that directory. When any configured threshold is exceeded, the command exits with status `2`, so cron, systemd, or a wrapper script can page or notify on failure.

`reports/latest` symlinks/Junctions are not followed during size calculation, so `reports/app_runs/` is counted once.
