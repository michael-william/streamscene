"""Tests for stream, post, and subscription business logic."""

import pytest

from streamscene.core import streams
from streamscene.core.models import Stream, Post, StreamSubscription


# ============================================================================
# STREAM OPERATIONS TESTS
# ============================================================================


def test_create_stream(session, sample_user):
    """Test creating a stream."""
    stream = streams.create_stream(
        session,
        owner_id=sample_user.id,
        name="Test Stream",
        description="A test stream",
        is_public=True,
    )

    assert stream.id is not None
    assert stream.name == "Test Stream"
    assert stream.owner_id == sample_user.id
    assert stream.is_public is True


def test_get_stream_by_id(session, sample_stream):
    """Test retrieving a stream by ID."""
    stream = streams.get_stream_by_id(session, sample_stream.id)

    assert stream is not None
    assert stream.id == sample_stream.id
    assert stream.name == sample_stream.name


def test_get_stream_by_id_not_found(session):
    """Test retrieving a non-existent stream."""
    from uuid import uuid4

    stream = streams.get_stream_by_id(session, uuid4())
    assert stream is None


def test_get_user_streams(session, sample_user, sample_stream):
    """Test getting all streams owned by a user."""
    # Create another stream
    stream2 = streams.create_stream(
        session,
        owner_id=sample_user.id,
        name="Second Stream",
    )
    session.commit()

    user_streams = streams.get_user_streams(session, sample_user.id)

    assert len(user_streams) == 2
    stream_ids = [s.id for s in user_streams]
    assert sample_stream.id in stream_ids
    assert stream2.id in stream_ids


def test_get_user_streams_empty(session, sample_user2):
    """Test getting streams for a user with no streams."""
    user_streams = streams.get_user_streams(session, sample_user2.id)
    assert len(user_streams) == 0


def test_update_stream(session, sample_stream):
    """Test updating stream properties."""
    updated = streams.update_stream(
        session,
        sample_stream.id,
        name="Updated Name",
        description="Updated description",
        is_public=True,
    )

    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.description == "Updated description"
    assert updated.is_public is True


def test_update_stream_not_found(session):
    """Test updating a non-existent stream."""
    from uuid import uuid4

    result = streams.update_stream(session, uuid4(), name="Test")
    assert result is None


def test_delete_stream(session, sample_stream):
    """Test deleting a stream."""
    stream_id = sample_stream.id

    result = streams.delete_stream(session, stream_id)
    assert result is True

    # Verify stream is deleted
    stream = streams.get_stream_by_id(session, stream_id)
    assert stream is None


def test_delete_stream_not_found(session):
    """Test deleting a non-existent stream."""
    from uuid import uuid4

    result = streams.delete_stream(session, uuid4())
    assert result is False


# ============================================================================
# POST OPERATIONS TESTS
# ============================================================================


def test_create_post(session, sample_stream, sample_user):
    """Test creating a post."""
    post = streams.create_post(
        session,
        stream_id=sample_stream.id,
        author_id=sample_user.id,
        text_content="Hello, world!",
    )

    assert post.id is not None
    assert post.stream_id == sample_stream.id
    assert post.author_id == sample_user.id
    assert post.text_content == "Hello, world!"
    assert post.content_type == "text"


def test_get_post_by_id(session, sample_post):
    """Test retrieving a post by ID."""
    post = streams.get_post_by_id(session, sample_post.id)

    assert post is not None
    assert post.id == sample_post.id
    assert post.text_content == sample_post.text_content


def test_get_stream_posts(session, sample_stream, sample_user):
    """Test getting all posts from a stream."""
    # Create multiple posts
    post1 = streams.create_post(
        session, sample_stream.id, sample_user.id, "Post 1"
    )
    post2 = streams.create_post(
        session, sample_stream.id, sample_user.id, "Post 2"
    )
    post3 = streams.create_post(
        session, sample_stream.id, sample_user.id, "Post 3"
    )
    session.commit()

    posts = streams.get_stream_posts(session, sample_stream.id)

    assert len(posts) == 3
    # Should be ordered by created_at DESC (newest first)
    assert posts[0].text_content == "Post 3"
    assert posts[2].text_content == "Post 1"


def test_get_stream_posts_with_limit(session, sample_stream, sample_user):
    """Test getting posts with limit."""
    # Create 5 posts
    for i in range(5):
        streams.create_post(
            session, sample_stream.id, sample_user.id, f"Post {i}"
        )
    session.commit()

    posts = streams.get_stream_posts(session, sample_stream.id, limit=2)

    assert len(posts) == 2


def test_get_stream_posts_with_offset(session, sample_stream, sample_user):
    """Test getting posts with offset."""
    # Create 5 posts
    for i in range(5):
        streams.create_post(
            session, sample_stream.id, sample_user.id, f"Post {i}"
        )
    session.commit()

    posts = streams.get_stream_posts(session, sample_stream.id, limit=2, offset=2)

    assert len(posts) == 2


def test_get_latest_stream_post(session, sample_stream, sample_user):
    """Test getting the most recent post."""
    post1 = streams.create_post(
        session, sample_stream.id, sample_user.id, "First"
    )
    post2 = streams.create_post(
        session, sample_stream.id, sample_user.id, "Latest"
    )
    session.commit()

    latest = streams.get_latest_stream_post(session, sample_stream.id)

    assert latest is not None
    assert latest.text_content == "Latest"
    assert latest.id == post2.id


def test_get_latest_stream_post_empty(session, sample_stream):
    """Test getting latest post from stream with no posts."""
    latest = streams.get_latest_stream_post(session, sample_stream.id)
    assert latest is None


def test_delete_post(session, sample_post):
    """Test deleting a post."""
    post_id = sample_post.id

    result = streams.delete_post(session, post_id)
    assert result is True

    # Verify post is deleted
    post = streams.get_post_by_id(session, post_id)
    assert post is None


# ============================================================================
# SUBSCRIPTION OPERATIONS TESTS
# ============================================================================


def test_subscribe_to_stream(session, sample_user2, sample_stream):
    """Test subscribing to a stream."""
    subscription = streams.subscribe_to_stream(
        session,
        user_id=sample_user2.id,
        stream_id=sample_stream.id,
    )

    assert subscription.id is not None
    assert subscription.user_id == sample_user2.id
    assert subscription.stream_id == sample_stream.id
    assert subscription.is_approved is True


def test_subscribe_to_stream_duplicate(session, sample_user, sample_stream):
    """Test that duplicate subscriptions are prevented."""
    # Create first subscription
    streams.subscribe_to_stream(session, sample_user.id, sample_stream.id)
    session.commit()

    # Try to create duplicate
    with pytest.raises(ValueError, match="already subscribed"):
        streams.subscribe_to_stream(session, sample_user.id, sample_stream.id)


def test_get_subscription(session, sample_user2, sample_stream):
    """Test retrieving a subscription."""
    # Create subscription
    sub = streams.subscribe_to_stream(
        session, sample_user2.id, sample_stream.id
    )
    session.commit()

    # Retrieve it
    retrieved = streams.get_subscription(
        session, sample_user2.id, sample_stream.id
    )

    assert retrieved is not None
    assert retrieved.id == sub.id


def test_get_subscription_not_found(session, sample_user, sample_stream):
    """Test retrieving a non-existent subscription."""
    sub = streams.get_subscription(session, sample_user.id, sample_stream.id)
    assert sub is None


def test_unsubscribe_from_stream(session, sample_user2, sample_stream):
    """Test unsubscribing from a stream."""
    # Create subscription
    streams.subscribe_to_stream(session, sample_user2.id, sample_stream.id)
    session.commit()

    # Unsubscribe
    result = streams.unsubscribe_from_stream(
        session, sample_user2.id, sample_stream.id
    )
    assert result is True

    # Verify subscription is gone
    sub = streams.get_subscription(session, sample_user2.id, sample_stream.id)
    assert sub is None


def test_unsubscribe_not_subscribed(session, sample_user, sample_stream):
    """Test unsubscribing when not subscribed."""
    result = streams.unsubscribe_from_stream(
        session, sample_user.id, sample_stream.id
    )
    assert result is False


def test_approve_subscription(session, sample_user2, sample_stream):
    """Test approving a pending subscription."""
    # Create pending subscription
    sub = streams.subscribe_to_stream(
        session, sample_user2.id, sample_stream.id, is_approved=False
    )
    session.commit()

    assert sub.is_approved is False

    # Approve it
    approved = streams.approve_subscription(
        session, sample_user2.id, sample_stream.id
    )

    assert approved is not None
    assert approved.is_approved is True


def test_get_subscribed_streams(session, sample_user, sample_user2):
    """Test getting all streams a user is subscribed to."""
    # Create streams
    stream1 = streams.create_stream(session, sample_user.id, "Stream 1")
    stream2 = streams.create_stream(session, sample_user.id, "Stream 2")
    session.commit()

    # Subscribe user2 to both
    streams.subscribe_to_stream(session, sample_user2.id, stream1.id)
    streams.subscribe_to_stream(session, sample_user2.id, stream2.id)
    session.commit()

    # Get subscribed streams
    subscribed = streams.get_subscribed_streams(session, sample_user2.id)

    assert len(subscribed) == 2
    stream_ids = [s.id for s in subscribed]
    assert stream1.id in stream_ids
    assert stream2.id in stream_ids


def test_get_stream_subscribers(session, sample_user, sample_user2, sample_stream):
    """Test getting all subscribers of a stream."""
    # Subscribe user2
    streams.subscribe_to_stream(session, sample_user2.id, sample_stream.id)
    session.commit()

    subscribers = streams.get_stream_subscribers(session, sample_stream.id)

    assert len(subscribers) == 1
    assert subscribers[0].id == sample_user2.id


def test_get_stream_subscribers_excludes_unapproved(
    session, sample_user, sample_user2, sample_stream
):
    """Test that unapproved subscriptions are excluded."""
    # Create unapproved subscription
    streams.subscribe_to_stream(
        session, sample_user2.id, sample_stream.id, is_approved=False
    )
    session.commit()

    subscribers = streams.get_stream_subscribers(session, sample_stream.id)

    assert len(subscribers) == 0


# ============================================================================
# PERMISSION HELPERS TESTS
# ============================================================================


def test_can_user_view_stream_owner(session, sample_user, sample_stream):
    """Test that owner can view their stream."""
    can_view = streams.can_user_view_stream(
        session, sample_user.id, sample_stream.id
    )
    assert can_view is True


def test_can_user_view_stream_public(session, sample_user2):
    """Test that anyone can view a public stream."""
    # Create public stream
    from streamscene.core.models import Stream

    public_stream = Stream(
        owner_id=sample_user2.id,
        name="Public Stream",
        is_public=True,
    )
    session.add(public_stream)
    session.commit()

    # Any user should be able to view
    from uuid import uuid4

    random_user_id = uuid4()
    can_view = streams.can_user_view_stream(
        session, random_user_id, public_stream.id
    )
    assert can_view is True


def test_can_user_view_stream_subscribed(session, sample_user2, sample_stream):
    """Test that subscribed user can view private stream."""
    # Stream is private
    assert sample_stream.is_public is False

    # Subscribe user2
    streams.subscribe_to_stream(session, sample_user2.id, sample_stream.id)
    session.commit()

    can_view = streams.can_user_view_stream(
        session, sample_user2.id, sample_stream.id
    )
    assert can_view is True


def test_can_user_view_stream_not_subscribed(session, sample_user2, sample_stream):
    """Test that non-subscribed user cannot view private stream."""
    # Stream is private
    assert sample_stream.is_public is False

    can_view = streams.can_user_view_stream(
        session, sample_user2.id, sample_stream.id
    )
    assert can_view is False


def test_can_user_post_to_stream_owner(session, sample_user, sample_stream):
    """Test that owner can post to their stream."""
    can_post = streams.can_user_post_to_stream(
        session, sample_user.id, sample_stream.id
    )
    assert can_post is True


def test_can_user_post_to_stream_subscribed(session, sample_user2, sample_stream):
    """Test that subscribed user can post."""
    streams.subscribe_to_stream(session, sample_user2.id, sample_stream.id)
    session.commit()

    can_post = streams.can_user_post_to_stream(
        session, sample_user2.id, sample_stream.id
    )
    assert can_post is True


def test_can_user_post_to_stream_not_subscribed(session, sample_user2, sample_stream):
    """Test that non-subscribed user cannot post."""
    can_post = streams.can_user_post_to_stream(
        session, sample_user2.id, sample_stream.id
    )
    assert can_post is False
