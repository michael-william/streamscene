"""Business logic for streams, posts, and subscriptions."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc

from .models import Stream, Post, StreamSubscription, User, Device
from .utils import generate_slug, ensure_unique_slug


def utc_now():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


# ============================================================================
# STREAM OPERATIONS
# ============================================================================


def create_stream(
    session: Session,
    owner_id: UUID,
    name: str,
    description: str = "",
    is_public: bool = False,
    allow_text: bool = True,
    allow_images: bool = False,  # MVP: text-only
    theme_name: str = "classic",
) -> Stream:
    """
    Create a new stream.

    Args:
        session: Database session
        owner_id: UUID of the stream owner
        name: Stream name
        description: Optional stream description
        is_public: Whether the stream is publicly visible
        allow_text: Whether text posts are allowed
        allow_images: Whether image posts are allowed (MVP: False)
        theme_name: E Ink display theme name (default: "classic")

    Returns:
        Stream: The created stream instance

    Raises:
        ValueError: If a stream with the same name already exists for this owner
    """
    # Check for duplicate stream name for this owner
    existing = session.query(Stream).filter(
        and_(Stream.owner_id == owner_id, Stream.name == name)
    ).first()

    if existing:
        raise ValueError(f"You already have a stream named '{name}'")

    # Generate a unique slug from the stream name
    base_slug = generate_slug(name)
    unique_slug = ensure_unique_slug(session, Stream, base_slug)

    stream = Stream(
        owner_id=owner_id,
        name=name,
        slug=unique_slug,
        description=description,
        is_public=is_public,
        allow_text=allow_text,
        allow_images=allow_images,
        theme_name=theme_name,
    )
    session.add(stream)
    session.flush()  # Get the ID without committing
    return stream


def get_stream_by_id(session: Session, stream_id: UUID) -> Optional[Stream]:
    """
    Get a stream by its ID.

    Args:
        session: Database session
        stream_id: Stream UUID

    Returns:
        Optional[Stream]: Stream instance or None if not found
    """
    return session.query(Stream).filter(Stream.id == stream_id).first()


def get_stream_by_slug(session: Session, slug: str) -> Optional[Stream]:
    """
    Get a stream by its slug.

    Args:
        session: Database session
        slug: Stream slug (URL-safe identifier)

    Returns:
        Optional[Stream]: Stream instance or None if not found
    """
    return session.query(Stream).filter(Stream.slug == slug).first()


def get_user_streams(session: Session, user_id: UUID) -> List[Stream]:
    """
    Get all streams owned by a user.

    Args:
        session: Database session
        user_id: User UUID

    Returns:
        List[Stream]: List of streams owned by the user
    """
    return (
        session.query(Stream)
        .filter(Stream.owner_id == user_id)
        .order_by(desc(Stream.created_at))
        .all()
    )


def get_subscribed_streams(session: Session, user_id: UUID) -> List[Stream]:
    """
    Get all streams a user is subscribed to.

    Args:
        session: Database session
        user_id: User UUID

    Returns:
        List[Stream]: List of subscribed streams
    """
    return (
        session.query(Stream)
        .join(StreamSubscription)
        .filter(
            and_(
                StreamSubscription.user_id == user_id,
                StreamSubscription.is_approved == True,
            )
        )
        .order_by(desc(Stream.created_at))
        .all()
    )


def update_stream(
    session: Session,
    stream_id: UUID,
    **kwargs
) -> Optional[Stream]:
    """
    Update stream properties.

    Args:
        session: Database session
        stream_id: Stream UUID
        **kwargs: Fields to update (name, description, is_public, etc.)

    Returns:
        Optional[Stream]: Updated stream or None if not found
    """
    stream = get_stream_by_id(session, stream_id)
    if not stream:
        return None

    for key, value in kwargs.items():
        if hasattr(stream, key):
            setattr(stream, key, value)

    stream.updated_at = utc_now()
    session.flush()
    return stream


def delete_stream(session: Session, stream_id: UUID) -> bool:
    """
    Delete a stream and all associated data (posts, subscriptions).

    Args:
        session: Database session
        stream_id: Stream UUID

    Returns:
        bool: True if deleted, False if not found
    """
    stream = get_stream_by_id(session, stream_id)
    if not stream:
        return False

    session.delete(stream)
    session.flush()
    return True


# ============================================================================
# POST OPERATIONS
# ============================================================================


def create_post(
    session: Session,
    stream_id: UUID,
    author_id: UUID,
    text_content: str,
    content_type: str = "text",
) -> Post:
    """
    Create a new text post in a stream.

    Args:
        session: Database session
        stream_id: Stream UUID
        author_id: Author's user UUID
        text_content: The text content of the post
        content_type: Type of content (default: "text")

    Returns:
        Post: The created post instance
    """
    post = Post(
        stream_id=stream_id,
        author_id=author_id,
        text_content=text_content,
        content_type=content_type,
    )
    session.add(post)
    session.flush()
    return post


def get_post_by_id(session: Session, post_id: UUID) -> Optional[Post]:
    """
    Get a post by its ID.

    Args:
        session: Database session
        post_id: Post UUID

    Returns:
        Optional[Post]: Post instance or None if not found
    """
    return session.query(Post).filter(Post.id == post_id).first()


def get_stream_posts(
    session: Session,
    stream_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> List[Post]:
    """
    Get posts from a stream, ordered by creation time (newest first).

    Eagerly loads author information to avoid N+1 queries.

    Args:
        session: Database session
        stream_id: Stream UUID
        limit: Maximum number of posts to return
        offset: Number of posts to skip

    Returns:
        List[Post]: List of posts with author information loaded
    """
    return (
        session.query(Post)
        .options(joinedload(Post.author))  # Eager-load author data
        .filter(Post.stream_id == stream_id)
        .order_by(desc(Post.created_at))
        .limit(limit)
        .offset(offset)
        .all()
    )


def get_latest_stream_post(session: Session, stream_id: UUID) -> Optional[Post]:
    """
    Get the most recent post from a stream.

    Args:
        session: Database session
        stream_id: Stream UUID

    Returns:
        Optional[Post]: Latest post or None if stream has no posts
    """
    return (
        session.query(Post)
        .filter(Post.stream_id == stream_id)
        .order_by(desc(Post.created_at))
        .first()
    )


def update_post(
    session: Session,
    post_id: UUID,
    text_content: str,
) -> Optional[Post]:
    """
    Update a post's text content.

    Args:
        session: Database session
        post_id: Post UUID
        text_content: New text content

    Returns:
        Optional[Post]: Updated post or None if not found
    """
    post = get_post_by_id(session, post_id)
    if not post:
        return None

    post.text_content = text_content
    post.updated_at = utc_now()
    session.flush()
    return post


def delete_post(session: Session, post_id: UUID) -> bool:
    """
    Delete a post.

    Args:
        session: Database session
        post_id: Post UUID

    Returns:
        bool: True if deleted, False if not found
    """
    post = get_post_by_id(session, post_id)
    if not post:
        return False

    session.delete(post)
    session.flush()
    return True


# ============================================================================
# SUBSCRIPTION OPERATIONS
# ============================================================================


def subscribe_to_stream(
    session: Session,
    user_id: UUID,
    stream_id: UUID,
    is_approved: bool = True,
) -> StreamSubscription:
    """
    Subscribe a user to a stream.

    Args:
        session: Database session
        user_id: User UUID
        stream_id: Stream UUID
        is_approved: Whether subscription is approved (False for private streams)

    Returns:
        StreamSubscription: The created subscription

    Raises:
        Exception: If subscription already exists
    """
    # Check if subscription already exists
    existing = get_subscription(session, user_id, stream_id)
    if existing:
        raise ValueError("User is already subscribed to this stream")

    subscription = StreamSubscription(
        user_id=user_id,
        stream_id=stream_id,
        is_approved=is_approved,
    )
    session.add(subscription)
    session.flush()
    return subscription


def get_subscription(
    session: Session,
    user_id: UUID,
    stream_id: UUID,
) -> Optional[StreamSubscription]:
    """
    Get a subscription record.

    Args:
        session: Database session
        user_id: User UUID
        stream_id: Stream UUID

    Returns:
        Optional[StreamSubscription]: Subscription or None if not found
    """
    return (
        session.query(StreamSubscription)
        .filter(
            and_(
                StreamSubscription.user_id == user_id,
                StreamSubscription.stream_id == stream_id,
            )
        )
        .first()
    )


def unsubscribe_from_stream(
    session: Session,
    user_id: UUID,
    stream_id: UUID,
) -> bool:
    """
    Unsubscribe a user from a stream.

    Args:
        session: Database session
        user_id: User UUID
        stream_id: Stream UUID

    Returns:
        bool: True if unsubscribed, False if subscription not found
    """
    subscription = get_subscription(session, user_id, stream_id)
    if not subscription:
        return False

    session.delete(subscription)
    session.flush()
    return True


def approve_subscription(
    session: Session,
    user_id: UUID,
    stream_id: UUID,
) -> Optional[StreamSubscription]:
    """
    Approve a pending subscription (for private streams).

    Args:
        session: Database session
        user_id: User UUID
        stream_id: Stream UUID

    Returns:
        Optional[StreamSubscription]: Updated subscription or None if not found
    """
    subscription = get_subscription(session, user_id, stream_id)
    if not subscription:
        return None

    subscription.is_approved = True
    session.flush()
    return subscription


def get_stream_subscribers(session: Session, stream_id: UUID) -> List[User]:
    """
    Get all approved subscribers of a stream.

    Args:
        session: Database session
        stream_id: Stream UUID

    Returns:
        List[User]: List of subscribed users
    """
    return (
        session.query(User)
        .join(StreamSubscription)
        .filter(
            and_(
                StreamSubscription.stream_id == stream_id,
                StreamSubscription.is_approved == True,
            )
        )
        .all()
    )


# ============================================================================
# PERMISSION HELPERS
# ============================================================================


def can_user_view_stream(session: Session, user_id: UUID, stream_id: UUID) -> bool:
    """
    Check if a user can view a stream.

    Args:
        session: Database session
        user_id: User UUID
        stream_id: Stream UUID

    Returns:
        bool: True if user can view the stream
    """
    stream = get_stream_by_id(session, stream_id)
    if not stream:
        return False

    # Owner can always view
    if stream.owner_id == user_id:
        return True

    # Public streams can be viewed by anyone
    if stream.is_public:
        return True

    # Check if user has approved subscription
    subscription = get_subscription(session, user_id, stream_id)
    return subscription is not None and subscription.is_approved


def can_user_post_to_stream(session: Session, user_id: UUID, stream_id: UUID) -> bool:
    """
    Check if a user can post to a stream.

    Args:
        session: Database session
        user_id: User UUID
        stream_id: Stream UUID

    Returns:
        bool: True if user can post to the stream
    """
    stream = get_stream_by_id(session, stream_id)
    if not stream:
        return False

    # Owner can always post
    if stream.owner_id == user_id:
        return True

    # Check if user has approved subscription
    subscription = get_subscription(session, user_id, stream_id)
    return subscription is not None and subscription.is_approved


def can_user_edit_post(session: Session, user_id: UUID, post_id: UUID) -> bool:
    """
    Check if a user can edit a post.

    Only the post author can edit their own posts.

    Args:
        session: Database session
        user_id: User UUID
        post_id: Post UUID

    Returns:
        bool: True if user can edit the post
    """
    from .auth import is_post_author

    return is_post_author(session, user_id, post_id)


def can_user_delete_post(session: Session, user_id: UUID, post_id: UUID) -> bool:
    """
    Check if a user can delete a post.

    Post authors can delete their own posts.
    Stream owners can delete any post in their streams.

    Args:
        session: Database session
        user_id: User UUID
        post_id: Post UUID

    Returns:
        bool: True if user can delete the post
    """
    from .auth import is_post_author

    post = get_post_by_id(session, post_id)
    if not post:
        return False

    # Post author can always delete
    if is_post_author(session, user_id, post_id):
        return True

    # Stream owner can delete any post in their stream
    stream = get_stream_by_id(session, post.stream_id)
    if stream and stream.owner_id == user_id:
        return True

    return False


# ============================================================================
# DEVICE OPERATIONS
# ============================================================================


def register_device(
    session: Session,
    device_uuid: UUID,
    user_id: UUID,
    nickname: Optional[str] = None,
) -> tuple[Device, str]:
    """
    Register a device and generate an API key.

    Args:
        session: Database session
        device_uuid: Pre-configured device UUID from SD card
        user_id: User ID who is registering the device
        nickname: Optional nickname for the device

    Returns:
        tuple: (Device instance, plaintext API key)

    Raises:
        ValueError: If device_uuid is already registered
    """
    from .auth import generate_api_key, hash_api_key

    # Check if device already exists
    existing_device = session.query(Device).filter(
        Device.device_uuid == device_uuid
    ).first()

    if existing_device and existing_device.user_id is not None:
        raise ValueError("Device is already registered")

    # Generate API key
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    if existing_device:
        # Update existing unregistered device
        existing_device.user_id = user_id
        existing_device.api_key_hash = api_key_hash
        existing_device.nickname = nickname or "My StreamScene Frame"
        existing_device.registered_at = utc_now()
        # Store API key temporarily in config for device to retrieve
        existing_device.config["pending_api_key"] = api_key
        device = existing_device
    else:
        # Create new device
        device = Device(
            device_uuid=device_uuid,
            user_id=user_id,
            api_key_hash=api_key_hash,
            nickname=nickname or "My StreamScene Frame",
            registered_at=utc_now(),
            config={"pending_api_key": api_key},  # Store API key temporarily
        )
        session.add(device)

    session.flush()
    return device, api_key


def get_device_content(session: Session, device_id: UUID) -> Optional[dict]:
    """
    Get the latest content for a device to display.

    Args:
        session: Database session
        device_id: Device UUID

    Returns:
        Optional[dict]: Content dictionary or None if no content available
    """
    device = session.query(Device).filter(Device.id == device_id).first()
    if not device:
        return None

    # If no stream is configured, return empty
    if not device.current_stream_id:
        return {
            "has_content": False,
            "content_type": "text",
            "text_content": "No stream configured. Please configure via web app.",
            "stream_name": "System",
            "posted_at": utc_now(),
        }

    # Get the stream
    stream = get_stream_by_id(session, device.current_stream_id)
    if not stream:
        return {
            "has_content": False,
            "content_type": "text",
            "text_content": "Configured stream not found.",
            "stream_name": "System",
            "posted_at": utc_now(),
        }

    # Get the latest post from the stream
    latest_post = get_latest_stream_post(session, device.current_stream_id)
    if not latest_post:
        return {
            "has_content": False,
            "content_type": "text",
            "text_content": "No posts yet in this stream.",
            "stream_name": stream.name,
            "posted_at": utc_now(),
        }

    return {
        "has_content": True,
        "content_type": latest_post.content_type,
        "text_content": latest_post.text_content,
        "image_url": latest_post.processed_image_path,
        "stream_name": stream.name,
        "theme_name": stream.theme_name,
        "posted_at": latest_post.created_at,
    }


def update_device_heartbeat(session: Session, device_id: UUID) -> bool:
    """
    Update device's last_seen timestamp.

    Args:
        session: Database session
        device_id: Device UUID

    Returns:
        bool: True if device was found and updated, False otherwise
    """
    device = session.query(Device).filter(Device.id == device_id).first()
    if not device:
        return False

    device.last_seen = utc_now()
    session.flush()
    return True


def get_user_devices(session: Session, user_id: UUID) -> List[Device]:
    """
    Get all devices owned by a user.

    Args:
        session: Database session
        user_id: User UUID

    Returns:
        List[Device]: List of device instances
    """
    return session.query(Device).filter(Device.user_id == user_id).all()


def get_device_by_id(session: Session, device_id: UUID) -> Optional[Device]:
    """
    Get a device by ID.

    Args:
        session: Database session
        device_id: Device UUID

    Returns:
        Optional[Device]: Device instance or None
    """
    return session.query(Device).filter(Device.id == device_id).first()


def update_device_stream(
    session: Session,
    device_id: UUID,
    stream_id: Optional[UUID],
) -> Optional[Device]:
    """
    Update the current stream for a device.

    Args:
        session: Database session
        device_id: Device UUID
        stream_id: Stream UUID to set (or None to clear)

    Returns:
        Optional[Device]: Updated device or None if not found
    """
    device = get_device_by_id(session, device_id)
    if not device:
        return None

    device.current_stream_id = stream_id
    session.flush()
    return device


def update_device_nickname(
    session: Session,
    device_id: UUID,
    nickname: str,
) -> Optional[Device]:
    """
    Update the nickname for a device.

    Args:
        session: Database session
        device_id: Device UUID
        nickname: New nickname for the device

    Returns:
        Optional[Device]: Updated device or None if not found

    Raises:
        ValueError: If nickname is empty or invalid
    """
    if not nickname or not nickname.strip():
        raise ValueError("Nickname cannot be empty")

    if len(nickname) > 100:
        raise ValueError("Nickname must be 100 characters or less")

    device = get_device_by_id(session, device_id)
    if not device:
        return None

    device.nickname = nickname.strip()
    session.flush()
    return device
