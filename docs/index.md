# CommandBus (Python) — Documentation

A small command bus with pluggable queue adapters. Define command messages as Pydantic models, register handlers, and execute commands in-process or via a queue (e.g. AWS SQS, RabbitMQ, Redis).

## Documentation

| Topic | Description |
|-------|-------------|
| [Installation](installation.md) | Install the package and optional extras (SQS, Redis, RabbitMQ). |
| [Quick start](quickstart.md) | Define messages and handlers, register, and execute. |
| [Handler decorator](handler-decorator.md) | Use `@router.command()` to generate the message from a function and get a message factory. |
| [Message formats and parsers](message-formats-and-parsers.md) | Repr, JSON, Base64 parsers and how to set a custom parser on the bus. |
| [Client and worker](client-and-worker.md) | Shared bus factory, producer client, and consumer worker. |
| [WorkerApp](worker-app.md) | FastAPI-style worker facade with `@app.command()` and in-process concurrency. |
| [Worker CLI](cli.md) | `command-bus-worker module[:attr]`: `CommandBus`, `EventBus`, `WorkerApp`, or `BusGroup`. |
| [Queue adapters](queue-adapters.md) | In-memory, SQS, RabbitMQ, and Redis adapters. |
| [Pub/sub events](pubsub-events.md) | `EventBus`, fan-out adapters, `@router.event()`. |
| [Execute and wait](execute-and-wait.md) | Unified `execute()` API, response store, and request/response. |
| [API reference](api-reference.md) | Overview of public types and methods. |

## Quick links

- **Minimal send:** `await bus.execute(on_order_created(order_id="x", amount_cents=10), wait=False)`
- **Wait for result:** `result = await bus.execute(on_order_created(...))` (with a response store on the bus)
- **Worker loop:** `await bus.work()` in a loop, or use the [Worker CLI](cli.md) (`command-bus-worker myapp.worker:bus`, or `:bus_group` for a group)
