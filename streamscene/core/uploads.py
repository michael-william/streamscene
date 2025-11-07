"""Upload utilities for handling file uploads."""

import os
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

from PIL import Image


UPLOAD_BASE_PATH = os.getenv("UPLOAD_PATH", "/var/lib/streamscene/uploads")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
PROFILE_PICTURE_SIZE = (300, 300)  # Resize to 300x300 for storage


def save_profile_picture(user_id: UUID, file_path: str) -> Optional[str]:
    """
    Save and process a profile picture upload.

    Args:
        user_id: User UUID
        file_path: Path to the uploaded file

    Returns:
        Relative path to the saved file, or None if failed

    Raises:
        ValueError: If file validation fails
    """
    # Validate file exists
    if not os.path.exists(file_path):
        raise ValueError("File does not exist")

    # Validate file size
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({MAX_FILE_SIZE} bytes)")

    # Validate file extension
    file_ext = Path(file_path).suffix.lower()
    if file_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"File extension {file_ext} not allowed. Must be one of: {ALLOWED_IMAGE_EXTENSIONS}")

    # Create user-specific directory
    user_dir = Path(UPLOAD_BASE_PATH) / "profile_pictures" / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp
    timestamp = int(time.time())
    new_filename = f"profile_{timestamp}.jpg"
    save_path = user_dir / new_filename

    # Open and process image
    try:
        with Image.open(file_path) as img:
            # Convert to RGB (removes alpha channel if present)
            if img.mode in ("RGBA", "LA", "P"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = rgb_img
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize to standard size (maintains aspect ratio, then crops to square)
            img.thumbnail(PROFILE_PICTURE_SIZE, Image.Resampling.LANCZOS)

            # Center crop to square if needed
            if img.size[0] != img.size[1]:
                min_dim = min(img.size)
                left = (img.size[0] - min_dim) // 2
                top = (img.size[1] - min_dim) // 2
                right = left + min_dim
                bottom = top + min_dim
                img = img.crop((left, top, right, bottom))

            # Save as JPEG with good quality
            img.save(save_path, "JPEG", quality=85, optimize=True)

    except Exception as e:
        raise ValueError(f"Failed to process image: {str(e)}")

    # Return relative path for database storage
    relative_path = f"profile_pictures/{user_id}/{new_filename}"
    return relative_path


def delete_profile_picture(relative_path: str) -> bool:
    """
    Delete a profile picture file.

    Args:
        relative_path: Relative path to the file

    Returns:
        True if deleted successfully, False otherwise
    """
    if not relative_path:
        return False

    full_path = Path(UPLOAD_BASE_PATH) / relative_path

    try:
        if full_path.exists():
            full_path.unlink()
            return True
    except Exception as e:
        print(f"Failed to delete file {full_path}: {e}")

    return False


def get_profile_picture_url(relative_path: Optional[str]) -> Optional[str]:
    """
    Get the full URL for a profile picture.

    Args:
        relative_path: Relative path to the file

    Returns:
        Full URL path, or None if no picture
    """
    if not relative_path:
        return None

    # Return path relative to uploads directory
    # In production, this would be served by nginx or a CDN
    return f"/uploads/{relative_path}"
