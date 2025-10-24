"""
Validation tests for Event models
"""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from src.models import Event, EventBatch


def test_valid_event():
    """Test creating a valid event"""
    event = Event(
        topic="test.topic",
        event_id="evt-123",
        timestamp=datetime.now(timezone.utc),
        source="test-service",
        payload={"key": "value"}
    )
    
    assert event.topic == "test.topic"
    assert event.event_id == "evt-123"
    assert event.source == "test-service"


def test_event_missing_required_field():
    """Test that missing required fields raise validation error"""
    with pytest.raises(ValidationError):
        Event(
            topic="test",
            # Missing event_id
            timestamp=datetime.now(timezone.utc),
            source="test",
            payload={}
        )


def test_event_empty_string_fields():
    """Test that empty strings are rejected"""
    with pytest.raises(ValidationError):
        Event(
            topic="",  # Empty topic
            event_id="evt-123",
            timestamp=datetime.now(timezone.utc),
            source="test",
            payload={}
        )


def test_event_whitespace_only_fields():
    """Test that whitespace-only strings are rejected"""
    with pytest.raises(ValidationError):
        Event(
            topic="   ",  # Whitespace only
            event_id="evt-123",
            timestamp=datetime.now(timezone.utc),
            source="test",
            payload={}
        )


def test_event_timestamp_validation():
    """Test timestamp field accepts datetime objects"""
    event = Event(
        topic="test",
        event_id="evt-123",
        timestamp=datetime.now(timezone.utc),
        source="test",
        payload={}
    )
    
    assert isinstance(event.timestamp, datetime)


def test_event_payload_accepts_dict():
    """Test that payload accepts dictionary"""
    payload = {
        "user_id": "user-123",
        "action": "login",
        "nested": {"data": "value"}
    }
    
    event = Event(
        topic="test",
        event_id="evt-123",
        timestamp=datetime.now(timezone.utc),
        source="test",
        payload=payload
    )
    
    assert event.payload == payload


def test_event_batch_valid():
    """Test creating a valid event batch"""
    events = [
        Event(
            topic="test",
            event_id=f"evt-{i}",
            timestamp=datetime.now(timezone.utc),
            source="test",
            payload={"index": i}
        )
        for i in range(3)
    ]
    
    batch = EventBatch(events=events)
    assert len(batch.events) == 3


def test_event_batch_empty_rejected():
    """Test that empty batch is rejected"""
    with pytest.raises(ValidationError):
        EventBatch(events=[])
