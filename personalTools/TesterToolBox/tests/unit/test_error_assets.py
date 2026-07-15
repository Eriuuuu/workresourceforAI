import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401

from tester_toolbox.core.error_assets import (
    build_comparison_images,
    extract_dwg_stem_from_errorinfo,
    extract_screenshot_diff_filename,
    resolve_dwg_export_images,
    resolve_screenshot_comparison_images,
    screenshot_base_name,
    sort_scripts_by_name,
)


SCREENSHOT_ERRORINFO = (
    "截图对比在1.0%的容差范围内存在差异！ | | 差异内容请查看日志validator文件夹内的文件： | "
    "截图验证器_test_2_diff.png | | 截图比较相同的部分会以淡色显示，差异部分会以红色高亮显示！; "
    "ProcessCommand: gm.view.navigate"
)

DWG_ERRORINFO = (
    "实际值: [NewExportToDwgCommand, 平面视图-1F-replay.dwg, Dxf]; "
    "期望值: [NewExportToDwgCommand, 批量标注-批量房间注释-平面视图-1F.dwg, Dxf]; "
    "ProcessCommand: gapExportToDWGCommand"
)


class ErrorAssetsTests(unittest.TestCase):
    def test_sort_scripts_by_name_supports_chinese_and_english(self):
        scripts = [
            {"testname": "脚本B"},
            {"testname": "ScriptA"},
            {"testname": "脚本A"},
            {"testname": "ScriptB"},
        ]
        sorted_scripts = sort_scripts_by_name(scripts)
        names = [item["testname"] for item in sorted_scripts]
        self.assertEqual(names, ["ScriptA", "ScriptB", "脚本A", "脚本B"])

    def test_extract_screenshot_diff_filename(self):
        self.assertEqual(extract_screenshot_diff_filename(SCREENSHOT_ERRORINFO), "截图验证器_test_2_diff.png")
        self.assertEqual(screenshot_base_name("截图验证器_test_2_diff.png"), "截图验证器_test_2")

    def test_resolve_screenshot_comparison_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_name = "截图脚本"
            validator_dir = root / script_name / "foo_validator"
            validator_dir.mkdir(parents=True)
            (validator_dir / "截图验证器_test_2_baseline.png").write_bytes(b"baseline")
            (validator_dir / "截图验证器_test_2.png").write_bytes(b"replay")
            (validator_dir / "截图验证器_test_2_diff.png").write_bytes(b"diff")

            images = resolve_screenshot_comparison_images(root, script_name, SCREENSHOT_ERRORINFO)
            self.assertEqual([img["label"] for img in images], ["原图", "本次回放", "差异图"])
            self.assertTrue(all(img["found"] for img in images))
            self.assertEqual(images[0]["relative_path"], f"{script_name}/foo_validator/截图验证器_test_2_baseline.png")
            self.assertEqual(images[1]["relative_path"], f"{script_name}/foo_validator/截图验证器_test_2.png")
            self.assertEqual(images[2]["relative_path"], f"{script_name}/foo_validator/截图验证器_test_2_diff.png")

    def test_resolve_screenshot_comparison_images_marks_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_name = "截图脚本"
            validator_dir = root / script_name / "foo_validator"
            validator_dir.mkdir(parents=True)
            (validator_dir / "截图验证器_test_2_diff.png").write_bytes(b"diff")

            images = resolve_screenshot_comparison_images(root, script_name, SCREENSHOT_ERRORINFO)
            self.assertFalse(images[0]["found"])
            self.assertFalse(images[1]["found"])
            self.assertTrue(images[2]["found"])

    def test_extract_dwg_stems_from_errorinfo(self):
        self.assertEqual(extract_dwg_stem_from_errorinfo(DWG_ERRORINFO, "期望值"), "批量标注-批量房间注释-平面视图-1F")
        self.assertEqual(extract_dwg_stem_from_errorinfo(DWG_ERRORINFO, "实际值"), "平面视图-1F-replay")

    def test_resolve_dwg_export_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_name = "导出脚本"
            script_dir = root / script_name
            script_dir.mkdir(parents=True)
            baseline = "批量标注-批量房间注释-平面视图-1F-Model.png"
            replay = "平面视图-1F-replay-批量标注-批量房间注释-平面视图-1F-Model.png"
            diff = "批量标注-批量房间注释-平面视图-1F-Model-diff.png"
            (script_dir / baseline).write_bytes(b"baseline")
            (script_dir / replay).write_bytes(b"replay")

            images = resolve_dwg_export_images(root, script_name, DWG_ERRORINFO)
            self.assertEqual([img["label"] for img in images], ["原图", "本次回放", "差异图"])
            self.assertTrue(images[0]["found"])
            self.assertTrue(images[1]["found"])
            self.assertFalse(images[2]["found"])
            self.assertEqual(images[0]["filename"], baseline)
            self.assertEqual(images[1]["filename"], replay)
            self.assertEqual(images[2]["filename"], diff)

    def test_build_comparison_images_dispatches_by_errortype(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script_name = "导出脚本"
            script_dir = root / script_name
            script_dir.mkdir(parents=True)
            (script_dir / "批量标注-批量房间注释-平面视图-1F-Model.png").write_bytes(b"baseline")

            screenshot_result = {
                "testname": script_name,
                "errortype": "截图对比存在差异",
                "errorinfo": SCREENSHOT_ERRORINFO,
            }
            dwg_result = {
                "testname": script_name,
                "errortype": "不相等的值_NewExportToDwgCommand",
                "errorinfo": DWG_ERRORINFO,
            }
            self.assertIsNotNone(build_comparison_images(screenshot_result, root))
            self.assertIsNotNone(build_comparison_images(dwg_result, root))
            self.assertIsNone(build_comparison_images({"testname": script_name, "errortype": "Crash"}, root))


if __name__ == "__main__":
    unittest.main()
