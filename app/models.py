"""
Pydantic models for request/response validation.
"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# E.164 phone number regex pattern
# Format: +[country code][number] (e.g., +14155552671)
E164_PATTERN = re.compile(r'^\+[1-9]\d{1,14}$')


class WebhookPayload(BaseModel):
    """
    Webhook payload model for incoming messages.
    
    Validates the JSON body structure and field constraints.
    Field aliases map API fields to database column names.
    """
    
    message_id: str = Field(
        ...,
        description="Unique message identifier"
    )
    
    from_msisdn: str = Field(
        ...,
        alias="from",
        description="Sender phone number in E.164 format"
    )
    
    to_msisdn: str = Field(
        ...,
        alias="to",
        description="Recipient phone number in E.164 format"
    )
    
    ts: str = Field(
        ...,
        description="Timestamp of the message"
    )
    
    text: Optional[str] = Field(
        default=None,
        max_length=4096,
        description="Message text content (optional, max 4096 characters)"
    )
    
    @field_validator("from_msisdn")
    @classmethod
    def validate_from_msisdn(cls, v: str) -> str:
        """Validate that 'from' field matches E.164 format."""
        if not E164_PATTERN.match(v):
            raise ValueError(
                f"'from' must be in E.164 format (e.g., +14155552671), got: {v}"
            )
        return v
    
    @field_validator("to_msisdn")
    @classmethod
    def validate_to_msisdn(cls, v: str) -> str:
        """Validate that 'to' field matches E.164 format."""
        if not E164_PATTERN.match(v):
            raise ValueError(
                f"'to' must be in E.164 format (e.g., +14155552671), got: {v}"
            )
        return v
    
    model_config = {
        "populate_by_name": True,  # Allow using both field name and alias
        "json_schema_extra": {
            "examples": [
                {
                    "message_id": "msg_123456",
                    "from": "+14155552671",
                    "to": "+14155552672",
                    "ts": "2025-12-07T10:30:00Z",
                    "text": "Hello, World!"
                }
            ]
        }
    }


class MessageResponse(BaseModel):
    """
    Response model for GET /messages endpoint.
    
    Returns stored message data with database column names.
    """
    
    message_id: str = Field(
        ...,
        description="Unique message identifier"
    )
    
    from_msisdn: str = Field(
        ...,
        description="Sender phone number in E.164 format"
    )
    
    to_msisdn: str = Field(
        ...,
        description="Recipient phone number in E.164 format"
    )
    
    ts: str = Field(
        ...,
        description="Timestamp of the message"
    )
    
    text: Optional[str] = Field(
        default=None,
        description="Message text content"
    )
    
    created_at: str = Field(
        ...,
        description="Timestamp when the message was stored in the database"
    )
    
    model_config = {
        "from_attributes": True,  # Enable ORM mode for SQLAlchemy models
        "json_schema_extra": {
            "examples": [
                {
                    "message_id": "msg_123456",
                    "from_msisdn": "+14155552671",
                    "to_msisdn": "+14155552672",
                    "ts": "2025-12-07T10:30:00Z",
                    "text": "Hello, World!",
                    "created_at": "2025-12-07T10:30:05Z"
                }
            ]
        }
    }


class StatsResponse(BaseModel):
    """
    Response model for GET /stats endpoint.
    
    Returns aggregate statistics about stored messages.
    """
    
    total_messages: int = Field(
        ...,
        description="Total number of messages stored"
    )
    
    senders_count: int = Field(
        ...,
        description="Number of unique sender phone numbers"
    )
    
    messages_per_sender: list[dict] = Field(
        ...,
        description="Top 10 senders with message counts"
    )
    
    first_message_ts: Optional[str] = Field(
        default=None,
        description="Timestamp of the first message"
    )
    
    last_message_ts: Optional[str] = Field(
        default=None,
        description="Timestamp of the last message"
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_messages": 150,
                    "senders_count": 25,
                    "messages_per_sender": [
                        {"from_msisdn": "+14155552671", "count": 45},
                        {"from_msisdn": "+14155552672", "count": 32}
                    ],
                    "first_message_ts": "2025-12-01T10:30:00Z",
                    "last_message_ts": "2025-12-07T15:45:00Z"
                }
            ]
        }
    }
