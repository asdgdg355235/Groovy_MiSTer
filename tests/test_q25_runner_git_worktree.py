#!/usr/bin/env python3
"""Verify that the user-side Quartus runner accepts ordinary and linked Git worktrees.

This test only invokes Git and Python. It never invokes Quartus.
"""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

RUNNER = Path(__file__).with_name("run_q25_lz4_user.py")
spec = importlib.util.spec_from_file_location("q25_user_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class GitWorktreeCheck(unittest.TestCase):
    def test_detached_worktree_and_normal_checkout(self):
        with tempfile.TemporaryDirectory(prefix="q25-git-worktree-test-") as td:
            base = Path(td)
            source = base / "source"
            linked = base / "linked"
            source.mkdir()
            git("init", "-q", str(source))
            git("config", "user.name", "Test", cwd=source)
            git("config", "user.email", "test@example.invalid", cwd=source)
            (source / "README").write_text("fixture\n")
            git("add", "README", cwd=source)
            git("commit", "-q", "-m", "test fixture", cwd=source)
            git("worktree", "add", "-q", "--detach", str(linked), "HEAD", cwd=source)

            self.assertTrue((source / ".git").is_dir())
            self.assertTrue((linked / ".git").is_file())
            self.assertEqual(runner.require_git_worktree(source), source)
            self.assertEqual(runner.require_git_worktree(linked), linked)

            archive = base / "archive"
            archive.mkdir()
            (archive / "README").write_text("fixture\n")
            with self.assertRaises(ValueError):
                runner.require_git_worktree(archive)

    def test_preflight_does_not_launch_quartus(self):
        # --preflight-only exits before any Quartus executable or subprocess.
        text = RUNNER.read_text()
        self.assertIn('if a.preflight_only:', text)
        self.assertLess(text.index('if a.preflight_only:'),
                        text.index('env=os.environ.copy()'))


if __name__ == "__main__":
    unittest.main()
