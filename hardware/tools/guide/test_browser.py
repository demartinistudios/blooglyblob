"""The preview models a case-sensitive GitHub Pages project path on any host."""

from pathlib import Path
import tempfile
import unittest

from hardware.tools.guide.browser import project_path


class ProjectPathTest(unittest.TestCase):
    def test_project_root_and_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "assets").mkdir()
            (root / "assets" / "part-P03.png").write_bytes(b"image")
            self.assertEqual(project_path(root, "/blooglyblob/"), root)
            self.assertEqual(
                project_path(root, "/blooglyblob/assets/part-P03.png?size=1"),
                root / "assets/part-P03.png",
            )
            for path in (
                "/assets/part-P03.png",
                "/blooglyblob/Assets/part-P03.png",
                "/blooglyblob/assets/part-p03.png",
                "/blooglyblob/../secret",
                "/blooglyblob/%2e%2e/secret",
                "/blooglyblob/missing.png",
            ):
                with self.subTest(path=path):
                    self.assertIsNone(project_path(root, path))

    def test_no_symlinks_or_prefix_lookalikes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real").write_text("private")
            (root / "link").symlink_to(root / "real")
            self.assertIsNone(project_path(root, "/blooglyblob/link"))
            self.assertIsNone(project_path(root, "/blooglyblob-other/real"))


if __name__ == "__main__":
    unittest.main()
