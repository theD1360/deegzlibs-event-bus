# EventBus (Python) — Documentation

A small event bus with pluggable queue adapters. Define event messages as Pydantic models, register handlers, and execute events in-process or via a queue (e.g. AWS SQS, RabbitMQ, Redis).

## Documentation

| Topic | Description |
|-------|-------------|
| [Installation](installation.md) | Install the package and optional extras (SQS, Redis, RabbitMQ). |
| [Quick start](quickstart.md) | Define messages and handlers, register, and execute. |
| [Handler decorator](handler-decorator.md) | Use `@registry.event()` to generate the message from a function and get a message factory. |
| [Message formats and parsers](message-formats-and-parsers.md) | Repr, JSON, Base64 parsers and how to set a custom parser on the bus. |
| [Client and worker](client-and-worker.md) | Shared bus factory, producer client, and consumer worker. |
| [Queue adapters](queue-adapters.md) | In-memory, SQS, RabbitMQ, and Redis adapters. |
| [Execute and wait](execute-and-wait.md) | Unified `execute()` API, response store, and request/response. |
| [API reference](api-reference.md) | Overview of public types and methods. |

## Quick links

- **Minimal send:** `await bus.execute(on_order_created(order_id="x", amount_cents=10), wait=False)`
- **Wait for result:** `result = await bus.execute(on_order_created(...))` (with a response store on the bus)
- **Worker loop:** `await bus.work()` in a loop
