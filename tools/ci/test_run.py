import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from run import archive_install, check_install, core_prefix


class PackagingTest(unittest.TestCase):
    def test_archive_and_core_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            core = root / "extracted" / "core"
            core.mkdir(parents=True)
            (core / "source-revision.txt").write_text("a" * 40 + "\n", encoding="utf-8")
            self.assertEqual(core_prefix(root / "extracted"), core)
            payload = root / "payload"
            payload.mkdir()
            (payload / "value").write_text("ok", encoding="utf-8")
            archive = archive_install(payload, root / "dist", "package")
            self.assertTrue(archive.is_file())
            self.assertEqual(len(archive.with_suffix(".gz.sha256").read_text().split()[0]), 64)

    def test_check_install_requires_module_and_stubs(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory)
            with self.assertRaises(ValueError):
                check_install(prefix, sys.executable)
            module = prefix / "pyopenms"
            module.mkdir()
            (module / "__init__.py").write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):  # stubs are part of the contract
                check_install(prefix, sys.executable)
            (module / "pyopenms.pyi").write_text("", encoding="utf-8")
            check_install(prefix, sys.executable)


if __name__ == "__main__":
    unittest.main()
