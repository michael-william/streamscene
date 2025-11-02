"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID


# ============================================================================
# DEVICE SCHEMAS
# ============================================================================


class DeviceRegisterRequest(BaseModel):
    """Request body for device registration."""

    device_uuid: UUID = Field(..., description="Pre-configured device UUID from SD card")
    nickname: Optional[str] = Field(None, description="Optional nickname for the device")


class DeviceRegisterResponse(BaseModel):
    """Response for successful device registration."""

    device_id: UUID = Field(..., description="Internal device ID")
    device_uuid: UUID = Field(..., description="Device UUID")
    api_key: str = Field(..., description="API key for device authentication (shown once)")
    nickname: str = Field(..., description="Device nickname")
    message: str = Field(..., description="Success message")


class DeviceContentResponse(BaseModel):
    """Response containing content to display on device."""

    content_type: str = Field(..., description="Content type: text, image, or mixed")
    text_content: Optional[str] = Field(None, description="Text content to display")
    image_url: Optional[str] = Field(None, description="URL to image to display")
    posted_at: datetime = Field(..., description="When the content was posted")
    stream_name: str = Field(..., description="Name of the stream")
    has_content: bool = Field(..., description="Whether there is content to display")


class DeviceConfigResponse(BaseModel):
    """Response containing device configuration."""

    device_id: UUID
    nickname: str
    current_stream_id: Optional[UUID]
    rotation_enabled: bool
    rotation_interval: int
    current_version: str
    config: dict


class DeviceHeartbeatResponse(BaseModel):
    """Response for device heartbeat."""

    status: str = Field(..., description="Status message")
    timestamp: datetime = Field(..., description="Server timestamp")


# ============================================================================
# STREAM SCHEMAS
# ============================================================================


class StreamResponse(BaseModel):
    """Response schema for stream information."""

    id: UUID
    name: str
    description: str
    owner_id: UUID
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PostResponse(BaseModel):
    """Response schema for post information."""

    id: UUID
    stream_id: UUID
    author_id: UUID
    content_type: str
    text_content: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
