import os
import subprocess
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(REPO_ROOT, "setup.sh")


class SetupWithoutATerminalTests(unittest.TestCase):
    """`curl | bash` leaves stdin pointing at the pipe, not the keyboard.

    setup.sh is interactive, so it must reattach to /dev/tty — and when there is
    no terminal at all, say so instead of dying silently at the first `read`.
    """

    def run_setup_without_tty(self):
        # start_new_session drops the controlling terminal, so /dev/tty fails to
        # open the same way it would in a truly non-interactive environment.
        return subprocess.run(
            ["bash", SETUP],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            start_new_session=True,
            cwd=REPO_ROOT,
        )

    def test_explains_the_problem_rather_than_exiting_silently(self):
        result = self.run_setup_without_tty()
        output = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode)
        self.assertIn("setup.sh", output)
        self.assertIn("interactive", output.lower())

    def test_does_not_get_as_far_as_opening_the_browser(self):
        result = self.run_setup_without_tty()
        self.assertNotIn("Press Enter to open", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
