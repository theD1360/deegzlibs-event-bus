"""Tests for command-bus unified CLI."""

import pytest

from command_bus.adapters.queue.in_memory_pubsub import _reset_in_memory_pubsub_broker


@pytest.fixture(autouse=True)
def _clean_pubsub_broker():
    _reset_in_memory_pubsub_broker()
    yield
    _reset_in_memory_pubsub_broker()


def test_cli_main_help():
    from command_bus import cli_main

    with pytest.raises(SystemExit) as exc:
        cli_main.main(["--help"])
    assert exc.value.code == 0


def test_cli_main_list_worker_app(capsys):
    from command_bus import cli_main

    code = cli_main.main(["list", "tests.support.cli_worker_app_multi_module:app"])
    assert code is None
    out = capsys.readouterr().out
    assert "orders" in out
    assert "events" in out
    assert "InMemoryQueueAdapter" in out
    assert "InMemoryPubSubAdapter" in out


def test_cli_main_count_and_drain(capsys):
    from command_bus import cli_main
    from tests.support import cli_worker_app_module as mod

    mod.app.bus.queue_adapter.purge_messages()
    mod.app.bus.queue_adapter.enqueue(mod.noop(value="x"))

    cli_main.main(["count", "tests.support.cli_worker_app_module:app"])
    out = capsys.readouterr().out
    assert "default: 1" in out

    cli_main.main(["drain", "-y", "tests.support.cli_worker_app_module:app"])
    out = capsys.readouterr().out
    assert "drained 1" in out

    cli_main.main(["count", "tests.support.cli_worker_app_module:app"])
    out = capsys.readouterr().out
    assert "default: 0" in out


def test_cli_main_purge(capsys):
    from command_bus import cli_main
    from tests.support import cli_worker_app_module as mod

    adapter = mod.app.bus.queue_adapter
    adapter.purge_messages()
    adapter.enqueue(mod.noop(value="a"))

    cli_main.main(["purge", "-y", "tests.support.cli_worker_app_module:app"])
    out = capsys.readouterr().out
    assert "purged 1" in out
