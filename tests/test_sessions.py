import shutil
import tempfile
import unittest
from pathlib import Path

from agent_v2.sessions import SessionStore, validate_project_dir


class SessionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.store = SessionStore(self.tmp / "sessions")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_get_append_delete(self) -> None:
        record = self.store.create(name="Demo", project_dir=str(self.project))
        self.assertEqual(record.name, "Demo")
        self.assertEqual(len(self.store.list()), 1)

        self.store.append_message(record.id, {"type": "user", "content": "hi"})
        loaded = self.store.get(record.id)
        self.assertEqual(loaded.messages[0]["content"], "hi")

        self.store.delete(record.id)
        self.assertEqual(self.store.list(), [])

    def test_bad_json_is_skipped(self) -> None:
        (self.store.root / "bad.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.store.list(), [])


class ValidateProjectDirTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_dir(self) -> None:
        self.assertEqual(validate_project_dir(str(self.tmp)), self.tmp.resolve())

    def test_relative_dir_resolves_from_base_dir(self) -> None:
        child = self.tmp / "test"
        child.mkdir()
        self.assertEqual(validate_project_dir("test", base_dir=self.tmp), child.resolve())

    def test_missing_dir(self) -> None:
        with self.assertRaises(ValueError):
            validate_project_dir(str(self.tmp / "missing"))

    def test_file_is_rejected(self) -> None:
        file_path = self.tmp / "file.txt"
        file_path.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            validate_project_dir(str(file_path))


if __name__ == "__main__":
    unittest.main()
