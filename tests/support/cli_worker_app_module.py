"""Minimal WorkerApp module for CLI integration tests."""

from command_bus import WorkerApp
from command_bus.adapters import InMemoryQueueAdapter

app = WorkerApp(
    queue_adapter=InMemoryQueueAdapter(queue_name="cli-worker-app-test"),
    concurrency=2,
)


@app.command()
def noop(value: str) -> None:
    pass
