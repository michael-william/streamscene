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

import os
import sys
import time
import signal
import subprocess
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
from setup.network import NetworkManager
from services import ConfigurationService, OTAService

# Import centralized logging configuration
from logging_config import (
    log_startup_info,
    main_logger,
    state_logger,
    api_logger,
    display_logger,
    network_logger,
    wifi_logger,
    registration_logger,
    ota_logger,
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

        # Network (connectivity, hotspot/portal setup flow, registration polling)
        self.network = NetworkManager(device_uuid=DEVICE_ID)
        main_logger.info("Network manager initialized")

        # API client (may not be usable until device is registered)
        self.api_client = StreamSceneAPIClient()
        api_logger.info("API client initialized")

        # Configuration service (business logic for config management)
        self.config_service = ConfigurationService(
            api_client=self.api_client
        )
        self.config_service.initialize()
        main_logger.info("Configuration service initialized")

        # OTA service (handles over-the-air updates)
        self.ota_service = OTAService(
            api_client=self.api_client,
            config_service=self.config_service,
        )
        self.ota_service.initialize()
        ota_logger.info("OTA service initialized")

        # Display and rendering
        self.renderer = ContentRenderer()
        self.display = get_display()
        display_logger.info("Display and renderer initialized")

        # Runtime state
        self.running = False
        self.loop_count = 0
        self.last_heartbeat = 0

        # Content tracking for smart refresh
        self.last_displayed_post_id = None
        self.rotation_index = 0

        main_logger.info("Initialization complete")

        # Fetch device configuration if registered (has API key)
        self._fetch_initial_config()

        # Check initial network status and skip WiFi setup if ethernet is available
        self._check_initial_network_status()

        # Check for pending OTA update verification (after reboot)
        self._check_ota_pending_verification()

    def _check_ota_pending_verification(self):
        """
        Check for pending OTA update verification after reboot.

        If an update was installed before the last reboot, verify it succeeded
        and report status to server. Rollback if verification fails.
        """
        pending = self.ota_service.check_pending_verification()
        if not pending:
            return

        ota_logger.info(f"Pending update verification: v{pending.get('update_version')}")

        if self.ota_service.verify_boot_success():
            ota_logger.info("Boot verification passed, completing update")
            self.ota_service.complete_pending_verification()
        else:
            ota_logger.warning("Boot verification failed, rolling back")
            self.ota_service.rollback_pending_update("Boot verification failed")

    def _check_mandatory_updates(self):
        """
        Check for and install mandatory updates.

        Called before normal operation. Mandatory updates must be installed
        immediately before displaying any content.

        Returns:
            True if device should continue to normal operation
            False if reboot is needed after mandatory update
        """
        if not API_KEY and not load_api_key():
            # Not registered yet, can't check for updates
            return True

        ota_logger.info("Checking for mandatory updates...")
        result = self.ota_service.handle_mandatory_update()

        if result.needs_reboot:
            ota_logger.info(f"Mandatory update v{result.version} installed, rebooting...")
            self.ota_service.trigger_reboot()
            return False

        if result.update_installed:
            ota_logger.warning(f"Mandatory update failed: {result.error}")

        return True

    def _check_ota_updates(self):
        """
        Check for OTA updates periodically.

        Called during normal operation (READY state).
        Non-mandatory updates are installed with reboot.
        """
        if not self.ota_service.should_check_for_updates():
            return

        ota_logger.info("Periodic OTA update check...")
        result = self.ota_service.run_update_cycle()

        if result.needs_reboot:
            ota_logger.info(f"Update v{result.version} installed, rebooting...")
            self.ota_service.trigger_reboot()
        elif result.error:
            ota_logger.warning(f"Update check failed: {result.error}")

    def _fetch_initial_config(self):
        """
        Fetch device configuration on startup if device is registered.

        Delegates to ConfigurationService.
        Note: config_service.initialize() already calls this, so this is a no-op.
        """
        # ConfigurationService already fetched config during initialization
        pass

    def _refresh_config_if_needed(self):
        """
        Refresh device configuration periodically.

        Delegates to ConfigurationService and resets rotation_index if rotation settings changed.
        """
        # Store old config for comparison
        old_config = self.config_service.config

        # Refresh config (service handles TTL, API calls, and change logging)
        new_config = self.config_service.refresh_if_needed()

        # Reset rotation index if rotation settings changed
        if old_config and new_config and old_config != new_config:
            # Reset if rotation_enabled changed
            if old_config.rotation_enabled != new_config.rotation_enabled:
                main_logger.info("[Config] Resetting rotation index (rotation mode changed)")
                self.rotation_index = 0
            # Reset if rotation_post_count changed
            elif old_config.rotation_post_count != new_config.rotation_post_count:
                main_logger.info("[Config] Resetting rotation index (post count changed)")
                self.rotation_index = 0

    def _check_initial_network_status(self):
        """
        Check network status at startup and skip WiFi setup if network is available.

        Uses NetworkManager to check connectivity.
        If ethernet or WiFi is available, skip WiFi setup and go to registration.
        """
        current_state = self.state_machine.current_state

        # Only check network if currently in WIFI_SETUP or CONNECTING state
        if current_state not in [DeviceState.WIFI_SETUP, DeviceState.CONNECTING]:
            main_logger.debug("[Network] Skipping initial network check (not in setup state)")
            return

        main_logger.info("[Network] Checking initial network status...")

        # Use NetworkManager to check connectivity
        status = self.network.check_initial_connectivity()

        if status.connected:
            main_logger.info(f"[Network] {status.connection_type.upper()} connected: {status.ip_address}")
            main_logger.info("[Network] Skipping WiFi setup, transitioning to AWAITING_REGISTRATION")

            # Transition directly to registration
            if self.state_machine.transition_to(
                DeviceState.AWAITING_REGISTRATION,
                state_data={
                    "connection_type": status.connection_type,
                    "ip_address": status.ip_address
                }
            ):
                main_logger.info(f"[Network] Successfully transitioned to AWAITING_REGISTRATION via {status.connection_type}")
            else:
                main_logger.warning("[Network] Failed to transition state, will continue normally")
        else:
            main_logger.info("[Network] No network connectivity available")
            main_logger.info("[Network] Will proceed with WiFi setup")

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
        wifi_logger.info("Starting WiFi credential capture")
        state_logger.info("Entering WIFI_SETUP state")

        # Check if we can skip WiFi setup (ethernet or saved credentials)
        check_result = self.network.check_network_and_credentials()

        if check_result.should_skip_wifi_setup:
            if check_result.connection_type == "ethernet":
                # Use ethernet directly
                wifi_logger.info("Using ethernet connection - skipping WiFi setup")
                state_logger.info("Transitioning to AWAITING_REGISTRATION via ethernet")
                self.state_machine.transition_to(DeviceState.AWAITING_REGISTRATION, state_data={
                    "connection_type": "ethernet",
                    "ip_address": check_result.ip_address
                })
                return
            elif check_result.connection_type == "saved_wifi":
                # Use saved credentials
                wifi_logger.info(f"Using saved credentials for: {check_result.credentials['ssid']}")
                state_logger.info("Transitioning to CONNECTING with saved credentials")
                self.state_machine.transition_to(DeviceState.CONNECTING, check_result.credentials)
                return

        # No saved credentials - run full WiFi setup flow
        wifi_logger.info("No ethernet or saved credentials - starting WiFi setup flow")

        # Display message on E Ink
        display_logger.info("Rendering WiFi setup message")
        image = self.renderer.render_message(
            "WiFi Setup",
            "Connect to the WiFi hotspot:\n\nStreamScene-XXXX\n\nPassword: streamscene\n\nA setup page will open automatically."
        )
        self.display.show(image)
        display_logger.info("WiFi setup message displayed")

        # Run WiFi setup flow
        credentials = self.network.run_wifi_setup_flow(timeout=1800)

        if credentials:
            wifi_logger.info(f"Successfully obtained credentials for SSID: {credentials['ssid']}")
            state_logger.info("Transitioning to CONNECTING state")
            self.state_machine.transition_to(DeviceState.CONNECTING, credentials)
        else:
            wifi_logger.error("WiFi setup failed")
            state_logger.error("Transitioning to ERROR state")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "WiFi setup timeout or failure"
            })

    def _handle_connecting(self):
        """Handle CONNECTING state - attempt to connect to WiFi."""
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

        # Connect to WiFi
        success, ip_address, error_reason = self.network.connect_to_wifi(
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
            wifi_logger.error(f"Failed to connect to {ssid} (reason: {error_reason})")
            state_logger.error("WiFi connection failed, returning to WIFI_SETUP")
            self.state_machine.transition_to(DeviceState.WIFI_SETUP)

    def _handle_awaiting_registration(self):
        """Handle AWAITING_REGISTRATION state - show QR code and poll.

        Registration cannot proceed without a working network path to the API.
        Verify that first: showing a QR code while offline tells the user
        everything is fine when nothing is, and there is no other channel on an
        E Ink device to correct that impression.
        """
        state_logger.info("Entering AWAITING_REGISTRATION state")
        registration_logger.info("Waiting for device registration")

        from setup.wifi_client import is_connected, is_online

        if not (is_connected() and is_online()):
            registration_logger.warning(
                "Cannot register while offline - returning to WIFI_SETUP so the "
                "hotspot comes back and the device stays reachable"
            )
            # Set aside the saved credentials first. WIFI_SETUP skips the
            # hotspot entirely when credentials exist, so falling back with them
            # still in place just retries the same failing network forever and
            # never opens a hotspot - leaving no way to reach the device at all.
            self._quarantine_wifi_credentials()
            self._show_offline_notice()
            # Check the result. transition_to() returns False for a transition
            # the state machine does not allow, and ignoring that silently
            # re-enters this state on the next loop - an invisible spin that
            # redraws the panel every ~20s and never reaches the hotspot code.
            if not self.state_machine.transition_to(DeviceState.WIFI_SETUP, {
                "reason": "no network in AWAITING_REGISTRATION"
            }):
                state_logger.error(
                    "Transition AWAITING_REGISTRATION -> WIFI_SETUP was rejected "
                    "by the state machine; falling back to ERROR to recover "
                    "rather than spinning in place"
                )
                self.state_machine.transition_to(DeviceState.ERROR, {
                    "error": "Offline while awaiting registration"
                })
            # Give the panel a rest: an E Ink refresh is ~30s and has a finite
            # lifetime, so do not let a recovery path redraw it in a tight loop.
            time.sleep(30)
            return

        # Get registration URL from service
        registration_url = self.network.get_registration_url()
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

        # Poll for registration (service handles polling logic)
        #
        # The timeout is deliberately short relative to how long someone may
        # take to register. Do NOT treat expiry as a fatal error: a user who
        # plugs the frame in and registers an hour later is a normal case, and
        # dropping to ERROR leaves a QR code on screen with no poll behind it -
        # indistinguishable from a working device. Expiry simply re-enters this
        # state, which re-checks connectivity and resumes polling.
        registration_logger.info("Starting registration polling (10 minute cycle, 10 second interval)")
        success = self.network.run_registration_flow(
            api_client=self.api_client,
            poll_interval=10,
            timeout=600
        )

        if success:
            registration_logger.info("Device successfully registered!")
            state_logger.info("Transitioning to REGISTERED state")
            self.state_machine.transition_to(DeviceState.REGISTERED)
        else:
            registration_logger.info(
                "No registration yet after this polling cycle - re-checking "
                "connectivity and continuing to wait"
            )
            self.state_machine.transition_to(DeviceState.AWAITING_REGISTRATION, {
                "reason": "registration poll cycle elapsed, retrying"
            })

    def _quarantine_wifi_credentials(self):
        """Move saved WiFi credentials aside so WIFI_SETUP opens the hotspot.

        Kept (not deleted) as wifi_credentials.json.failed for diagnosis.
        """
        from setup.wifi_client import WIFI_CONFIG_FILE

        try:
            if WIFI_CONFIG_FILE.exists():
                failed = WIFI_CONFIG_FILE.with_suffix(".json.failed")
                WIFI_CONFIG_FILE.replace(failed)
                wifi_logger.warning(
                    "Saved WiFi credentials did not yield a working connection; "
                    "moved to %s so setup can capture new ones", failed
                )
        except Exception as e:
            wifi_logger.error("Could not quarantine WiFi credentials: %s", e)

    def _show_offline_notice(self):
        """Tell the user on the panel that the device cannot reach the server.

        Without this the display keeps showing whatever was drawn last, which
        during setup is a QR code implying success.
        """
        try:
            image = self.renderer.render_message(
                title="No Network",
                message=(
                    "Could not reach StreamScene.\n\n"
                    "Reconnect to the StreamScene-XXXX\n"
                    "WiFi network to set up again."
                ),
            )
            self.display.show(image)
        except Exception as e:
            display_logger.warning("Could not render offline notice: %s", e)

    def _handle_registered(self):
        """Handle REGISTERED state - device just got registered."""
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

    def _attempt_network_recovery(self):
        """
        Attempt to recover network connection without changing device state.

        Delegates to NetworkManager for actual recovery logic.
        Stays in READY state to preserve registration.

        Returns:
            Tuple of (success: bool, error_reason: Optional[str])
        """
        return self.network.attempt_recovery()

    def _handle_ready(self):
        """Handle READY state - normal operation with smart refresh. Stay in READY even if offline."""
        state_logger.info("Entering READY state")

        # Validate that we have API key
        if not API_KEY and not load_api_key():
            api_logger.error("No API key available - cannot fetch content")
            state_logger.error("Missing API key, transitioning to ERROR state")
            self.state_machine.transition_to(DeviceState.ERROR, {
                "error": "Missing API key - device not properly registered"
            })
            return

        # Check for mandatory updates on first entry to READY state
        if not hasattr(self, '_mandatory_update_checked'):
            self._mandatory_update_checked = True
            if not self._check_mandatory_updates():
                # Reboot triggered for mandatory update
                return

        # Track consecutive failures for network recovery
        if not hasattr(self, 'consecutive_failures'):
            self.consecutive_failures = 0

        # Refresh config periodically (every 2 minutes max)
        self._refresh_config_if_needed()

        # Check for OTA updates periodically (every hour by default)
        self._check_ota_updates()

        try:
            # Determine operation mode from config
            rotation_enabled, rotation_interval, rotation_count = self.config_service.get_rotation_settings()

            # Fetch content (with rotation_index if in rotation mode)
            if rotation_enabled:
                api_logger.info(f"Fetching content from server (rotation index: {self.rotation_index})...")
                content = self.api_client.fetch_content(rotation_index=self.rotation_index)
            else:
                api_logger.info("Fetching content from server...")
                content = self.api_client.fetch_content()

            if content:
                # Reset failure counter on successful fetch
                self.consecutive_failures = 0

                # Determine if display refresh is needed
                current_post_id = content.get("post_id")
                should_refresh = False

                if rotation_enabled:
                    # Rotation mode: always refresh to show next post
                    should_refresh = True
                    api_logger.info(f"[Rotation] Displaying post (mode: rotating)")
                else:
                    # Static mode: only refresh if content changed
                    if current_post_id != self.last_displayed_post_id:
                        should_refresh = True
                        api_logger.info(f"[Static] New content detected (post_id: {current_post_id})")
                    else:
                        api_logger.info("[Static] Content unchanged, skipping display refresh")

                # Refresh display if needed
                if should_refresh:
                    # Check if we have a pre-rendered image from the server
                    if content.get("rendered_image_url"):
                        display_logger.info("Downloading pre-rendered image from server")
                        image = self.api_client.fetch_content_image(rotation_index=self.rotation_index)
                        if image:
                            display_logger.info("Displaying server-rendered image on E Ink display")
                            self.display.show(image)
                        else:
                            display_logger.warning("Failed to download rendered image, falling back to local rendering")
                            image = self.renderer.render_content(content)
                            self.display.show(image)
                    else:
                        # Fallback to local rendering for legacy content
                        display_logger.info("Rendering fetched content to image (local)")
                        image = self.renderer.render_content(content)
                        display_logger.info("Displaying image on E Ink display")
                        self.display.show(image)

                    # Update tracking
                    self.last_displayed_post_id = current_post_id

                    # Increment rotation index for next cycle (wraps automatically on server)
                    if rotation_enabled:
                        self.rotation_index = (self.rotation_index + 1) % rotation_count
                        api_logger.info(f"Rotation index advanced to {self.rotation_index}")

                    api_logger.info("Content update complete")
                else:
                    display_logger.info("Display refresh skipped (content unchanged)")

            else:
                # Failed to fetch content
                api_logger.warning("Failed to fetch content from server")
                self.consecutive_failures += 1

                # Check if ethernet is down after first failure - immediate WiFi failover
                if self.consecutive_failures >= 1:
                    # Check if ethernet is down
                    if not self.network.is_ethernet_up():
                        api_logger.info("Ethernet is DOWN - attempting immediate WiFi failover")
                        success, error_reason = self._attempt_network_recovery()

                        if success:
                            # WiFi recovery successful - continue without showing error!
                            api_logger.info("WiFi failover successful - continuing normal operation")
                            self.consecutive_failures = 0
                            self._last_error_reason = None
                            # Don't show error - just continue to next loop
                            return
                        else:
                            # WiFi recovery failed - now show error
                            api_logger.warning(f"WiFi failover failed (reason: {error_reason})")
                            self._last_error_reason = error_reason

                            # Handle wrong WiFi credentials - transition to WiFi setup
                            if error_reason == "wrong_credentials":
                                api_logger.error("Wrong WiFi credentials detected - clearing credentials and entering WiFi setup mode")
                                self.network.clear_saved_credentials()

                                # Render message before state transition
                                display_logger.info("Rendering WiFi credentials error message")
                                image = self.renderer.render_error(
                                    "Wrong WiFi password.\n\nEntering WiFi setup mode..."
                                )
                                self.display.show(image)
                                time.sleep(5)  # Give user time to see message

                                # Transition to WiFi setup
                                state_logger.info("Transitioning to WIFI_SETUP state due to wrong credentials")
                                self.state_machine.transition_to(DeviceState.WIFI_SETUP, {
                                    "reason": "wrong_credentials"
                                })
                                return

                            # Render error message for other failures
                            display_logger.info("Rendering error message")
                            error_message = "Unable to fetch content. Check network connection."

                            # Customize error message based on error reason
                            if self._last_error_reason == "network_not_found":
                                error_message = "WiFi network not found.\n\nCheck if router is online."
                            elif self._last_error_reason == "timeout":
                                error_message = "WiFi connection timeout.\n\nCheck network signal."

                            image = self.renderer.render_error(error_message)
                            self.display.show(image)
                    else:
                        # Ethernet still up - wait for 2nd failure before showing error
                        if self.consecutive_failures >= 2:
                            # Network issue but ethernet is up - show generic error
                            display_logger.info("Rendering error message (ethernet up, likely server issue)")
                            image = self.renderer.render_error("Unable to fetch content. Check network connection.")
                            self.display.show(image)

            # Send heartbeat if needed
            if time.time() - self.last_heartbeat >= HEARTBEAT_INTERVAL:
                api_logger.info(f"Sending heartbeat to server (interval: {HEARTBEAT_INTERVAL}s)")
                if self.api_client.send_heartbeat():
                    self.last_heartbeat = time.time()
                    api_logger.info("Heartbeat sent successfully")
                else:
                    api_logger.warning("Heartbeat failed - server may be unreachable")

            # Sleep until next poll (use rotation_interval if rotating, else 60s)
            if rotation_enabled:
                poll_interval = rotation_interval
                main_logger.info(f"Sleeping for {poll_interval}s (rotation mode)")
            else:
                poll_interval = 60  # Always check every minute in static mode
                main_logger.info(f"Sleeping for {poll_interval}s (static mode)")

            time.sleep(poll_interval)

        except Exception as e:
            api_logger.error(f"Error during content fetch/display: {e}", exc_info=True)
            # Don't transition to error state for transient failures
            # Just log and retry on next loop
            main_logger.info("Retrying in 60s")
            time.sleep(60)

    def _handle_error(self):
        """Handle ERROR state - display error and attempt recovery with enhanced logging."""
        state_logger.info("Entering ERROR state")
        state_data = self.state_machine.get_all_state_data()
        error = state_data.get("error", "Unknown error")
        previous_state = state_data.get("previous_state", "unknown")
        reason = state_data.get("reason", "")

        main_logger.error(f"Error occurred: {error}")
        main_logger.info(f"Previous state: {previous_state}")
        if reason:
            main_logger.info(f"Error reason: {reason}")

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

        # Recovery logic based on error reason or error message
        if reason == "network_lost" or "wifi" in error.lower() or "network" in error.lower():
            main_logger.info("Network-related error detected - restarting WiFi setup")
            state_logger.info("Transitioning to WIFI_SETUP for network recovery")

            self.state_machine.transition_to(DeviceState.WIFI_SETUP, {
                "recovery_from": "error",
                "original_error": error
            })
        elif "registration" in error.lower():
            main_logger.info("Registration-related error detected - showing QR code again")
            state_logger.info("Transitioning to AWAITING_REGISTRATION for recovery")
            self.state_machine.transition_to(DeviceState.AWAITING_REGISTRATION)
        elif "api key" in error.lower():
            main_logger.info("API key error detected - returning to registration")
            state_logger.info("Transitioning to AWAITING_REGISTRATION for re-registration")
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
            if self.network.is_in_ap_mode():
                network_logger.info("Stopping active hotspot")
                self.network.stop_hotspot()
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
