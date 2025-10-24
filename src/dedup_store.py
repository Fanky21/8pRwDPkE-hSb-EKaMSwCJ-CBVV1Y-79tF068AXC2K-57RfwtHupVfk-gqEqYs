"""
Persistent deduplication store using SQLite
Ensures idempotency and survives service restarts
"""
import logging
import aiosqlite
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DedupStore:
    """
    Persistent key-value store for deduplication
    Uses SQLite to maintain state across restarts
    """
    
    def __init__(self, db_path: str = "data/dedup.db"):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None
        
    async def initialize(self):
        """Initialize database and create table if not exists"""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                topic TEXT NOT NULL,
                event_id TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                PRIMARY KEY (topic, event_id)
            )
        """)
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_topic 
            ON processed_events(topic)
        """)
        await self.db.commit()
        logger.info(f"Dedup store initialized at {self.db_path}")
        
    async def is_duplicate(self, topic: str, event_id: str) -> bool:
        """
        Check if event has been processed before
        Returns True if event is a duplicate
        """
        if not self.db:
            raise RuntimeError("DedupStore not initialized")
            
        cursor = await self.db.execute(
            "SELECT 1 FROM processed_events WHERE topic = ? AND event_id = ?",
            (topic, event_id)
        )
        result = await cursor.fetchone()
        return result is not None
        
    async def mark_processed(self, topic: str, event_id: str, timestamp: str) -> bool:
        """
        Mark event as processed
        Returns True if successfully marked (was not duplicate)
        Returns False if already existed (was duplicate)
        """
        if not self.db:
            raise RuntimeError("DedupStore not initialized")
            
        try:
            await self.db.execute(
                """INSERT INTO processed_events (topic, event_id, first_seen_at) 
                   VALUES (?, ?, ?)""",
                (topic, event_id, timestamp)
            )
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Primary key violation - event already exists
            logger.debug(f"Duplicate event detected: topic={topic}, event_id={event_id}")
            return False
            
    async def get_unique_topics(self) -> list[str]:
        """Get list of all unique topics that have been processed"""
        if not self.db:
            raise RuntimeError("DedupStore not initialized")
            
        cursor = await self.db.execute(
            "SELECT DISTINCT topic FROM processed_events ORDER BY topic"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
        
    async def count_processed(self, topic: Optional[str] = None) -> int:
        """Count total processed events, optionally filtered by topic"""
        if not self.db:
            raise RuntimeError("DedupStore not initialized")
            
        if topic:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM processed_events WHERE topic = ?",
                (topic,)
            )
        else:
            cursor = await self.db.execute(
                "SELECT COUNT(*) FROM processed_events"
            )
        result = await cursor.fetchone()
        return result[0] if result else 0
        
    async def close(self):
        """Close database connection"""
        if self.db:
            await self.db.close()
            logger.info("Dedup store closed")
