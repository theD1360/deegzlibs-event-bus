"""Tests for file-based queue adapter."""

import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from event_bus import EventBus, EventBusRegistry, EventMessage, EventMessageHandler
from event_bus.adapters import FileQueueAdapter


class SampleMessage(EventMessage):
    value: str
    number: int = 0


def test_file_queue_adapter_enqueue():
    """Test enqueueing messages."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        msg = SampleMessage(value="test1", number=1)
        adapter.enqueue(msg)

        messages = adapter.get_messages()
        assert len(messages) == 1
        assert "test1" in messages[0].body
        assert "number=1" in messages[0].body or '"number":1' in messages[0].body


def test_file_queue_adapter_dequeue():
    """Test dequeuing messages."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        msg = SampleMessage(value="test1")
        adapter.enqueue(msg)

        messages = adapter.get_messages()
        assert len(messages) == 1

        adapter.dequeue(messages[0])
        messages = adapter.get_messages()
        assert len(messages) == 0


def test_file_queue_adapter_multiple_messages():
    """Test handling multiple messages."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        adapter.enqueue(SampleMessage(value="msg1"))
        adapter.enqueue(SampleMessage(value="msg2"))
        adapter.enqueue(SampleMessage(value="msg3"))

        messages = adapter.get_messages(max_messages=10)
        assert len(messages) == 3

        # Verify all messages are present
        bodies = [m.body for m in messages]
        assert any("msg1" in b for b in bodies)
        assert any("msg2" in b for b in bodies)
        assert any("msg3" in b for b in bodies)


def test_file_queue_adapter_queue_name_filtering():
    """Test that messages are filtered by queue name."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter1 = FileQueueAdapter(
            queue_name="queue1", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )
        adapter2 = FileQueueAdapter(
            queue_name="queue2", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        adapter1.enqueue(SampleMessage(value="msg1"))
        adapter2.enqueue(SampleMessage(value="msg2"))

        # Each adapter should only see its own messages
        messages1 = adapter1.get_messages()
        messages2 = adapter2.get_messages()

        assert len(messages1) == 1
        assert len(messages2) == 1
        assert "msg1" in messages1[0].body
        assert "msg2" in messages2[0].body


def test_file_queue_adapter_delay_seconds():
    """Test delayed message delivery."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        # Enqueue with delay
        adapter.enqueue(SampleMessage(value="delayed"), delay_seconds=0.2)

        # Should not be available immediately
        messages = adapter.get_messages()
        assert len(messages) == 0

        # Wait for delay
        time.sleep(0.3)

        # Should be available now
        messages = adapter.get_messages()
        assert len(messages) == 1
        assert "delayed" in messages[0].body


def test_file_queue_adapter_persistence():
    """Test that queue persists across adapter instances."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"

        # Create adapter, enqueue, close
        adapter1 = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )
        adapter1.enqueue(SampleMessage(value="persisted"))
        del adapter1

        # Create new adapter instance, should see the message
        adapter2 = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )
        messages = adapter2.get_messages()
        assert len(messages) == 1
        assert "persisted" in messages[0].body


def test_file_queue_adapter_empty_queue():
    """Test getting messages from empty queue."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        messages = adapter.get_messages()
        assert len(messages) == 0


def test_file_queue_adapter_message_wrapper():
    """Test that messages have the expected wrapper interface."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        adapter.enqueue(SampleMessage(value="test"))
        messages = adapter.get_messages()

        assert len(messages) == 1
        msg = messages[0]
        assert hasattr(msg, "body")
        assert isinstance(msg.body, str)
        assert "test" in msg.body


@pytest.mark.asyncio
async def test_file_queue_adapter_with_event_bus():
    """Test FileQueueAdapter integration with EventBus."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="events", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )
        registry = EventBusRegistry()
        received: list[str] = []

        class Handler(EventMessageHandler):
            def process(self, message: EventMessage):
                received.append(message.value)

        registry.register(SampleMessage, Handler)
        bus = EventBus(queue_adapter=adapter, event_registry=registry)

        # Execute messages
        await bus.execute(SampleMessage(value="msg1"), wait=False)
        await bus.execute(SampleMessage(value="msg2"), wait=False)

        # Process messages
        await bus.work()
        await bus.work()

        assert len(received) == 2
        assert "msg1" in received
        assert "msg2" in received


def test_file_queue_adapter_dequeue_nonexistent():
    """Test dequeuing a message that doesn't exist (should not error)."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        # Create a fake message wrapper
        class FakeMessage:
            def __init__(self):
                self.body = "nonexistent message"

        fake_msg = FakeMessage()
        # Should not raise an error
        adapter.dequeue(fake_msg)


def test_file_queue_adapter_default_storage_location():
    """Test that default storage location is created."""
    adapter = FileQueueAdapter(queue_name="test")
    # Should not raise an error
    assert adapter.storage_file is not None
    assert adapter.storage_file.parent.exists() or adapter.storage_file.parent == Path.home() / ".qubot"


def test_file_queue_adapter_concurrent_operations():
    """Test that multiple operations work correctly."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=0  # No hiding for this test
        )

        # Enqueue multiple messages
        for i in range(5):
            adapter.enqueue(SampleMessage(value=f"msg{i}", number=i))

        # Get all messages
        messages = adapter.get_messages(max_messages=10)
        assert len(messages) == 5

        # Dequeue some
        adapter.dequeue(messages[0])
        adapter.dequeue(messages[1])

        # Should have 3 remaining
        remaining = adapter.get_messages(max_messages=10)
        assert len(remaining) == 3


def test_file_queue_adapter_visibility_timeout():
    """Test that messages are hidden after retrieval."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=1
        )

        # Enqueue a message
        adapter.enqueue(SampleMessage(value="msg1"))

        # Get the message (should be visible)
        messages = adapter.get_messages()
        assert len(messages) == 1

        # Immediately try to get messages again - should be hidden
        messages2 = adapter.get_messages()
        assert len(messages2) == 0

        # Wait for visibility timeout to expire
        time.sleep(1.1)

        # Message should be visible again
        messages3 = adapter.get_messages()
        assert len(messages3) == 1
        assert "msg1" in messages3[0].body


def test_file_queue_adapter_visibility_timeout_custom():
    """Test custom visibility timeout parameter."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=60
        )

        adapter.enqueue(SampleMessage(value="msg1"))

        # Get with custom visibility timeout
        messages = adapter.get_messages(visibility_timeout=0.5)
        assert len(messages) == 1

        # Should be hidden
        messages2 = adapter.get_messages()
        assert len(messages2) == 0

        # Wait for custom timeout
        time.sleep(0.6)

        # Should be visible again
        messages3 = adapter.get_messages()
        assert len(messages3) == 1


def test_file_queue_adapter_visibility_timeout_multiple_messages():
    """Test visibility timeout with multiple messages."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=1
        )

        # Enqueue multiple messages
        adapter.enqueue(SampleMessage(value="msg1"))
        adapter.enqueue(SampleMessage(value="msg2"))
        adapter.enqueue(SampleMessage(value="msg3"))

        # Get 2 messages (they become hidden)
        messages = adapter.get_messages(max_messages=2)
        assert len(messages) == 2

        # Should only get the remaining visible message (msg3)
        messages2 = adapter.get_messages()
        assert len(messages2) == 1

        # Now all 3 messages should be hidden (the third one was just retrieved)
        messages3 = adapter.get_messages()
        assert len(messages3) == 0

        # Wait for timeout
        time.sleep(1.1)

        # Should get all 3 messages back (they're visible again after timeout)
        messages4 = adapter.get_messages(max_messages=10)
        assert len(messages4) == 3


def test_file_queue_adapter_dequeue_removes_hidden_message():
    """Test that dequeue properly removes messages even when hidden."""
    with TemporaryDirectory() as tmpdir:
        queue_file = Path(tmpdir) / "queue.json"
        adapter = FileQueueAdapter(
            queue_name="test", 
            storage_file=queue_file,
            default_visibility_timeout=60
        )

        adapter.enqueue(SampleMessage(value="msg1"))

        # Get message (makes it hidden)
        messages = adapter.get_messages()
        assert len(messages) == 1

        # Dequeue it
        adapter.dequeue(messages[0])

        # Wait and check - should not reappear
        time.sleep(0.1)
        messages2 = adapter.get_messages()
        assert len(messages2) == 0

