# WorkerApp

`WorkerApp` is a FastAPI-style entry point for command workers: one object owns the router, queue adapter, and bus. Register handlers with `@app.command()` and run the worker with `app.run()` or the [Worker CLI](cli.md).

## Motivation

Like FastAPI + Uvicorn/Gunicorn, worker throughput comes from two layers:

| Layer | FastAPI | WorkerApp |
|-------|---------|-----------|
| OS processes | `gunicorn -w 4` | `command-bus-worker ... --workers 4` |
| In-process concurrency | asyncio (many connections per process) | `concurrency` / `--concurrency` (many messages per poll) |

## Quick start (in-memory)

Single-process demo — producer and consumer share one queue:

```python
from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter, InMemoryResponseStore

adapter = InMemoryQueueAdapter(queue_name="demo")
app = WorkerApp(
    queue_adapter=adapter,
    concurrency=3,
    response_store=InMemoryResponseStore(),
)

@app.command()
async def add(a: int, b: int) -> int:
    return a + b

@app.command()
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

Run the included example:

```bash
PYTHONPATH=src python examples/worker_app_demo.py
```

## CLI

Point the worker CLI at your `WorkerApp` instance (like uvicorn):

```bash
command-bus-worker myapp.worker:app --workers 2 --concurrency 5
```

| Option | Default | Description |
|--------|---------|-------------|
| `--workers` | `1` | OS process count (competing consumers on shared queues). |
| `--concurrency` | app's `concurrency` (or `1` for `CommandBus`) | Parallel message dispatch per process. |
| `--poll-interval` | `0.05` | Idle sleep between poll ticks. |

## In-memory vs production adapters

`InMemoryQueueAdapter` stores messages in a **process-local** deque. It works well for tests and single-process demos. Do **not** use `--workers > 1` with in-memory queues — each process gets its own empty queue. For multi-process workers, use SQS, Redis, or RabbitMQ ([queue adapters](queue-adapters.md)).

## API

### `WorkerApp(...)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `queue_adapter` | `InMemoryQueueAdapter(queue_name=...)` | Queue backend. |
| `queue_name` | `"default"` | Used when no adapter is passed. |
| `concurrency` | `1` | Max messages fetched and dispatched in parallel per `work()` call. |
| `response_store` | `None` | Enables `execute(..., wait=True)`. |
| `response_ttl_seconds` | `60` | TTL for stored responses. |

### Methods

- **`@app.command()`** — register a command handler (same as `@router.command()`).
- **`await app.execute(message, ...)`** — enqueue a command.
- **`await app.work()`** — poll once; returns number of messages handled.
- **`await app.run(poll_interval=0.05)`** — dev loop until cancelled.
- **`app.bus`** — underlying `CommandBus` for advanced use.

## See also

- [Handler decorator](handler-decorator.md) — `@router.command()` behaviour.
- [Worker CLI](cli.md) — process model and options.
- [Client and worker](client-and-worker.md) — shared factory pattern for production.
