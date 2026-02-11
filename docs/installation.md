# Installation

## Core package

```bash
pip install deegzlibs-event-bus
```

This gives you the event bus, in-memory queue adapter, in-memory response store, and repr/JSON/Base64 parsers.

## Optional extras

| Extra | Use case |
|-------|----------|
| `[sqs]` | AWS SQS queue adapter |
| `[redis]` | Redis queue adapter and Redis response store (for `execute_and_wait`) |
| `[rabbitmq]` | RabbitMQ queue adapter (requires `pika`) |

Examples:

```bash
pip install deegzlibs-event-bus[sqs]
pip install deegzlibs-event-bus[redis]
pip install deegzlibs-event-bus[rabbitmq]
```

Install multiple extras with a comma:

```bash
pip install deegzlibs-event-bus[sqs,redis]
```
