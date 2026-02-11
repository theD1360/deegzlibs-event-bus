"""Tests for file-based response store."""

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from event_bus.adapters import FileResponseStore


def test_file_response_store_set_get():
    """Test basic set and get operations."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        # Test storing and retrieving a dict
        store.set("key1", {"test": "value"}, ttl_seconds=60)
        result = store.get("key1")
        assert result == {"test": "value"}

        # Test storing a string
        store.set("key2", "simple string", ttl_seconds=60)
        assert store.get("key2") == "simple string"

        # Test storing a number
        store.set("key3", 42, ttl_seconds=60)
        assert store.get("key3") == 42


def test_file_response_store_delete():
    """Test delete operation."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        store.set("key1", {"data": "value"}, ttl_seconds=60)
        assert store.get("key1") is not None

        store.delete("key1")
        assert store.get("key1") is None


def test_file_response_store_ttl_expiry():
    """Test that entries expire after TTL."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        # Set with very short TTL
        store.set("key1", {"data": "value"}, ttl_seconds=0.1)
        assert store.get("key1") is not None

        # Wait for expiry
        time.sleep(0.2)
        assert store.get("key1") is None


def test_file_response_store_default_ttl():
    """Test default TTL behavior."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        # Set with 0 TTL (should use default)
        store.set("key1", {"data": "value"}, ttl_seconds=0)
        # Should still be available immediately
        assert store.get("key1") is not None


def test_file_response_store_persistence():
    """Test that data persists across store instances."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"

        # Create store, set value, close
        store1 = FileResponseStore(storage_file=store_file)
        store1.set("key1", {"data": "persisted"}, ttl_seconds=3600)
        del store1

        # Create new store instance, should see the value
        store2 = FileResponseStore(storage_file=store_file)
        result = store2.get("key1")
        assert result == {"data": "persisted"}


def test_file_response_store_nonexistent_key():
    """Test getting a non-existent key returns None."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        assert store.get("nonexistent") is None


def test_file_response_store_overwrite():
    """Test that setting the same key overwrites the value."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        store.set("key1", {"old": "value"}, ttl_seconds=60)
        store.set("key1", {"new": "value"}, ttl_seconds=60)

        result = store.get("key1")
        assert result == {"new": "value"}


def test_file_response_store_json_serialization():
    """Test that complex objects are properly serialized/deserialized."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        complex_data = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "number": 42.5,
            "bool": True,
            "null": None,
        }

        store.set("complex", complex_data, ttl_seconds=60)
        result = store.get("complex")
        assert result == complex_data


def test_file_response_store_default_storage_location():
    """Test that default storage location is created."""
    store = FileResponseStore()
    # Should not raise an error
    assert store.storage_file is not None
    assert store.storage_file.parent.exists() or store.storage_file.parent == Path.home() / ".qubot"


def test_file_response_store_multiple_keys():
    """Test storing and retrieving multiple keys."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        store.set("key1", "value1", ttl_seconds=60)
        store.set("key2", "value2", ttl_seconds=60)
        store.set("key3", "value3", ttl_seconds=60)

        assert store.get("key1") == "value1"
        assert store.get("key2") == "value2"
        assert store.get("key3") == "value3"


def test_file_response_store_expired_cleanup():
    """Test that expired entries are removed from storage."""
    with TemporaryDirectory() as tmpdir:
        store_file = Path(tmpdir) / "responses.json"
        store = FileResponseStore(storage_file=store_file)

        # Set with short TTL
        store.set("key1", "value1", ttl_seconds=0.1)
        store.set("key2", "value2", ttl_seconds=60)  # Long TTL

        # Wait for key1 to expire
        time.sleep(0.2)

        # Access key1 (should trigger cleanup)
        assert store.get("key1") is None

        # key2 should still exist
        assert store.get("key2") == "value2"

        # Verify key1 was removed from file
        with open(store_file, 'r') as f:
            data = json.load(f)
            assert "key1" not in data
            assert "key2" in data

