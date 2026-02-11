"""File-based response store for persistent cross-process request/response."""

import fcntl
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ...interfaces import ResponseStore


class FileResponseStore(ResponseStore):
    """File-based response store that persists to disk for cross-process access."""

    def __init__(self, storage_file: Optional[Path] = None) -> None:
        """
        Initialize file-based response store.
        
        Args:
            storage_file: Path to JSON file for storage. Defaults to ~/.qubot/responses.json
        """
        if storage_file is None:
            storage_dir = Path.home() / ".qubot"
            storage_dir.mkdir(exist_ok=True)
            storage_file = storage_dir / "responses.json"
        
        self.storage_file = Path(storage_file)
        self._lock_file = self.storage_file.with_suffix('.lock')
        self._lock = None

    def _acquire_lock(self):
        """Acquire file-based lock."""
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

    def _load_store(self) -> Dict[str, Dict[str, Any]]:
        """Load store from disk."""
        if not self.storage_file.exists():
            return {}
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_store(self, store: Dict[str, Dict[str, Any]]) -> None:
        """Save store to disk."""
        try:
            # Create parent directory if it doesn't exist
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(store, f, indent=2)
        except Exception as e:
            raise RuntimeError(f"Failed to save response store: {e}") from e

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Store a response value with optional TTL."""
        try:
            self._acquire_lock()
            store = self._load_store()
            
            # Serialize value to JSON string
            if not isinstance(value, str):
                value_str = json.dumps(value)
            else:
                value_str = value
            
            # Use default TTL if 0 is provided (matching interface behavior)
            ttl = ttl_seconds if ttl_seconds > 0 else 3600
            expiry = time.time() + ttl
            
            store[key] = {
                "value": value_str,
                "expiry": expiry
            }
            
            self._save_store(store)
        finally:
            self._release_lock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a response value if it exists and hasn't expired."""
        try:
            self._acquire_lock()
            store = self._load_store()
            
            if key not in store:
                return None
            
            entry = store[key]
            value_str = entry.get("value")
            expiry = entry.get("expiry", 0)
            
            # Check if expired
            if time.time() > expiry:
                del store[key]
                self._save_store(store)
                return None
            
            # Try to deserialize JSON, return as-is if it fails
            try:
                return json.loads(value_str)
            except (json.JSONDecodeError, TypeError):
                return value_str
        finally:
            self._release_lock()

    def delete(self, key: str) -> None:
        """Delete a response value."""
        try:
            self._acquire_lock()
            store = self._load_store()
            if key in store:
                del store[key]
                self._save_store(store)
        finally:
            self._release_lock()

