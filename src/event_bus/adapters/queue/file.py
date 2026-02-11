"""File-based queue adapter for persistent cross-process event queuing."""

import fcntl
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from ...interfaces import EventBusAdapter, EventMessage


class FileQueueAdapter(EventBusAdapter):
    """File-based queue adapter that persists to disk for cross-process access."""

    def __init__(self, queue_name: str = "events", storage_file: Path = None) -> None:
        """
        Initialize file-based queue adapter.
        
        Args:
            queue_name: Name of the queue
            storage_file: Path to JSON file for storage. Defaults to ~/.qubot/queue.json
        """
        self.queue_name = queue_name
        
        if storage_file is None:
            storage_dir = Path.home() / ".qubot"
            storage_dir.mkdir(exist_ok=True)
            storage_file = storage_dir / "queue.json"
        
        self.storage_file = Path(storage_file)
        self._lock_file = self.storage_file.with_suffix('.lock')
        self._lock = None

    def _acquire_lock(self):
        """Simple file-based lock."""
        self._lock = open(self._lock_file, 'w', encoding='utf-8')
        fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX)

    def _release_lock(self):
        """Release file-based lock."""
        if self._lock is not None:
            try:
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_UN)
            except (OSError, ValueError):
                pass
            finally:
                self._lock.close()
                self._lock = None

    def _load_queue(self) -> List[Dict[str, Any]]:
        """Load queue from disk."""
        if not self.storage_file.exists():
            return []
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_queue(self, queue: List[Dict[str, Any]]) -> None:
        """Save queue to disk."""
        try:
            # Create parent directory if it doesn't exist
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save queue: {e}") from e

    def enqueue(self, message_instance: EventMessage, delay_seconds: int = 0) -> None:
        """Add a message to the queue."""
        try:
            self._acquire_lock()
            queue = self._load_queue()

            # Serialize the message with full module path
            # Format: module.ClassName(arg1=val1, arg2=val2, ...)
            class_name = message_instance.__class__.__name__
            module_name = message_instance.__class__.__module__
            full_class_path = f"{module_name}.{class_name}"

            # Get the arguments from the message instance
            if hasattr(message_instance, 'model_dump'):
                args_dict = message_instance.model_dump()
            else:
                args_dict = message_instance.__dict__
            
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in args_dict.items())
            message_str = f"{full_class_path}({args_str})"

            queue.append({
                "id": str(uuid.uuid4()),
                "message": message_str,
                "delay_until": time.time() + delay_seconds,
                "queue_name": self.queue_name
            })

            self._save_queue(queue)
        finally:
            self._release_lock()

    def dequeue(self, message_instance: Any) -> None:
        """Remove a message from the queue."""
        try:
            self._acquire_lock()
            queue = self._load_queue()

            # Find and remove the message
            # Try to get the message string from the QueueMessage wrapper
            if hasattr(message_instance, 'body'):
                message_str = message_instance.body
            elif hasattr(message_instance, '__repr__'):
                message_str = repr(message_instance)
            else:
                message_str = str(message_instance)
            
            queue[:] = [msg for msg in queue if msg.get("message") != message_str]

            self._save_queue(queue)
        finally:
            self._release_lock()

    def get_messages(self, *args: Any, **kwargs: Any) -> List[Any]:
        """Get messages from the queue."""
        try:
            self._acquire_lock()
            queue = self._load_queue()
            current_time = time.time()

            # Filter messages for this queue that are ready (delay has passed)
            ready_messages = [
                msg for msg in queue
                if msg.get("queue_name") == self.queue_name
                and msg.get("delay_until", 0) <= current_time
            ]

            # Return as message objects (the bus will parse them)
            class QueueMessage:
                def __init__(self, msg_data: Dict[str, Any]):
                    self.body = msg_data["message"]
                    self._data = msg_data

                def __repr__(self):
                    return self.body

            return [QueueMessage(msg) for msg in ready_messages]
        finally:
            self._release_lock()

