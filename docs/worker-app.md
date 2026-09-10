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

Try the full demo:

```bash
PYTHONPATH=src python examples/worker_app_demo.py
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
- **`await app.execute(message, ...)`** — send a command.
- **`await app.work()`** — poll the queue once; returns how many messages were handled.
- **`await app.run(poll_interval=0.05)`** — keep polling until cancelled (handy in dev).
- **`app.bus`** — the underlying `CommandBus` if you need lower-level access.

## See also

- [Quick start](quickstart.md) — first steps with WorkerApp.
- [Handler decorator](handler-decorator.md) — how `@app.command()` works.
- [Worker CLI](cli.md) — process model and all CLI options.
- [Client and worker](client-and-worker.md) — splitting producer and consumer in production.
