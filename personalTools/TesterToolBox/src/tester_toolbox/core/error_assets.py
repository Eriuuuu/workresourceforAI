import locale
import re
from functools import cmp_to_key
from pathlib import Path

IMAGE_LABELS = ("原图", "本次回放", "差异图")


def _init_collator():
    for loc in ("Chinese_China.utf8", "Chinese_China.936", "Chinese_China", "zh_CN.UTF-8", ""):
        try:
            locale.setlocale(locale.LC_COLLATE, loc)
            return locale.strcoll
        except locale.Error:
            continue
    return None


_COLLATOR = _init_collator()


def compare_script_names(name_a, name_b):
    left = name_a or ""
    right = name_b or ""
    if _COLLATOR is not None:
        try:
            return _COLLATOR(left, right)
        except Exception:
            pass
    return (left > right) - (left < right)


def sort_scripts_by_name(scripts):
    def compare_items(item_a, item_b):
        return compare_script_names(item_a.get("testname"), item_b.get("testname"))

    return sorted(scripts, key=cmp_to_key(compare_items))


def extract_screenshot_diff_filename(errorinfo):
    if not isinstance(errorinfo, str):
        return None
    match = re.search(r"([^|\s]+_diff\.png)", errorinfo, re.IGNORECASE)
    return match.group(1) if match else None


def screenshot_base_name(diff_filename):
    if not diff_filename:
        return None
    stem = Path(diff_filename).stem
    if stem.lower().endswith("_diff"):
        return stem[:-5]
    return stem


def find_validator_folder(log_folder):
    if not log_folder.is_dir():
        return None
    for entry in sorted(log_folder.iterdir(), key=lambda p: p.name):
        if entry.is_dir() and entry.name.endswith("_validator"):
            return entry
    return None


def _image_entry(label, search_dir, filename, root_dir):
    found = False
    relative_path = ""
    if search_dir and filename:
        candidate = search_dir / filename
        if candidate.is_file():
            found = True
            relative_path = candidate.relative_to(root_dir).as_posix()
    return {
        "label": label,
        "filename": filename or "",
        "relative_path": relative_path,
        "found": found,
    }


def resolve_screenshot_comparison_images(root_dir, testname, errorinfo):
    diff_filename = extract_screenshot_diff_filename(errorinfo)
    if not diff_filename:
        return None

    base_name = screenshot_base_name(diff_filename)
    if not base_name:
        return None

    root = Path(root_dir)
    log_folder = root / testname
    validator_folder = find_validator_folder(log_folder)
    search_dir = validator_folder or log_folder

    baseline_name = f"{base_name}_baseline.png"
    replay_name = f"{base_name}.png"
    diff_name = diff_filename if diff_filename.lower().endswith(".png") else f"{base_name}_diff.png"

    return [
        _image_entry(IMAGE_LABELS[0], search_dir, baseline_name, root),
        _image_entry(IMAGE_LABELS[1], search_dir, replay_name, root),
        _image_entry(IMAGE_LABELS[2], search_dir, diff_name, root),
    ]


def extract_dwg_stem_from_errorinfo(errorinfo, value_label):
    if not isinstance(errorinfo, str):
        return None
    match = re.search(rf"{re.escape(value_label)}:\s*\[([^,\]]+),\s*([^,\]]+),\s*([^\]]+)\]", errorinfo)
    if not match:
        return None
    dwg_name = match.group(2).strip()
    if dwg_name.lower().endswith(".dwg"):
        return Path(dwg_name).stem
    return None


def resolve_dwg_export_images(root_dir, testname, errorinfo):
    expect_stem = extract_dwg_stem_from_errorinfo(errorinfo, "期望值")
    actual_stem = extract_dwg_stem_from_errorinfo(errorinfo, "实际值")
    if not expect_stem or not actual_stem:
        return None

    root = Path(root_dir)
    search_dir = root / testname

    baseline_name = f"{expect_stem}-Model.png"
    diff_name = f"{expect_stem}-Model-diff.png"
    replay_name = f"{actual_stem}-{expect_stem}-Model.png"

    return [
        _image_entry(IMAGE_LABELS[0], search_dir, baseline_name, root),
        _image_entry(IMAGE_LABELS[1], search_dir, replay_name, root),
        _image_entry(IMAGE_LABELS[2], search_dir, diff_name, root),
    ]


def build_comparison_images(result, root_dir):
    errortype = result.get("errortype") or ""
    errorinfo = result.get("errorinfo")
    testname = result.get("testname")
    if not testname or not root_dir:
        return None

    if errortype == "截图对比存在差异":
        return resolve_screenshot_comparison_images(root_dir, testname, errorinfo)
    if errortype == "不相等的值_NewExportToDwgCommand":
        return resolve_dwg_export_images(root_dir, testname, errorinfo)
    return None
