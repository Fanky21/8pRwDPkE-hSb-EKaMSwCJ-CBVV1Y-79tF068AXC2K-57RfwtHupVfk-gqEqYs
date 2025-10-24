"""
FastAPI Event Aggregator Service
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional, Union

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse

from src.models import (
    Event,
    EventBatch,
    EventResponse,
    StatsResponse,
    EventQueryResponse
)
from src.dedup_store import DedupStore
from src.processor import EventProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state
dedup_store: Optional[DedupStore] = None
event_processor: Optional[EventProcessor] = None
start_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown
    """
    global dedup_store, event_processor, start_time
    
    # Startup
    logger.info("Starting Event Aggregator Service...")
    start_time = time.time()
    
    # Initialize dedup store
    dedup_store = DedupStore(db_path="data/dedup.db")
    await dedup_store.initialize()
    
    # Initialize event processor
    event_processor = EventProcessor(dedup_store)
    await event_processor.start()
    
    logger.info("Event Aggregator Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Event Aggregator Service...")
    
    if event_processor:
        await event_processor.stop()
    
    if dedup_store:
        await dedup_store.close()
    
    logger.info("Event Aggregator Service stopped")


# Create FastAPI app
app = FastAPI(
    title="Event Aggregator Service",
    description="Aggregator service with idempotency and deduplication",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Event Aggregator",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/publish", response_model=EventResponse, status_code=status.HTTP_202_ACCEPTED)
async def publish_events(data: Union[Event, EventBatch]):
    """
    Publish single event or batch of events
    
    Accepts:
    - Single Event object
    - EventBatch with array of events
    
    Returns statistics about received, processed, and duplicate events
    """
    if not event_processor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event processor not initialized"
        )
    
    # Normalize to list
    events: List[Event] = []
    if isinstance(data, Event):
        events = [data]
    else:
        events = data.events
    
    # Publish to processor
    result = await event_processor.publish(events)
    
    # Get current stats for response
    stats = event_processor.get_stats()
    
    return EventResponse(
        received=result["received"],
        unique_processed=stats["unique_processed"],
        duplicate_dropped=stats["duplicate_dropped"],
        message=f"Received {result['received']} event(s) for processing"
    )


@app.get("/events", response_model=EventQueryResponse)
async def get_events(topic: Optional[str] = None):
    """
    Get processed events, optionally filtered by topic
    
    Query Parameters:
    - topic: Filter events by topic (optional)
    
    Returns list of unique processed events
    """
    if not event_processor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event processor not initialized"
        )
    
    events = event_processor.get_events(topic=topic)
    
    return EventQueryResponse(
        topic=topic,
        count=len(events),
        events=events
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get aggregator statistics
    
    Returns:
    - received: Total events received
    - unique_processed: Unique events processed
    - duplicate_dropped: Duplicate events dropped
    - topics: List of unique topics
    - uptime_seconds: Service uptime
    """
    if not event_processor or not dedup_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized"
        )
    
    stats = event_processor.get_stats()
    topics = await dedup_store.get_unique_topics()
    uptime = time.time() - start_time
    
    return StatsResponse(
        received=stats["received"],
        unique_processed=stats["unique_processed"],
        duplicate_dropped=stats["duplicate_dropped"],
        topics=topics,
        uptime_seconds=uptime
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
