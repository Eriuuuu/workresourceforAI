import configparser
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401

from tester_toolbox.core.loglocate.ini_builder import (
    build_ascii_ini_filename,
    build_locate_ini_from_error_collection,
    list_enabled_ini_sections,
    prepare_functional_collection_ini,
    read_ini,
    write_ini_with_run_flags,
)


def _write_collection_ini(path, sections):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    for section, enabled in sections.items():
        parser[section] = {
            "IsNeedToRun": "1" if enabled else "0",
            "JsFiles": f"{section}.js",
            "Count": "1",
        }
    with path.open("w", encoding="utf-8") as file:
        parser.write(file, space_around_delimiters=False)


class IniBuilderUnitTests(unittest.TestCase):
    def test_list_enabled_ini_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini_path = Path(tmp) / "collection.ini"
            _write_collection_ini(ini_path, {"S1": True, "S2": False, "S3": True})
            self.assertEqual(list_enabled_ini_sections(ini_path), ["S1", "S3"])

    def test_build_locate_ini_only_enables_regression_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            error_ini = workspace / "ErrorTestCollection.ini"
            _write_collection_ini(error_ini, {"S1": True, "S2": True, "S3": True})

            locate_ini = build_locate_ini_from_error_collection(
                error_ini,
                {"S1", "S3"},
                workspace,
            )
            parser = read_ini(locate_ini)
            self.assertEqual(set(parser.sections()), {"S1", "S2", "S3"})
            self.assertEqual(parser.get("S1", "IsNeedToRun"), "1")
            self.assertEqual(parser.get("S2", "IsNeedToRun"), "0")
            self.assertEqual(parser.get("S3", "IsNeedToRun"), "1")
            self.assertTrue(str(locate_ini).isascii())

    def test_prepare_functional_collection_ini_ascii_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "user_collection.ini"
            _write_collection_ini(source, {"Alpha": True})
            copied = prepare_functional_collection_ini(source, workspace)
            self.assertTrue(copied.exists())
            self.assertTrue(str(copied).isascii())
            self.assertEqual(list_enabled_ini_sections(copied), ["Alpha"])
            self.assertEqual(copied.parent, workspace / "locate_temp_ini")

    def test_locate_temp_ini_dir_under_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            from tester_toolbox.core.loglocate.ini_builder import get_locate_temp_ini_dir

            workspace = Path(tmp) / "ws"
            temp_dir = get_locate_temp_ini_dir(workspace)
            self.assertEqual(temp_dir, workspace.resolve() / "locate_temp_ini")
            self.assertTrue(temp_dir.exists())

    def test_build_ascii_ini_filename_non_ascii_script(self):
        filename = build_ascii_ini_filename(3, "性能脚本/中文用例.js")
        self.assertTrue(filename.isascii())
        self.assertTrue(filename.startswith("003_"))
        self.assertTrue(filename.endswith(".ini"))

    def test_write_ini_with_run_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.ini"
            output = Path(tmp) / "output.ini"
            _write_collection_ini(source, {"A": True, "B": True, "C": False})
            write_ini_with_run_flags(source, output, ["A"])
            parser = read_ini(output)
            self.assertEqual(parser.get("A", "IsNeedToRun"), "1")
            self.assertEqual(parser.get("B", "IsNeedToRun"), "0")


if __name__ == "__main__":
    unittest.main()
