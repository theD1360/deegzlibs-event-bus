"""Tests for queue_admin helpers."""

import pytest

from command_bus import CommandBus, EventBus, Router, WorkerApp
from command_bus.adapters import InMemoryPubSubAdapter, InMemoryQueueAdapter
from command_bus.adapters.queue.in_memory_pubsub import _reset_in_memory_pubsub_broker
from command_bus.queue_admin import (
    drain_queue,
    get_message_count,
    load_target,
    purge_queue,
    resolve_queues,
    select_queues,
)


@pytest.fixture(autouse=True)
def _clean_pubsub_broker():
    _reset_in_memory_pubsub_broker()
    yield
    _reset_in_memory_pubsub_broker()


def test_resolve_worker_app_queues():
    orders = CommandBus(
        queue_adapter=InMemoryQueueAdapter(queue_name="orders"),
        command_router=Router(),
    )
    events = EventBus(
        queue_adapter=InMemoryPubSubAdapter(queue_name="events"),
        command_router=Router(),
    )
    app = WorkerApp(create_default_bus=False)
    app.register(orders, name="orders")
    app.register(events, name="events")

    descriptors = resolve_queues(__import__("builtins"), "app", app)
    assert [d.label for d in descriptors] == ["orders", "events"]
    assert descriptors[0].bus_kind == "command"
    assert descriptors[1].bus_kind == "event"


def test_in_memory_count_drain_purge():
    adapter = InMemoryQueueAdapter(queue_name="q")
    adapter.enqueue(__import__("command_bus").CommandMessage())
    adapter.enqueue(__import__("command_bus").CommandMessage())

    assert get_message_count(adapter) == 2
    assert drain_queue(adapter) == 2
    assert get_message_count(adapter) == 0

    adapter.enqueue(__import__("command_bus").CommandMessage())
    assert purge_queue(adapter) == 1
    assert get_message_count(adapter) == 0


def test_select_queues_filters():
    adapter = InMemoryQueueAdapter(queue_name="q")
    bus = CommandBus(queue_adapter=adapter, command_router=Router())
    app = WorkerApp(create_default_bus=False)
    app.register(bus, name="only")

    descriptors = resolve_queues(__import__("builtins"), "app", app)
    selected = select_queues(descriptors, "only")
    assert len(selected) == 1

    with pytest.raises(Exception, match="No queue named"):
        select_queues(descriptors, "missing")


def test_load_target_worker_app_module():
    from tests.support import cli_worker_app_multi_module as mod

    module, attr, target = load_target("tests.support.cli_worker_app_multi_module:app")
    assert attr == "app"
    assert target is mod.app
    descriptors = resolve_queues(module, attr, target)
    assert {d.label for d in descriptors} == {"orders", "events"}
