import shutil
import tempfile
import unittest
from pathlib import Path

from agent_v2.special_features import build_project_context


class SpecialFeaturesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_project_context_skips_local_secrets(self) -> None:
        (self.tmp / "README.md").write_text("# Demo\nA tiny project.", encoding="utf-8")
        (self.tmp / ".env").write_text("SECRET=should_not_appear", encoding="utf-8")
        (self.tmp / "src").mkdir()
        (self.tmp / "src" / "main.py").write_text("print('hello')", encoding="utf-8")

        context = build_project_context(self.tmp)

        self.assertIn("README.md", context)
        self.assertIn("src/main.py", context)
        self.assertNotIn("should_not_appear", context)


if __name__ == "__main__":
    unittest.main()
