#!/usr/bin/env python3
"""Tests for fetch_emoji._download_images."""
import importlib.util
import json
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

SENTINEL = "custom_emoji_images.done"

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
            sentinel = os.path.join(tmpdir, SENTINEL)
            emoji = {
                "rocket":   "https://example.com/abc123.png",
                "confetti": "https://example.com/def456.gif",
            }
            with mock.patch.object(fe, "ICON_CACHE", tmpdir), \
                 mock.patch.object(fe, "CUSTOM_EMOJI_IMAGES_DONE", sentinel), \
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

    def test_sentinel_created_after_main_completes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            cache_file  = os.path.join(tmpdir, "custom_emoji.json")
            sentinel    = os.path.join(tmpdir, SENTINEL)
            icon_cache  = os.path.join(tmpdir, "icons")

            with open(config_file, "w") as f:
                json.dump({"token": "xoxp-fake"}, f)

            api_response = json.dumps({
                "ok": True,
                "emoji": {"myemoji": "https://example.com/myemoji.png"},
            }).encode()

            call_num = [0]
            def fake_urlopen(req_or_url, timeout=None):
                call_num[0] += 1
                cm = mock.MagicMock()
                # First call is emoji.list API, second is image download
                cm.__enter__.return_value.read.return_value = (
                    api_response if call_num[0] == 1 else _FAKE_PNG
                )
                cm.__exit__.return_value = False
                return cm

            with mock.patch.object(fe, "CONFIG_FILE", config_file), \
                 mock.patch.object(fe, "CUSTOM_EMOJI_CACHE", cache_file), \
                 mock.patch.object(fe, "CUSTOM_EMOJI_IMAGES_DONE", sentinel), \
                 mock.patch.object(fe, "ICON_CACHE", icon_cache), \
                 mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
                fe.main()

            self.assertTrue(os.path.exists(sentinel), "sentinel file should exist after main()")
            self.assertTrue(os.path.exists(os.path.join(icon_cache, "myemoji.png")))

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
