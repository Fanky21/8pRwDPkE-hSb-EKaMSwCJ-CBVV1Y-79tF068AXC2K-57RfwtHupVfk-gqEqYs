"""
Unit tests for DedupStore
"""
import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_dedup_store_initialization(dedup_store):
    """Test that dedup store initializes correctly"""
    assert dedup_store is not None
    assert dedup_store.db is not None


@pytest.mark.asyncio
async def test_is_duplicate_new_event(dedup_store):
    """Test that a new event is not detected as duplicate"""
    is_dup = await dedup_store.is_duplicate("topic1", "event1")
    assert is_dup is False


@pytest.mark.asyncio
async def test_mark_processed_new_event(dedup_store):
    """Test marking a new event as processed"""
    timestamp = datetime.now(timezone.utc).isoformat()
    result = await dedup_store.mark_processed("topic1", "event1", timestamp)
    assert result is True
    
    # Verify it's now marked as duplicate
    is_dup = await dedup_store.is_duplicate("topic1", "event1")
    assert is_dup is True


@pytest.mark.asyncio
async def test_mark_processed_duplicate_event(dedup_store):
    """Test that duplicate events are detected and rejected"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Mark first time - should succeed
    result1 = await dedup_store.mark_processed("topic1", "event1", timestamp)
    assert result1 is True
    
    # Mark second time - should fail (duplicate)
    result2 = await dedup_store.mark_processed("topic1", "event1", timestamp)
    assert result2 is False


@pytest.mark.asyncio
async def test_different_topics_same_event_id(dedup_store):
    """Test that same event_id on different topics are treated as different events"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    result1 = await dedup_store.mark_processed("topic1", "event1", timestamp)
    assert result1 is True
    
    result2 = await dedup_store.mark_processed("topic2", "event1", timestamp)
    assert result2 is True


@pytest.mark.asyncio
async def test_get_unique_topics(dedup_store):
    """Test retrieving unique topics"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    await dedup_store.mark_processed("topic_a", "event1", timestamp)
    await dedup_store.mark_processed("topic_b", "event2", timestamp)
    await dedup_store.mark_processed("topic_a", "event3", timestamp)
    
    topics = await dedup_store.get_unique_topics()
    assert len(topics) == 2
    assert "topic_a" in topics
    assert "topic_b" in topics


@pytest.mark.asyncio
async def test_count_processed(dedup_store):
    """Test counting processed events"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    await dedup_store.mark_processed("topic1", "event1", timestamp)
    await dedup_store.mark_processed("topic1", "event2", timestamp)
    await dedup_store.mark_processed("topic2", "event3", timestamp)
    
    total_count = await dedup_store.count_processed()
    assert total_count == 3
    
    topic1_count = await dedup_store.count_processed(topic="topic1")
    assert topic1_count == 2
    
    topic2_count = await dedup_store.count_processed(topic="topic2")
    assert topic2_count == 1


@pytest.mark.asyncio
async def test_persistence_across_instances(temp_db_path):
    """Test that dedup store persists data across restarts"""
    from src.dedup_store import DedupStore
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # First instance - add data
    store1 = DedupStore(db_path=temp_db_path)
    await store1.initialize()
    await store1.mark_processed("topic1", "event1", timestamp)
    await store1.close()
    
    # Second instance - verify data persisted
    store2 = DedupStore(db_path=temp_db_path)
    await store2.initialize()
    is_dup = await store2.is_duplicate("topic1", "event1")
    assert is_dup is True
    
    count = await store2.count_processed()
    assert count == 1
    await store2.close()
