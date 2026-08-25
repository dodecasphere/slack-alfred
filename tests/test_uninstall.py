import json
import os
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNINSTALL = os.path.join(REPO_ROOT, "uninstall.sh")

TOKEN = "xoxp-real-token"


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.tmp, ".config", "slack-alfred")
        self.agents_dir = os.path.join(self.tmp, "Library", "LaunchAgents")
        os.makedirs(self.config_dir)
        os.makedirs(self.agents_dir)
        self.plist = os.path.join(
            self.agents_dir, "com.michaeldulle.slack-alfred.scheduler.plist"
        )
        open(self.plist, "w").close()

    def make_install(self, relpath, git=False):
        path = os.path.join(self.tmp, relpath)
        os.makedirs(os.path.join(path, "icons"))
        open(os.path.join(path, "setup.sh"), "w").close()
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump({"token": TOKEN, "statuses": []}, f)
        if git:
            os.makedirs(os.path.join(path, ".git"))
        os.symlink(
            os.path.join(path, "config.json"),
            os.path.join(self.config_dir, "config.json"),
        )
        os.symlink(os.path.join(path, "icons"), os.path.join(self.config_dir, "icons"))
        return path

    def run_uninstall(self, *flags):
        # --yes: the confirmation prompt itself is covered in test_uninstall_remote.
        result = subprocess.run(
            ["bash", UNINSTALL, "--yes", *flags],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": self.tmp, "XDG_CONFIG_HOME": ""},
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout

    def test_removes_a_managed_install_and_its_links(self):
        install = self.make_install(".local/share/slack-alfred")
        self.run_uninstall()
        self.assertFalse(os.path.exists(install))
        self.assertFalse(os.path.lexists(os.path.join(self.config_dir, "config.json")))
        self.assertFalse(os.path.lexists(os.path.join(self.config_dir, "icons")))

    def test_removes_the_scheduler_launch_agent(self):
        self.make_install(".local/share/slack-alfred")
        self.run_uninstall()
        self.assertFalse(os.path.exists(self.plist))

    def test_never_deletes_a_dev_checkout(self):
        checkout = self.make_install("Projects/slack-alfred", git=True)
        self.run_uninstall()
        self.assertTrue(os.path.exists(os.path.join(checkout, "config.json")))
        self.assertFalse(os.path.lexists(os.path.join(self.config_dir, "config.json")))

    def test_keep_token_leaves_the_token_behind_as_a_real_file(self):
        self.make_install(".local/share/slack-alfred")
        self.run_uninstall("--keep-token")
        saved = os.path.join(self.config_dir, "config.json")
        self.assertTrue(os.path.isfile(saved))
        self.assertFalse(os.path.islink(saved))
        with open(saved) as f:
            self.assertEqual(TOKEN, json.load(f)["token"])

    def test_without_keep_token_the_token_is_gone(self):
        self.make_install(".local/share/slack-alfred")
        self.run_uninstall()
        self.assertFalse(os.path.exists(os.path.join(self.config_dir, "config.json")))

    def test_is_safe_to_run_when_nothing_is_installed(self):
        out = self.run_uninstall()
        self.assertIn("Nothing", out)


if __name__ == "__main__":
    unittest.main()
