"""StreamScene E Ink Client - State-Driven Main Loop

This is the main entry point for the StreamScene client with Phase 5 state machine.
The device lifecycle is managed through states: wifi_setup → connecting →
awaiting_registration → registered → ready.

Usage:
    # Initial setup (no credentials needed)
    python main.py

    # Device will automatically:
    # 1. Start WiFi hotspot if no credentials
    # 2. Show captive portal for WiFi setup
    # 3. Connect to WiFi
    # 4. Show QR code for registration
    # 5. Wait for user to scan and register
    # 6. Enter normal operation mode

Environment Variables (optional):
    STREAMSCENE_API_URL - Server URL (default: http://localhost:8000)
    STREAMSCENE_DEVICE_ID - Device UUID (default: read from /boot/firmware/streamscene-device.txt)
    STREAMSCENE_API_KEY - API key (default: saved after registration)
    STREAMSCENE_DISPLAY_MODE - "eink" or "headless" (default: headless)
"""

import sys
import time
import signal
import logging
from typing import Optional
from pathlib import Path

from .config import (
    validate_config,
    POLL_INTERVAL,
    HEARTBEAT_INTERVAL,
    DEVICE_ID,
    API_KEY,
    save_api_key,
    load_api_key,
)
from .api_client import StreamSceneAPIClient
from .display import get_display
from .renderer import ContentRenderer
from .states import StateMachine, DeviceState
from .setup.network_manager import NetworkManager
from .setup.setup_manager import SetupManager
from .setup.registration import get_registration_url

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class StreamSceneClient:
    """Main client application with state machine."""

    def __init__(self):
        """Initialize client."""
        print("=" * 60)
        print("StreamScene E Ink Client v1.0.0 (Phase 5)")
        print("=" * 60)

        # Validate basic configuration (device UUID required, API key optional)
        try:
            validate_config(require_api_key=False)
            print("✓ Configuration validated")
        except ValueError as e:
            print(f"✗ Configuration error: {e}")
            sys.exit(1)

        # Initialize components
        print("\n[Client] Initializing components...")

        # State machine (loads persisted state or starts at wifi_setup)
        self.state_machine = StateMachine()
        logger.info(f"[Client] Starting in state: {self.state_machine.current_state.value}")

        # Setup components (WiFi, registration)
        self.network_manager = NetworkManager()
        self.setup_manager = SetupManager()

        # API client (may not be usable until device is registered)
        self.api_client = StreamSceneAPIClient()

        # Display and rendering
        self.renderer = ContentRenderer()
        self.display = get_display()

        # Runtime state
        self.running = False
        self.loop_count = 0
        self.last_heartbeat = 0

        print("[Client] Initialization complete\n")

    def run(self):
        """Run the state-driven main loop."""
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print("[Client] Starting state-driven main loop...")
        print("[Client] Press Ctrl+C to stop\n")

        self.running = True

        while self.running:
            self.loop_count += 1
            current_state = self.state_machine.current_state

            print(f"\n{'=' * 60}")
            print(f"[Client] Loop {self.loop_count} - State: {current_state.value}")
            print(f"{'=' * 60}")

            try:
                # State-driven execution
                if current_state == DeviceState.WIFI_SETUP:
                    self._handle_wifi_setup()

                elif current_state == DeviceState.CONNECTING:
                    self._handle_connecting()

                elif current_state == DeviceState.AWAITING_REGISTRATION:
                    self._handle_awaiting_registration()

                elif current_state == DeviceState.REGISTERED:
                    self._handle_registered()

                elif current_state == DeviceState.READY:
                    self._handle_ready()

                elif current_state == DeviceState.ERROR:
                    self._handle_error()

                else:
                    logger.error(f"[Client] Unknown state: {current_state}")
                    self.state_machine.transition_to(DeviceState.ERROR, {
                        "error": "Unknown state",
                        "previous_state": str(current_state)
                    })

            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"[Client] Error in main loop: {e}", exc_info=True)
                self.state_machine.transition_to(DeviceState.ERROR, {
                    "error": str(e),
                    "previous_state": str(current_state)
                })
                time.sleep(10)  # Brief pause before error handling

        print("\n[Client] Shutting down...")
        self._cleanup()

    def _handle_wifi_setup(self):
        """Handle WIFI_SETUP state - create hotspot and run captive portal."""
        logger.info("[WiFi Setup] Starting WiFi credential capture...")

        # Display message on E Ink
        image = self.renderer.render_message(
            "WiFi Setup",
            "Connect to the WiFi hotspot:\n\nStreamScene-XXXX\n\nPassword: streamscene\n\nA setup page will open automatically."
        )
        self.display.show(image)

        # Run WiFi setup flow
        credentials = self.setup_manager.run_wifi_setup(timeout=1800)  # 30 min timeout

        if credentials:
            logger.info(f"[WiFi Setup] Got credentials for SSID: {credentials['ssid']}")
            self.state_machine.transition_to(DeviceState.CONNECTING, credentials)
        else:
            logger.error("[WiFi Setup] Failed to get credentials")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "WiFi setup timeout or failure"
            })

    def _handle_connecting(self):
        """Handle CONNECTING state - attempt to connect to WiFi."""
        state_data = self.state_machine.get_state_data()
        ssid = state_data.get("ssid")
        password = state_data.get("password")

        if not ssid or not password:
            logger.error("[Connecting] No WiFi credentials in state data")
            self.state_machine.transition_to(DeviceState.WIFI_SETUP)
            return

        logger.info(f"[Connecting] Attempting to connect to {ssid}...")

        # Display connecting message
        image = self.renderer.render_message(
            "Connecting to WiFi",
            f"Connecting to:\n{ssid}\n\nPlease wait..."
        )
        self.display.show(image)

        # Switch to client mode and connect
        success, ip_address = self.network_manager.switch_to_client_mode(
            ssid=ssid,
            password=password,
            timeout=30
        )

        if success:
            logger.info(f"[Connecting] Connected! IP: {ip_address}")
            self.state_machine.transition_to(DeviceState.AWAITING_REGISTRATION, {
                "ip_address": ip_address
            })
        else:
            logger.error("[Connecting] Failed to connect to WiFi")
            # Go back to WiFi setup
            self.state_machine.transition_to(DeviceState.WIFI_SETUP)

    def _handle_awaiting_registration(self):
        """Handle AWAITING_REGISTRATION state - show QR code and poll."""
        logger.info("[Registration] Waiting for device registration...")

        # Generate registration URL
        registration_url = get_registration_url(DEVICE_ID)
        logger.info(f"[Registration] URL: {registration_url}")

        # Display QR code
        image = self.renderer.render_qr_code(
            registration_url,
            title="Scan to Register",
            instructions="1. Scan QR code with phone\n2. Log in to StreamScene\n3. Choose a nickname\n4. Click Register"
        )
        self.display.show(image)

        # Poll for registration
        logger.info("[Registration] Polling for registration (30 min timeout)...")
        success = self.setup_manager.run_registration_flow(
            api_client=self.api_client,
            poll_interval=10,  # Check every 10 seconds
            timeout=1800  # 30 minutes
        )

        if success:
            logger.info("[Registration] Device registered!")
            self.state_machine.transition_to(DeviceState.REGISTERED)
        else:
            logger.error("[Registration] Registration timeout")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "Registration timeout - please try again"
            })

    def _handle_registered(self):
        """Handle REGISTERED state - device just got registered."""
        logger.info("[Registered] Device successfully registered!")

        # Try to load API key (should have been saved by registration)
        api_key = load_api_key()

        if not api_key:
            logger.warning("[Registered] No API key found after registration")
            # Try fetching config to get API key (may be in response)
            # For now, transition to ready and let it fail if key is missing
            logger.warning("[Registered] Proceeding without API key - may need manual intervention")

        # Display success message
        image = self.renderer.render_message(
            "Registration Complete!",
            "Your device is now registered.\n\nStarting normal operation...",
            color="green"
        )
        self.display.show(image)

        time.sleep(5)  # Show success message for 5 seconds

        # Mark setup as complete and transition to ready
        self.state_machine.transition_to(DeviceState.READY, {
            "setup_completed_at": time.time()
        })

    def _handle_ready(self):
        """Handle READY state - normal operation."""
        logger.info("[Ready] Fetching and displaying content...")

        # Validate that we have API key
        if not API_KEY and not load_api_key():
            logger.error("[Ready] No API key available")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "Missing API key - device not properly registered"
            })
            return

        try:
            # Fetch content from API
            content = self.api_client.fetch_content()

            if content:
                # Render content to image
                logger.info("[Ready] Rendering content...")
                image = self.renderer.render_content(content)

                # Display image
                logger.info("[Ready] Displaying image...")
                self.display.show(image)

                logger.info("[Ready] ✓ Update complete")
            else:
                # Failed to fetch content - render error
                logger.warning("[Ready] Failed to fetch content")
                image = self.renderer.render_error(
                    "Unable to fetch content. Check network connection."
                )
                self.display.show(image)

            # Send heartbeat if needed
            if time.time() - self.last_heartbeat >= HEARTBEAT_INTERVAL:
                logger.info("[Ready] Sending heartbeat...")
                if self.api_client.send_heartbeat():
                    self.last_heartbeat = time.time()
                    logger.info("[Ready] ✓ Heartbeat sent")
                else:
                    logger.warning("[Ready] ✗ Heartbeat failed")

            # Sleep until next poll
            logger.info(f"[Ready] Sleeping for {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)

        except Exception as e:
            logger.error(f"[Ready] Error: {e}", exc_info=True)
            # Don't transition to error state for transient failures
            # Just log and retry on next loop
            time.sleep(POLL_INTERVAL)

    def _handle_error(self):
        """Handle ERROR state - display error and attempt recovery."""
        state_data = self.state_machine.get_state_data()
        error = state_data.get("error", "Unknown error")
        previous_state = state_data.get("previous_state", "unknown")

        logger.error(f"[Error] Error state: {error}")
        logger.info(f"[Error] Previous state: {previous_state}")

        # Display error on E Ink
        image = self.renderer.render_error(
            f"Error: {error}\n\nAttempting recovery..."
        )
        self.display.show(image)

        # Wait before attempting recovery
        time.sleep(10)

        # Recovery logic based on previous state
        if "wifi" in error.lower() or "network" in error.lower():
            logger.info("[Error] Network error - restarting WiFi setup")
            self.state_machine.transition_to(DeviceState.WIFI_SETUP)
        elif "registration" in error.lower():
            logger.info("[Error] Registration error - showing QR code again")
            self.state_machine.transition_to(DeviceState.AWAITING_REGISTRATION)
        else:
            # Generic error - try to continue from READY state
            logger.info("[Error] Attempting to continue normal operation")
            self.state_machine.transition_to(DeviceState.READY)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"[Client] Received signal {signum}, shutting down...")
        self.running = False

    def _cleanup(self):
        """Clean up resources."""
        logger.info("[Client] Cleaning up...")

        try:
            # Stop any active hotspot
            if self.network_manager.is_in_ap_mode():
                logger.info("[Client] Stopping hotspot...")
                self.network_manager.stop_hotspot()

            # Put display to sleep
            self.display.sleep()
        except Exception as e:
            logger.error(f"[Client] Error during cleanup: {e}")

        logger.info("[Client] Goodbye!")


def main():
    """Entry point."""
    client = StreamSceneClient()
    client.run()


if __name__ == "__main__":
    main()
