# Using @registry.event() with Separate Client/Worker Processes

When using `@registry.event()` with separate client and worker processes, you **must** define your event handlers in a **shared module** that both processes import. This ensures the generated message classes can be properly resolved.

## The Problem

If you define handlers directly in `client.py` and `worker.py` (both running as `__main__`), the message classes will have module paths like `__main__.on_order_createdMessage`. When the worker tries to parse these messages, it can't find the class because its `__main__` is different from the client's `__main__`.

## The Solution: Shared Module

### Step 1: Create a shared events module

```python
# events.py (shared module)
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import FileQueueAdapter, FileResponseStore

# Create a shared registry
registry = EventBusRegistry()

# Define handlers using the decorator
@registry.event()
def on_order_created(order_id: str, amount_cents: int):
    print(f"Processing order {order_id} for {amount_cents} cents")
    return {"status": "processed", "order_id": order_id}

@registry.event()
def on_payment_received(order_id: str, amount_cents: int):
    print(f"Payment received for order {order_id}: {amount_cents} cents")

# Factory function to create the bus (shared configuration)
def create_bus():
    queue_adapter = FileQueueAdapter(queue_name="events")
    response_store = FileResponseStore()
    return EventBus(
        queue_adapter=queue_adapter,
        event_registry=registry,
        response_store=response_store,
    )
```

### Step 2: Client script

```python
# client.py
import asyncio
from events import create_bus, on_order_created, on_payment_received

async def main():
    bus = create_bus()
    
    # Use the message factories from the shared module
    await bus.execute(on_order_created(order_id="ord-1", amount_cents=1999), wait=False)
    await bus.execute(on_payment_received(order_id="ord-1", amount_cents=1999), wait=False)
    
    print("Messages enqueued!")

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Worker script

```python
# worker.py
import asyncio
from events import create_bus  # Import the shared module

async def run_worker():
    bus = create_bus()  # Same configuration as client
    
    while True:
        await bus.work()  # Process messages from queue
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_worker())
```

## Why This Works

1. **Shared module**: Both client and worker import from `events.py`, so the message classes are registered in the same module namespace.
2. **Module path**: Messages will have paths like `events.on_order_createdMessage(...)` instead of `__main__.on_order_createdMessage(...)`.
3. **Import resolution**: When the worker parses a message, it can successfully import `events` and find the message class.

## Error Messages

If you encounter import errors, you'll now see helpful messages like:

```
Class 'on_order_createdMessage' not found in module '__main__'. 
This usually happens when client and worker are separate scripts. 
Solution: Define event handlers in a shared module that both 
client and worker import. See docs/client-and-worker.md
```

This guides you to use the shared module pattern shown above.

