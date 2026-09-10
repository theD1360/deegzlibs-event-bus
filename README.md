# DeegzLibs CommandBus (Python)

A small command and event bus with pluggable queue adapters. Register handlers, send commands or publish events, and process them in-process or through a queue (SQS, SNS, RabbitMQ, Redis, and more).

## Installation

```bash
pip install deegzlibs-command-bus
```

Optional extras: **`[sqs]`**, **`[sns]`**, **`[boto3]`**, **`[redis]`**, **`[rabbitmq]`**. See [Installation](docs/installation.md).

## Quick start — commands (WorkerApp)

**WorkerApp** wraps your handlers and a **queue adapter**. The adapter is the queue itself — `execute()` writes to it, `work()` reads from it. Producer and worker must use the **same adapter** (same backend and queue name):

```python
import asyncio
from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter

# Where commands wait between send and process.
# Swap for SqsQueueAdapter, RedisQueueAdapter, etc. in production.
queue = InMemoryQueueAdapter(queue_name="orders")

app = WorkerApp(queue_adapter=queue)

@app.command()
def on_order_created(order_id: str, amount_cents: int):
    print(f"Order {order_id}: {amount_cents} cents")

async def main():
    # Producer: enqueue via the adapter
    await app.execute(on_order_created(order_id="ord-1", amount_cents=1999), wait=False)
    # Worker: dequeue via the same adapter
    await app.work()

if __name__ == "__main__":
    asyncio.run(main())
```

In production, split this into two modules that share the same queue setup — see [Client and worker](docs/client-and-worker.md).

Run the worker as a separate process (like `uvicorn` for web apps):

```bash
command-bus-worker myapp.worker:app --workers 4
```

The CLI imports your module and runs `app.work()` in a loop — it does **not** call `main()`. Your worker module defines `app` (with its adapter and handlers); the client module sends commands using the same queue configuration.

- **`--workers`** — how many worker processes share the queue
- **`--concurrency`** — how many messages each process handles at once

If you have the repo locally, try the in-memory demo:

```bash
PYTHONPATH=src python examples/worker_app_demo.py
```

More on WorkerApp (response stores, production queues, concurrency): [WorkerApp docs](docs/worker-app.md).

Need the lower-level API (`CommandBus`, `Router`, message classes)? See the [full quick start](docs/quickstart.md).

## Quick start — events

Each event is delivered to **every subscriber**:

```python
from command_bus import EventBus, Router
from command_bus.adapters import InMemoryPubSubAdapter

router = Router()
bus = EventBus(
    queue_adapter=InMemoryPubSubAdapter(queue_name="order-events"),
    command_router=router,
)

@router.event()
def on_order_created(order_id: str, amount_cents: int):
    print(f"Order {order_id}: {amount_cents} cents")

await bus.publish(on_order_created(order_id="ord-1", amount_cents=1999))
await bus.work()
```

See [Pub/sub events](docs/pubsub-events.md) for fan-out adapters and multi-worker setups.

## Documentation

| Topic | Description |
|-------|-------------|
| [Quick start](docs/quickstart.md) | WorkerApp plus step-by-step wiring. |
| [WorkerApp](docs/worker-app.md) | Handlers, concurrency, in-memory and production setup. |
| [Worker CLI](docs/cli.md) | `command-bus-worker module[:attr]`. |
| [Installation](docs/installation.md) | Package and extras. |
| [Handler decorator](docs/handler-decorator.md) | `@app.command()` / `@router.command()`. |
| [Client and worker](docs/client-and-worker.md) | Split producer and consumer in production. |
| [Queue adapters](docs/queue-adapters.md) | In-memory, SQS, RabbitMQ, Redis. |
| [Execute and wait](docs/execute-and-wait.md) | Send a command and get the result back. |
| [Pub/sub events](docs/pubsub-events.md) | EventBus and fan-out. |
| [Message formats and parsers](docs/message-formats-and-parsers.md) | Repr, JSON, Base64. |
| [API reference](docs/api-reference.md) | Types and methods. |

## License

MIT
