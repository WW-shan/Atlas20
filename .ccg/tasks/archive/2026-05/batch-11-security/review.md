# Batch 11 Review

## External CCG Reviewer

- Round 1 session: `0b52b122-c887-4c2a-9fe7-273300a5df50`
- Round 2 session: `713a246f-d160-4c2a-a275-2569088efbff`

## Findings Applied

- Rejected wildcard CORS origins in prod.
- Switched API key comparison to `hmac.compare_digest`.
- Added universe-refresh deduplication for existing queued/running jobs.
- Added non-mock worker wiring coverage for `download_and_cache_raw_data`.
- Avoided materializing the full provider file list during data-source mtime scans.
- Adjusted `_time.today()` override coverage.
- Ignored arbitrary `X-API-Key` rate-limit buckets when API keys are not configured.
- Softened the S9 comment to document no static report mount without implying GET auth.

## Findings Deferred

- API keys remain optional in prod because the Batch 11 hard requirement says an empty set disables auth for backward compatibility.
- Universe-refresh dedup is not process-race-proof; a unique job table or partial index belongs in a later persistence/schema batch.
- Data-source cache is process-local and lock-free by design for the MVP 5-minute cache.

## Result

Round 2 found no Critical issues. Remaining items are follow-up hygiene or later-batch architecture work.
