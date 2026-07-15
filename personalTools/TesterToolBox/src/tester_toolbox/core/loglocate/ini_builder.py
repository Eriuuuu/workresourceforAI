import configparser
import hashlib
import re
import shutil
import tempfile
from pathlib import Path


PRODUCT_INI_CANDIDATES = {
    "GAP": [
        r"tests\GAP_Performance\GAPPerfTest_QTY.ini",
        r"tests\GAP_Performance\GAPPerfTest_GCC.ini",
        r"tests\GAP_Performance\GAPPerfTest_GAP.ini",
    ],
    "GBMP": [
        r"tests\QuickPerformance\QuickPerformanceTestCollection-win10.ini",
    ],
    "GST": [
        r"tests\GST_Performance\GSTPerfTest_GST.ini",
        r"tests\GST_Performance\GSTPerfTest_GCC.ini",
        r"tests\GST_Performance\GSTPerfTest_QTY.ini",
    ],
    "GMEP": [
        r"tests\Performance_Collaboration\GMEPPerfTest_GMEP.ini",
        r"tests\Performance_Collaboration\GMEPPerfTest_GCC.ini",
    ],
}


def read_ini(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8-sig")
    return parser


def find_product_ini_files(tests_path, product):
    tests_root = Path(tests_path).resolve()
    if tests_root.name.lower() != "tests":
        raise ValueError(f"testsPath 必须指向 tests 目录：{tests_path}")
    repo_root = tests_root.parent
    files = []
    for relative in PRODUCT_INI_CANDIDATES.get((product or "").upper(), []):
        path = repo_root / relative
        if path.exists():
            files.append(path)
    return files


def normalize_script_name(name):
    text = (name or "").strip().replace("/", "\\")
    return Path(text).name.lower()


_ASCII_STEM_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


def _script_name_digest(script_name):
    stem = Path(normalize_script_name(script_name)).stem
    return hashlib.sha1(stem.encode("utf-8")).hexdigest()[:12]


def ensure_ascii_path(path, label="路径"):
    text = str(path)
    if not text.isascii():
        raise ValueError(f"临时 ini {label} 必须纯 ASCII：{text}")
    return Path(text)


def build_ascii_ini_filename(package_index, script_name):
    normalized = normalize_script_name(script_name)
    stem = Path(normalized).stem
    digest = _script_name_digest(script_name)
    if _ASCII_STEM_PATTERN.fullmatch(stem):
        filename = f"{package_index:03d}_{stem}.ini"
    else:
        ascii_part = re.sub(r"[^A-Za-z0-9_\-]", "", stem).strip("_-")
        if ascii_part:
            filename = f"{package_index:03d}_{ascii_part}_{digest}.ini"
        else:
            filename = f"{package_index:03d}_{digest}.ini"
    if not filename.isascii():
        raise ValueError(f"临时 ini 文件名必须纯 ASCII：{filename}")
    return filename


def get_locate_temp_ini_dir(workspace=None):
    if workspace:
        base = Path(workspace).resolve() / "locate_temp_ini"
    else:
        base = Path(tempfile.gettempdir()) / "TesterToolBox" / "locate_temp_ini"
    base.mkdir(parents=True, exist_ok=True)
    return base


def build_ascii_ini_path(package_index, script_name, workspace=None):
    path = get_locate_temp_ini_dir(workspace) / build_ascii_ini_filename(package_index, script_name)
    return ensure_ascii_path(path.resolve(), label="路径")


def build_ini_section_index(tests_path, product):
    index = {}
    for ini_file in find_product_ini_files(tests_path, product):
        parser = read_ini(ini_file)
        for section in parser.sections():
            js_files = parser.get(section, "JsFiles", fallback="")
            for script in [item.strip() for item in js_files.split(";") if item.strip()]:
                index.setdefault(normalize_script_name(script), []).append((ini_file, section, dict(parser.items(section))))
    return index


def build_temp_ini(tests_path, product, script_names, run_count, output_file):
    section_index = build_ini_section_index(tests_path, product)
    output = configparser.ConfigParser(interpolation=None)
    output.optionxform = str
    missing = []

    for script_name in sorted({normalize_script_name(name) for name in script_names}):
        matches = section_index.get(script_name)
        if not matches:
            missing.append(script_name)
            continue
        for _ini_file, section, values in matches:
            values["IsNeedToRun"] = "1"
            values["Count"] = str(run_count)
            output[section] = values

    if missing:
        raise ValueError(f"未在产品原始 ini 中找到脚本：{', '.join(missing)}")

    output_path = ensure_ascii_path(output_file, label="输出路径")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        output.write(file, space_around_delimiters=False)
    return output_path


def is_section_enabled(parser, section):
    return parser.get(section, "IsNeedToRun", fallback="0").strip() == "1"


def list_enabled_ini_sections(ini_path):
    parser = read_ini(ini_path)
    sections = []
    for section in parser.sections():
        if is_section_enabled(parser, section):
            sections.append(section)
    return sections


def collect_failed_ini_sections(result_log_path):
    ini_file = Path(result_log_path) / "ErrorTestCollection.ini"
    if not ini_file.exists():
        return set()
    parser = read_ini(ini_file)
    return set(parser.sections())


def prepare_functional_collection_ini(source_ini, workspace=None):
    source = Path(source_ini).resolve()
    if not source.exists():
        raise FileNotFoundError(f"脚本集合 ini 不存在：{source}")
    digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:8]
    dest = get_locate_temp_ini_dir(workspace) / f"functional_{digest}.ini"
    shutil.copy2(source, dest)
    return ensure_ascii_path(dest.resolve(), label="路径")


def get_error_collection_ini_path(result_log_path):
    return Path(result_log_path) / "ErrorTestCollection.ini"


def write_ini_with_run_flags(source_ini, output_ini, enabled_sections):
    parser = read_ini(source_ini)
    output = configparser.ConfigParser(interpolation=None)
    output.optionxform = str
    enabled = set(enabled_sections or [])
    for section in parser.sections():
        values = dict(parser.items(section))
        values["IsNeedToRun"] = "1" if section in enabled else "0"
        output[section] = values
    output_path = ensure_ascii_path(output_ini, label="输出路径")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        output.write(file, space_around_delimiters=False)
    return output_path


def build_locate_ini_from_error_collection(error_collection_ini, regression_scripts, workspace=None):
    parser = read_ini(error_collection_ini)
    regression = set(regression_scripts or [])
    dest = get_locate_temp_ini_dir(workspace) / "functional_locate.ini"
    return write_ini_with_run_flags(error_collection_ini, dest, [s for s in parser.sections() if s in regression])
