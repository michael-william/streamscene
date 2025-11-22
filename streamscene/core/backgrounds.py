"""Background image management for Meme It posts."""

import uuid
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session

from streamscene.core.models import BackgroundImage, utc_now

# Default backgrounds directory
BACKGROUNDS_DIR = Path("/root/streamscene/backgrounds")

# Default backgrounds with display names (filename -> display name)
DEFAULT_BACKGROUNDS = {
    "white.png": "White",
    "black.png": "Black",
    "blue.png": "Blue",
    "red.png": "Red",
    "green.png": "Green",
    "purple.png": "Purple",
    "orange.png": "Orange",
    "dark_slate.png": "Dark Slate",
    "blue_purple_gradient.png": "Blue to Purple",
    "green_blue_gradient.png": "Green to Blue",
    "yellow_orange_gradient.png": "Yellow to Orange",
    "red_gradient.png": "Red Gradient",
    "pattern_lines.png": "Diagonal Lines",
}


def get_background_path(filename: str) -> Path:
    """
    Get full path to background image.

    Args:
        filename: Background image filename

    Returns:
        Path to background image

    Raises:
        FileNotFoundError: If background doesn't exist
    """
    path = BACKGROUNDS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Background image not found: {filename}")
    return path


def list_filesystem_backgrounds() -> List[dict]:
    """
    List all background images available in filesystem.

    Returns:
        List of dicts with filename and display_name
    """
    if not BACKGROUNDS_DIR.exists():
        return []

    backgrounds = []
    for filepath in BACKGROUNDS_DIR.glob("*.png"):
        filename = filepath.name
        display_name = DEFAULT_BACKGROUNDS.get(filename, filename.replace("_", " ").title())
        backgrounds.append({
            "filename": filename,
            "display_name": display_name,
            "path": str(filepath)
        })

    return sorted(backgrounds, key=lambda x: x["display_name"])


def seed_default_backgrounds(db: Session) -> int:
    """
    Seed database with default background images.

    Checks filesystem for available backgrounds and creates database
    records for any that don't already exist.

    Args:
        db: Database session

    Returns:
        Number of backgrounds added
    """
    filesystem_backgrounds = list_filesystem_backgrounds()
    existing_filenames = {
        bg.filename for bg in db.query(BackgroundImage).all()
    }

    added_count = 0
    for idx, bg_info in enumerate(filesystem_backgrounds):
        if bg_info["filename"] not in existing_filenames:
            background = BackgroundImage(
                id=uuid.uuid4(),
                filename=bg_info["filename"],
                display_name=bg_info["display_name"],
                is_active=True,
                sort_order=idx,
                created_at=utc_now()
            )
            db.add(background)
            added_count += 1

    db.commit()
    return added_count


def get_all_backgrounds(db: Session, active_only: bool = True) -> List[BackgroundImage]:
    """
    Get all backgrounds from database.

    Args:
        db: Database session
        active_only: Only return active backgrounds (default True)

    Returns:
        List of BackgroundImage objects, sorted by sort_order
    """
    query = db.query(BackgroundImage)

    if active_only:
        query = query.filter(BackgroundImage.is_active == True)

    return query.order_by(BackgroundImage.sort_order).all()


def get_background_by_filename(db: Session, filename: str) -> Optional[BackgroundImage]:
    """
    Get background by filename.

    Args:
        db: Database session
        filename: Background image filename

    Returns:
        BackgroundImage object or None if not found
    """
    return db.query(BackgroundImage).filter(
        BackgroundImage.filename == filename
    ).first()


def get_default_background(db: Session) -> Optional[BackgroundImage]:
    """
    Get the default background (first active background).

    Used for migrating existing text posts.

    Args:
        db: Database session

    Returns:
        BackgroundImage object or None if no backgrounds exist
    """
    # Try to get white background first (best for black text)
    white_bg = get_background_by_filename(db, "white.png")
    if white_bg and white_bg.is_active:
        return white_bg

    # Otherwise, return first active background
    backgrounds = get_all_backgrounds(db, active_only=True)
    return backgrounds[0] if backgrounds else None


def create_background(
    db: Session,
    filename: str,
    display_name: str,
    is_active: bool = True,
    sort_order: int = 0
) -> BackgroundImage:
    """
    Create a new background image record.

    Args:
        db: Database session
        filename: Background image filename (must exist in BACKGROUNDS_DIR)
        display_name: Human-readable name
        is_active: Whether background is available for use
        sort_order: Display order in UI

    Returns:
        BackgroundImage object

    Raises:
        FileNotFoundError: If background file doesn't exist
        ValueError: If background already exists in database
    """
    # Verify file exists
    get_background_path(filename)

    # Check if already exists
    existing = get_background_by_filename(db, filename)
    if existing:
        raise ValueError(f"Background already exists: {filename}")

    background = BackgroundImage(
        id=uuid.uuid4(),
        filename=filename,
        display_name=display_name,
        is_active=is_active,
        sort_order=sort_order,
        created_at=utc_now()
    )

    db.add(background)
    db.commit()
    db.refresh(background)

    return background


def update_background(
    db: Session,
    background_id: uuid.UUID,
    display_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_order: Optional[int] = None
) -> Optional[BackgroundImage]:
    """
    Update a background image record.

    Args:
        db: Database session
        background_id: Background UUID
        display_name: New display name (optional)
        is_active: New active status (optional)
        sort_order: New sort order (optional)

    Returns:
        Updated BackgroundImage object or None if not found
    """
    background = db.query(BackgroundImage).filter(
        BackgroundImage.id == background_id
    ).first()

    if not background:
        return None

    if display_name is not None:
        background.display_name = display_name
    if is_active is not None:
        background.is_active = is_active
    if sort_order is not None:
        background.sort_order = sort_order

    db.commit()
    db.refresh(background)

    return background


def delete_background(db: Session, background_id: uuid.UUID) -> bool:
    """
    Delete a background image record.

    Note: Does not delete the actual file, only the database record.

    Args:
        db: Database session
        background_id: Background UUID

    Returns:
        True if deleted, False if not found
    """
    background = db.query(BackgroundImage).filter(
        BackgroundImage.id == background_id
    ).first()

    if not background:
        return False

    db.delete(background)
    db.commit()

    return True
