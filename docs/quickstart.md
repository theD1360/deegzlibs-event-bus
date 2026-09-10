# Quick start

## Commands with WorkerApp

The simplest way to get started is **`WorkerApp`**: handlers plus a **queue adapter** that stores commands until a worker picks them up.

```python
import asyncio
from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter

# The adapter is the queue. execute() writes here; work() reads from here.
queue = InMemoryQueueAdapter(queue_name="orders")
app = WorkerApp(queue_adapter=queue)

@app.command()
def on_order_created(order_id: str, amount_cents: int):
    print(f"Order {order_id}: {amount_cents} cents")

async def main():
    await app.execute(on_order_created(order_id="ord-1", amount_cents=1999), wait=False)
    await app.work()

if __name__ == "__main__":
    asyncio.run(main())
```

Running the file directly executes `main()` — both sides share one in-memory queue, which is fine for local tests.

In production you split producer and worker, but both still point at the **same queue adapter** (same type, queue name, and connection). `execute()` enqueues; `work()` dequeues and runs your handler:

| Role | What it does |
|------|--------------|
| Client | `await app.execute(...)` → adapter.enqueue |
| Worker | `await app.work()` → adapter.get_messages → handler |

Swap `InMemoryQueueAdapter` for [SQS, Redis, or RabbitMQ](queue-adapters.md) when processes run separately.

To run the worker from the command line (like `uvicorn` for web apps):

```bash
command-bus-worker myapp.worker:app --workers 2
```

The CLI imports your module and polls the queue. It does **not** call `main()` — put send logic in a [client module](client-and-worker.md) that uses the same queue setup.

See [WorkerApp](worker-app.md) for concurrency, in-memory demos, and production setup.

## How it works (step by step)

If you prefer to wire things up yourself, or need full control over the pieces:

### 1. Define a message

Subclass `CommandMessage` with the fields your command needs:

```python
from command_bus import CommandMessage

class OrderCreated(CommandMessage):
    order_id: str
    amount_cents: int
```

### 2. Write a handler

A handler is a class with a `process(self, message)` method (sync or async):

```python
from command_bus import CommandMessage, Handler

class SendOrderConfirmation(Handler):
    def process(self, message: CommandMessage):
        print(f"Order {message.order_id} confirmed")
```

### 3. Connect and run

Register the handler, create a bus with a queue adapter, send commands, and process them on the worker side:

```python
from command_bus import CommandBus, Router
from command_bus.adapters import InMemoryQueueAdapter

router = Router()
router.register(OrderCreated, SendOrderConfirmation)

bus = CommandBus(
    queue_adapter=InMemoryQueueAdapter(queue_name="commands"),
    command_router=router,
)

await bus.execute(OrderCreated(order_id="ord-1", amount_cents=1999), wait=False)
await bus.work()
```

`WorkerApp` does this wiring for you — the steps above are what happen under the hood.

## Events

For pub/sub (one publish, many subscribers), use **`EventBus`** instead. See [Pub/sub events](pubsub-events.md).

## Next steps

- **[Handler decorator](handler-decorator.md)** — skip writing message classes by hand with `@router.command()` or `@app.command()`.
- **[Queue adapters](queue-adapters.md)** — swap in-memory for SQS, Redis, or RabbitMQ in production.
- **[Client and worker](client-and-worker.md)** — share one setup between your app (producer) and worker (consumer).
- **[Execute and wait](execute-and-wait.md)** — send a command and get the handler's return value back.
- **[Worker CLI](cli.md)** — run multiple worker processes with `command-bus-worker`.
