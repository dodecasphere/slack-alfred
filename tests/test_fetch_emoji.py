#!/usr/bin/env python3
"""Tests for fetch_emoji._download_images."""
import importlib.util
import os
import sys
import tempfile
import unittest
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "fetch_emoji",
    os.path.join(os.path.dirname(__file__), "..", "workflow", "fetch_emoji.py"),
)
fe = importlib.util.module_from_spec(_spec)
sys.modules["fetch_emoji"] = fe
_spec.loader.exec_module(fe)

_FAKE_PNG = b"\x89PNG\r\n\x1a\n"  # minimal PNG header bytes


def _mock_urlopen(data=_FAKE_PNG):
    """Return a context manager mock that yields a response with .read() → data."""
    response = mock.MagicMock()
    response.read.return_value = data
    cm = mock.MagicMock()
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return mock.MagicMock(return_value=cm)


class TestDownloadImages(unittest.TestCase):

    def test_downloads_png_and_gif(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            emoji = {
                "rocket": "https://example.com/abc123.png",
                "confetti": "https://example.com/def456.gif",
            }
            with mock.patch.object(fe, "ICON_CACHE", tmpdir), \
                 mock.patch("urllib.request.urlopen", _mock_urlopen()):
                fe._download_images(emoji)

            self.assertTrue(os.path.exists(os.path.join(tmpdir, "rocket.png")))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "confetti.gif")))
            with open(os.path.join(tmpdir, "rocket.png"), "rb") as f:
                self.assertEqual(f.read(), _FAKE_PNG)

    def test_skips_already_cached_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = os.path.join(tmpdir, "existing.png")
            with open(dest, "wb") as f:
                f.write(b"original")

            emoji = {"existing": "https://example.com/existing.png"}
            with mock.patch.object(fe, "ICON_CACHE", tmpdir), \
                 mock.patch("urllib.request.urlopen", _mock_urlopen()) as mock_open:
                fe._download_images(emoji)

            mock_open.assert_not_called()
            with open(dest, "rb") as f:
                self.assertEqual(f.read(), b"original")

    def test_continues_after_failed_download(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            emoji = {
                "bad":  "https://example.com/bad.png",
                "good": "https://example.com/good.png",
            }

            call_count = 0
            def flaky_urlopen(url, timeout=None):
                nonlocal call_count
                call_count += 1
                if "bad" in url:
                    raise OSError("network error")
                return _mock_urlopen()()

            with mock.patch.object(fe, "ICON_CACHE", tmpdir), \
                 mock.patch("urllib.request.urlopen", side_effect=flaky_urlopen):
                fe._download_images(emoji)

            self.assertFalse(os.path.exists(os.path.join(tmpdir, "bad.png")))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "good.png")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
