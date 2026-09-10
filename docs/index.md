# CommandBus (Python)

A small command and event bus with pluggable queue adapters. Register handlers, send commands, and process them in-process or via a queue (SQS, RabbitMQ, Redis, and more).

## Quick start — commands (WorkerApp)

**WorkerApp** wraps your handlers and a **queue adapter**. The adapter stores commands between send and process — producer and worker must use the **same backend and queue name**:

```python
import asyncio
from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter

queue = InMemoryQueueAdapter(queue_name="orders")
app = WorkerApp(queue_adapter=queue)

@app.command()
def on_order_created(order_id: str, amount_cents: int):
    print(f"Order {order_id}: {amount_cents} cents")

async def main():
    await app.execute(on_order_created(order_id="ord-1", amount_cents=1999), wait=False)  # enqueue
    await app.work()  # dequeue and dispatch

if __name__ == "__main__":
    asyncio.run(main())
```

Run workers from the command line:

```bash
command-bus-worker myapp.worker:app --workers 4
```

The CLI imports your module and polls the queue — it does **not** run `main()`. The worker module holds `app` and the adapter; a separate client sends commands through the same queue setup. See [Client and worker](client-and-worker.md).

See [WorkerApp](worker-app.md) for concurrency, request/response, and production queue setup. For step-by-step wiring with `CommandBus` and message classes, see [Quick start](quickstart.md).

## Quick start — events

Each event reaches **every subscriber**. See [Pub/sub events](pubsub-events.md).

## Documentation

| Topic | Description |
|-------|-------------|
| [Quick start](quickstart.md) | WorkerApp plus step-by-step wiring. |
| [WorkerApp](worker-app.md) | Handlers, concurrency, in-memory and production setup. |
| [Worker CLI](cli.md) | `command-bus-worker module[:attr]`. |
| [Installation](installation.md) | Package and extras. |
| [Handler decorator](handler-decorator.md) | `@app.command()` / `@router.command()`. |
| [Client and worker](client-and-worker.md) | Split producer and consumer in production. |
| [Queue adapters](queue-adapters.md) | In-memory, SQS, RabbitMQ, Redis. |
| [Execute and wait](execute-and-wait.md) | Send a command and get the result back. |
| [Pub/sub events](pubsub-events.md) | EventBus and fan-out. |
| [Message formats and parsers](message-formats-and-parsers.md) | Repr, JSON, Base64. |
| [API reference](api-reference.md) | Types and methods. |
