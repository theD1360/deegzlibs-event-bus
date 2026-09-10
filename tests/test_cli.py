"""Tests for command_bus.cli."""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_cli_help():
    from command_bus import cli

    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_parse_target():
    from command_bus import cli

    assert cli._parse_target("pkg.mod") == ("pkg.mod", "bus")
    assert cli._parse_target("  pkg.mod  ") == ("pkg.mod", "bus")
    assert cli._parse_target("pkg.mod:orders_bus") == ("pkg.mod", "orders_bus")
    assert cli._parse_target("pkg.sub:command_bus_group") == ("pkg.sub", "command_bus_group")


def test_parse_target_invalid():
    from command_bus import cli

    with pytest.raises(SystemExit, match="Invalid target"):
        cli._parse_target("nodots:")
    with pytest.raises(SystemExit, match="Invalid target"):
        cli._parse_target(":onlyattr")


def test_worker_jobs():
    from command_bus import cli

    assert cli._worker_jobs("bus", 3) == [("bus", 1), ("bus", 2), ("bus", 3)]


def test_resolve_single_bus():
    from command_bus import cli
    from tests.support import cli_worker_module

    label, bus = cli._resolve_single_bus(cli_worker_module, "bus")
    assert label == "bus"
    assert bus is cli_worker_module.bus


def test_cli_command_bus_group_jobs(monkeypatch):
    from command_bus import cli

    captured: dict = {}

    def capture(module_name, jobs, poll_interval, log_level, concurrency):
        captured["jobs"] = jobs
        captured["module"] = module_name
        captured["concurrency"] = concurrency

    monkeypatch.setattr(cli, "_run_worker_processes", capture)
    cli.main(["tests.support.cli_group_worker_module:command_bus_group", "--workers", "1"])
    assert captured["jobs"] == [
        ("orders_bus", 1),
        ("orders_bus", 2),
        ("priority_bus", 1),
    ]
    assert captured["module"] == "tests.support.cli_group_worker_module"


def test_cli_single_bus_default_attr(monkeypatch):
    from command_bus import cli

    captured: dict = {}

    def capture(module_name, jobs, poll_interval, log_level, concurrency):
        captured["jobs"] = jobs
        captured["concurrency"] = concurrency

    monkeypatch.setattr(cli, "_run_worker_processes", capture)
    cli.main(["tests.support.cli_worker_module", "--workers", "2"])
    assert captured["jobs"] == [("bus", 1), ("bus", 2)]


def test_cli_single_bus_explicit_attr(monkeypatch):
    from command_bus import cli

    captured: dict = {}

    def capture(module_name, jobs, poll_interval, log_level, concurrency):
        captured["jobs"] = jobs
        captured["concurrency"] = concurrency

    monkeypatch.setattr(cli, "_run_worker_processes", capture)
    cli.main(["tests.support.cli_worker_module:bus", "--workers", "1"])
    assert captured["jobs"] == [("bus", 1)]


def test_cli_target_must_be_bus_or_group(monkeypatch):
    import types

    from command_bus import cli

    fake = types.SimpleNamespace(thing="oops")

    monkeypatch.setattr(cli.importlib, "import_module", lambda name: fake)

    with pytest.raises(SystemExit, match="CommandBus, EventBus, WorkerApp, or BusGroup"):
        cli.main(["fake.module:thing", "--workers", "1"])


def test_cli_worker_app_target(monkeypatch):
    from command_bus import cli

    captured: dict = {}

    def capture(module_name, jobs, poll_interval, log_level, concurrency):
        captured["jobs"] = jobs
        captured["concurrency"] = concurrency

    monkeypatch.setattr(cli, "_run_worker_processes", capture)
    cli.main(["tests.support.cli_worker_app_module:app", "--workers", "1"])
    assert captured["jobs"] == [("app", 1)]
    assert captured["concurrency"] == 2


def test_cli_worker_app_concurrency_override(monkeypatch):
    from command_bus import cli

    captured: dict = {}

    def capture(module_name, jobs, poll_interval, log_level, concurrency):
        captured["concurrency"] = concurrency

    monkeypatch.setattr(cli, "_run_worker_processes", capture)
    cli.main(
        [
            "tests.support.cli_worker_app_module:app",
            "--workers",
            "1",
            "--concurrency",
            "5",
        ]
    )
    assert captured["concurrency"] == 5


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM worker stop is POSIX-specific")
def test_cli_worker_app_lifecycle(monkeypatch):
    import logging
    import os
    import signal

    from command_bus import cli
    from tests.support import cli_worker_app_lifecycle_module as lifecycle_mod

    lifecycle_mod.lifecycle_log.clear()

    async def stop_after_one_work(target, concurrency):
        os.kill(os.getpid(), signal.SIGTERM)

    monkeypatch.setattr(cli, "_do_work", stop_after_one_work)
    cli._process_worker_main(
        "tests.support.cli_worker_app_lifecycle_module",
        "app",
        1,
        0.0,
        logging.WARNING,
        1,
    )
    assert lifecycle_mod.lifecycle_log == ["startup", "shutdown"]
