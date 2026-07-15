import os
import re
from pathlib import Path

from tester_toolbox.config.settings import ERROR_PATTERNS, MAX_TAIL_LINES, OUTPUT_INTERMEDIATE_DATA, PROCESS_CMD_REGEX
from .common import read_file_tail, read_text_with_fallback, split_lines_like_groovy, write_json_file
from .error_assets import build_comparison_images, sort_scripts_by_name
from .reports import write_html_report


def parse_ini_file(ini_file):
    names = []
    seen = set()
    try:
        for line in split_lines_like_groovy(read_text_with_fallback(ini_file)):
            line = line.replace("\ufeff", "", 1).strip()
            if not line.startswith("JsFiles="):
                continue
            value = line[len("JsFiles="):].strip()
            for part in value.split(";"):
                part = part.strip()
                if not part.endswith(".js"):
                    continue
                file_name = Path(part).name if "/" in part or "\\" in part else part
                script_name = file_name[:-3]
                if script_name and script_name not in seen:
                    seen.add(script_name)
                    names.append(script_name)
    except OSError as exc:
        print(f"[WARN] 读取INI文件异常: {exc}")
    return names


def collect_folder_names(root_dir):
    names = []
    try:
        for entry in os.scandir(root_dir):
            if entry.is_dir() and entry.name not in ("tests", "GPUCache"):
                names.append(entry.name)
    except OSError:
        pass
    return names


def extract_raw_error_log_lines(lines):
    result = []
    start = max(0, len(lines) - MAX_TAIL_LINES)
    for i in range(len(lines) - 1, start - 1, -1):
        result.insert(0, lines[i])
        if lines[i].strip().startswith("JrnCmd.ProcessCommand"):
            break
    return result


def extract_process_command_name(line):
    try:
        match = PROCESS_CMD_REGEX.search(line)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def find_last_process_command_name(lines):
    for line in reversed(lines):
        text = line.strip()
        if text.startswith("JrnCmd.ProcessCommand"):
            return extract_process_command_name(text)
    return None


def find_last_non_empty_line(lines):
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return None


def extract_dbg_warn_info(line):
    info = {"File": "", "Line": "", "Function": "", "Message": "", "Name": "", "Date": ""}
    patterns = {
        "File": r"File:\s*([^|]+)",
        "Line": r"Line:\s*(\d+)",
        "Function": r"Function:\s*([^|]+)",
        "Message": r"Message:\s*([^|]+)",
        "Name": r"Name:\s*([^|]+)",
        "Date": r"Date:\s*([^|\s]+)",
    }
    try:
        for key, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                info[key] = match.group(1).strip()
    except Exception as exc:
        print(f"[WARN] 提取DBG_WARN信息异常: {exc}")
    return info


def extract_expect_first_param(line):
    match = re.search(r'<期望值>"([^"]*)"', line)
    return match.group(1) if match else ""


def extract_first_param_from_triple(line):
    match = re.search(r'"([^"]*)",\s*"([^"]*)",\s*"([^"]*)"', line)
    return match.group(1) if match else ""


def extract_value_mismatch_info(line):
    parts = []
    actual = re.search(r'<实际值>"([^"]*)",\s*"([^"]*)",\s*"([^"]*)"', line)
    if actual:
        parts.append(f"实际值: [{actual.group(1)}, {actual.group(2)}, {actual.group(3)}]")
    expect = re.search(r'<期望值>"([^"]*)",\s*"([^"]*)",\s*"([^"]*)"', line)
    if expect:
        parts.append(f"期望值: [{expect.group(1)}, {expect.group(2)}, {expect.group(3)}]")
    return "; ".join(parts) if parts else ""


def extract_previous_uncompared_info(line, error_msg):
    triples = re.findall(r'"([^"]*)",\s*"([^"]*)",\s*"([^"]*)"', line)
    if not triples:
        return error_msg
    return "未比较值: " + "; ".join(f"[{a}, {b}, {c}]" for a, b, c in triples)


def extract_error_message(line):
    result = {"errortype": "", "errorinfo": ""}
    try:
        error_match = re.search(r"Error Message:\s*(.*)", line)
        if not error_match:
            return result

        error_msg = error_match.group(1).strip()
        matched_pattern = None
        for pattern in ERROR_PATTERNS:
            if pattern["keyword"] in error_msg:
                matched_pattern = pattern
                break

        if matched_pattern:
            base_type = matched_pattern["errortype"]
            extract_param = matched_pattern["extractParam"]
            if extract_param == "expect1st":
                param = extract_expect_first_param(line)
                result["errortype"] = f"{base_type}_{param}" if param else base_type
                result["errorinfo"] = extract_value_mismatch_info(line)
            elif extract_param == "first1st":
                param = extract_first_param_from_triple(line)
                result["errortype"] = f"{base_type}_{param}" if param else base_type
                result["errorinfo"] = extract_previous_uncompared_info(line, error_msg)
            else:
                result["errortype"] = base_type
                result["errorinfo"] = error_msg
        else:
            result["errortype"] = error_msg
            result["errorinfo"] = error_msg
    except Exception as exc:
        print(f"[WARN] 提取Error Message异常: {exc}")
        result["errortype"] = "OtherReason"
        result["errorinfo"] = f"解析异常: {exc}"
    return result


def analyze_script(root_dir, testname):
    root = Path(root_dir)
    log_folder = root / testname
    js_file = log_folder / f"{testname}.js"

    if not js_file.exists() or not js_file.is_file():
        print("[INFO]   日志文件不存在")
        return {"testname": testname, "errortype": "NoLog", "errorinfo": "日志文件不存在", "rawerrorlogtxt": []}

    log_lines = read_file_tail(js_file, MAX_TAIL_LINES)
    if not log_lines:
        return {"testname": testname, "errortype": "OtherReason", "errorinfo": "No error info", "rawerrorlogtxt": []}

    raw_lines = extract_raw_error_log_lines(log_lines)
    print(f"[INFO]   提取日志尾部成功，共 {len(raw_lines)} 行")

    dmp_files = [p for p in log_folder.iterdir() if p.is_file() and p.name.lower().endswith(".dmp")]
    if dmp_files:
        last_cmd = find_last_process_command_name(log_lines)
        print(f"[INFO]   发现崩溃文件：{', '.join(p.name for p in dmp_files)}")
        return {"testname": testname, "errortype": "Crash", "errorinfo": last_cmd or "No ProcessCommand found", "rawerrorlogtxt": raw_lines}

    last_line = find_last_non_empty_line(log_lines)
    if last_line is not None and last_line.startswith("//[DBG_WARN ]"):
        warn_info = extract_dbg_warn_info(last_line)
        print("[INFO]   发现DebugWarning")
        return {"testname": testname, "errortype": "DebugWarning", "errorinfo": warn_info, "rawerrorlogtxt": raw_lines}

    if last_line is not None and "Error Message:" in last_line:
        error_result = extract_error_message(last_line)
        last_cmd = find_last_process_command_name(log_lines)
        if last_cmd:
            if error_result["errorinfo"]:
                error_result["errorinfo"] += f"; ProcessCommand: {last_cmd}"
            else:
                error_result["errorinfo"] = f"ProcessCommand: {last_cmd}"
        print(f"[INFO]   错误消息类型：{error_result['errortype']}")
        return {
            "testname": testname,
            "errortype": error_result["errortype"],
            "errorinfo": error_result["errorinfo"],
            "rawerrorlogtxt": raw_lines,
        }

    last_cmd = find_last_process_command_name(log_lines)
    print("[INFO]   无明确错误消息，标记为OtherReason")
    return {"testname": testname, "errortype": "OtherReason", "errorinfo": last_cmd or "No error info", "rawerrorlogtxt": raw_lines}


def build_script_record(result, root_dir=None):
    record = {
        "testname": result.get("testname"),
        "errortype": result.get("errortype"),
        "errorinfo": result.get("errorinfo"),
        "rawerrorlogtxt": result.get("rawerrorlogtxt"),
    }
    comparison_images = build_comparison_images(result, root_dir)
    if comparison_images:
        record["comparison_images"] = comparison_images
    return record


def extract_expect_triple_from_errorinfo(errorinfo):
    if not isinstance(errorinfo, str):
        return None
    expect = re.search(r"期望值:\s*\[([^\]]+)\]", errorinfo)
    if expect:
        return expect.group(1)
    uncompared = re.search(r"未比较值:\s*\[([^\]]+)\]", errorinfo)
    if uncompared:
        return uncompared.group(1)
    return None


def build_category_key(result):
    errortype = result.get("errortype") or "Unclassified"
    if errortype == "DebugWarning":
        info = result.get("errorinfo")
        if isinstance(info, dict):
            detail_key = f"{info.get('File')}|{info.get('Line')}|{info.get('Function')}|{info.get('Message')}|{info.get('Name')}|{info.get('Date')}"
            return f"DebugWarning|{detail_key}"
        return errortype

    if errortype in ("不相等的值_windowTitle", "不相等的值_事务数据", "前面还有未比较的值_windowTitle", "前面还有未比较的值_事务数据"):
        expect_triple = extract_expect_triple_from_errorinfo(result.get("errorinfo"))
        if expect_triple:
            return f"{errortype}|{expect_triple}"
        return errortype

    if errortype == "OtherReason":
        info = result.get("errorinfo")
        if isinstance(info, str) and info:
            return f"OtherReason|{info}"
        if info is not None:
            return f"OtherReason|{info}"
        return "OtherReason|未知"

    return errortype


def classify_results(analysis_results, root_dir=None):
    groups = {}
    for result in analysis_results:
        category_key = build_category_key(result)
        if category_key not in groups:
            base_type = category_key.split("|", 1)[0] if "|" in category_key else category_key
            groups[category_key] = {"category_name": category_key, "base_type": base_type, "script_count": 0, "scripts": []}
        groups[category_key]["scripts"].append(build_script_record(result, root_dir))
    for group in groups.values():
        group["scripts"] = sort_scripts_by_name(group["scripts"])
        group["script_count"] = len(group["scripts"])
    return list(groups.values())


def sort_categories(categories):
    crash = [c for c in categories if c["category_name"] == "Crash"]
    no_log = [c for c in categories if c["category_name"] == "NoLog"]
    other_reason = [c for c in categories if c["category_name"].startswith("OtherReason")]
    rest = [c for c in categories if c["category_name"] != "Crash" and c["category_name"] != "NoLog" and not c["category_name"].startswith("OtherReason")]
    rest.sort(key=lambda c: (-c["script_count"], c["category_name"]))
    other_reason.sort(key=lambda c: (-c["script_count"], c["category_name"]))
    return crash + rest + other_reason + no_log


def run_analysis(root_path):
    root_dir = Path((root_path or "").strip())
    if not root_dir.exists() or not root_dir.is_dir():
        raise ValueError(f"目录不存在或不是有效目录 - {root_path}")

    print(f"[INFO] 根目录：{root_dir.absolute()}")
    ini_file = root_dir / "ErrorTestCollection.ini"
    if ini_file.exists() and ini_file.is_file():
        print("[INFO] 找到 ErrorTestCollection.ini，解析中...")
        testnames = parse_ini_file(ini_file)
        print(f"[INFO] 共解析到 {len(testnames)} 个唯一脚本名")
    else:
        print("[INFO] 未找到 INI，将使用一级子目录作为脚本名")
        testnames = collect_folder_names(root_dir)
        print(f"[INFO] 共找到 {len(testnames)} 个一级子目录")

    json_file = root_dir / "error_classification_result.json"
    html_file = root_dir / "error_classification_result.html"

    if not testnames:
        print("[WARN] 脚本列表为空，输出空结果")
        empty_output = {
            "summary": {
                "total_scripts": 0,
                "analyzed_scripts": 0,
                "categories_count": 0,
                "root_path": str(root_dir.absolute()),
            },
            "categories": [],
        }
        write_json_file(json_file, empty_output)
        write_html_report(html_file, empty_output)
        return {"jsonFile": json_file, "htmlFile": html_file, "summary": empty_output["summary"]}

    analysis_results = []
    for testname in testnames:
        print(f"[INFO] 开始分析脚本：{testname}")
        try:
            result = analyze_script(root_dir, testname)
            analysis_results.append(result)
            print(f"[INFO]   errortype={result.get('errortype')}")
        except Exception as exc:
            print(f"[ERROR] 分析异常：{testname} - {exc}")
            analysis_results.append({"testname": testname, "errortype": "OtherReason", "errorinfo": f"分析异常: {exc}", "rawerrorlogtxt": []})

    if OUTPUT_INTERMEDIATE_DATA:
        write_json_file(
            root_dir / "analysis_intermediate.json",
            {"total": len(testnames), "analysisResults": [build_script_record(r, root_dir) for r in analysis_results]},
        )

    categories = sort_categories(classify_results(analysis_results, root_dir))
    no_log_count = sum(1 for item in analysis_results if item.get("errortype") == "NoLog")
    output = {
        "summary": {
            "total_scripts": len(testnames),
            "analyzed_scripts": len(testnames) - no_log_count,
            "categories_count": len(categories),
            "root_path": str(root_dir.absolute()),
        },
        "categories": categories,
    }
    write_json_file(json_file, output)
    write_html_report(html_file, output)
    print(f"[INFO] 分类汇总完成，共 {len(categories)} 个类别")
    print(f"[INFO] 总脚本数: {len(testnames)}, 已分析: {len(testnames) - no_log_count}, 无日志: {no_log_count}")
    return {"jsonFile": json_file, "htmlFile": html_file, "summary": output["summary"]}


