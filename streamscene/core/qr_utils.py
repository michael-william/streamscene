"""QR code generation utilities for StreamScene device registration."""

import io
import os
from typing import Optional
import uuid

import qrcode
from qrcode.image.pil import PilImage


def generate_registration_qr(
    device_uuid: uuid.UUID,
    base_url: Optional[str] = None,
    box_size: int = 10,
    border: int = 4,
) -> bytes:
    """
    Generate a QR code for device registration.

    Args:
        device_uuid: The unique device UUID
        base_url: Base URL of the StreamScene web application.
                 Defaults to FRONTEND_URL from environment or localhost.
        box_size: Size of each QR code box in pixels (default: 10)
        border: Border size in boxes (default: 4, minimum: 4)

    Returns:
        QR code image as PNG bytes

    Example:
        >>> device_uuid = uuid.uuid4()
        >>> qr_bytes = generate_registration_qr(device_uuid)
        >>> with open('device_qr.png', 'wb') as f:
        ...     f.write(qr_bytes)
    """
    # Get base URL from environment or use default
    if base_url is None:
        base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Create registration URL
    # Format: https://streamscene.dataandstories.com/register?device_uuid=xxx
    registration_url = f"{base_url}/register?device_uuid={device_uuid}"

    # Create QR code
    qr = qrcode.QRCode(
        version=1,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=box_size,
        border=border,
    )
    qr.add_data(registration_url)
    qr.make(fit=True)

    # Generate image
    img = qr.make_image(fill_color="black", back_color="white", image_factory=PilImage)

    # Convert to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer.getvalue()


def save_registration_qr(
    device_uuid: uuid.UUID,
    output_path: str,
    base_url: Optional[str] = None,
    box_size: int = 10,
    border: int = 4,
) -> str:
    """
    Generate and save a QR code for device registration.

    Args:
        device_uuid: The unique device UUID
        output_path: Path to save the QR code image (must end in .png)
        base_url: Base URL of the StreamScene web application
        box_size: Size of each QR code box in pixels
        border: Border size in boxes

    Returns:
        Path to the saved QR code image

    Raises:
        ValueError: If output_path doesn't end in .png

    Example:
        >>> device_uuid = uuid.uuid4()
        >>> path = save_registration_qr(device_uuid, "/tmp/device.png")
        >>> print(f"QR code saved to {path}")
    """
    if not output_path.endswith(".png"):
        raise ValueError("Output path must end in .png")

    # Generate QR code
    qr_bytes = generate_registration_qr(
        device_uuid=device_uuid,
        base_url=base_url,
        box_size=box_size,
        border=border,
    )

    # Ensure directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Save to file
    with open(output_path, "wb") as f:
        f.write(qr_bytes)

    return output_path


def get_registration_url(device_uuid: uuid.UUID, base_url: Optional[str] = None) -> str:
    """
    Get the registration URL for a device (without generating QR code).

    Args:
        device_uuid: The unique device UUID
        base_url: Base URL of the StreamScene web application

    Returns:
        Full registration URL

    Example:
        >>> device_uuid = uuid.uuid4()
        >>> url = get_registration_url(device_uuid)
        >>> print(url)
        https://streamscene.dataandstories.com/register?device_uuid=...
    """
    if base_url is None:
        base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    return f"{base_url}/register?device_uuid={device_uuid}"
