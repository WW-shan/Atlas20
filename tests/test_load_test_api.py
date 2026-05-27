from scripts.load_test_api import RequestSample, build_summary, percentile


def test_percentile_interpolates_sorted_values() -> None:
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([100], 95) == 100
    assert percentile([], 95) == 0


def test_build_summary_passes_when_thresholds_are_met() -> None:
    samples = [
        RequestSample(path="/api/overview", latency_ms=20, status_code=200),
        RequestSample(path="/api/options", latency_ms=30, status_code=200),
        RequestSample(path="/api/runs", latency_ms=40, status_code=200),
    ]

    summary = build_summary(
        samples,
        target_rps=3,
        duration_seconds=1.0,
        p95_threshold_ms=200,
        min_success_rate=1.0,
        min_rps_ratio=0.95,
    )

    assert summary["passed"] is True
    assert summary["actual_rps"] == 3.0
    assert summary["p95_ms"] == 39.0
    assert summary["status_counts"] == {"200": 3}
    assert summary["path_status_counts"] == {
        "/api/overview": {"200": 1},
        "/api/options": {"200": 1},
        "/api/runs": {"200": 1},
    }


def test_build_summary_fails_on_status_or_latency_threshold() -> None:
    samples = [
        RequestSample(path="/api/overview", latency_ms=20, status_code=200),
        RequestSample(path="/api/options", latency_ms=500, status_code=500),
    ]

    summary = build_summary(
        samples,
        target_rps=2,
        duration_seconds=1.0,
        p95_threshold_ms=200,
        min_success_rate=1.0,
        min_rps_ratio=0.95,
    )

    assert summary["passed"] is False
    assert summary["failed"] == 1
    assert summary["status_counts"] == {"200": 1, "500": 1}
    assert summary["path_status_counts"]["/api/options"] == {"500": 1}
