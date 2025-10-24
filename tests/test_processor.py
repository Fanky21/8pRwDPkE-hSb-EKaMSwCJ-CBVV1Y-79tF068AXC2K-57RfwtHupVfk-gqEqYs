"""
Unit tests for EventProcessor
"""
import pytest
import asyncio
from datetime import datetime, timezone
from src.models import Event


def create_test_event(topic: str, event_id: str) -> Event:
    """Helper to create test events"""
    return Event(
        topic=topic,
        event_id=event_id,
        timestamp=datetime.now(timezone.utc),
        source="test-source",
        payload={"test": "data"}
    )


@pytest.mark.asyncio
async def test_processor_publish_single_event(event_processor):
    """Test publishing a single event"""
    event = create_test_event("test.topic", "evt-001")
    result = await event_processor.publish([event])
    
    assert result["received"] == 1
    
    # Give processor time to process
    await asyncio.sleep(0.5)
    
    stats = event_processor.get_stats()
    assert stats["received"] == 1
    assert stats["unique_processed"] == 1
    assert stats["duplicate_dropped"] == 0


@pytest.mark.asyncio
async def test_processor_duplicate_detection(event_processor):
    """Test that processor correctly detects and drops duplicates"""
    event1 = create_test_event("test.topic", "evt-001")
    event2 = create_test_event("test.topic", "evt-001")  # Same ID - duplicate
    
    await event_processor.publish([event1])
    await asyncio.sleep(0.5)
    
    await event_processor.publish([event2])
    await asyncio.sleep(0.5)
    
    stats = event_processor.get_stats()
    assert stats["received"] == 2
    assert stats["unique_processed"] == 1
    assert stats["duplicate_dropped"] == 1


@pytest.mark.asyncio
async def test_processor_batch_events(event_processor):
    """Test processing batch of events"""
    events = [
        create_test_event("topic1", f"evt-{i}")
        for i in range(10)
    ]
    
    await event_processor.publish(events)
    await asyncio.sleep(1)
    
    stats = event_processor.get_stats()
    assert stats["received"] == 10
    assert stats["unique_processed"] == 10
    assert stats["duplicate_dropped"] == 0


@pytest.mark.asyncio
async def test_processor_mixed_unique_and_duplicates(event_processor):
    """Test processing mix of unique and duplicate events"""
    events = [
        create_test_event("topic1", "evt-001"),
        create_test_event("topic1", "evt-002"),
        create_test_event("topic1", "evt-001"),  # Duplicate
        create_test_event("topic1", "evt-003"),
        create_test_event("topic1", "evt-002"),  # Duplicate
    ]
    
    await event_processor.publish(events)
    await asyncio.sleep(1)
    
    stats = event_processor.get_stats()
    assert stats["received"] == 5
    assert stats["unique_processed"] == 3
    assert stats["duplicate_dropped"] == 2


@pytest.mark.asyncio
async def test_get_events_all(event_processor):
    """Test retrieving all processed events"""
    events = [
        create_test_event("topic1", "evt-001"),
        create_test_event("topic2", "evt-002"),
    ]
    
    await event_processor.publish(events)
    await asyncio.sleep(0.5)
    
    retrieved = event_processor.get_events()
    assert len(retrieved) == 2


@pytest.mark.asyncio
async def test_get_events_by_topic(event_processor):
    """Test retrieving events filtered by topic"""
    events = [
        create_test_event("topic1", "evt-001"),
        create_test_event("topic1", "evt-002"),
        create_test_event("topic2", "evt-003"),
    ]
    
    await event_processor.publish(events)
    await asyncio.sleep(0.5)
    
    topic1_events = event_processor.get_events(topic="topic1")
    assert len(topic1_events) == 2
    
    topic2_events = event_processor.get_events(topic="topic2")
    assert len(topic2_events) == 1


@pytest.mark.asyncio
async def test_processor_persistence_simulation(temp_db_path):
    """Test that after restart, duplicates are still prevented"""
    from src.dedup_store import DedupStore
    from src.processor import EventProcessor
    
    event = create_test_event("test.topic", "evt-persistent")
    
    # First processor instance
    store1 = DedupStore(db_path=temp_db_path)
    await store1.initialize()
    processor1 = EventProcessor(store1)
    await processor1.start()
    
    await processor1.publish([event])
    await asyncio.sleep(0.5)
    
    stats1 = processor1.get_stats()
    assert stats1["unique_processed"] == 1
    
    await processor1.stop()
    await store1.close()
    
    # Second processor instance (simulating restart)
    store2 = DedupStore(db_path=temp_db_path)
    await store2.initialize()
    processor2 = EventProcessor(store2)
    await processor2.start()
    
    # Try to process same event again
    await processor2.publish([event])
    await asyncio.sleep(0.5)
    
    stats2 = processor2.get_stats()
    # New processor instance, so received=1, but should be duplicate
    assert stats2["received"] == 1
    assert stats2["unique_processed"] == 0
    assert stats2["duplicate_dropped"] == 1
    
    await processor2.stop()
    await store2.close()
