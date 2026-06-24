import sys
import tempfile
import unittest
from pathlib import Path


class GroundingDINOImportPathTest(unittest.TestCase):
    def test_ensure_groundingdino_path_adds_local_repo_root(self):
        from models.langsam.import_paths import ensure_groundingdino_path

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gd_root = root / "models" / "langsam" / "GroundingDINO"
            package_dir = gd_root / "groundingdino"
            package_dir.mkdir(parents=True)
            (package_dir / "__init__.py").write_text("")

            before = list(sys.path)
            try:
                added = ensure_groundingdino_path(root)
                self.assertTrue(added)
                self.assertEqual(sys.path[0], str(gd_root))
            finally:
                sys.path[:] = before


if __name__ == "__main__":
    unittest.main()
