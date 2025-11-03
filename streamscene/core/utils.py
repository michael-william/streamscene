"""Utility functions for StreamScene core logic."""

import re
import unicodedata
from sqlalchemy.orm import Session
from typing import Optional


def generate_slug(text: str, max_length: int = 100) -> str:
    """
    Generate a URL-safe slug from text.

    Converts to lowercase, removes special characters, replaces spaces with hyphens.

    Args:
        text: The text to convert to a slug
        max_length: Maximum length of the slug (default: 100)

    Returns:
        A URL-safe slug string

    Examples:
        >>> generate_slug("Family Updates")
        'family-updates'
        >>> generate_slug("Mom's Photos!")
        'moms-photos'
        >>> generate_slug("Hello   World")
        'hello-world'
    """
    # Normalize unicode characters (convert accented chars to ASCII equivalents)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)

    # Remove all non-alphanumeric characters except hyphens
    text = re.sub(r'[^a-z0-9-]', '', text)

    # Remove multiple consecutive hyphens
    text = re.sub(r'-+', '-', text)

    # Strip hyphens from start and end
    text = text.strip('-')

    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length].rstrip('-')

    return text or 'stream'  # Fallback if slug is empty


def ensure_unique_slug(session: Session, model_class, slug: str, exclude_id: Optional[str] = None) -> str:
    """
    Ensure slug is unique by appending a number if needed.

    Args:
        session: SQLAlchemy session
        model_class: The model class (e.g., Stream)
        slug: The proposed slug
        exclude_id: Optional ID to exclude from uniqueness check (for updates)

    Returns:
        A unique slug (may have -2, -3, etc. appended)

    Examples:
        If 'family-updates' exists, returns 'family-updates-2'
        If 'family-updates' and 'family-updates-2' exist, returns 'family-updates-3'
    """
    original_slug = slug
    counter = 2

    while True:
        # Check if slug exists
        query = session.query(model_class).filter(model_class.slug == slug)

        # Exclude the current record if updating
        if exclude_id:
            query = query.filter(model_class.id != exclude_id)

        existing = query.first()

        if not existing:
            return slug

        # Slug exists, try with counter
        slug = f"{original_slug}-{counter}"
        counter += 1

        # Safety check to prevent infinite loop
        if counter > 1000:
            # Fallback to adding a random suffix
            import uuid
            return f"{original_slug}-{str(uuid.uuid4())[:8]}"
