# Queue adapters

The bus uses an **EventBusAdapter** to enqueue and dequeue messages. Adapters are responsible for transport only; the bus handles parsing and handler dispatch.

## In-memory

**InMemoryEventBusAdapter** – FIFO queue in process. No extra dependencies. Useful for tests or single-process use. `delay_seconds` is ignored.

```python
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import InMemoryEventBusAdapter

adapter = InMemoryEventBusAdapter(queue_name="events")
bus = EventBus(queue_adapter=adapter)
```

Constructor: **`InMemoryEventBusAdapter(queue_name: str = "default")`**

---

## SQS

**SqsEventBusAdapter** – AWS SQS. Install with `pip install deegzlibs-event-bus[sqs]`.

```python
import boto3
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import SqsEventBusAdapter

sqs = boto3.resource("sqs")
adapter = SqsEventBusAdapter(queue_name="my-events", sqs_client=sqs)
registry = EventBusRegistry()
bus = EventBus(queue_adapter=adapter, event_registry=registry)
```

Constructor: **`SqsEventBusAdapter(queue_name: str, sqs_client)`** – `sqs_client` is a boto3 SQS resource.

---

## RabbitMQ

**RabbitMqEventBusAdapter** – RabbitMQ via pika. Install with `pip install deegzlibs-event-bus[rabbitmq]`.

```python
from event_bus import EventBus, EventBusRegistry
from event_bus.adapters import RabbitMqEventBusAdapter

adapter = RabbitMqEventBusAdapter(
    queue_name="my-events",
    connection_url="amqp://guest:guest@localhost/",
)
# Or: connection_params=pika.ConnectionParameters(host='localhost', port=5672)
bus = EventBus(queue_adapter=adapter)
```

Constructor: **`RabbitMqEventBusAdapter(queue_name, connection_url=None, connection_params=None)`** – provide either `connection_url` or `connection_params`.

- **`delay_seconds`** is not supported by plain RabbitMQ (use a delayed-message plugin if needed).
- The adapter keeps a single connection for consuming. Call **`adapter.close()`** when shutting down workers to release it.

---

## Redis

**RedisEventBusAdapter** – Redis Lists (LPUSH/BRPOP). Install with `pip install deegzlibs-event-bus[redis]`. You can use the same Redis instance for the queue and for the [response store](execute-and-wait.md) (e.g. `execute_and_wait`).

```python
import redis
from event_bus import EventBus
from event_bus.adapters import RedisEventBusAdapter

r = redis.Redis(host="localhost", port=6379)
adapter = RedisEventBusAdapter(redis_client=r, queue_name="events")
bus = EventBus(queue_adapter=adapter)
```

Constructor: **`RedisEventBusAdapter(redis_client, queue_name: str)`**.

- **`delay_seconds`** is not supported (Redis List has no native delay).
- Messages are removed when popped; failed handlers do not automatically requeue.
