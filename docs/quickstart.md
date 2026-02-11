# Quick start

## 1. Define event messages

Subclass `EventMessage` (a Pydantic model). Use it for the payload of your events.

```python
from event_bus import EventMessage

class OrderCreated(EventMessage):
    order_id: str
    amount_cents: int
```

## 2. Define handlers

Implement `EventMessageHandler`: define a class with a `process(self, message)` method. The method can be sync or async.

```python
from event_bus import EventMessage, EventMessageHandler

class SendOrderConfirmation(EventMessageHandler):
    def process(self, message: EventMessage):
        print(f"Order {message.order_id} confirmed")
```

## 3. Register and execute

Create a registry, register the message type with the handler, then use a bus (with a queue adapter) to execute events. The bus enqueues the message; a worker later runs `await bus.work()` to dispatch to handlers.

```python
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import InMemoryEventBusAdapter

registry = EventBusRegistry()
registry.register(OrderCreated, SendOrderConfirmation)

adapter = InMemoryEventBusAdapter(queue_name="events")
bus = EventBus(queue_adapter=adapter, event_registry=registry)

# Enqueue an event (fire-and-forget)
await bus.execute(OrderCreated(order_id="ord-1", amount_cents=1999), wait=False)

# Worker: poll queue and run handlers
await bus.work()
```

## Dispatching without a queue

If you don't use a queue adapter, you can parse a message string and dispatch in-process:

```python
from event_bus import MessageParser

msg_str = "your.module.OrderCreated(order_id='abc', amount_cents=1999)"
parser = MessageParser(msg_str)
event = parser.initialize()
for entry in registry.get_handlers_for_message(event):
    handler = entry.handler_instance()
    await handler(event)
```

## Next steps

- Use the **[handler decorator](handler-decorator.md)** to avoid defining a message class and get a message factory: `bus.execute(on_order_created(order_id=1, amount_cents=10), wait=False)`.
- Configure a **[queue adapter](queue-adapters.md)** (SQS, Redis, RabbitMQ) and a **[client/worker](client-and-worker.md)** setup.
- Use **[execute and wait](execute-and-wait.md)** with a response store to get the handler result back.
