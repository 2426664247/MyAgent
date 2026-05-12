import shutil
import tempfile
import unittest
from pathlib import Path

from agent_v2.sandbox import PathSandbox


class SandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.sandbox = PathSandbox(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_resolve_relative(self) -> None:
        result = self.sandbox.resolve("sub/file.txt")
        expected = (self.tmp / "sub" / "file.txt").resolve()
        self.assertEqual(result, expected)

    def test_resolve_absolute_inside(self) -> None:
        target = self.tmp / "ok.txt"
        result = self.sandbox.resolve(str(target))
        self.assertEqual(result, target.resolve())

    def test_reject_escape(self) -> None:
        with self.assertRaises(ValueError):
            self.sandbox.resolve("../outside.txt")

    def test_reject_absolute_outside(self) -> None:
        with self.assertRaises(ValueError):
            self.sandbox.resolve("C:/Windows/System32/config.sys")


if __name__ == "__main__":
    unittest.main()
