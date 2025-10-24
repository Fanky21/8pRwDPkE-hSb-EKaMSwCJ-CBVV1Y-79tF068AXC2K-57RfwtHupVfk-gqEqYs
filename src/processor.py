"""
Event processor with in-memory queue and async consumer
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from src.models import Event
from src.dedup_store import DedupStore

logger = logging.getLogger(__name__)


class EventProcessor:
    """
    Processes events from in-memory queue with deduplication
    Implements at-least-once delivery semantics
    """
    
    def __init__(self, dedup_store: DedupStore):
        self.dedup_store = dedup_store
        self.queue: asyncio.Queue = asyncio.Queue()
        self.processed_events: List[Event] = []
        self.stats = {
            "received": 0,
            "unique_processed": 0,
            "duplicate_dropped": 0
        }
        self.consumer_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the consumer task"""
        if self._running:
            logger.warning("Consumer already running")
            return
            
        self._running = True
        self.consumer_task = asyncio.create_task(self._consumer_loop())
        logger.info("Event processor started")
        
    async def stop(self):
        """Stop the consumer task gracefully"""
        self._running = False
        if self.consumer_task:
            # Wait for queue to be empty
            await self.queue.join()
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("Event processor stopped")
        
    async def publish(self, events: List[Event]) -> dict:
        """
        Publish events to the queue
        Returns statistics about received/processed/duplicates
        """
        received = len(events)
        self.stats["received"] += received
        
        # Add all events to queue for processing
        for event in events:
            await self.queue.put(event)
            
        logger.info(f"Published {received} events to queue")
        
        return {
            "received": received
        }
        
    async def _consumer_loop(self):
        """
        Consumer loop that processes events from queue
        Implements deduplication logic
        """
        logger.info("Consumer loop started")
        
        while self._running:
            try:
                # Get event from queue with timeout
                event = await asyncio.wait_for(
                    self.queue.get(), 
                    timeout=1.0
                )
                
                await self._process_event(event)
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                # No event in queue, continue
                continue
            except asyncio.CancelledError:
                logger.info("Consumer loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                
    async def _process_event(self, event: Event):
        """
        Process a single event with deduplication
        """
        topic = event.topic
        event_id = event.event_id
        timestamp = event.timestamp.isoformat()
        
        # Check for duplicate and mark as processed atomically
        is_new = await self.dedup_store.mark_processed(topic, event_id, timestamp)
        
        if is_new:
            # New event - process it
            self.stats["unique_processed"] += 1
            self.processed_events.append(event)
            logger.info(f"Processed new event: topic={topic}, event_id={event_id}")
        else:
            # Duplicate event - drop it
            self.stats["duplicate_dropped"] += 1
            logger.warning(f"Dropped duplicate event: topic={topic}, event_id={event_id}")
            
    def get_stats(self) -> dict:
        """Get current statistics"""
        return self.stats.copy()
        
    def get_events(self, topic: Optional[str] = None) -> List[Event]:
        """
        Get processed events, optionally filtered by topic
        """
        if topic:
            return [e for e in self.processed_events if e.topic == topic]
        return self.processed_events.copy()
        
    def get_unique_topics(self) -> List[str]:
        """Get list of unique topics from processed events"""
        topics = set(e.topic for e in self.processed_events)
        return sorted(list(topics))
