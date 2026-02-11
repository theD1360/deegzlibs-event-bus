# Handler decorator

Instead of defining a message class and a handler class, you can use **`@registry.event()`**. The decorator:

1. Builds an **EventMessage** subclass from the function’s parameters (names and type annotations).
2. Registers a handler that calls your function when the message is dispatched (with keyword args from the message).
3. Returns a **message factory**: calling the decorated function returns the prefilled message instance.

So you can send events like this:

```python
await bus.execute(on_order_created(order_id=1, amount_cents=10), wait=False)
```

## Example

```python
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import RedisEventBusAdapter
import redis

r = redis.Redis(host="localhost", port=6379)
adapter = RedisEventBusAdapter(redis_client=r, queue_name="events")
registry = EventBusRegistry()
bus = EventBus(queue_adapter=adapter, event_registry=registry)

@registry.event()
def on_order_created(order_id: str, amount_cents: int):
    print(f"Order {order_id} confirmed for {amount_cents} cents")

# Calling the decorator returns the message instance; pass it to execute
await bus.execute(on_order_created(order_id="ord-1", amount_cents=1999), wait=False)
result = await bus.execute(on_order_created(order_id="ord-2", amount_cents=500))  # wait=True when response_store set

await bus.work()
```

## Behaviour

- **Message factory:** After decoration, `on_order_created` is no longer the original function. Calling `on_order_created(order_id="x", amount_cents=100)` returns an instance of the generated message class (e.g. `on_order_createdMessage`), which you pass to `bus.execute(...)`.
- **Handler:** The original function is still the handler logic. It is invoked when the bus dispatches the message (e.g. in `bus.work()`). It is also available as **`func._handler_func`** for tests.
- **Generated message class:** Attached as **`func._event_message_class`**. The class is also registered on the function’s module so repr-based parsers can resolve it when dispatching from the queue.
- **Sync and async:** Both sync and async handler functions are supported.

## Optional and default parameters

The generated message supports optional and default parameter values the same way as the function:

```python
@registry.event()
def handle(tag: str, count: int = 0, extra: Optional[str] = None) -> str:
    return f"{tag}:{count}:{extra!r}"

# These all work
msg1 = handle(tag="a")
msg2 = handle(tag="b", count=2, extra="x")
```

## Positional and keyword arguments

You can call the factory with positional or keyword arguments; they are mapped to the message fields:

```python
on_order_created(1, 10)                    # positional
on_order_created(order_id="1", amount_cents=10)  # keyword
```
