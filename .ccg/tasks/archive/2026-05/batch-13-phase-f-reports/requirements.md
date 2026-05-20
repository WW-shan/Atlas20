# Phase F Requirements

- Generate markdown, PDF, PNG, and ZIP artifacts from completed runs.
- Serve downloads as authenticated `FileResponse` streams instead of URL stubs.
- Whitelist downloads with per-run `report_manifest.json` and sha256 checks.
- Keep report generation synchronous for the MVP and return a completed 202 response.
- Add a weekly APScheduler job that generates the featured digest from the latest completed run.
- Keep the existing modal payload compatible with the current frontend request shape.
- Disable the scheduler in pytest runs.
