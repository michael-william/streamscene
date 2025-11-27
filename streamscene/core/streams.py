"""Business logic for streams, posts, and subscriptions."""

from datetime import datetime, timezone
from typing import List, Optional, BinaryIO
from uuid import UUID
from pathlib import Path
import hashlib
import io
import os

from PIL import Image
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc

from .models import Stream, Post, StreamSubscription, User, Device
from .utils import generate_slug, ensure_unique_slug
from .image_renderer import ImageRenderer, hex_to_rgb
from .backgrounds import get_background_path, get_default_background


def utc_now():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


# ============================================================================
# IMAGE STORAGE CONSTANTS
# ============================================================================

UPLOADS_DIR = Path("/root/streamscene/uploads/posts")
RENDERED_DIR = Path("/root/streamscene/cache/rendered")

# Ensure directories exist
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RENDERED_DIR.mkdir(parents=True, exist_ok=True)

# Initialize renderer (shared instance)
_renderer = None


def get_renderer() -> ImageRenderer:
    """Get shared ImageRenderer instance."""
    global _renderer
    if _renderer is None:
        _renderer = ImageRenderer()
    return _renderer


# ============================================================================
# IMAGE HANDLING HELPERS
# ============================================================================


def save_uploaded_image(image_bytes: bytes, post_id: UUID) -> str:
    """
    Save uploaded image to disk.

    Args:
        image_bytes: Image file bytes
        post_id: Post UUID (used in filename)

    Returns:
        Relative path to saved image

    Raises:
        ValueError: If image format is invalid
    """
    # Open and validate image
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()  # Verify it's a valid image
    except Exception as e:
        raise ValueError(f"Invalid image file: {e}")

    # Re-open image (verify() closes it)
    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA to RGB if needed
    if img.mode == "RGBA":
        # Create white background
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Save with post ID as filename
    filename = f"{post_id}.jpg"
    filepath = UPLOADS_DIR / filename
    img.save(filepath, "JPEG", quality=90, optimize=True)

    return str(filepath)


def render_and_cache_post(
    post: Post,
    stream_name: str,
    author_name: str
) -> str:
    """
    Render post to 800x480 PNG and cache it.

    Args:
        post: Post object
        stream_name: Stream display name
        author_name: Author display name

    Returns:
        Path to rendered PNG file

    Raises:
        ValueError: If post type is invalid or required fields missing
    """
    renderer = get_renderer()

    # Parse colors
    text_color = hex_to_rgb(post.text_color)
    outline_color = hex_to_rgb(post.outline_color)

    # Get outline_width and font_family (with defaults for old posts)
    outline_width = getattr(post, 'outline_width', 2) or 2
    font_family = getattr(post, 'font_family', 'montserrat') or 'montserrat'

    # Determine post type and render
    if post.content_type == "picture":
        # Support both old posts (image_path) and new posts (temp_image_bytes)
        if post.image_path:
            # Backward compatibility: old post with saved file
            rendered_img = renderer.render_picture_post(
                image_path=post.image_path,
                text_content=post.text_content or "",
                stream_name=stream_name,
                author_name=author_name,
                post_date=post.created_at,
                text_color=text_color,
                outline_color=outline_color,
                outline_width=outline_width,
                font_family=font_family
            )
        elif hasattr(post, '_temp_image_bytes') and post._temp_image_bytes:
            # New posts: render from in-memory bytes
            from PIL import Image
            temp_img = Image.open(io.BytesIO(post._temp_image_bytes))
            rendered_img = renderer.render_picture_post(
                image=temp_img,  # Pass PIL Image directly
                text_content=post.text_content or "",
                stream_name=stream_name,
                author_name=author_name,
                post_date=post.created_at,
                text_color=text_color,
                outline_color=outline_color,
                outline_width=outline_width,
                font_family=font_family
            )
        else:
            raise ValueError("Picture posts require image_path or temp_image_bytes")

    elif post.content_type == "meme":
        if not post.background_name:
            raise ValueError("Meme posts require background_name")

        background_path = str(get_background_path(post.background_name))

        rendered_img = renderer.render_meme_post(
            background_image_path=background_path,
            text_content=post.text_content or "",
            stream_name=stream_name,
            author_name=author_name,
            post_date=post.created_at,
            text_color=text_color,
            outline_color=outline_color,
            outline_width=outline_width,
            font_family=font_family
        )

    else:
        raise ValueError(f"Unknown content_type: {post.content_type}")

    # Generate cache key (hash of post content including style settings)
    cache_key = hashlib.sha256(
        f"{post.id}{post.content_type}{post.text_content}{post.text_color}{post.outline_color}{outline_width}{font_family}".encode('utf-8')
    ).hexdigest()[:16]

    # Save rendered image
    filename = f"{post.id}_{cache_key}.png"
    filepath = RENDERED_DIR / filename
    rendered_img.save(filepath, "PNG", optimize=True)

    return str(filepath)


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
    content_type: str = "meme",
    image_bytes: Optional[bytes] = None,
    background_name: Optional[str] = None,
    text_color: str = "#000000",
    outline_color: str = "#FFFFFF",
    outline_width: int = 2,
    font_family: str = "montserrat",
) -> Post:
    """
    Create a new post in a stream (picture or meme).

    Args:
        session: Database session
        stream_id: Stream UUID
        author_id: Author's user UUID
        text_content: The text content (max 160 chars)
        content_type: "picture" or "meme" (default: "meme")
        image_bytes: Image file bytes (required for picture posts)
        background_name: Background filename (required for meme posts)
        text_color: Hex color code for text (default: black)
        outline_color: Hex color code for outline (default: white)
        outline_width: Outline thickness (0 = disabled, default: 2)
        font_family: Font family name (default: montserrat)

    Returns:
        Post: The created post instance

    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Validate text length
    if text_content and len(text_content) > 160:
        raise ValueError("Text content must be 160 characters or less")

    # Validate content_type
    if content_type not in ["picture", "meme"]:
        raise ValueError(f"Invalid content_type: {content_type}")

    # Validate required fields per content type
    if content_type == "picture" and not image_bytes:
        raise ValueError("Picture posts require image_bytes")
    if content_type == "meme" and not background_name:
        # Use default white background if not specified
        default_bg = get_default_background(session)
        if default_bg:
            background_name = default_bg.filename
        else:
            raise ValueError("Meme posts require background_name and no default available")

    # Track rendered file for cleanup on failure
    rendered_file_path = None

    try:
        # Create post record
        post = Post(
            stream_id=stream_id,
            author_id=author_id,
            text_content=text_content,
            content_type=content_type,
            background_name=background_name,
            text_color=text_color,
            outline_color=outline_color,
            outline_width=outline_width,
            font_family=font_family,
        )
        session.add(post)
        session.flush()  # Generate post.id

        # Store image bytes temporarily (don't save original to disk)
        if content_type == "picture" and image_bytes:
            post.image_path = None  # No original stored (save 60-70% storage)
            post._temp_image_bytes = image_bytes  # Temporary in-memory storage

        # Get stream and author names for rendering
        stream = session.query(Stream).filter(Stream.id == stream_id).first()
        author = session.query(User).filter(User.id == author_id).first()

        if not stream or not author:
            raise ValueError("Stream or author not found")

        # Render and cache the post (writes file to disk)
        post.processed_image_path = render_and_cache_post(
            post=post,
            stream_name=stream.name,
            author_name=author.display_name
        )
        rendered_file_path = post.processed_image_path

        session.flush()
        return post

    except Exception as e:
        # Clean up rendered file if it was created before transaction failed
        if rendered_file_path and os.path.exists(rendered_file_path):
            try:
                os.remove(rendered_file_path)
                logger.info(f"[CLEANUP] Removed orphaned render: {rendered_file_path}")
            except Exception as cleanup_err:
                logger.error(f"[CLEANUP] Failed to delete {rendered_file_path}: {cleanup_err}")
        raise


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
    Update a post's text content and re-render the cached image.

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

    # Update text content
    post.text_content = text_content
    post.updated_at = utc_now()
    session.flush()

    # Re-render the cached image with new content
    stream = get_stream_by_id(session, post.stream_id)
    author = session.query(User).filter(User.id == post.author_id).first()

    if stream and author:
        # Delete old cached image if it exists
        if post.processed_image_path and os.path.exists(post.processed_image_path):
            try:
                os.remove(post.processed_image_path)
            except Exception:
                pass  # Ignore cleanup errors

        # Re-render with updated content
        post.processed_image_path = render_and_cache_post(
            post=post,
            stream_name=stream.name,
            author_name=author.display_name
        )
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


def get_device_content(session: Session, device_id: UUID, rotation_index: int = 0) -> Optional[dict]:
    """
    Get content for a device to display, with optional rotation support.

    Args:
        session: Database session
        device_id: Device UUID
        rotation_index: Index for content rotation (0-based)

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
            "post_id": None,
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
            "post_id": None,
            "stream_name": "System",
            "posted_at": utc_now(),
        }

    # Determine which post to return based on rotation settings
    if device.rotation_enabled:
        # Rotation mode: get multiple posts and return one by index
        posts = (
            session.query(Post)
            .filter(Post.stream_id == device.current_stream_id)
            .order_by(Post.created_at.desc())
            .limit(device.rotation_post_count)
            .all()
        )

        if not posts:
            return {
                "has_content": False,
                "content_type": "text",
                "text_content": "No posts yet in this stream.",
                "post_id": None,
                "stream_name": stream.name,
                "posted_at": utc_now(),
            }

        # Get post at rotation_index (wrapping around if needed)
        post = posts[rotation_index % len(posts)]
    else:
        # Static mode: get latest post only
        post = get_latest_stream_post(session, device.current_stream_id)
        if not post:
            return {
                "has_content": False,
                "content_type": "text",
                "text_content": "No posts yet in this stream.",
                "post_id": None,
                "stream_name": stream.name,
                "posted_at": utc_now(),
            }

    return {
        "has_content": True,
        "content_type": post.content_type,
        "text_content": post.text_content,
        "image_url": post.processed_image_path,
        "post_id": str(post.id),
        "stream_name": stream.name,
        "theme_name": stream.theme_name,
        "posted_at": post.created_at,
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


def update_device_rotation(
    session: Session,
    device_id: UUID,
    rotation_enabled: bool,
    rotation_interval: int,
    rotation_post_count: int = 10,
) -> Optional[Device]:
    """
    Update rotation settings for a device.

    Args:
        session: Database session
        device_id: Device UUID
        rotation_enabled: Enable/disable rotation
        rotation_interval: Interval in seconds between posts
        rotation_post_count: Number of posts to rotate through (2-10)

    Returns:
        Optional[Device]: Updated device or None if not found

    Raises:
        ValueError: If rotation settings are invalid
    """
    if rotation_enabled:
        if rotation_interval < 60:
            raise ValueError("Rotation interval must be at least 60 seconds (1 minute)")

        if rotation_interval > 86400:
            raise ValueError("Rotation interval must be less than 24 hours")

        if rotation_post_count < 2:
            raise ValueError("Post count must be at least 2")

        if rotation_post_count > 10:
            raise ValueError("Post count must be at most 10")

    device = get_device_by_id(session, device_id)
    if not device:
        return None

    device.rotation_enabled = rotation_enabled
    device.rotation_interval = rotation_interval
    device.rotation_post_count = rotation_post_count if rotation_enabled else 1
    session.flush()
    return device
