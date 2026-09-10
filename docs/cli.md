# Worker CLI

The package includes a small **command-line worker** that imports your module, resolves a **`CommandBus`**, **`EventBus`**, or **`BusGroup`**, and runs **`await bus.work()`** in a loop. Each logical worker runs in its **own OS process** so CPU-heavy handlers are not serialized by the CPython GIL.

The first argument is a **target** in the same spirit as **uvicorn** / **gunicorn**: **`dotted.module:attribute`**. The CLI loads that attribute and branches on its type (`CommandBus`, `EventBus`, `WorkerApp`, or `BusGroup`).

## How to run

After installing the package, use the console script (recommended) or the module entry point:

```bash
command-bus-worker myapp.worker:bus --workers 4
```

If the attribute name is **`bus`**, you can omit **`:bus`** (same default as uvicorn’s common `app` pattern, but here the default attribute is **`bus`**):

```bash
command-bus-worker myapp.worker --workers 4
```

```bash
python -m command_bus.cli myapp.worker:bus_group --workers 2
```

The module path must be importable on `PYTHONPATH` (or installed in the active environment).

## Target resolution

| Target example | Meaning |
|----------------|---------|
| `myapp.worker` | Import `myapp.worker`, use attribute **`bus`** (must be a `CommandBus` or `EventBus`). |
| `myapp.worker:orders_bus` | Import `myapp.worker`, use attribute **`orders_bus`**. |
| `myapp.worker:bus_group` | Import `myapp.worker`, use attribute **`bus_group`** (must be a `BusGroup`). |
| `myapp.worker:app` | Import `myapp.worker`, use attribute **`app`** (must be a `WorkerApp`). |

If the attribute is not a **`CommandBus`**, **`EventBus`**, **`WorkerApp`**, or **`BusGroup`**, the CLI exits with an error.

See [WorkerApp](worker-app.md) for the FastAPI-style facade and in-memory example.

## Worker module layout

### Single `CommandBus`

Expose a **`CommandBus`** at **`bus`** (or point the target at another attribute name):

```python
# myapp/worker.py
from command_bus import CommandBus, Router
from command_bus.adapters import SqsQueueAdapter
import boto3

router = Router()
# ... register handlers on router ...

sqs = boto3.resource("sqs")
adapter = SqsQueueAdapter(queue_name="orders", sqs_client=sqs)
bus = CommandBus(queue_adapter=adapter, command_router=router)
```

```bash
command-bus-worker myapp.worker --workers 2
command-bus-worker myapp.worker:orders_bus --workers 2   # if you named it orders_bus
```

The parent process imports the module once to validate the target before spawning workers. **Each child process imports the module again** and uses **`getattr(module, bus_attr)`** for its queue loop. With **`fork`** (POSIX), avoid opening non–fork-safe resources at import time if possible; prefer lazy initialization inside handlers or after import.

### `BusGroup` (several buses, one CLI)

Define a **`BusGroup`** and point the target at it. Pass each bus instance into **`WorkerConfig`**. The CLI finds the **module-level attribute name** for each bus (same object identity on the worker module) so child processes can re-import the module and `getattr` the bus—nothing is pickled.

Each bus **must** be assigned to a top-level attribute on that module (e.g. `orders_bus = CommandBus(...)`). If the same instance is bound under several names, the **lexicographically smallest** name is used. After **fork**, avoid opening non–fork-safe clients at import time before workers start.

```python
# myapp/worker.py
from command_bus import CommandBus, BusGroup, Router, WorkerConfig
from command_bus.adapters import SqsQueueAdapter
import boto3

router = Router()
# ... register handlers ...

sqs = boto3.resource("sqs")
orders_bus = CommandBus(
    queue_adapter=SqsQueueAdapter(queue_name="orders", sqs_client=sqs),
    command_router=router,
)
priority_bus = CommandBus(
    queue_adapter=SqsQueueAdapter(queue_name="priority", sqs_client=sqs),
    command_router=router,
)

bus_group = BusGroup(
    WorkerConfig(orders_bus, workers=4),
    WorkerConfig(priority_bus, workers=2),
)
```

```bash
command-bus-worker myapp.worker:bus_group
```

If a **`WorkerConfig`** omits **`workers`**, the CLI **`--workers`** value is used for that entry only.

> **Note:** The attribute name `command_bus_group` with a **`CommandBusGroup`** instance still works (deprecated alias).

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `TARGET` | (required) | `module` or `module:attribute` (see above). |
| `--workers` | `1` | Process count for one bus or `WorkerApp`, or default per `WorkerConfig` when `workers` is omitted in a `BusGroup`. |
| `--concurrency` | `WorkerApp.concurrency` or `1` | In-process parallel message dispatch per worker process. |
| `--poll-interval` | `0.05` | Seconds to sleep after each `work()` iteration when polling (reduces CPU when the queue is often empty). Use `0` for no sleep (still yields briefly in the asyncio loop). |
| `-v` / `--verbose` | off | Once: INFO logging. Twice: DEBUG. |

Run **`command-bus-worker --help`** for the full usage text.

## Multiple queues without a group

Run **separate** worker processes, each with its own target:

```bash
command-bus-worker myapp.worker:orders_bus --workers 4 &
command-bus-worker myapp.worker:priority_bus --workers 2 &
```

## Process model

| Platform | Start method | Notes |
|----------|----------------|-------|
| Linux / macOS | `fork` | Separate interpreter per worker; no shared GIL across workers. |
| Windows | `spawn` | Same idea, but each child starts a fresh interpreter (no `fork` on Windows). |

The parent handles **SIGINT** / **SIGTERM** and stops children with **`terminate()`** (SIGTERM on Unix). Child workers ignore **SIGINT** so the terminal does not deliver the same signal to every process in the foreground group in a conflicting way; they shut down on **SIGTERM** from the parent.

For **`WorkerApp`** targets, each child process runs **`@app.on_startup`** handlers before the first **`work()`** poll and **`@app.on_shutdown`** handlers when the loop exits. See [WorkerApp](worker-app.md#lifecycle-hooks).

## See also

- [Client and worker](client-and-worker.md) — shared bus factory pattern and hand-written `asyncio` worker loops.
- [Queue adapters](queue-adapters.md) — configuring SQS, Redis, RabbitMQ, and in-memory queues.
