"""WorkerApp module for CLI lifecycle integration tests."""

from command_bus import WorkerApp

lifecycle_log: list[str] = []

app = WorkerApp(queue_adapter=__import__(
    "command_bus.adapters", fromlist=["InMemoryQueueAdapter"]
).InMemoryQueueAdapter(queue_name="cli-lifecycle"))


@app.on_startup
def on_startup():
    lifecycle_log.append("startup")


@app.on_shutdown
def on_shutdown():
    lifecycle_log.append("shutdown")


@app.command()
def noop(tag: str) -> None:
    pass
