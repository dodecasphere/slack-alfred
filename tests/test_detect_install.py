import json
import os
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DETECT = os.path.join(REPO_ROOT, "tools", "detect_install.sh")


def bash(fn_call, home):
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; ' + fn_call, "_", DETECT],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": home, "XDG_CONFIG_HOME": ""},
    )
    return result.stdout.strip(), result


class FakeHome:
    def __init__(self, tmp):
        self.home = tmp
        self.config_dir = os.path.join(tmp, ".config", "slack-alfred")
        os.makedirs(self.config_dir)

    def make_install(self, relpath, git=False, token="xoxp-YOUR-TOKEN-HERE"):
        path = os.path.join(self.home, relpath)
        os.makedirs(path, exist_ok=True)
        open(os.path.join(path, "setup.sh"), "w").close()
        with open(os.path.join(path, "config.json"), "w") as f:
            json.dump({"token": token}, f)
        if git:
            os.makedirs(os.path.join(path, ".git"), exist_ok=True)
        return path

    def link_config_to(self, install_dir):
        os.symlink(
            os.path.join(install_dir, "config.json"),
            os.path.join(self.config_dir, "config.json"),
        )


class DetectInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake = FakeHome(self.tmp)

    def test_reports_nothing_on_a_clean_machine(self):
        out, _ = bash("detect_install", self.tmp)
        self.assertEqual("", out)

    def test_follows_the_config_symlink_to_a_dev_checkout(self):
        checkout = self.fake.make_install("Projects/slack-alfred", git=True)
        self.fake.link_config_to(checkout)
        out, _ = bash("detect_install", self.tmp)
        self.assertEqual(checkout, out)

    def test_finds_the_default_install_dir_without_a_symlink(self):
        managed = self.fake.make_install(".local/share/slack-alfred")
        out, _ = bash("detect_install", self.tmp)
        self.assertEqual(managed, out)

    def test_prefers_the_symlink_over_the_default_dir(self):
        self.fake.make_install(".local/share/slack-alfred")
        checkout = self.fake.make_install("Projects/slack-alfred", git=True)
        self.fake.link_config_to(checkout)
        out, _ = bash("detect_install", self.tmp)
        self.assertEqual(checkout, out)

    def test_ignores_a_symlink_pointing_at_a_deleted_checkout(self):
        gone = os.path.join(self.tmp, "gone")
        os.makedirs(gone)
        open(os.path.join(gone, "config.json"), "w").close()
        self.fake.link_config_to(gone)
        os.remove(os.path.join(gone, "config.json"))
        out, _ = bash("detect_install", self.tmp)
        self.assertEqual("", out)


class InstallKindTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake = FakeHome(self.tmp)

    def test_a_git_checkout_is_a_dev_install(self):
        checkout = self.fake.make_install("Projects/slack-alfred", git=True)
        out, _ = bash('install_kind "%s"' % checkout, self.tmp)
        self.assertEqual("dev", out)

    def test_a_downloaded_copy_is_a_managed_install(self):
        managed = self.fake.make_install(".local/share/slack-alfred")
        out, _ = bash('install_kind "%s"' % managed, self.tmp)
        self.assertEqual("managed", out)


class HasTokenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fake = FakeHome(self.tmp)

    def has_token(self, install):
        _, result = bash('has_token "%s/config.json"' % install, self.tmp)
        return result.returncode == 0

    def test_placeholder_does_not_count(self):
        install = self.fake.make_install("x")
        self.assertFalse(self.has_token(install))

    def test_a_real_token_counts(self):
        install = self.fake.make_install("x", token="xoxp-123-abc")
        self.assertTrue(self.has_token(install))

    def test_a_missing_config_does_not_count(self):
        self.assertFalse(self.has_token(os.path.join(self.tmp, "nope")))


if __name__ == "__main__":
    unittest.main()
