# Execute and wait (unified API)

**`execute()`** is async and is the single entry point for sending events. Behaviour depends on whether the bus has a **response store** and on the **`wait`** flag.

## Behaviour

| Scenario | What happens |
|----------|----------------|
| **No response store** | `await bus.execute(event)` only enqueues and returns `None`. `wait` is ignored. |
| **Response store, `wait=True` (default when store is set)** | Bus enqueues the event with a `correlation_id`, then polls the response store until the worker stores the handler result (or timeout). Returns that result. |
| **Response store, `wait=False`** | Only enqueues; returns `None`. Fire-and-forget. |

So:

- **With response store:** `result = await bus.execute(event)` waits for the handler result by default; use `await bus.execute(event, wait=False)` to only enqueue.
- **Without response store:** `await bus.execute(event)` just enqueues.

**`execute_and_wait(event, ...)`** is a convenience for **`execute(event, wait=True, ...)`**.

## Getting responses (request/response)

To get a result back from the worker:

1. Install Redis support: **`pip install deegzlibs-event-bus[redis]`** (or use another response store implementation).
2. Create a **response store** and pass it into the bus. Client and worker must use the **same store** (e.g. same Redis instance).
3. **Client:** call **`result = await bus.execute(event)`** or **`result = await bus.execute_and_wait(event, timeout_seconds=30)`**.
4. **Worker:** no change. After each handler runs, if the event has a `correlation_id` and the bus has a `response_store`, the last non-`None` return value is stored under that id.

Handler return values must be JSON-serializable (or Pydantic models; they are stored via `model_dump()`).

### Example: class-based handler

```python
import boto3
import redis
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import SqsEventBusAdapter, RedisResponseStore

registry = EventBusRegistry()
registry.register(OrderCreated, SendOrderConfirmation)

def create_bus():
    r = redis.Redis(host="localhost", port=6379, decode_responses=False)
    response_store = RedisResponseStore(r, key_prefix="myapp:response:", default_ttl_seconds=60)
    adapter = SqsEventBusAdapter(queue_name="orders", sqs_client=boto3.resource("sqs"))
    bus = EventBus(queue_adapter=adapter, event_registry=registry, response_store=response_store)
    return bus

# Client
async def main():
    bus = create_bus()
    result = await bus.execute_and_wait(OrderCreated(order_id="ord-1", amount_cents=1999), timeout_seconds=10)
    print(result)  # whatever the handler returned
```

### Example: with `@registry.event()`

The decorated function’s return value is what the client receives. Use the message factory with `execute` or `execute_and_wait`:

```python
@registry.event()
def process_order(order_id: str, amount_cents: int) -> dict:
    # do work...
    return {"status": "processed", "order_id": order_id}

# Client
bus = create_bus()
result = await bus.execute(process_order(order_id="ord-1", amount_cents=1999))  # default wait=True
# or: result = await bus.execute_and_wait(process_order(order_id="ord-1", amount_cents=1999), timeout_seconds=10)
```

## Timeout

If the worker never stores a result (handler doesn’t return or raises), the client gets **`TimeoutError`** after **`timeout_seconds`** (default 30). You can pass **`timeout_seconds`**, **`poll_interval_seconds`**, and **`response_ttl_seconds`** to **`execute()`** or **`execute_and_wait()`**.

## Response store implementations

- **InMemoryResponseStore** – In-memory (no deps). Useful for tests. From **`event_bus.adapters`**.
- **RedisResponseStore** – Redis-backed. Install with **`pip install deegzlibs-event-bus[redis]`**. From **`event_bus.adapters`**.
