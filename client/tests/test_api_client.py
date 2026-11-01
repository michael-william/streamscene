"""StreamSceneAPIClient key handling."""

import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api_client import StreamSceneAPIClient


class TestSetApiKey(unittest.TestCase):
    def test_key_obtained_after_startup_is_sent(self):
        # Startup in setup mode: no key, so no auth header on the session.
        client = StreamSceneAPIClient(device_id="test-device", api_key="")
        client.api_key = ""
        client.session.headers.pop("X-Device-Api-Key", None)

        client.set_api_key("new-key")

        self.assertEqual(client.api_key, "new-key")
        self.assertEqual(client.session.headers["X-Device-Api-Key"], "new-key")


class TestHeartbeatReportsVersion(unittest.TestCase):
    def test_heartbeat_body_carries_installed_version(self):
        client = StreamSceneAPIClient(device_id="test-device", api_key="k")
        with patch("api_client.config.get_current_version", return_value="1.3.0"), \
             patch.object(client.session, "post") as post:
            post.return_value = MagicMock(status_code=200, json=lambda: {"status": "ok"})
            self.assertTrue(client.send_heartbeat())

        self.assertEqual(post.call_args.kwargs["json"], {"version": "1.3.0"})


if __name__ == "__main__":
    unittest.main()
