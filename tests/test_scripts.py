import os
import re
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from esb_outages.poll import poll_lock

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
        return git(self.origin, "log", "--format=%s", "--all").splitlines()


class TestBackup(BackupTestCase):
    def test_a_clean_backup_pushes(self):
        result = self.backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.pushed()), 1)

    def test_commits_from_another_host_are_merged_before_the_push(self):
        self.assertEqual(self.backup().returncode, 0)
        other = self.data.parent / "other"
        git(self.data.parent, "clone", "-q", str(self.origin), str(other))
        (other / "raw" / "runs-2026-09-pi2.jsonl").write_text('{"run_id": "b"}\n')
        git(other, "add", "raw")
        git(other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "standby")
        git(other, "push", "-q", "origin", "main")
        (self.data / "raw" / "runs-2026-09.jsonl").write_text('{"run_id": "a"}\n{"run_id": "c"}\n')
        result = self.backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        tree = git(self.origin, "ls-tree", "--name-only", "main", "raw/")
        self.assertIn("runs-2026-09-pi2.jsonl", tree)
        self.assertIn('"c"', git(self.origin, "show", "main:raw/runs-2026-09.jsonl"))

    def test_a_stale_index_lock_is_announced(self):
        (self.data / ".git" / "index.lock").touch()
        result = self.backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ESB backup: failed", result.stderr)

    def test_a_failed_fetch_carries_git_s_own_error(self):
        git(self.data, "remote", "set-url", "origin", str(self.origin) + "-gone")
        result = self.backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git fetch failed", result.stderr)
        self.assertIn("does not appear to be a git repository", result.stderr)

    def test_no_fixed_file_in_the_shared_tmp(self):
        # A leftover file there that the esb user cannot write failed every backup.
        self.assertNotIn("/tmp/", BACKUP.read_text())

    def test_it_waits_for_a_poll_to_finish_writing(self):
        env = {**GIT_ENV, "ESB_DATA_DIR": str(self.data)}
        env.pop("ESB_ALERT_WEBHOOK", None)
        with poll_lock(self.data) as acquired:
            self.assertTrue(acquired)
            proc = subprocess.Popen(
                ["sh", str(BACKUP)], env=env, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            time.sleep(2)
            waiting, pushed_early = proc.poll() is None, self.pushed()
        _, err = proc.communicate(timeout=60)
        self.assertTrue(waiting, "finished while a poll held the lock")
        self.assertEqual(pushed_early, [])
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(len(self.pushed()), 1)

    def test_a_push_from_another_host_during_the_wait_is_merged(self):
        self.assertEqual(self.backup().returncode, 0)
        other = self.data.parent / "other"
        git(self.data.parent, "clone", "-q", str(self.origin), str(other))
        # Something new to commit, so the retry's merge is a merge commit.
        with (self.data / "raw" / "runs-2026-09.jsonl").open("a") as log:
            log.write('{"run_id": "c"}\n')
        fetched = self.data / ".git" / "FETCH_HEAD"
        before = fetched.stat().st_mtime_ns
        env = {**GIT_ENV, "ESB_DATA_DIR": str(self.data)}
        env.pop("ESB_ALERT_WEBHOOK", None)
        with poll_lock(self.data):
            proc = subprocess.Popen(
                ["sh", str(BACKUP)], env=env, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            deadline = time.monotonic() + 30
            while fetched.stat().st_mtime_ns == before:
                if time.monotonic() > deadline:
                    proc.kill()
                    proc.communicate()
                    self.fail("the backup never fetched")
                time.sleep(0.05)
            time.sleep(0.5)  # the fetch has written FETCH_HEAD; let it exit
            (other / "raw" / "runs-2026-09-pi2.jsonl").write_text('{"run_id": "b"}\n')
            git(other, "add", "raw")
            git(other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "standby")
            git(other, "push", "-q", "origin", "main")
        _, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        # Only the retry could have merged: the first fetch predates the push.
        self.assertTrue(git(self.data, "log", "--merges", "--format=%H").strip())
        tree = git(self.origin, "ls-tree", "--name-only", "main", "raw/")
        self.assertIn("runs-2026-09-pi2.jsonl", tree)
        self.assertIn('"c"', git(self.origin, "show", "main:raw/runs-2026-09.jsonl"))

    def test_a_retried_push_commits_what_a_poll_wrote_meanwhile(self):
        # The first push fails, as it would against a newer origin; in between
        # a poll appends to a file origin also changed, far enough apart for
        # git to merge the two.
        runs = self.data / "raw" / "runs-2026-09.jsonl"
        runs.write_text("".join(f'{{"run_id": "{n}"}}\n' for n in "adefg"))
        self.assertEqual(self.backup().returncode, 0)
        other = self.data.parent / "other"
        git(self.data.parent, "clone", "-q", str(self.origin), str(other))
        theirs = other / "raw" / "runs-2026-09.jsonl"
        theirs.write_text(theirs.read_text().replace('"a"', '"b"'))
        git(other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "standby")
        hook = self.data / ".git" / "hooks" / "pre-push"
        hook.write_text(
            "#!/bin/sh\n"
            f'if [ ! -e "{self.data}/.pushed-once" ]; then\n'
            f'  touch "{self.data}/.pushed-once"\n'
            f'  git -C "{other}" push -q origin main\n'
            f'  printf "%s\\n" \'{{"run_id": "c"}}\' >> "{self.data}/raw/runs-2026-09.jsonl"\n'
            "  exit 1\n"
            "fi\n"
        )
        hook.chmod(0o755)
        result = self.backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        log = git(self.origin, "show", "main:raw/runs-2026-09.jsonl")
        self.assertIn('"b"', log)
        self.assertIn('"c"', log)

    def test_the_unit_s_timeout_is_announced(self):
        env = {**GIT_ENV, "ESB_DATA_DIR": str(self.data)}
        env.pop("ESB_ALERT_WEBHOOK", None)
        with poll_lock(self.data):
            proc = subprocess.Popen(
                ["sh", str(BACKUP)], env=env, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, start_new_session=True,
            )
            time.sleep(1)
            # systemd signals the unit's whole control group.
            os.killpg(proc.pid, signal.SIGTERM)
            _, err = proc.communicate(timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("ESB backup: failed", err)
        # The timeout is as likely to land on a stalled push as before it.
        self.assertNotIn("before the push", err)

    def test_nothing_git_leaves_running_keeps_the_lock(self):
        # As a detached auto-gc would: every poll meanwhile would skip its run.
        hook = self.data / ".git" / "hooks" / "post-commit"
        hook.write_text("#!/bin/sh\nsleep 10 >/dev/null 2>&1 &\n")
        hook.chmod(0o755)
        self.assertEqual(self.backup().returncode, 0)
        with poll_lock(self.data) as acquired:
            self.assertTrue(acquired)

class TestBackupUnit(unittest.TestCase):
    unit = (REPO / "scripts" / "systemd" / "esb-backup.service").read_text()

    def test_a_stalled_push_cannot_hold_the_unit_forever(self):
        [timeout] = re.findall(r"^TimeoutStartSec=(\d+)$", self.unit, re.M)
        [wait] = re.findall(r"flock -w (\d+)", BACKUP.read_text())
        [connect] = re.findall(r"ConnectTimeout=(\d+)", self.unit)
        [alive] = re.findall(r"ServerAliveInterval=(\d+)", self.unit)
        [count] = re.findall(r"ServerAliveCountMax=(\d+)", self.unit)
        dead_connection = int(connect) + int(alive) * int(count)
        # A push retry waits for the lock a second time, and fetches and pushes
        # twice; the rest is local git.
        needed = 2 * int(wait) + 4 * dead_connection + 300
        self.assertGreaterEqual(int(timeout), needed)

    def test_the_backup_outwaits_any_poll_systemd_allows(self):
        poll = (REPO / "scripts" / "systemd" / "esb-outages.service").read_text()
        [backstop] = re.findall(r"^TimeoutStartSec=(\d+)$", poll, re.M)
        # After SIGTERM the poll closes its run out, still holding the lock.
        [stop] = re.findall(r"^TimeoutStopSec=(\d+)$", poll, re.M)
        self.assertNotRegex(poll, r"(?m)^TimeoutSec=")
        [wait] = re.findall(r"flock -w (\d+)", BACKUP.read_text())
        # A poll holding it started before the wait did, so this is margin.
        self.assertGreaterEqual(int(wait), int(backstop) + int(stop) + 120)

    def test_ssh_gives_up_on_a_dead_connection(self):
        [ssh] = re.findall(r'GIT_SSH_COMMAND=([^"]*)"', self.unit)
        self.assertIn("-o ConnectTimeout=", ssh)
        self.assertIn("-o ServerAliveInterval=", ssh)


class TestWrapper(unittest.TestCase):
    """esb-wrapper.sh with stand-ins for id and sudo that record what sudo got."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self._tmp.name)
        (self.bin / "id").write_text("#!/bin/sh\necho 0\n")
        (self.bin / "sudo").write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" > "$RECORD.argv"\nenv > "$RECORD.env"\n'
        )
        for name in ("id", "sudo"):
            (self.bin / name).chmod(0o755)

    def tearDown(self):
        self._tmp.cleanup()

    def test_secrets_reach_sudo_in_the_environment_not_its_command_line(self):
        secrets = {
            "ESB_ALERT_WEBHOOK": "https://ntfy.sh/secret-topic",
            "ESB_HEARTBEAT_URL": "https://hc-ping.com/secret-uuid",
            "ESB_API_KEY": "secret-key",
        }
        record = self.bin / "record"
        env = {**os.environ, **secrets, "RECORD": str(record),
               "PATH": f"{self.bin}:{os.environ['PATH']}"}
        subprocess.run(
            ["sh", str(REPO / "scripts" / "esb-wrapper.sh"), "stats"],
            env=env, check=True, timeout=30,
        )
        argv = Path(f"{record}.argv").read_text()
        self.assertNotIn("secret", argv)
        self.assertIn("stats", argv.splitlines())
        [preserved] = [a for a in argv.splitlines() if a.startswith("--preserve-env=")]
        passed = Path(f"{record}.env").read_text().splitlines()
        for name, value in secrets.items():
            self.assertIn(name, preserved)
            self.assertIn(f"{name}={value}", passed)


if __name__ == "__main__":
    unittest.main()
