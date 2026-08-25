import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNINSTALL = os.path.join(REPO_ROOT, "uninstall.sh")

TOKEN = "xoxp-real-token"


def make_tarball(dest_dir):
    """A stand-in for the GitHub tarball: same layout, --strip-components=1."""
    path = os.path.join(dest_dir, "repo.tar.gz")
    with tarfile.open(path, "w:gz") as tar:
        for name in ("uninstall.sh", "tools"):
            tar.add(os.path.join(REPO_ROOT, name), arcname="slack-alfred-main/" + name)
    return "file://" + path


class RemoteUninstallTests(unittest.TestCase):
    """`curl … | bash` runs uninstall.sh with no repo around it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.tmp, ".config", "slack-alfred")
        os.makedirs(self.config_dir)
        os.makedirs(os.path.join(self.tmp, "Library", "LaunchAgents"))

        self.install = os.path.join(self.tmp, ".local", "share", "slack-alfred")
        os.makedirs(os.path.join(self.install, "icons"))
        open(os.path.join(self.install, "setup.sh"), "w").close()
        with open(os.path.join(self.install, "config.json"), "w") as f:
            json.dump({"token": TOKEN, "statuses": []}, f)
        os.symlink(
            os.path.join(self.install, "config.json"),
            os.path.join(self.config_dir, "config.json"),
        )

        # A copy with no tools/ beside it, the way curl pipes it into bash.
        self.standalone = os.path.join(self.tmp, "piped-uninstall.sh")
        shutil.copy(UNINSTALL, self.standalone)
        self.tarball = make_tarball(self.tmp)

    def run_standalone(self, *flags, stdin=""):
        return subprocess.run(
            ["bash", self.standalone, *flags],
            input=stdin,
            capture_output=True,
            text=True,
            start_new_session=True,
            env={
                **os.environ,
                "HOME": self.tmp,
                "XDG_CONFIG_HOME": "",
                "SLACK_ALFRED_TARBALL_URL": self.tarball,
            },
        )

    def test_fetches_its_helpers_and_removes_the_install(self):
        result = self.run_standalone("--yes")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(os.path.exists(self.install))

    def test_asks_before_removing_anything(self):
        result = self.run_standalone(stdin="n\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(os.path.exists(self.install))
        self.assertIn("Cancelled", result.stdout)

    def test_a_typed_yes_goes_ahead(self):
        result = self.run_standalone(stdin="y\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(os.path.exists(self.install))

    def test_no_answer_at_all_removes_nothing(self):
        result = self.run_standalone()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(os.path.exists(self.install))

    def test_names_what_it_is_about_to_remove(self):
        result = self.run_standalone(stdin="n\n")
        self.assertIn(self.install, result.stdout)


if __name__ == "__main__":
    unittest.main()
