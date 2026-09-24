import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKUP = REPO / "scripts" / "backup-to-git.sh"


def git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=GIT_ENV
    ).stdout


GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


class BackupTestCase(unittest.TestCase):
    """backup-to-git.sh against a throwaway data repo and a bare origin."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.origin = root / "origin.git"
        self.data = root / "data"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        git(root, "init", "-q", "-b", "main", str(self.data))
        git(self.data, "remote", "add", "origin", str(self.origin))
        (self.data / "raw").mkdir()
        (self.data / "raw" / "runs-2026-09.jsonl").write_text('{"run_id": "a"}\n')

    def tearDown(self):
        self._tmp.cleanup()

    def backup(self, **env):
        env = {**GIT_ENV, "ESB_DATA_DIR": str(self.data), **env}
        env.pop("ESB_ALERT_WEBHOOK", None)
        return subprocess.run(
            ["sh", str(BACKUP)], env=env, capture_output=True, text=True, timeout=60
        )

    def pushed(self):
        return git(self.origin, "log", "--format=%s", "main").splitlines()


class TestBackup(BackupTestCase):
    def test_a_clean_backup_pushes(self):
        result = self.backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.pushed()), 1)

    def test_a_stale_index_lock_is_announced(self):
        (self.data / ".git" / "index.lock").touch()
        result = self.backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ESB backup: failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
