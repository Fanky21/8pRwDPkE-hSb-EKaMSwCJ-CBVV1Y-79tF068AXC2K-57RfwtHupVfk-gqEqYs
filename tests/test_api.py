"""
Integration tests for FastAPI endpoints
"""
import pytest
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test health check endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Event Aggregator"
        assert data["status"] == "running"


@pytest.mark.asyncio
async def test_publish_single_event():
    """Test publishing a single event"""
    event = {
        "topic": "test.event",
        "event_id": "test-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "payload": {"data": "test"}
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/publish", json=event)
        assert response.status_code == 202
        data = response.json()
        assert data["received"] == 1


@pytest.mark.asyncio
async def test_publish_batch_events():
    """Test publishing batch of events"""
    events = {
        "events": [
            {
                "topic": "test.event",
                "event_id": f"test-{i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "test",
                "payload": {"index": i}
            }
            for i in range(5)
        ]
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/publish", json=events)
        assert response.status_code == 202
        data = response.json()
        assert data["received"] == 5


@pytest.mark.asyncio
async def test_invalid_event_schema():
    """Test that invalid events are rejected"""
    invalid_event = {
        "topic": "test",
        # Missing required fields
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/publish", json=invalid_event)
        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_events_endpoint():
    """Test retrieving processed events"""
    event = {
        "topic": "test.retrieve",
        "event_id": "retrieve-001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "payload": {"data": "test"}
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Publish event
        await client.post("/publish", json=event)
        await asyncio.sleep(0.5)
        
        # Retrieve events
        response = await client.get("/events")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1


@pytest.mark.asyncio
async def test_get_events_filtered_by_topic():
    """Test retrieving events filtered by topic"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Publish events to different topics
        await client.post("/publish", json={
            "topic": "topic.filter1",
            "event_id": "filter-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "test",
            "payload": {}
        })
        
        await client.post("/publish", json={
            "topic": "topic.filter2",
            "event_id": "filter-002",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "test",
            "payload": {}
        })
        
        await asyncio.sleep(0.5)
        
        # Get events for specific topic
        response = await client.get("/events?topic=topic.filter1")
        assert response.status_code == 200
        data = response.json()
        assert data["topic"] == "topic.filter1"


@pytest.mark.asyncio
async def test_stats_endpoint():
    """Test statistics endpoint"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields
        assert "received" in data
        assert "unique_processed" in data
        assert "duplicate_dropped" in data
        assert "topics" in data
        assert "uptime_seconds" in data
        assert isinstance(data["topics"], list)
        assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_stress_small_load():
    """Test small stress load - measure execution time"""
    import time
    
    events = {
        "events": [
            {
                "topic": "stress.test",
                "event_id": f"stress-{i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "stress-test",
                "payload": {"index": i}
            }
            for i in range(100)
        ]
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        start = time.time()
        response = await client.post("/publish", json=events)
        elapsed = time.time() - start
        
        assert response.status_code == 202
        assert elapsed < 5.0  # Should complete within 5 seconds
        
        # Wait for processing
        await asyncio.sleep(2)
        
        # Verify stats
        stats_response = await client.get("/stats")
        assert stats_response.status_code == 200
