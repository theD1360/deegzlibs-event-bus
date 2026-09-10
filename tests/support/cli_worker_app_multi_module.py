"""WorkerApp with multiple registered buses for CLI tests."""

from command_bus import CommandBus, EventBus, Router, WorkerApp
from command_bus.adapters import InMemoryPubSubAdapter, InMemoryQueueAdapter

orders_router = Router()
events_router = Router()


@orders_router.command()
def noop_order(value: str) -> None:
    pass


@events_router.event()
def noop_event(value: str) -> None:
    pass


orders = CommandBus(
    queue_adapter=InMemoryQueueAdapter(queue_name="cli-orders"),
    command_router=orders_router,
)
events = EventBus(
    queue_adapter=InMemoryPubSubAdapter(queue_name="cli-events"),
    command_router=events_router,
)

app = WorkerApp(create_default_bus=False)
app.register(orders, name="orders", workers=2, concurrency=2)
app.register(events, name="events", workers=1, concurrency=4)
