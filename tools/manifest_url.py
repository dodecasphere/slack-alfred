#!/usr/bin/env python3
"""Build the "create a Slack app from this manifest" URL used by setup.sh.

Slack's app-creation page accepts a prefilled manifest via the `manifest_json`
query parameter, so the user lands on a confirmation screen with every scope
already selected instead of clicking through the OAuth settings by hand.
"""

import json
import os
import sys
from urllib.parse import urlencode

NEW_APP_URL = "https://api.slack.com/apps"

DEFAULT_MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "slack-app-manifest.json",
)


def build_create_app_url(manifest):
    """Return the api.slack.com URL that prefills `manifest` in the new-app flow."""
    query = urlencode(
        {"new_app": "1", "manifest_json": json.dumps(manifest, separators=(",", ":"))}
    )
    return "%s?%s" % (NEW_APP_URL, query)


def load_manifest(path=DEFAULT_MANIFEST_PATH):
    with open(path) as f:
        return json.load(f)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MANIFEST_PATH
    print(build_create_app_url(load_manifest(path)))


if __name__ == "__main__":
    main()
