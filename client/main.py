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
from typing import Optional
from pathlib import Path

from config import (
    validate_config,
    POLL_INTERVAL,
    HEARTBEAT_INTERVAL,
    DEVICE_ID,
    API_KEY,
    save_api_key,
    load_api_key,
)
from api_client import StreamSceneAPIClient
from display import get_display
from renderer import ContentRenderer
from states import StateMachine, DeviceState
from setup.network_manager import NetworkManager
from setup.setup_manager import SetupManager
from setup.registration import get_registration_url

# Import centralized logging configuration
from logging_config import (
    log_startup_info,
    main_logger,
    state_logger,
    api_logger,
    display_logger,
)


class StreamSceneClient:
    """Main client application with state machine."""

    def __init__(self):
        """Initialize client."""
        # Log startup information
        log_startup_info()
        main_logger.info("StreamScene E Ink Client v1.0.0 (Phase 5)")
        main_logger.info(f"Device UUID: {DEVICE_ID}")

        # Validate basic configuration (device UUID required, API key optional)
        try:
            validate_config(require_api_key=False)
            main_logger.info("Configuration validated successfully")
        except ValueError as e:
            main_logger.error(f"Configuration validation failed: {e}")
            sys.exit(1)

        # Initialize components
        main_logger.info("Initializing components...")

        # State machine (loads persisted state or starts at wifi_setup)
        self.state_machine = StateMachine(device_uuid=DEVICE_ID)
        state_logger.info(f"Starting in state: {self.state_machine.current_state.value}")

        # Setup components (WiFi, registration)
        self.network_manager = NetworkManager(device_uuid=DEVICE_ID)
        main_logger.info("Network manager initialized")

        self.setup_manager = SetupManager(device_uuid=DEVICE_ID, network_manager=self.network_manager)
        main_logger.info("Setup manager initialized")

        # API client (may not be usable until device is registered)
        self.api_client = StreamSceneAPIClient()
        api_logger.info("API client initialized")

        # Display and rendering
        self.renderer = ContentRenderer()
        self.display = get_display()
        display_logger.info("Display and renderer initialized")

        # Runtime state
        self.running = False
        self.loop_count = 0
        self.last_heartbeat = 0

        main_logger.info("Initialization complete")

    def run(self):
        """Run the state-driven main loop."""
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        main_logger.info("Starting state-driven main loop")
        main_logger.info("Press Ctrl+C to stop")

        self.running = True

        while self.running:
            self.loop_count += 1
            current_state = self.state_machine.current_state

            main_logger.info("=" * 60)
            main_logger.info(f"Loop {self.loop_count} - State: {current_state.value}")
            main_logger.info("=" * 60)

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
                    state_logger.error(f"Unknown state: {current_state}")
                    self.state_machine.transition_to(DeviceState.ERROR, {
                        "error": "Unknown state",
                        "previous_state": str(current_state)
                    })

            except KeyboardInterrupt:
                raise
            except Exception as e:
                main_logger.error(f"Error in main loop: {e}", exc_info=True)
                self.state_machine.transition_to(DeviceState.ERROR, {
                    "error": str(e),
                    "previous_state": str(current_state)
                })
                time.sleep(10)  # Brief pause before error handling

        main_logger.info("Shutting down...")
        self._cleanup()

    def _handle_wifi_setup(self):
        """Handle WIFI_SETUP state - create hotspot and run captive portal."""
        from logging_config import wifi_logger

        wifi_logger.info("Starting WiFi credential capture")
        state_logger.info("Entering WIFI_SETUP state")

        # First check if we already have saved credentials
        saved_credentials = self.setup_manager.check_saved_credentials()

        if saved_credentials:
            wifi_logger.info(f"Found saved credentials for SSID: {saved_credentials['ssid']}")
            wifi_logger.info("Skipping hotspot setup, using saved credentials")
            state_logger.info("Transitioning to CONNECTING with saved credentials")
            self.state_machine.transition_to(DeviceState.CONNECTING, saved_credentials)
            return

        # No saved credentials - run full WiFi setup flow
        wifi_logger.info("No saved credentials found")
        wifi_logger.info("Starting hotspot setup flow")

        # Display message on E Ink
        display_logger.info("Rendering WiFi setup message")
        image = self.renderer.render_message(
            "WiFi Setup",
            "Connect to the WiFi hotspot:\n\nStreamScene-XXXX\n\nPassword: streamscene\n\nA setup page will open automatically."
        )
        self.display.show(image)
        display_logger.info("WiFi setup message displayed")

        # Run WiFi setup flow
        wifi_logger.info("Starting WiFi setup flow (30 minute timeout)")
        credentials = self.setup_manager.run_wifi_setup(timeout=1800)  # 30 min timeout

        if credentials:
            wifi_logger.info(f"Successfully obtained credentials for SSID: {credentials['ssid']}")
            state_logger.info("Transitioning to CONNECTING state")
            self.state_machine.transition_to(DeviceState.CONNECTING, credentials)
        else:
            wifi_logger.error("Failed to obtain WiFi credentials (timeout or user error)")
            state_logger.error("WiFi setup failed, transitioning to ERROR state")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "WiFi setup timeout or failure"
            })

    def _handle_connecting(self):
        """Handle CONNECTING state - attempt to connect to WiFi."""
        from logging_config import wifi_logger

        state_logger.info("Entering CONNECTING state")
        state_data = self.state_machine.get_all_state_data()
        ssid = state_data.get("ssid")
        password = state_data.get("password")

        if not ssid or not password:
            wifi_logger.error("No WiFi credentials in state data")
            state_logger.error("Missing credentials, returning to WIFI_SETUP")
            self.state_machine.transition_to(DeviceState.WIFI_SETUP)
            return

        wifi_logger.info(f"Attempting to connect to SSID: {ssid}")

        # Display connecting message
        display_logger.info("Rendering connecting message")
        image = self.renderer.render_message(
            "Connecting to WiFi",
            f"Connecting to:\n{ssid}\n\nPlease wait..."
        )
        self.display.show(image)
        display_logger.info("Connecting message displayed")

        # Switch to client mode and connect
        wifi_logger.info("Switching to WiFi client mode (30 second timeout)")
        success, ip_address = self.network_manager.switch_to_client_mode(
            ssid=ssid,
            password=password,
            timeout=30
        )

        if success:
            wifi_logger.info(f"Successfully connected! IP address: {ip_address}")
            state_logger.info("WiFi connected, transitioning to AWAITING_REGISTRATION")
            self.state_machine.transition_to(DeviceState.AWAITING_REGISTRATION, {
                "ip_address": ip_address
            })
        else:
            wifi_logger.error(f"Failed to connect to {ssid}")
            state_logger.error("WiFi connection failed, returning to WIFI_SETUP")
            # Go back to WiFi setup
            self.state_machine.transition_to(DeviceState.WIFI_SETUP)

    def _handle_awaiting_registration(self):
        """Handle AWAITING_REGISTRATION state - show QR code and poll."""
        from logging_config import registration_logger

        state_logger.info("Entering AWAITING_REGISTRATION state")
        registration_logger.info("Waiting for device registration")

        # Generate registration URL
        registration_url = get_registration_url(DEVICE_ID)
        registration_logger.info(f"Registration URL: {registration_url}")

        # Display QR code
        display_logger.info("Rendering registration QR code")
        image = self.renderer.render_qr_code(
            registration_url,
            title="Scan to Register",
            instructions="1. Scan QR code with phone\n2. Log in to StreamScene\n3. Choose a nickname\n4. Click Register"
        )
        self.display.show(image)
        display_logger.info("QR code displayed")

        # Poll for registration
        registration_logger.info("Starting registration polling (30 minute timeout, 10 second interval)")
        success = self.setup_manager.run_registration_flow(
            api_client=self.api_client,
            poll_interval=10,  # Check every 10 seconds
            timeout=1800  # 30 minutes
        )

        if success:
            registration_logger.info("Device successfully registered!")
            state_logger.info("Transitioning to REGISTERED state")
            self.state_machine.transition_to(DeviceState.REGISTERED)
        else:
            registration_logger.error("Registration timeout - no response from server")
            state_logger.error("Registration failed, transitioning to ERROR state")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "Registration timeout - please try again"
            })

    def _handle_registered(self):
        """Handle REGISTERED state - device just got registered."""
        from logging_config import registration_logger

        state_logger.info("Entering REGISTERED state")
        registration_logger.info("Device successfully registered!")

        # Try to load API key (should have been saved by registration)
        api_key = load_api_key()

        if not api_key:
            registration_logger.warning("No API key found after registration")
            # Try fetching config to get API key (may be in response)
            # For now, transition to ready and let it fail if key is missing
            registration_logger.warning("Proceeding without API key - may need manual intervention")
        else:
            registration_logger.info("API key loaded successfully")

        # Display success message
        display_logger.info("Rendering registration success message")
        image = self.renderer.render_message(
            "Registration Complete!",
            "Your device is now registered.\n\nStarting normal operation...",
            color="green"
        )
        self.display.show(image)
        display_logger.info("Success message displayed")

        registration_logger.info("Showing success message for 5 seconds")
        time.sleep(5)  # Show success message for 5 seconds

        # Mark setup as complete and transition to ready
        state_logger.info("Setup complete, transitioning to READY state")
        self.state_machine.transition_to(DeviceState.READY, {
            "setup_completed_at": time.time()
        })

    def _handle_ready(self):
        """Handle READY state - normal operation."""
        state_logger.info("Entering READY state")
        api_logger.info("Fetching and displaying content")

        # Validate that we have API key
        if not API_KEY and not load_api_key():
            api_logger.error("No API key available - cannot fetch content")
            state_logger.error("Missing API key, transitioning to ERROR state")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "Missing API key - device not properly registered"
            })
            return

        try:
            # Fetch content from API
            api_logger.info("Fetching content from server...")
            content = self.api_client.fetch_content()

            if content:
                # Render content to image
                display_logger.info("Rendering fetched content to image")
                image = self.renderer.render_content(content)

                # Display image
                display_logger.info("Displaying image on E Ink display")
                self.display.show(image)

                api_logger.info("Content update complete")
            else:
                # Failed to fetch content - render error
                api_logger.warning("Failed to fetch content from server")
                display_logger.info("Rendering error message")
                image = self.renderer.render_error(
                    "Unable to fetch content. Check network connection."
                )
                self.display.show(image)

            # Send heartbeat if needed
            if time.time() - self.last_heartbeat >= HEARTBEAT_INTERVAL:
                api_logger.info(f"Sending heartbeat to server (interval: {HEARTBEAT_INTERVAL}s)")
                if self.api_client.send_heartbeat():
                    self.last_heartbeat = time.time()
                    api_logger.info("Heartbeat sent successfully")
                else:
                    api_logger.warning("Heartbeat failed - server may be unreachable")

            # Sleep until next poll
            main_logger.info(f"Sleeping for {POLL_INTERVAL}s until next poll")
            time.sleep(POLL_INTERVAL)

        except Exception as e:
            api_logger.error(f"Error during content fetch/display: {e}", exc_info=True)
            # Don't transition to error state for transient failures
            # Just log and retry on next loop
            main_logger.info(f"Retrying in {POLL_INTERVAL}s")
            time.sleep(POLL_INTERVAL)

    def _handle_error(self):
        """Handle ERROR state - display error and attempt recovery."""
        state_logger.info("Entering ERROR state")
        state_data = self.state_machine.get_all_state_data()
        error = state_data.get("error", "Unknown error")
        previous_state = state_data.get("previous_state", "unknown")

        main_logger.error(f"Error occurred: {error}")
        main_logger.info(f"Previous state: {previous_state}")

        # Display error on E Ink
        display_logger.info("Rendering error message")
        image = self.renderer.render_error(
            f"Error: {error}\n\nAttempting recovery..."
        )
        self.display.show(image)
        display_logger.info("Error message displayed")

        # Wait before attempting recovery
        main_logger.info("Waiting 10 seconds before attempting recovery")
        time.sleep(10)

        # Recovery logic based on previous state
        if "wifi" in error.lower() or "network" in error.lower():
            main_logger.info("Network-related error detected - restarting WiFi setup")
            state_logger.info("Transitioning to WIFI_SETUP for recovery")
            self.state_machine.transition_to(DeviceState.WIFI_SETUP)
        elif "registration" in error.lower():
            main_logger.info("Registration-related error detected - showing QR code again")
            state_logger.info("Transitioning to AWAITING_REGISTRATION for recovery")
            self.state_machine.transition_to(DeviceState.AWAITING_REGISTRATION)
        else:
            # Generic error - try to continue from READY state
            main_logger.info("Generic error - attempting to continue normal operation")
            state_logger.info("Transitioning to READY state for recovery")
            self.state_machine.transition_to(DeviceState.READY)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        main_logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.running = False

    def _cleanup(self):
        """Clean up resources."""
        main_logger.info("Cleaning up resources...")

        try:
            # Stop any active hotspot
            if self.network_manager.is_in_ap_mode():
                from logging_config import network_logger
                network_logger.info("Stopping active hotspot")
                self.network_manager.stop_hotspot()
                network_logger.info("Hotspot stopped successfully")

            # Put display to sleep
            display_logger.info("Putting display to sleep")
            self.display.sleep()
            display_logger.info("Display sleep complete")
        except Exception as e:
            main_logger.error(f"Error during cleanup: {e}", exc_info=True)

        main_logger.info("=" * 60)
        main_logger.info("StreamScene Client Shutdown Complete")
        main_logger.info("=" * 60)


def main():
    """Entry point."""
    client = StreamSceneClient()
    client.run()


if __name__ == "__main__":
    main()
