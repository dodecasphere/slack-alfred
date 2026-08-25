import json
import os
import sys
import unittest
from urllib.parse import parse_qs, urlparse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import manifest_url  # noqa: E402

MANIFEST_PATH = os.path.join(REPO_ROOT, "slack-app-manifest.json")

REQUIRED_USER_SCOPES = {
    "users.profile:write",
    "users.profile:read",
    "users:write",
    "emoji:read",
}


class ManifestFileTests(unittest.TestCase):
    def setUp(self):
        with open(MANIFEST_PATH) as f:
            self.manifest = json.load(f)

    def test_has_a_display_name(self):
        self.assertTrue(self.manifest["display_information"]["name"])

    def test_requests_exactly_the_scopes_the_workflow_needs(self):
        scopes = set(self.manifest["oauth_config"]["scopes"]["user"])
        self.assertEqual(REQUIRED_USER_SCOPES, scopes)

    def test_requests_no_bot_scopes(self):
        self.assertNotIn("bot", self.manifest["oauth_config"]["scopes"])

    def test_declares_no_server_side_features(self):
        settings = self.manifest["settings"]
        self.assertFalse(settings["socket_mode_enabled"])
        self.assertFalse(settings["org_deploy_enabled"])


class CreateAppUrlTests(unittest.TestCase):
    def test_url_targets_slack_new_app_flow(self):
        url = manifest_url.build_create_app_url({"display_information": {"name": "X"}})
        parsed = urlparse(url)
        self.assertEqual("https", parsed.scheme)
        self.assertEqual("api.slack.com", parsed.netloc)
        self.assertEqual("/apps", parsed.path)
        self.assertEqual(["1"], parse_qs(parsed.query)["new_app"])

    def test_manifest_round_trips_through_the_query_string(self):
        manifest = {"display_information": {"name": "Slack Status & Presence"}}
        url = manifest_url.build_create_app_url(manifest)
        encoded = parse_qs(urlparse(url).query)["manifest_json"][0]
        self.assertEqual(manifest, json.loads(encoded))

    def test_repo_manifest_produces_a_usable_url(self):
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        url = manifest_url.build_create_app_url(manifest)
        encoded = parse_qs(urlparse(url).query)["manifest_json"][0]
        self.assertEqual(manifest, json.loads(encoded))


if __name__ == "__main__":
    unittest.main()
