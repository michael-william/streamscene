"""Tests for authentication and user management."""

import pytest

from streamscene.core import auth
from streamscene.core.models import User


def test_get_or_create_user_creates_new(session):
    """Test creating a new user via get_or_create_user."""
    user = auth.get_or_create_user(session, "new-user-123")

    assert user.id is not None
    assert user.authentik_user_id == "new-user-123"

    # Verify user is in database
    db_user = session.query(User).filter(
        User.authentik_user_id == "new-user-123"
    ).first()
    assert db_user is not None
    assert db_user.id == user.id


def test_get_or_create_user_returns_existing(session, sample_user):
    """Test getting an existing user via get_or_create_user."""
    original_id = sample_user.id

    user = auth.get_or_create_user(session, sample_user.authentik_user_id)

    assert user.id == original_id
    assert user.authentik_user_id == sample_user.authentik_user_id

    # Verify no duplicate was created
    count = session.query(User).filter(
        User.authentik_user_id == sample_user.authentik_user_id
    ).count()
    assert count == 1


def test_get_user_by_id(session, sample_user):
    """Test getting a user by UUID."""
    user = auth.get_user_by_id(session, sample_user.id)

    assert user is not None
    assert user.id == sample_user.id


def test_get_user_by_id_not_found(session):
    """Test getting a non-existent user by UUID."""
    from uuid import uuid4

    user = auth.get_user_by_id(session, uuid4())
    assert user is None


def test_get_user_by_authentik_id(session, sample_user):
    """Test getting a user by Authentik ID."""
    user = auth.get_user_by_authentik_id(session, sample_user.authentik_user_id)

    assert user is not None
    assert user.id == sample_user.id


def test_generate_api_key():
    """Test API key generation."""
    key1 = auth.generate_api_key()
    key2 = auth.generate_api_key()

    # Should be different
    assert key1 != key2

    # Should be reasonable length (default 64 chars generates ~86 char base64)
    assert len(key1) > 60
    assert len(key2) > 60


def test_hash_and_verify_api_key():
    """Test API key hashing and verification."""
    api_key = auth.generate_api_key()
    hashed = auth.hash_api_key(api_key)

    # Hash should be different from original
    assert hashed != api_key

    # Should verify correctly
    assert auth.verify_api_key(api_key, hashed) is True

    # Wrong key should not verify
    wrong_key = auth.generate_api_key()
    assert auth.verify_api_key(wrong_key, hashed) is False


def test_hash_api_key_produces_different_hashes():
    """Test that same API key produces different hashes (due to salt)."""
    api_key = "test-key-123"

    hash1 = auth.hash_api_key(api_key)
    hash2 = auth.hash_api_key(api_key)

    # Different hashes due to different salts
    assert hash1 != hash2

    # But both should verify
    assert auth.verify_api_key(api_key, hash1) is True
    assert auth.verify_api_key(api_key, hash2) is True


def test_verify_api_key_handles_invalid_hash():
    """Test that verify_api_key handles invalid hashes gracefully."""
    api_key = "test-key"
    invalid_hash = "not-a-valid-hash"

    # Should return False, not raise exception
    assert auth.verify_api_key(api_key, invalid_hash) is False


def test_is_stream_owner(session, sample_user, sample_user2, sample_stream):
    """Test stream ownership check."""
    # Owner should return True
    assert auth.is_stream_owner(session, sample_user.id, sample_stream.id) is True

    # Non-owner should return False
    assert auth.is_stream_owner(session, sample_user2.id, sample_stream.id) is False


def test_is_stream_owner_nonexistent_stream(session, sample_user):
    """Test stream ownership check with non-existent stream."""
    from uuid import uuid4

    assert auth.is_stream_owner(session, sample_user.id, uuid4()) is False


def test_is_post_author(session, sample_user, sample_user2, sample_post):
    """Test post authorship check."""
    # Author should return True
    assert auth.is_post_author(session, sample_user.id, sample_post.id) is True

    # Non-author should return False
    assert auth.is_post_author(session, sample_user2.id, sample_post.id) is False
