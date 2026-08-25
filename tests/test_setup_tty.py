import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SetupWithoutATerminalTests(unittest.TestCase):
    """`curl | bash` leaves stdin pointing at the pipe, not the keyboard.

    The walkthrough is interactive, so setup.sh must reattach to /dev/tty — and
    when there is no terminal at all, say so instead of dying silently at the
    first `read`.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.install = os.path.join(self.tmp, "install")
        os.makedirs(self.install)
        for name in ("setup.sh", "config.example.json", "slack-app-manifest.json"):
            shutil.copy(os.path.join(REPO_ROOT, name), self.install)
        shutil.copytree(
            os.path.join(REPO_ROOT, "tools"), os.path.join(self.install, "tools")
        )
        with open(os.path.join(self.install, "config.json"), "w") as f:
            json.dump({"token": "xoxp-YOUR-TOKEN-HERE", "statuses": []}, f)

    def run_setup_without_tty(self):
        # start_new_session drops the controlling terminal, so /dev/tty fails to
        # open the same way it would in a truly non-interactive environment.
        return subprocess.run(
            ["bash", os.path.join(self.install, "setup.sh")],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            start_new_session=True,
            env={**os.environ, "SLACK_ALFRED_NO_BUILD": "1", "HOME": self.tmp},
        )

    def test_explains_the_problem_rather_than_exiting_silently(self):
        result = self.run_setup_without_tty()
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode)
        self.assertIn("setup.sh", output)
        self.assertIn("terminal", output.lower())

    def test_does_not_get_as_far_as_opening_the_browser(self):
        result = self.run_setup_without_tty()
        self.assertNotIn("Press Enter to open", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
