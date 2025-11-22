"""Captive portal web server for WiFi setup.

This module provides a simple HTTP server for the WiFi setup captive portal.
NO JAVASCRIPT - pure HTML forms for maximum compatibility.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path
import json
import os
import logging
import threading

from .wifi_client import scan_networks

logger = logging.getLogger(__name__)

# Where to save WiFi credentials
WIFI_CONFIG_FILE = Path.home() / "streamscene-client" / "wifi_credentials.json"


class PortalHandler(BaseHTTPRequestHandler):
    """Handle captive portal HTTP requests."""

    # Class variable to signal when credentials are received
    credentials_received = False
    saved_credentials = {}

    def do_GET(self):
        """Serve setup page or redirect to it."""
        path = self.path.split('?')[0]  # Remove query string

        if path == "/" or path.startswith("/setup") or path == "/index.html":
            # Serve main setup page
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_setup_page().encode('utf-8'))
        elif path == "/success":
            # Success page after credentials submitted
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_success_page().encode('utf-8'))
        else:
            # Redirect all other requests to setup page (captive portal behavior)
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()

    def do_POST(self):
        """Handle WiFi credential submission."""
        if self.path != "/" and not self.path.startswith("/setup"):
            self.send_error(404)
            return

        try:
            # Read POST data
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = parse_qs(post_data)

            # Extract credentials - handle both dropdown and manual entry
            network_select = params.get('network_select', [''])[0].strip()
            manual_ssid = params.get('manual_ssid', [''])[0].strip()
            password = params.get('password', [''])[0]

            # Determine which SSID to use
            if network_select == "__manual__":
                # User selected manual entry
                ssid = manual_ssid
                logger.info(f"Using manual SSID entry: {ssid}")
            else:
                # User selected from dropdown
                ssid = network_select
                logger.info(f"Using selected network: {ssid}")

            if not ssid:
                # Send error page
                self.send_response(400)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(self.get_error_page("WiFi network name is required").encode('utf-8'))
                return

            # Save credentials
            credentials = {
                "ssid": ssid,
                "password": password,
                "configured": True
            }

            # Ensure directory exists
            config_dir = os.path.dirname(WIFI_CONFIG_FILE)
            os.makedirs(config_dir, exist_ok=True)

            # Write to file
            with open(WIFI_CONFIG_FILE, 'w') as f:
                json.dump(credentials, f, indent=2)

            logger.info(f"WiFi credentials saved: SSID={ssid}")

            # Set class variable to signal credentials received
            PortalHandler.credentials_received = True
            PortalHandler.saved_credentials = credentials

            # Redirect to success page
            self.send_response(302)
            self.send_header("Location", "/success")
            self.end_headers()

        except Exception as e:
            logger.error(f"Error processing POST request: {e}")
            self.send_response(500)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_error_page(f"Server error: {str(e)}").encode('utf-8'))

    def get_setup_page(self) -> str:
        """HTML form for WiFi setup (NO JAVASCRIPT)."""
        # Scan available WiFi networks
        networks = scan_networks()

        # Generate network options HTML
        network_options = ""
        if networks:
            logger.info(f"Rendering {len(networks)} networks in dropdown")
            for network in networks:
                ssid = network['ssid']
                signal = network['signal']
                encrypted = network['encrypted']

                # Signal strength indicator (bars)
                if signal >= -50:
                    signal_bars = "▂▄▆█"  # Excellent
                elif signal >= -60:
                    signal_bars = "▂▄▆"   # Good
                elif signal >= -70:
                    signal_bars = "▂▄"    # Fair
                else:
                    signal_bars = "▂"     # Weak

                # Lock icon for encrypted networks
                lock_icon = "🔒" if encrypted else ""

                # Build option display text
                display_text = f"{ssid} {signal_bars} {lock_icon}"
                network_options += f'                <option value="{ssid}">{display_text}</option>\n'
        else:
            logger.warning("No networks found during scan")
            network_options = '                <option value="" disabled>No networks found</option>\n'

        # Add manual entry option
        network_options += '                <option value="__manual__">📝 Enter network name manually</option>\n'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>StreamScene WiFi Setup</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #333;
            font-size: 28px;
            margin-bottom: 10px;
            text-align: center;
        }}
        .subtitle {{
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 16px;
        }}
        .form-group {{
            margin-bottom: 24px;
        }}
        label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
            font-size: 14px;
        }}
        select,
        input[type="text"],
        input[type="password"] {{
            width: 100%;
            padding: 14px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
            font-family: monospace;
        }}
        select:focus,
        input[type="text"]:focus,
        input[type="password"]:focus {{
            outline: none;
            border-color: #667eea;
        }}
        select {{
            cursor: pointer;
            background: white;
        }}
        button {{
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
        }}
        button:active {{
            transform: translateY(0);
        }}
        .note {{
            margin-top: 20px;
            padding: 16px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 4px;
            font-size: 14px;
            color: #555;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 20px;
            font-size: 48px;
        }}
        .hidden {{
            display: none;
        }}
        .info {{
            font-size: 12px;
            color: #888;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🖼️</div>
        <h1>StreamScene WiFi Setup</h1>
        <p class="subtitle">Connect your StreamScene device to your home WiFi network</p>

        <form method="POST" action="/">
            <div class="form-group">
                <label for="network_select">Select WiFi Network</label>
                <select id="network_select" name="network_select" required>
                    <option value="" selected>Choose a network...</option>
{network_options}
                </select>
                <div class="info">
                    Signal strength: ▂▄▆█ (excellent) to ▂ (weak) | 🔒 = Password protected
                </div>
            </div>

            <div class="form-group" id="manual_ssid_group">
                <label for="manual_ssid">Network Name (SSID)</label>
                <input
                    type="text"
                    id="manual_ssid"
                    name="manual_ssid"
                    placeholder="Enter network name manually"
                    autocomplete="off"
                >
                <div class="info">Only needed if you selected "Enter network name manually"</div>
            </div>

            <div class="form-group">
                <label for="password">WiFi Password</label>
                <input
                    type="password"
                    id="password"
                    name="password"
                    placeholder="Enter your WiFi password (leave blank if none)"
                    autocomplete="off"
                >
            </div>

            <button type="submit">Connect to WiFi</button>
        </form>

        <div class="note">
            <strong>Note:</strong> After clicking "Connect to WiFi", your StreamScene device will
            attempt to connect to your network. This may take 10-20 seconds.
            You can then reconnect to your normal WiFi network.
        </div>
    </div>
</body>
</html>
"""

    def get_success_page(self) -> str:
        """Success confirmation page."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WiFi Setup Complete</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        .checkmark {
            font-size: 72px;
            margin-bottom: 20px;
        }
        h1 {
            color: #11998e;
            font-size: 28px;
            margin-bottom: 16px;
        }
        p {
            color: #555;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 16px;
        }
        .steps {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-top: 24px;
            text-align: left;
        }
        .steps h2 {
            font-size: 18px;
            margin-bottom: 12px;
            color: #333;
        }
        .steps ol {
            margin-left: 20px;
        }
        .steps li {
            margin-bottom: 8px;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✓</div>
        <h1>WiFi Credentials Saved!</h1>
        <p>Your StreamScene device is now connecting to your home WiFi network.</p>

        <div class="steps">
            <h2>Next Steps:</h2>
            <ol>
                <li>Disconnect from the StreamScene WiFi network</li>
                <li>Reconnect to your normal WiFi network</li>
                <li>Wait 10-20 seconds for your device to connect</li>
                <li>Your device will display a QR code for registration</li>
            </ol>
        </div>

        <p style="margin-top: 24px; font-size: 14px; color: #888;">
            You can close this page now.
        </p>
    </div>
</body>
</html>
"""

    def get_error_page(self, error_message: str) -> str:
        """Error page."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error - WiFi Setup</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }}
        .error-icon {{
            font-size: 72px;
            margin-bottom: 20px;
        }}
        h1 {{
            color: #eb3349;
            font-size: 28px;
            margin-bottom: 16px;
        }}
        p {{
            color: #555;
            font-size: 16px;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        a {{
            display: inline-block;
            padding: 14px 32px;
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: transform 0.2s;
        }}
        a:hover {{
            transform: translateY(-2px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon">⚠️</div>
        <h1>Error</h1>
        <p>{error_message}</p>
        <a href="/">Try Again</a>
    </div>
</body>
</html>
"""

    def log_message(self, format, *args):
        """Custom logging (suppress default logging, use our logger)."""
        logger.debug(f"{self.address_string()} - {format % args}")


class CaptivePortalServer:
    """Captive portal server with lifecycle management."""

    def __init__(self, port: int = 80):
        """
        Initialize captive portal server.

        Args:
            port: Port to listen on (default: 80 for captive portal behavior)
        """
        self.port = port
        self.server = None
        self.server_thread = None

    def start(self):
        """Start the captive portal server in a background thread."""
        if self.server is not None:
            logger.warning("Server already running")
            return

        # Reset credentials received flag
        PortalHandler.credentials_received = False
        PortalHandler.saved_credentials = {}

        try:
            self.server = HTTPServer(('0.0.0.0', self.port), PortalHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            logger.info(f"✓ Captive portal server started on port {self.port}")
            logger.info(f"  Access at: http://192.168.4.1")
        except Exception as e:
            logger.error(f"Failed to start captive portal server: {e}")
            raise

    def stop(self):
        """Stop the captive portal server."""
        if self.server is None:
            return

        try:
            self.server.shutdown()
            self.server.server_close()
            if self.server_thread:
                self.server_thread.join(timeout=5)
            self.server = None
            self.server_thread = None
            logger.info("✓ Captive portal server stopped")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")

    def is_running(self) -> bool:
        """Check if server is running."""
        return self.server is not None and self.server_thread is not None and self.server_thread.is_alive()

    def has_credentials(self) -> bool:
        """Check if credentials have been received."""
        return PortalHandler.credentials_received

    def get_credentials(self) -> dict:
        """Get saved credentials."""
        return PortalHandler.saved_credentials.copy()


if __name__ == "__main__":
    # Test server
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Starting captive portal server...")
    print("Access at: http://192.168.4.1 (or http://localhost if testing locally)")
    print("Press Ctrl+C to stop")

    server = CaptivePortalServer(port=8080)  # Use 8080 for local testing (80 requires root)
    server.start()

    try:
        import time
        while True:
            time.sleep(1)
            if server.has_credentials():
                print("\n✓ Credentials received!")
                print(f"  SSID: {server.get_credentials()['ssid']}")
                break
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.stop()
