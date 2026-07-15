import tempfile
import unittest
import zipfile
from pathlib import Path

import tests  # noqa: F401

from tester_toolbox.core.loglocate.packages import (
    ensure_local_archive,
    is_remote_package_source,
    normalize_package_source,
    parse_package_source,
    prepare_package,
    validate_local_package_archive,
)


class PackageSourceTests(unittest.TestCase):
    def test_is_remote_package_source(self):
        self.assertTrue(is_remote_package_source("ftp://nas.example.com/pkg.zip"))
        self.assertFalse(is_remote_package_source(r"C:\packages\GAP_20260101.zip"))

    def test_normalize_local_zip_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "GAP_20260101_a_b_c.zip"
            zip_path.write_bytes(b"")
            normalized = normalize_package_source(str(zip_path))
            self.assertEqual(normalized, str(zip_path.resolve()))

    def test_normalize_file_uri(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "local_pkg.zip"
            zip_path.write_bytes(b"")
            uri = zip_path.as_uri()
            self.assertEqual(normalize_package_source(uri), str(zip_path.resolve()))

    def test_validate_local_package_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "pkg.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("root/app.exe", b"exe")
            validated = validate_local_package_archive(str(zip_path))
            self.assertEqual(validated, str(zip_path.resolve()))

    def test_validate_rejects_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            validate_local_package_archive(r"C:\not_exists\missing.zip")

    def test_validate_rejects_non_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt_path = Path(tmp) / "pkg.txt"
            txt_path.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_local_package_archive(str(txt_path))

    def test_parse_local_zip_metadata(self):
        source = r"D:\builds\GAP\20260101\GAP_20260101_author_ab_cd_ef.zip"
        package = parse_package_source(source)
        self.assertEqual(package.product, "GAP")
        self.assertEqual(package.date, "20260101")
        self.assertEqual(package.archive_name, "GAP_20260101_author_ab_cd_ef.zip")

    def test_ensure_local_archive_copies_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / "GAP_20260101_a.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("GAP/app.exe", b"exe")
            workspace = tmp_path / "workspace"
            package = parse_package_source(str(zip_path))
            archive = ensure_local_archive(package, workspace)
            self.assertTrue(archive.exists())
            self.assertEqual(archive.name, package.archive_name)
            self.assertNotEqual(archive.resolve(), zip_path.resolve())

    def test_prepare_local_zip_extracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / "GAP_20260101_a.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("GAP/app.exe", b"exe")
            workspace = tmp_path / "workspace"
            package = parse_package_source(str(zip_path))
            prepared = prepare_package(package, workspace)
            self.assertTrue(prepared.extract_dir.exists())
            self.assertTrue((prepared.extract_dir / "app.exe").exists())


if __name__ == "__main__":
    unittest.main()
