import json
import os
import re
from pathlib import Path

from .common import now_text, read_all_lines_with_fallback, round_double, write_json_file
from .reports import write_performance_compare_html_report, write_performance_html_report


def normalize_run_log_name(script_name):
    return re.sub(r"_\d+$", "", script_name)


def collect_js_files(root_dir):
    js_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            lower = name.lower()
            if lower.endswith(".js") and not lower.endswith("_full.js"):
                js_files.append(Path(dirpath) / name)
    return sorted(js_files, key=lambda p: str(p.absolute()))


def parse_duration_to_seconds(duration):
    text = (duration or "").strip().lower()
    if not text:
        return None
    try:
        total = 0.0
        matched = False
        for value, unit in re.findall(r"(?i)(\d+(?:\.\d+)?)(h|m|s)", text):
            matched = True
            number = float(value)
            unit = unit.lower()
            if unit == "h":
                total += number * 3600.0
            elif unit == "m":
                total += number * 60.0
            elif unit == "s":
                total += number
        if matched:
            return round_double(total, 4)
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            return float(text)
    except Exception:
        pass
    return None


def parse_time_performance_line(line):
    normalized = re.sub(r"^\ufeff", "", line or "", count=1).strip()
    if not normalized.startswith("JrnDbg.TimeEnd"):
        return None
    match = re.search(r'JrnDbg\.TimeEnd\(\s*"([^"]*)".*?//.*?本次耗时:\s*([0-9hmsHMS:.]+)', normalized)
    if not match:
        return None
    seconds = parse_duration_to_seconds(match.group(2))
    if seconds is None:
        return None
    return {"pointName": match.group(1), "value": seconds}


def parse_memory_performance_line(line):
    normalized = re.sub(r"^\ufeff", "", line or "", count=1).strip()
    if not normalized.startswith("JrnDbg.MemoryEnd"):
        return None
    match = re.search(r'JrnDbg\.MemoryEnd\(\s*"([^"]*)".*?//.*?本次耗内存:\s*([+-]?\d+(?:\.\d+)?)KB', normalized)
    if not match:
        return None
    return {"pointName": match.group(1), "value": float(match.group(2))}


def extract_performance_records(js_file, root_dir):
    script_name = js_file.name[:-3]
    log_name = normalize_run_log_name(script_name)
    relative_path = os.path.relpath(js_file, root_dir)
    records = []
    for index, line in enumerate(read_all_lines_with_fallback(js_file), start=1):
        time_record = parse_time_performance_line(line)
        if time_record:
            records.append({
                "log_name": log_name,
                "script_name": script_name,
                "file_path": relative_path,
                "line_number": index,
                "point_name": time_record["pointName"],
                "point_type": "time",
                "performance_data": time_record["value"],
            })
        memory_record = parse_memory_performance_line(line)
        if memory_record:
            records.append({
                "log_name": log_name,
                "script_name": script_name,
                "file_path": relative_path,
                "line_number": index,
                "point_name": memory_record["pointName"],
                "point_type": "memory",
                "performance_data": memory_record["value"],
            })
    return records


def build_performance_averages(raw_records):
    groups = {}
    for record in raw_records:
        key = (record["log_name"], record["point_name"], record["point_type"])
        groups.setdefault(key, []).append(record)
    points = []
    for (log_name, point_name, point_type), records in groups.items():
        values = [float(r["performance_data"]) for r in records]
        average = sum(values) / len(values)
        points.append({
            "log_name": log_name,
            "point_name": point_name,
            "point_type": point_type,
            "average": round_double(average, 4),
            "count": len(values),
            "values": [round_double(v, 4) for v in values],
        })
    return sorted(points, key=lambda p: (p["log_name"], p["point_type"], p["point_name"]))


def run_performance_analysis(root_path):
    root_dir = Path((root_path or "").strip())
    if not root_dir.exists() or not root_dir.is_dir():
        raise ValueError(f"目录不存在或不是有效目录 - {root_path}")

    print(f"[INFO] 性能日志根目录：{root_dir.absolute()}")
    js_files = collect_js_files(root_dir)
    print(f"[INFO] 共找到 {len(js_files)} 个 JS 日志文件")
    raw_records = []
    for js_file in js_files:
        print(f"[INFO] 解析性能日志：{js_file.name}")
        raw_records.extend(extract_performance_records(js_file, root_dir))

    points = build_performance_averages(raw_records)
    output = {
        "summary": {"total_js_files": len(js_files), "total_records": len(raw_records), "total_points": len(points), "generated_at": now_text()},
        "points": points,
    }
    json_file = root_dir / "performance_analysis_result.json"
    html_file = root_dir / "performance_analysis_result.html"
    write_json_file(json_file, output)
    write_performance_html_report(html_file, output)
    print(f"[INFO] 性能分析完成，共 {len(points)} 个统计点，原始记录 {len(raw_records)} 条")
    return {"jsonFile": json_file, "htmlFile": html_file, "summary": output["summary"]}


def build_performance_point_key(point):
    return f"{point.get('log_name')}\u0001{point.get('point_name')}\u0001{point.get('point_type')}"


def index_performance_points(points):
    return {build_performance_point_key(point): point for point in points}


def compare_performance_data(cluster_data, benchmark_data, point_type):
    diff = cluster_data - benchmark_data
    if point_type == "time":
        if benchmark_data < 1:
            if diff > 0.3:
                return False
            if diff < -0.3:
                return True
        else:
            if benchmark_data < 2:
                threshold = 30
            elif benchmark_data < 5:
                threshold = 20
            elif benchmark_data < 50:
                threshold = 15
            else:
                threshold = 10
            diff_percentage = (diff / benchmark_data) * 100
            if diff_percentage > threshold:
                return False
            if diff_percentage < -threshold:
                return True
    elif point_type == "memory":
        if benchmark_data == 0:
            return None
        diff_percentage = (diff / benchmark_data) * 100
        if diff_percentage > 10:
            return False
        if diff_percentage < -10:
            return True
    return None


def run_performance_compare(benchmark_json_path, current_json_path):
    benchmark_file = Path((benchmark_json_path or "").strip())
    current_file = Path((current_json_path or "").strip())
    if not benchmark_file.exists() or not benchmark_file.is_file():
        raise ValueError(f"基线 JSON 不存在或不是有效文件 - {benchmark_json_path}")
    if not current_file.exists() or not current_file.is_file():
        raise ValueError(f"当前 JSON 不存在或不是有效文件 - {current_json_path}")

    benchmark_data = json.loads(benchmark_file.read_text(encoding="utf-8-sig"))
    current_data = json.loads(current_file.read_text(encoding="utf-8-sig"))
    benchmark_index = index_performance_points(benchmark_data.get("points") or [])
    bad_list, good_list, non_list, same_list = [], [], [], []

    for current_point in current_data.get("points") or []:
        benchmark_point = benchmark_index.get(build_performance_point_key(current_point))
        if not benchmark_point:
            non_list.append({
                "log_name": current_point.get("log_name"),
                "point_name": current_point.get("point_name"),
                "point_type": current_point.get("point_type"),
                "current_average": current_point.get("average"),
                "current_values": current_point.get("values") or [],
                "benchmark": "notfound",
                "benchmark_values": [],
            })
            continue

        current_value = float(current_point.get("average"))
        benchmark_value = float(benchmark_point.get("average"))
        compare_result = compare_performance_data(current_value, benchmark_value, str(current_point.get("point_type")))
        item = {
            "log_name": current_point.get("log_name"),
            "point_name": current_point.get("point_name"),
            "point_type": current_point.get("point_type"),
            "current_average": round_double(current_value, 4),
            "benchmark_average": round_double(benchmark_value, 4),
            "diff": round_double(current_value - benchmark_value, 4),
            "current_values": current_point.get("values") or [],
            "benchmark_values": benchmark_point.get("values") or [],
        }
        if compare_result is False:
            bad_list.append(item)
        elif compare_result is True:
            good_list.append(item)
        else:
            same_list.append(item)

    output = {
        "summary": {
            "benchmark_file": str(benchmark_file.absolute()),
            "current_file": str(current_file.absolute()),
            "tolerance": "time: 按基线耗时区间使用绝对/百分比阈值; memory: 10%",
            "regression_count": len(bad_list),
            "improvement_count": len(good_list),
            "not_found_count": len(non_list),
            "unchanged_count": len(same_list),
            "generated_at": now_text(),
        },
        "衰退点个数": len(bad_list),
        "衰退points": bad_list,
        "优化点个数": len(good_list),
        "优化points": good_list,
        "未找到基线的点个数": len(non_list),
        "未找到基线的points": non_list,
        "无显著差异点个数": len(same_list),
        "无显著差异points": same_list,
    }

    output_file = current_file.parent / "performance_compare_result.json"
    html_file = current_file.parent / "performance_compare_result.html"
    write_json_file(output_file, output)
    write_performance_compare_html_report(html_file, output)
    print(f"[INFO] 性能对比完成，衰退 {len(bad_list)} 个，优化 {len(good_list)} 个，未找到基线 {len(non_list)} 个")
    return {"jsonFile": output_file, "htmlFile": html_file, "summary": output["summary"]}


