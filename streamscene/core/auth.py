"""Authentication and user management logic."""

import secrets
from typing import Optional
from uuid import UUID

import bcrypt
from sqlalchemy.orm import Session

from .models import User


def get_or_create_user(session: Session, authentik_user_id: str) -> User:
    """
    Get an existing user by Authentik ID or create a new one.

    Authentik is the single source of truth for user data.
    We only store a reference to the Authentik user ID.

    Args:
        session: Database session
        authentik_user_id: The unique identifier from Authentik

    Returns:
        User: The user instance (existing or newly created)
    """
    # Try to find existing user
    user = session.query(User).filter(
        User.authentik_user_id == authentik_user_id
    ).first()

    if user:
        return user

    # Create new user if not found
    user = User(authentik_user_id=authentik_user_id)
    session.add(user)
    session.flush()
    return user


def get_user_by_id(session: Session, user_id: UUID) -> Optional[User]:
    """
    Get a user by their UUID.

    Args:
        session: Database session
        user_id: User UUID

    Returns:
        Optional[User]: User instance or None if not found
    """
    return session.query(User).filter(User.id == user_id).first()


def get_user_by_authentik_id(session: Session, authentik_user_id: str) -> Optional[User]:
    """
    Get a user by their Authentik user ID.

    Args:
        session: Database session
        authentik_user_id: The Authentik user identifier

    Returns:
        Optional[User]: User instance or None if not found
    """
    return session.query(User).filter(
        User.authentik_user_id == authentik_user_id
    ).first()


# ============================================================================
# API KEY MANAGEMENT (for device authentication)
# ============================================================================


def generate_api_key(length: int = 64) -> str:
    """
    Generate a cryptographically secure API key.

    Args:
        length: Length of the API key (default: 64 characters)

    Returns:
        str: A URL-safe random string
    """
    return secrets.token_urlsafe(length)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using bcrypt.

    Args:
        api_key: The plaintext API key

    Returns:
        str: The hashed API key
    """
    # Bcrypt has a 72-byte limit, so truncate if necessary
    key_bytes = api_key.encode('utf-8')[:72]

    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(key_bytes, salt)
    return hashed.decode('utf-8')


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.

    Args:
        api_key: The plaintext API key to verify
        hashed_key: The hashed API key from the database

    Returns:
        bool: True if the API key matches, False otherwise
    """
    try:
        # Truncate to match what was hashed (bcrypt 72-byte limit)
        key_bytes = api_key.encode('utf-8')[:72]
        return bcrypt.checkpw(
            key_bytes,
            hashed_key.encode('utf-8')
        )
    except Exception:
        return False


# ============================================================================
# PERMISSION CHECKS
# ============================================================================


def is_stream_owner(session: Session, user_id: UUID, stream_id: UUID) -> bool:
    """
    Check if a user owns a specific stream.

    Args:
        session: Database session
        user_id: User UUID
        stream_id: Stream UUID

    Returns:
        bool: True if user owns the stream
    """
    from .models import Stream  # Import here to avoid circular dependency

    stream = session.query(Stream).filter(Stream.id == stream_id).first()
    return stream is not None and stream.owner_id == user_id


def is_post_author(session: Session, user_id: UUID, post_id: UUID) -> bool:
    """
    Check if a user authored a specific post.

    Args:
        session: Database session
        user_id: User UUID
        post_id: Post UUID

    Returns:
        bool: True if user authored the post
    """
    from .models import Post  # Import here to avoid circular dependency

    post = session.query(Post).filter(Post.id == post_id).first()
    return post is not None and post.author_id == user_id
