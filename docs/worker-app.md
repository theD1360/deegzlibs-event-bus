# WorkerApp

`WorkerApp` is the orchestration shell for worker processes: lifecycle hooks, shared middleware, and CLI targeting. For a **single command queue**, use the constructor shortcut with `@app.command()` and `app.execute()`. For **multiple queues** (commands and events), construct `CommandBus` / `EventBus` yourself and mount them with `app.register()`.

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
PYTHONPATH=src python examples/worker_app_multi_queue_demo.py
```

## Multi-queue: commands and events

Build buses yourself, register handlers on each bus router, then mount on one app:

```python
from command_bus import WorkerApp, CommandBus, EventBus, Router
from command_bus.adapters import InMemoryQueueAdapter, InMemoryPubSubAdapter

orders_router = Router()
events_router = Router()

@orders_router.command()
def process_order(order_id: str) -> None:
    ...

@events_router.event()
def on_order_created(order_id: str) -> None:
    ...

orders = CommandBus(
    queue_adapter=InMemoryQueueAdapter(queue_name="orders"),
    command_router=orders_router,
)
events = EventBus(
    queue_adapter=InMemoryPubSubAdapter(queue_name="order-events"),
    command_router=events_router,
)

app = WorkerApp(create_default_bus=False)
app.register(orders, name="orders", workers=4, concurrency=2)
app.register(events, name="events", workers=2, concurrency=4)
```

- **Send** on the bus: `await orders.execute(...)`, `await events.publish(...)` (not on `app`).
- **Consume** via CLI or `app.run()` — the app polls registered buses.
- **Middleware and lifecycle** are app-wide; registered buses share the app's middleware list.

## Running in production

Point the worker CLI at your app (same idea as `uvicorn myapp.main:app`):

```bash
# All registered queues (orders×4 + events×2 processes when configured above)
command-bus-worker myapp.worker:app

# Dedicated worker for one queue (separate K8s Deployment, same image)
command-bus-worker myapp.worker:app --queue orders --workers 8
command-bus-worker myapp.worker:app --queue events
```

| Option | Default | What it does |
|--------|---------|--------------|
| `--queue` | all registered | Consume only this registered queue name. |
| `--workers` | `1` or per-queue `workers=` | OS processes for the target queue(s). |
| `--concurrency` | app's setting, or `1` | How many messages each process handles **at once**. |
| `--poll-interval` | `0.05` | Pause between polls when the queue is empty. |

Use a shared queue backend (SQS, Redis, RabbitMQ) when `--workers` is greater than 1. The in-memory adapter only works inside a single process.

For multi-queue apps, prefer **`BusGroup`-style per-queue `workers=`** on `register()` instead of one global `--workers` when spawning all queues.

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
| `response_store` | `None` | Set this to enable `execute(..., wait=True)` on the default bus. |
| `response_ttl_seconds` | `60` | How long responses are kept. |
| `create_default_bus` | `True` | Set `False` for register-only multi-queue apps. |

### `app.register(bus, ...)`

Mount an existing `CommandBus` or `EventBus`:

| Parameter | Description |
|-----------|-------------|
| `name` | CLI `--queue` target; defaults to `bus.queue_adapter.queue_name`. |
| `workers` | Default OS process count for this queue (CLI `--workers` overrides with `--queue`). |
| `concurrency` | In-process parallel dispatch for this queue. |

Returns a `RegisteredBus`. Use `app.get(name)` / `app.queues` to inspect.

### Methods

- **`@app.command()`** — register on the default command bus router (single-queue shortcut).
- **`app.register(bus, ...)`** — mount a command or event bus for CLI/work orchestration.
- **`@app.on_startup`** / **`@app.on_shutdown`** — lifecycle decorators.
- **`@app.middleware`** / **`app.add_middleware(...)`** — register dispatch middleware (shared by registered buses).
- **`await app.startup()`** / **`await app.shutdown()`** — run lifecycle handlers manually.
- **`await app.execute(message, ...)`** — send on the default command bus.
- **`await app.work(queue_name=...)`** — poll once; omit `queue_name` to poll all registered buses.
- **`await app.run(poll_interval=0.05)`** — startup, poll until cancelled, then shutdown.
- **`app.bus`** — the default `CommandBus` (single-queue shortcut).

## See also

- [Quick start](quickstart.md) — first steps with WorkerApp.
- [Handler decorator](handler-decorator.md) — how `@app.command()` works.
- [Worker CLI](cli.md) — process model and all CLI options.
- [Client and worker](client-and-worker.md) — splitting producer and consumer in production.
