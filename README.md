# DeegzLibs EventBus (Python)

A small event bus with pluggable queue adapters. Define event messages as Pydantic models, register handlers, and execute events in-process or via a queue (e.g. AWS SQS, RabbitMQ, Redis).

## Installation

```bash
pip install deegzlibs-event-bus
```

Optional extras: **`[sqs]`**, **`[redis]`**, **`[rabbitmq]`**. See [Installation](docs/installation.md).

## Quick start

```python
from event_bus import EventBus, EventBusRegistry, EventMessage, EventMessageHandler
from event_bus.adapters import InMemoryEventBusAdapter

registry = EventBusRegistry()
adapter = InMemoryEventBusAdapter(queue_name="events")
bus = EventBus(queue_adapter=adapter, event_registry=registry)

@registry.event()
def on_order_created(order_id: str, amount_cents: int):
    print(f"Order {order_id}: {amount_cents} cents")

# Fire-and-forget
await bus.execute(on_order_created(order_id="ord-1", amount_cents=1999), wait=False)

# Worker: poll and dispatch
await bus.work()
```

For full examples (messages, handlers, SQS/Redis, execute-and-wait), see the [documentation](docs/index.md).

## Documentation

| Topic | Description |
|-------|-------------|
| [Installation](docs/installation.md) | Package and extras. |
| [Quick start](docs/quickstart.md) | Messages, handlers, register, execute. |
| [Handler decorator](docs/handler-decorator.md) | `@registry.event()` and message factory. |
| [Message formats and parsers](docs/message-formats-and-parsers.md) | Repr, JSON, Base64, custom parser. |
| [Client and worker](docs/client-and-worker.md) | Shared module, producer, consumer. |
| [Queue adapters](docs/queue-adapters.md) | In-memory, SQS, RabbitMQ, Redis. |
| [Execute and wait](docs/execute-and-wait.md) | Response store, request/response. |
| [API reference](docs/api-reference.md) | Types and methods overview. |

## License

MIT
