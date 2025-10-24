"""
Event models and validation schemas
"""
from datetime import datetime
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, field_validator


class Event(BaseModel):
    """
    Event model with required fields according to specification
    """
    topic: str = Field(..., min_length=1, description="Event topic")
    event_id: str = Field(..., min_length=1, description="Unique event identifier")
    timestamp: datetime = Field(..., description="Event timestamp in ISO8601 format")
    source: str = Field(..., min_length=1, description="Event source identifier")
    payload: Dict[str, Any] = Field(..., description="Event payload data")

    @field_validator('topic', 'event_id', 'source')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure string fields are not empty or whitespace only"""
        if not v or not v.strip():
            raise ValueError('Field cannot be empty or whitespace only')
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "user.created",
                "event_id": "evt-12345",
                "timestamp": "2025-10-24T10:30:00Z",
                "source": "auth-service",
                "payload": {
                    "user_id": "user-123",
                    "email": "user@example.com"
                }
            }
        }


class EventBatch(BaseModel):
    """
    Batch of events for bulk publishing
    """
    events: List[Event] = Field(..., min_length=1, description="List of events")


class EventResponse(BaseModel):
    """
    Response for published events
    """
    received: int
    unique_processed: int
    duplicate_dropped: int
    message: str


class StatsResponse(BaseModel):
    """
    Statistics about the aggregator service
    """
    received: int = Field(..., description="Total events received")
    unique_processed: int = Field(..., description="Unique events processed")
    duplicate_dropped: int = Field(..., description="Duplicate events dropped")
    topics: List[str] = Field(..., description="List of unique topics")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")


class EventQueryResponse(BaseModel):
    """
    Response for event queries
    """
    topic: Optional[str] = None
    count: int
    events: List[Event]
