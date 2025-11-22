"""API client for StreamScene server communication

Handles all communication with the StreamScene API:
- Fetching content to display
- Sending heartbeats
- Getting device configuration
- Retry logic and error handling
"""

import time
from typing import Optional, Dict, Any
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config


class StreamSceneAPIClient:
    """Client for StreamScene API communication."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        device_id: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize API client.

        Args:
            base_url: API base URL (default: from config)
            device_id: Device UUID (default: from config)
            api_key: API key for authentication (default: from config)
        """
        self.base_url = (base_url or config.API_BASE_URL).rstrip("/")
        self.device_id = device_id or config.DEVICE_ID
        self.api_key = api_key or config.API_KEY

        if not self.device_id:
            raise ValueError("Device ID is required")

        # API key is optional during setup phase (before registration)
        # Methods requiring authentication will fail gracefully if missing
        # This allows polling for registration status without credentials

        # Create session with retry logic
        self.session = self._create_session()

        print(f"[API Client] Initialized for device {self.device_id}")
        print(f"[API Client] API URL: {self.base_url}")
        if self.api_key:
            print(f"[API Client] API key: present")
        else:
            print(f"[API Client] API key: not set (setup mode)")

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic.

        Returns:
            Configured requests.Session
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=config.RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        headers = {"User-Agent": "StreamScene-Client/1.0"}

        # Only add API key if present (allows unauthenticated calls during setup)
        if self.api_key:
            headers["X-Device-Api-Key"] = self.api_key

        session.headers.update(headers)

        return session

    def fetch_content(self, rotation_index: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Fetch current content to display from the API.

        Args:
            rotation_index: Optional rotation index for content rotation mode

        Returns:
            Dict with content data, or None if request fails

        Response format:
            {
                "content_type": "text",
                "text_content": "Message text",
                "image_url": null,
                "posted_at": "2025-11-02T12:00:00Z",
                "stream_name": "Family Updates",
                "has_content": true
            }
        """
        url = f"{self.base_url}/api/devices/{self.device_id}/content"

        # Add rotation_index as query parameter if provided
        params = {}
        if rotation_index is not None:
            params['rotation_index'] = rotation_index
            print(f"[API Client] Fetching content (rotation_index={rotation_index})")

        try:
            print(f"[API Client] Fetching content from {url}")
            response = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            print(f"[API Client] Content received: {data.get('stream_name', 'Unknown')}")

            return data

        except requests.exceptions.RequestException as e:
            print(f"[API Client] Error fetching content: {e}")
            return None

    def fetch_content_image(self, rotation_index: Optional[int] = None) -> Optional['Image.Image']:
        """
        Fetch pre-rendered content image from the API.

        Args:
            rotation_index: Optional rotation index for content rotation mode

        Returns:
            PIL Image object, or None if request fails
        """
        from PIL import Image
        import io

        url = f"{self.base_url}/api/devices/{self.device_id}/content/image"

        # Add rotation_index as query parameter if provided
        params = {}
        if rotation_index is not None:
            params['rotation_index'] = rotation_index

        try:
            print(f"[API Client] Fetching rendered image from {url}")
            response = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            # Load image from response bytes
            image = Image.open(io.BytesIO(response.content))
            print(f"[API Client] Image received ({image.width}x{image.height}, {image.mode})")

            return image

        except requests.exceptions.RequestException as e:
            print(f"[API Client] Error fetching image: {e}")
            return None
        except Exception as e:
            print(f"[API Client] Error loading image: {e}")
            return None

    def send_heartbeat(self) -> bool:
        """
        Send heartbeat to indicate device is online.

        Returns:
            True if heartbeat sent successfully, False otherwise
        """
        url = f"{self.base_url}/api/devices/{self.device_id}/heartbeat"

        try:
            print(f"[API Client] Sending heartbeat to {url}")
            response = self.session.post(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            print(f"[API Client] Heartbeat sent: {data.get('status', 'unknown')}")

            return True

        except requests.exceptions.RequestException as e:
            print(f"[API Client] Error sending heartbeat: {e}")
            return False

    def get_config(self) -> Optional[Dict[str, Any]]:
        """
        Get device configuration from the API.

        Returns:
            Dict with configuration, or None if request fails

        Response format:
            {
                "device_id": "uuid",
                "nickname": "My Frame",
                "current_stream_id": "uuid",
                "rotation_enabled": false,
                "rotation_interval": 60,
                "current_version": "1.0.0",
                "config": {}
            }
        """
        url = f"{self.base_url}/api/devices/{self.device_id}/config"

        try:
            print(f"[API Client] Fetching config from {url}")
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            print(f"[API Client] Config received for {data.get('nickname', 'Unknown')}")

            return data

        except requests.exceptions.RequestException as e:
            print(f"[API Client] Error fetching config: {e}")
            return None

    # Alias for compatibility with registration code
    def fetch_config(self) -> Optional[Dict[str, Any]]:
        """Alias for get_config(). Used during registration polling."""
        return self.get_config()

    def health_check(self) -> bool:
        """
        Check if API server is reachable.

        Returns:
            True if server is healthy, False otherwise
        """
        url = f"{self.base_url}/api/health"

        try:
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            return data.get("status") == "ok"

        except requests.exceptions.RequestException:
            return False

    def wait_for_server(self, max_attempts: int = 10, delay: int = 5) -> bool:
        """
        Wait for API server to become available.

        Args:
            max_attempts: Maximum number of connection attempts
            delay: Delay between attempts in seconds

        Returns:
            True if server became available, False if all attempts failed
        """
        print(f"[API Client] Waiting for server at {self.base_url}...")

        for attempt in range(1, max_attempts + 1):
            if self.health_check():
                print(f"[API Client] Server is healthy")
                return True

            print(f"[API Client] Attempt {attempt}/{max_attempts} failed, retrying in {delay}s...")
            time.sleep(delay)

        print(f"[API Client] Server not available after {max_attempts} attempts")
        return False

    def check_registration_status(self) -> Optional[Dict[str, Any]]:
        """
        Check device registration status (unauthenticated).

        This endpoint does not require API key authentication.
        Used during setup to detect when device has been registered.

        Returns:
            Dict with registration status:
            {
                "is_registered": bool,
                "api_key": str or None,
                "nickname": str or None
            }
            Returns None if request fails.
        """
        url = f"{self.base_url}/api/devices/{self.device_id}/registration-status"

        try:
            print(f"[API Client] Checking registration status...")
            # Use a temporary session without API key for this unauthenticated request
            response = requests.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            print(f"[API Client] Registration check: is_registered={data.get('is_registered')}")

            return data

        except requests.exceptions.RequestException as e:
            print(f"[API Client] Error checking registration status: {e}")
            return None


if __name__ == "__main__":
    # Test API client
    import sys

    try:
        client = StreamSceneAPIClient()

        print("\n=== Testing API Health ===")
        if client.health_check():
            print("✓ API server is healthy")
        else:
            print("✗ API server is not reachable")
            sys.exit(1)

        print("\n=== Testing Content Fetch ===")
        content = client.fetch_content()
        if content:
            print(f"✓ Content fetched:")
            print(f"  Stream: {content.get('stream_name')}")
            print(f"  Has content: {content.get('has_content')}")
            print(f"  Text: {content.get('text_content', 'N/A')[:50]}...")
        else:
            print("✗ Failed to fetch content")

        print("\n=== Testing Heartbeat ===")
        if client.send_heartbeat():
            print("✓ Heartbeat sent")
        else:
            print("✗ Failed to send heartbeat")

        print("\n=== Testing Config Fetch ===")
        device_config = client.get_config()
        if device_config:
            print(f"✓ Config fetched:")
            print(f"  Nickname: {device_config.get('nickname')}")
            print(f"  Stream ID: {device_config.get('current_stream_id')}")
        else:
            print("✗ Failed to fetch config")

    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("\nSet required environment variables:")
        print("  export STREAMSCENE_DEVICE_ID='your-device-uuid'")
        print("  export STREAMSCENE_API_KEY='your-api-key'")
        sys.exit(1)
