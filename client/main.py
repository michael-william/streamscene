"""StreamScene E Ink Client - Main Loop

This is the main entry point for the StreamScene client.
It runs continuously, fetching content from the API and displaying it on the E Ink screen.

Usage:
    # Set environment variables
    export STREAMSCENE_API_URL="http://your-server:8000"
    export STREAMSCENE_DEVICE_ID="your-device-uuid"
    export STREAMSCENE_API_KEY="your-api-key"

    # Run in headless mode (testing)
    python main.py

    # Run on Raspberry Pi with E Ink (after hardware setup)
    export STREAMSCENE_DISPLAY_MODE="eink"
    sudo python main.py  # sudo required for GPIO access
"""

import sys
import time
import signal
from typing import Optional

from .config import validate_config, POLL_INTERVAL, HEARTBEAT_INTERVAL
from .api_client import StreamSceneAPIClient
from .display import get_display
from .renderer import ContentRenderer


class StreamSceneClient:
    """Main client application."""

    def __init__(self):
        """Initialize client."""
        print("=" * 60)
        print("StreamScene E Ink Client v1.0.0")
        print("=" * 60)

        # Validate configuration
        try:
            validate_config()
            print("✓ Configuration validated")
        except ValueError as e:
            print(f"✗ Configuration error: {e}")
            sys.exit(1)

        # Initialize components
        print("\n[Client] Initializing components...")

        self.api_client = StreamSceneAPIClient()
        self.renderer = ContentRenderer()
        self.display = get_display()

        self.running = False
        self.loop_count = 0
        self.last_heartbeat = 0

        print("[Client] Initialization complete\n")

    def run(self):
        """Run the main client loop."""
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Wait for API server to be available
        if not self.api_client.wait_for_server():
            print("[Client] Cannot connect to API server. Exiting.")
            return

        print("[Client] Starting main loop...")
        print(f"[Client] Polling interval: {POLL_INTERVAL}s")
        print(f"[Client] Heartbeat interval: {HEARTBEAT_INTERVAL}s")
        print("[Client] Press Ctrl+C to stop\n")

        self.running = True
        self.last_heartbeat = time.time()

        while self.running:
            self.loop_count += 1
            print(f"\n{'=' * 60}")
            print(f"[Client] Loop {self.loop_count}")
            print(f"{'=' * 60}")

            try:
                # Fetch content from API
                content = self.api_client.fetch_content()

                if content:
                    # Render content to image
                    print("[Client] Rendering content...")
                    image = self.renderer.render_content(content)

                    # Display image
                    print("[Client] Displaying image...")
                    self.display.show(image)

                    print("[Client] ✓ Update complete")
                else:
                    # Failed to fetch content - render error
                    print("[Client] Failed to fetch content, showing error...")
                    image = self.renderer.render_error(
                        "Unable to connect to server. Check network connection."
                    )
                    self.display.show(image)

                # Send heartbeat if needed
                if time.time() - self.last_heartbeat >= HEARTBEAT_INTERVAL:
                    print("[Client] Sending heartbeat...")
                    if self.api_client.send_heartbeat():
                        self.last_heartbeat = time.time()
                        print("[Client] ✓ Heartbeat sent")
                    else:
                        print("[Client] ✗ Heartbeat failed")

                # Sleep until next poll
                print(f"[Client] Sleeping for {POLL_INTERVAL}s...")
                time.sleep(POLL_INTERVAL)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[Client] Error in main loop: {e}")
                print(f"[Client] Retrying in {POLL_INTERVAL}s...")
                time.sleep(POLL_INTERVAL)

        print("\n[Client] Shutting down...")
        self._cleanup()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\n[Client] Received signal {signum}, shutting down...")
        self.running = False

    def _cleanup(self):
        """Clean up resources."""
        print("[Client] Cleaning up...")

        try:
            # Put display to sleep
            self.display.sleep()
        except Exception as e:
            print(f"[Client] Error during cleanup: {e}")

        print("[Client] Goodbye!")


def main():
    """Entry point."""
    client = StreamSceneClient()
    client.run()


if __name__ == "__main__":
    main()
