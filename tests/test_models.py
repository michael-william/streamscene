"""Tests for SQLAlchemy models."""

import pytest
from uuid import UUID

from streamscene.core.models import User, Stream, Post, StreamSubscription, Device


def test_user_creation(session):
    """Test creating a user."""
    user = User(authentik_user_id="test-user-789")
    session.add(user)
    session.commit()

    assert user.id is not None
    assert isinstance(user.id, UUID)
    assert user.authentik_user_id == "test-user-789"
    assert user.created_at is not None
    assert user.updated_at is not None


def test_stream_creation(session, sample_user):
    """Test creating a stream."""
    stream = Stream(
        owner_id=sample_user.id,
        name="My Stream",
        description="Test description",
        is_public=True,
        allow_text=True,
        allow_images=False,
    )
    session.add(stream)
    session.commit()

    assert stream.id is not None
    assert isinstance(stream.id, UUID)
    assert stream.owner_id == sample_user.id
    assert stream.name == "My Stream"
    assert stream.is_public is True
    assert stream.allow_text is True
    assert stream.allow_images is False


def test_post_creation(session, sample_stream, sample_user):
    """Test creating a post."""
    post = Post(
        stream_id=sample_stream.id,
        author_id=sample_user.id,
        content_type="text",
        text_content="Hello, world!",
    )
    session.add(post)
    session.commit()

    assert post.id is not None
    assert isinstance(post.id, UUID)
    assert post.stream_id == sample_stream.id
    assert post.author_id == sample_user.id
    assert post.text_content == "Hello, world!"


def test_stream_subscription(session, sample_user, sample_user2, sample_stream):
    """Test creating a stream subscription."""
    subscription = StreamSubscription(
        user_id=sample_user2.id,
        stream_id=sample_stream.id,
        is_approved=True,
    )
    session.add(subscription)
    session.commit()

    assert subscription.id is not None
    assert subscription.user_id == sample_user2.id
    assert subscription.stream_id == sample_stream.id
    assert subscription.is_approved is True


def test_unique_subscription_constraint(session, sample_user, sample_stream):
    """Test that duplicate subscriptions are prevented."""
    # Create first subscription
    sub1 = StreamSubscription(
        user_id=sample_user.id,
        stream_id=sample_stream.id,
    )
    session.add(sub1)
    session.commit()

    # Try to create duplicate subscription
    sub2 = StreamSubscription(
        user_id=sample_user.id,
        stream_id=sample_stream.id,
    )
    session.add(sub2)

    with pytest.raises(Exception):  # Should raise IntegrityError
        session.commit()


def test_cascade_delete_stream(session, sample_stream, sample_post):
    """Test that deleting a stream cascades to posts."""
    stream_id = sample_stream.id
    post_id = sample_post.id

    # Delete the stream
    session.delete(sample_stream)
    session.commit()

    # Post should also be deleted
    post = session.query(Post).filter(Post.id == post_id).first()
    assert post is None


def test_stream_relationships(session, sample_stream, sample_user):
    """Test stream relationships."""
    # Refresh to load relationships
    session.refresh(sample_stream)

    assert sample_stream.owner == sample_user
    assert sample_stream.owner.id == sample_user.id


def test_device_creation(session, sample_user):
    """Test creating a device."""
    from uuid import uuid4

    device_uuid = uuid4()
    device = Device(
        device_uuid=device_uuid,
        user_id=sample_user.id,
        nickname="Living Room Frame",
        rotation_enabled=True,
        rotation_interval=90,
    )
    session.add(device)
    session.commit()

    assert device.id is not None
    assert device.device_uuid == device_uuid
    assert device.user_id == sample_user.id
    assert device.nickname == "Living Room Frame"
    assert device.rotation_interval == 90
