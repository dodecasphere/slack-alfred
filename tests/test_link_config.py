import json
import os
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK_CONFIG = os.path.join(REPO_ROOT, "tools", "link_config.sh")

PLACEHOLDER = "xoxp-YOUR-TOKEN-HERE"


class SymlinkTests(unittest.TestCase):
    """`symlink` wires ~/.config/slack-alfred at a specific install's files.

    The hard case is a second install: the link already exists but points at an
    older checkout, so the token written by setup.sh lands in a file nothing reads.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = os.path.join(self.tmp, "install", "config.json")
        os.makedirs(os.path.dirname(self.target))
        self.link = os.path.join(self.tmp, "config", "config.json")
        os.makedirs(os.path.dirname(self.link))

    def write_config(self, path, token):
        with open(path, "w") as f:
            json.dump({"token": token, "statuses": []}, f)

    def run_symlink(self, target=None, link=None):
        result = subprocess.run(
            ["bash", "-c", 'source "$1"; symlink "$2" "$3"', "_",
             LINK_CONFIG, target or self.target, link or self.link],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return result.stdout

    def token_at(self, path):
        with open(path) as f:
            return json.load(f)["token"]

    def test_creates_the_link_when_nothing_is_there(self):
        self.write_config(self.target, PLACEHOLDER)
        self.run_symlink()
        self.assertEqual(self.target, os.readlink(self.link))

    def test_leaves_a_link_that_already_points_at_this_install(self):
        self.write_config(self.target, "xoxp-good")
        os.symlink(self.target, self.link)
        self.run_symlink()
        self.assertEqual(self.target, os.readlink(self.link))
        self.assertEqual("xoxp-good", self.token_at(self.target))

    def test_migrates_a_real_config_file_and_backs_it_up(self):
        self.write_config(self.target, PLACEHOLDER)
        self.write_config(self.link, "xoxp-existing")
        self.run_symlink()
        self.assertEqual(self.target, os.readlink(self.link))
        self.assertEqual("xoxp-existing", self.token_at(self.target))
        self.assertTrue(os.path.exists(self.link + ".bak"))

    def test_repoints_a_link_left_behind_by_an_older_install(self):
        old_install = os.path.join(self.tmp, "old", "config.json")
        os.makedirs(os.path.dirname(old_install))
        self.write_config(old_install, "xoxp-from-old-install")
        os.symlink(old_install, self.link)
        self.write_config(self.target, PLACEHOLDER)

        self.run_symlink()

        self.assertEqual(self.target, os.readlink(self.link))
        self.assertEqual("xoxp-from-old-install", self.token_at(self.target))

    def test_keeps_this_installs_token_when_repointing(self):
        old_install = os.path.join(self.tmp, "old", "config.json")
        os.makedirs(os.path.dirname(old_install))
        self.write_config(old_install, "xoxp-stale")
        os.symlink(old_install, self.link)
        self.write_config(self.target, "xoxp-fresh")

        self.run_symlink()

        self.assertEqual(self.target, os.readlink(self.link))
        self.assertEqual("xoxp-fresh", self.token_at(self.target))

    def test_repoints_a_stale_directory_link(self):
        old_dir = os.path.join(self.tmp, "old-icons")
        new_dir = os.path.join(self.tmp, "install", "icons")
        os.makedirs(old_dir)
        os.makedirs(new_dir)
        link = os.path.join(self.tmp, "config", "icons")
        os.symlink(old_dir, link)

        self.run_symlink(target=new_dir, link=link)

        self.assertEqual(new_dir, os.readlink(link))

    def test_replaces_a_broken_link(self):
        os.symlink(os.path.join(self.tmp, "gone", "config.json"), self.link)
        self.write_config(self.target, PLACEHOLDER)
        self.run_symlink()
        self.assertEqual(self.target, os.readlink(self.link))


if __name__ == "__main__":
    unittest.main()
