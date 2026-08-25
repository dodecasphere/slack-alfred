import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOKEN = "xoxp-already-configured"


class SetupWithAnExistingTokenTests(unittest.TestCase):
    """Re-running setup.sh should not march the user through Slack again."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.install = os.path.join(self.tmp, "install")
        os.makedirs(self.install)
        for name in ("setup.sh", "config.example.json"):
            shutil.copy(os.path.join(REPO_ROOT, name), self.install)
        shutil.copytree(
            os.path.join(REPO_ROOT, "tools"), os.path.join(self.install, "tools")
        )
        shutil.copy(
            os.path.join(REPO_ROOT, "slack-app-manifest.json"), self.install
        )
        self.config = os.path.join(self.install, "config.json")

    def write_token(self, token):
        with open(self.config, "w") as f:
            json.dump({"token": token, "statuses": []}, f)

    def run_setup(self, *flags):
        # SLACK_ALFRED_NO_BUILD stops before build.sh so the test never touches
        # Alfred, launchd, or the network.
        return subprocess.run(
            ["bash", os.path.join(self.install, "setup.sh"), *flags],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            start_new_session=True,
            env={**os.environ, "SLACK_ALFRED_NO_BUILD": "1", "HOME": self.tmp},
        )

    def test_skips_the_walkthrough_when_a_token_is_already_configured(self):
        self.write_token(TOKEN)
        result = self.run_setup()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("Press Enter to open", result.stdout)
        self.assertIn("--reconfigure", result.stdout)

    def test_keeps_the_existing_token(self):
        self.write_token(TOKEN)
        self.run_setup()
        with open(self.config) as f:
            self.assertEqual(TOKEN, json.load(f)["token"])

    def test_reconfigure_wants_the_walkthrough_again(self):
        self.write_token(TOKEN)
        result = self.run_setup("--reconfigure")
        # Nothing to type into here, so wanting the walkthrough shows up as the
        # "needs a terminal" refusal rather than a clean skip-and-build.
        self.assertNotEqual(0, result.returncode)
        self.assertIn("terminal", result.stderr.lower())

    def test_placeholder_token_still_wants_the_walkthrough(self):
        self.write_token("xoxp-YOUR-TOKEN-HERE")
        result = self.run_setup()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("terminal", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
