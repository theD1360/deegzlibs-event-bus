# WorkerApp

`WorkerApp` is the recommended way to build a command worker. You pass in a **queue adapter** (where commands wait), register handlers with `@app.command()`, and use `execute()` to enqueue and `work()` to dequeue.

Producer and worker must use the same adapter configuration — see [Client and worker](client-and-worker.md).

## Quick start (in-memory)

Good for local development and tests. Producer and consumer share one queue in the same process:

```python
from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter, InMemoryResponseStore

app = WorkerApp(
    queue_adapter=InMemoryQueueAdapter(queue_name="demo"),
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

Try the demos:

```bash
PYTHONPATH=src python examples/worker_app_demo.py
PYTHONPATH=src python examples/worker_app_lifecycle_middleware_demo.py
```

## Running in production

Point the worker CLI at your app (same idea as `uvicorn myapp.main:app`):

```bash
command-bus-worker myapp.worker:app --workers 2 --concurrency 5
```

| Option | Default | What it does |
|--------|---------|--------------|
| `--workers` | `1` | Number of worker **processes** sharing the queue. |
| `--concurrency` | app's setting, or `1` | How many messages each process handles **at once**. |
| `--poll-interval` | `0.05` | Pause between polls when the queue is empty. |

Use a shared queue backend (SQS, Redis, RabbitMQ) when `--workers` is greater than 1. The in-memory adapter only works inside a single process.

## Lifecycle hooks

Run setup and teardown once per worker process. Handlers can be sync or async:

```python
app = WorkerApp()

@app.on_startup
async def open_pool():
    # Open DB/Redis connections here (not at module import time when using fork)
    ...

@app.on_shutdown
async def close_pool():
    ...
```

- **`app.run()`** calls startup before polling and shutdown in a `finally` block.
- **`command-bus-worker myapp.worker:app`** does the same in each worker child process.

Open connections in startup, not at import time, when using multi-process workers on POSIX (`fork`).

## Middleware

Middleware wraps each message dispatch (parse + handlers). Register on the app or directly on `CommandBus` / `EventBus`:

```python
from command_bus import DispatchContext

@app.middleware
async def log_dispatch(ctx: DispatchContext, call_next):
    print("before", ctx.raw_message[:80])
    await call_next(ctx)
    print("after", ctx.parsed_message)
```

- First registered middleware is **outermost** (runs first on the way in, last on the way out).
- Use **`ctx.app`** inside middleware when dispatch runs from a `WorkerApp`.
- Use **`ctx.state`** for per-message shared data between middleware layers.
- Failed middleware or handlers still dequeue the message (existing behavior); there is no automatic requeue.

Class-based middleware:

```python
app.add_middleware(LoggingMiddleware, logger=my_logger)
```

## API

### `WorkerApp(...)`

| Parameter | Default | Description |
|-----------|---------|-------------|
| `queue_adapter` | in-memory | Where commands are stored. |
| `queue_name` | `"default"` | Used when no adapter is passed. |
| `concurrency` | `1` | Max messages processed in parallel per `work()` call. |
| `response_store` | `None` | Set this to enable `execute(..., wait=True)`. |
| `response_ttl_seconds` | `60` | How long responses are kept. |

### Methods

- **`@app.command()`** — register a command handler.
- **`@app.on_startup`** / **`@app.on_shutdown`** — lifecycle decorators.
- **`@app.middleware`** / **`app.add_middleware(...)`** — register dispatch middleware.
- **`await app.startup()`** / **`await app.shutdown()`** — run lifecycle handlers manually.
- **`await app.execute(message, ...)`** — send a command.
- **`await app.work()`** — poll the queue once; returns how many messages were handled.
- **`await app.run(poll_interval=0.05)`** — startup, poll until cancelled, then shutdown.
- **`app.bus`** — the underlying `CommandBus` if you need lower-level access.

## See also

- [Quick start](quickstart.md) — first steps with WorkerApp.
- [Handler decorator](handler-decorator.md) — how `@app.command()` works.
- [Worker CLI](cli.md) — process model and all CLI options.
- [Client and worker](client-and-worker.md) — splitting producer and consumer in production.
