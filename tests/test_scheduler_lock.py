import subprocess
import sys
import types

from atlas20.api.scheduler import start_scheduler
from atlas20.api.settings import Settings


class FakeScheduler:
    def __init__(self, *, timezone):
        self.timezone = timezone
        self.jobs = []
        self.started = False
        self.shutdown_calls = []

    def add_job(self, *args, **kwargs):
        self.jobs.append((args, kwargs))

    def start(self):
        self.started = True

    def shutdown(self, wait=True):
        self.shutdown_calls.append(wait)


def _settings(tmp_path) -> Settings:
    data_root = tmp_path / "data"
    data_root.mkdir()
    return Settings(data_root=data_root, report_root=tmp_path / "reports")


def _enable_fake_scheduler(monkeypatch) -> None:
    monkeypatch.delenv("ATLAS20_DISABLE_SCHEDULER", raising=False)
    apscheduler = types.ModuleType("apscheduler")
    schedulers = types.ModuleType("apscheduler.schedulers")
    asyncio_module = types.ModuleType("apscheduler.schedulers.asyncio")
    asyncio_module.AsyncIOScheduler = FakeScheduler
    monkeypatch.setitem(sys.modules, "apscheduler", apscheduler)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers", schedulers)
    monkeypatch.setitem(sys.modules, "apscheduler.schedulers.asyncio", asyncio_module)


def test_start_scheduler_acquires_file_lock(tmp_path, monkeypatch) -> None:
    _enable_fake_scheduler(monkeypatch)
    scheduler = start_scheduler(_settings(tmp_path))
    try:
        assert isinstance(scheduler, FakeScheduler)
        assert scheduler.started is True
        assert (tmp_path / "data" / ".scheduler.lock").exists()
    finally:
        scheduler.shutdown(wait=False)


def test_start_scheduler_returns_none_when_lock_is_held_by_another_process(tmp_path, monkeypatch) -> None:
    _enable_fake_scheduler(monkeypatch)
    settings = _settings(tmp_path)
    lock_path = settings.data_root / ".scheduler.lock"
    code = (
        "from filelock import FileLock; import sys, time; "
        "lock = FileLock(sys.argv[1], timeout=1); lock.acquire(); "
        "print('ready', flush=True); time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(lock_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "ready"
        assert start_scheduler(settings) is None
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_scheduler_shutdown_releases_lock_for_next_start(tmp_path, monkeypatch) -> None:
    _enable_fake_scheduler(monkeypatch)
    settings = _settings(tmp_path)

    first = start_scheduler(settings)
    first.shutdown(wait=False)
    second = start_scheduler(settings)
    try:
        assert isinstance(second, FakeScheduler)
        assert second.started is True
    finally:
        second.shutdown(wait=False)


def test_disable_scheduler_short_circuits_before_lock(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ATLAS20_DISABLE_SCHEDULER", "1")
    scheduler = start_scheduler(_settings(tmp_path))

    assert scheduler is None
    assert not (tmp_path / "data" / ".scheduler.lock").exists()
