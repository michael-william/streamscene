"""SQLAlchemy ORM models for StreamScene."""

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped

from .database import Base


def utc_now():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    """
    User model - Minimal local representation.
    Authentik is the single source of truth for user data.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    authentik_user_id: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)

    # Display information (cached from Authentik for performance)
    email: Mapped[str] = Column(String(255), nullable=True, index=True)
    username: Mapped[str] = Column(String(255), nullable=True)
    name: Mapped[str] = Column(String(255), nullable=True)
    profile_picture: Mapped[str] = Column(String(500), nullable=True)  # Relative path to profile image

    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    owned_streams: Mapped[List["Stream"]] = relationship("Stream", back_populates="owner", cascade="all, delete-orphan")
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    subscriptions: Mapped[List["StreamSubscription"]] = relationship(
        "StreamSubscription", back_populates="user", cascade="all, delete-orphan"
    )
    devices: Mapped[List["Device"]] = relationship("Device", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        display = self.email or self.username or self.authentik_user_id
        return f"<User(id={self.id}, display={display})>"


class Stream(Base):
    """Stream model - Shared message channels."""

    __tablename__ = "streams"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = Column(String(100), nullable=False)
    slug: Mapped[str] = Column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str] = Column(Text, default="", nullable=False)
    is_public: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    allow_text: Mapped[bool] = Column(Boolean, default=True, nullable=False)
    allow_images: Mapped[bool] = Column(Boolean, default=False, nullable=False)  # MVP: False
    show_history: Mapped[bool] = Column(Boolean, default=True, nullable=False)
    max_history_items: Mapped[int] = Column(Integer, default=50, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint('owner_id', 'name', name='uq_owner_stream_name'),
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="owned_streams")
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="stream", cascade="all, delete-orphan")
    subscriptions: Mapped[List["StreamSubscription"]] = relationship(
        "StreamSubscription", back_populates="stream", cascade="all, delete-orphan"
    )
    device_settings: Mapped[List["DeviceStreamSettings"]] = relationship(
        "DeviceStreamSettings", back_populates="stream", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Stream(id={self.id}, name={self.name}, owner_id={self.owner_id})>"


class Post(Base):
    """Post model - Messages posted to streams."""

    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stream_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete=("CASCADE")), nullable=False, index=True
    )
    content_type: Mapped[str] = Column(String(20), default="text", nullable=False)  # 'text', 'image', 'mixed'
    text_content: Mapped[str] = Column(Text, nullable=True)
    image_path: Mapped[str] = Column(String(500), nullable=True)  # Defer to Phase 5
    processed_image_path: Mapped[str] = Column(String(500), nullable=True)  # Defer to Phase 5
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    stream: Mapped["Stream"] = relationship("Stream", back_populates="posts")
    author: Mapped["User"] = relationship("User", back_populates="posts")

    # Composite index for efficient queries
    __table_args__ = (
        Index("idx_posts_stream_created", "stream_id", "created_at"),
        Index("idx_posts_author_created", "author_id", "created_at"),
    )

    def __repr__(self):
        return f"<Post(id={self.id}, stream_id={self.stream_id}, author_id={self.author_id})>"


class StreamSubscription(Base):
    """StreamSubscription model - Many-to-many relationship between users and streams."""

    __tablename__ = "stream_subscriptions"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stream_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_approved: Mapped[bool] = Column(Boolean, default=True, nullable=False)  # For private streams
    subscribed_at: Mapped[datetime] = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    stream: Mapped["Stream"] = relationship("Stream", back_populates="subscriptions")

    # Unique constraint: a user can only subscribe once to a stream
    __table_args__ = (
        UniqueConstraint("user_id", "stream_id", name="uq_user_stream"),
        Index("idx_stream_subs", "user_id", "stream_id"),
    )

    def __repr__(self):
        return f"<StreamSubscription(user_id={self.user_id}, stream_id={self.stream_id})>"


class Device(Base):
    """Device model - Raspberry Pi E Ink devices."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    device_uuid: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )  # Pre-configured on SD card
    user_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )  # Null until registered
    nickname: Mapped[str] = Column(String(100), default="My StreamScene Frame", nullable=False)
    api_key_hash: Mapped[str] = Column(String(255), nullable=True)  # Bcrypt hashed
    current_version: Mapped[str] = Column(String(50), default="1.0.0", nullable=False)
    last_seen: Mapped[datetime] = Column(DateTime(timezone=True), nullable=True)
    current_stream_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("streams.id", ondelete="SET NULL"), nullable=True
    )
    rotation_enabled: Mapped[bool] = Column(Boolean, default=False, nullable=False)
    rotation_interval: Mapped[int] = Column(Integer, default=60, nullable=False)  # Seconds, minimum 60
    registered_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=True)
    config: Mapped[dict] = Column(JSON, default=dict, nullable=False)  # Additional device configuration

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="devices")
    stream_settings: Mapped[List["DeviceStreamSettings"]] = relationship(
        "DeviceStreamSettings", back_populates="device", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Device(id={self.id}, device_uuid={self.device_uuid}, user_id={self.user_id})>"


class DeviceStreamSettings(Base):
    """DeviceStreamSettings model - Per-device stream display configuration."""

    __tablename__ = "device_stream_settings"

    id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    device_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stream_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True), ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True
    )
    display_order: Mapped[int] = Column(Integer, default=0, nullable=False)  # Order in rotation
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False)  # Include in rotation

    # Relationships
    device: Mapped["Device"] = relationship("Device", back_populates="stream_settings")
    stream: Mapped["Stream"] = relationship("Stream", back_populates="device_settings")

    __table_args__ = (Index("idx_device_stream_settings", "device_id", "stream_id"),)

    def __repr__(self):
        return f"<DeviceStreamSettings(device_id={self.device_id}, stream_id={self.stream_id}, order={self.display_order})>"
