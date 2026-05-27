# API Load Testing

Atlas20 keeps the read-path load baseline dependency-light: use the Python runner in `scripts/load_test_api.py` against a real Uvicorn process. The default profile sends 100 requests per second across the main console GET endpoints and fails when p95 latency is 200 ms or higher, any request fails, or actual throughput drops below 95 RPS.

## Start The API

Use seed/mock-friendly local settings so the run does not depend on external providers:

```powershell
New-Item -ItemType Directory -Force output\load\reports, output\load\data | Out-Null
$loadRoot = (Resolve-Path output\load).Path.Replace("\", "/")
$env:PYTHONPATH = "src"
$env:ATLAS20_DISABLE_SCHEDULER = "1"
$env:ATLAS20_REPORT_ROOT = (Resolve-Path output\load\reports).Path
$env:ATLAS20_DATA_ROOT = (Resolve-Path output\load\data).Path
$env:ATLAS20_DB_URL = "sqlite:///$loadRoot/atlas20-load.sqlite"
python -m uvicorn atlas20.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

## Run The Baseline

```powershell
python scripts/load_test_api.py --base-url http://127.0.0.1:8000 --rps 100 --duration-seconds 60 --p95-ms 200
```

The command writes `output/load/api-load-summary.json` and exits non-zero if thresholds fail. For a quick local smoke, lower only the duration:

```powershell
python scripts/load_test_api.py --duration-seconds 10
```

## Default Endpoint Mix

- `/api/overview`
- `/api/options`
- `/api/runs?page=1&pageSize=14&dateRange=all&q=&chips=`
- `/api/runs/queue`
- `/api/compare?ids=atlas,momentum,meanrev&range=YTD`
- `/api/universe/timeline`
- `/api/universe/sources`
- `/api/universe/alerts`
- `/api/reports?sort=recent`
