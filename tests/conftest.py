"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path

from src.dedup_store import DedupStore
from src.processor import EventProcessor


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_dedup.db"
    yield str(db_path)
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
async def dedup_store(temp_db_path):
    """Create a fresh dedup store for each test"""
    store = DedupStore(db_path=temp_db_path)
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
async def event_processor(dedup_store):
    """Create an event processor with dedup store"""
    processor = EventProcessor(dedup_store)
    await processor.start()
    yield processor
    await processor.stop()


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for Windows compatibility"""
    if hasattr(asyncio, 'WindowsSelectorEventLoopPolicy'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
