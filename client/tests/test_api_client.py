"""StreamSceneAPIClient key handling."""

import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
