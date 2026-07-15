from dataclasses import replace
from pathlib import Path

from tester_toolbox.config.settings import DEFAULT_LOCATE_TIMEOUT_SECONDS, LOCATE_RUN_COUNT_OPTIONS
from tester_toolbox.core.common import now_text
from tester_toolbox.core.paths import resolve_run_test_exe

from .ini_builder import build_ascii_ini_path, build_temp_ini
from .locate_common import normalize_tests_path, normalize_timeout_seconds, package_to_dict
from .models import LocateRequest, PackageRunResult, PerformancePoint, RegressionStandard
from .reports import write_loglocate_reports
from .run_bus import LOCATE_TASK_BUS
from .runner import run_and_collect_points
from .standards import is_regression, standard_to_dict
from .packages import prepare_package, resolve_extract_dir
from .packages import parse_package_source


def parse_point_line(line, default_standard="platform"):
    text = (line or "").strip()
    if not text or text.startswith("#"):
        return None
    parts = [part.strip() for part in text.split("|")]
    point_id = parts[0]
    point_type = parts[1] if len(parts) > 1 and parts[1] else "time"
    standard = parts[2] if len(parts) > 2 and parts[2] else default_standard
    threshold = float(parts[3]) if len(parts) > 3 and parts[3] else None

    if ".js::" in point_id:
        script_name, point_name = point_id.split("::", 1)
    elif ".js." in point_id:
        script_name, point_name = point_id.split(".js.", 1)
        script_name += ".js"
    elif "::" in point_id:
        script_name, point_name = point_id.split("::", 1)
    else:
        raise ValueError(f"性能点格式不正确：{line}。建议格式：脚本名.js::性能点名|time|平台标准")

    return PerformancePoint(
        script_name=Path(script_name.strip()).name,
        point_name=point_name.strip(),
        point_type=point_type,
        standard_name=standard,
        threshold=threshold,
    )


def parse_points_text(text, default_standard="platform"):
    points = []
    standards = {}
    for line in (text or "").splitlines():
        point = parse_point_line(line, default_standard)
        if not point:
            continue
        points.append(point)
        standards[point.key] = RegressionStandard(point.standard_name, point.threshold)
    if not points:
        raise ValueError("请至少输入一个性能点")
    return points, standards


def normalize_run_count(run_count):
    value = int(str(run_count).strip())
    if str(value) not in LOCATE_RUN_COUNT_OPTIONS:
        raise ValueError(f"运行次数 m 必须是 {', '.join(LOCATE_RUN_COUNT_OPTIONS)} 之一")
    return value


def point_key_from_point(point):
    log_name = Path(point.script_name).stem
    return f"{log_name}\u0001{point.point_name}\u0001{point.point_type}"


def index_points(points):
    return {f"{item.get('log_name')}\u0001{item.get('point_name')}\u0001{item.get('point_type')}": item for item in points}


class RegressionLocator:
    def __init__(self, request, task_bus=None):
        self.request = request
        self.task_bus = task_bus or LOCATE_TASK_BUS
        self.workspace = Path(request.workspace)
        self.packages = [parse_package_source(source, index) for index, source in enumerate(request.package_sources)]
        if len(self.packages) < 2:
            raise ValueError("性能衰退定位至少需要 2 个包")
        self.cache = {}
        self.run_records = []
        self.run_test_exe = resolve_run_test_exe()

    def grouped_points(self):
        groups = {}
        for point in self.request.performance_points:
            groups.setdefault(Path(point.script_name).name, []).append(point)
        return groups

    def prepared_package(self, package_index):
        self.task_bus.check_cancelled()
        package = self.packages[package_index]
        if package.extract_dir and Path(package.extract_dir).exists():
            effective_dir = resolve_extract_dir(Path(package.extract_dir))
            if effective_dir != Path(package.extract_dir):
                package = replace(package, extract_dir=effective_dir)
                self.packages[package_index] = package
            print(f"[INFO] 复用已准备包 [{package_index + 1}/{len(self.packages)}]：{package.package_name}")
            return package
        prepared = prepare_package(package, self.workspace, task_bus=self.task_bus)
        self.packages[package_index] = prepared
        return prepared

    def run_package_script(self, package_index, script_name):
        self.task_bus.check_cancelled()
        cache_key = (package_index, script_name)
        if cache_key in self.cache:
            print(f"[INFO] 复用 RunTest 缓存：包={self.packages[package_index].package_name}，脚本={script_name}")
            return self.cache[cache_key]

        package = self.prepared_package(package_index)
        print(
            f"[INFO] 开始 RunTest [{package_index + 1}/{len(self.packages)}]："
            f"包={package.package_name}，脚本={script_name}，ExePath={package.extract_dir}"
        )
        self.task_bus.check_cancelled()
        temp_ini = build_ascii_ini_path(package.index, script_name, self.workspace)
        print(f"[INFO] 生成临时 ini：{temp_ini}")
        build_temp_ini(self.request.tests_path, package.product, [script_name], self.request.run_count, temp_ini)
        self.task_bus.check_cancelled()
        raw_result, points = run_and_collect_points(
            self.run_test_exe,
            package.extract_dir,
            self.request.tests_path,
            self.request.mp_flag,
            temp_ini,
            self.request.timeout_seconds,
            task_bus=self.task_bus,
        )
        result = PackageRunResult(package, script_name, Path(raw_result.get("resultLogPath")), index_points(points))
        self.cache[cache_key] = result
        self.run_records.append({
            "package_index": package_index,
            "package_name": package.package_name,
            "script_name": script_name,
            "result_log_path": str(result.result_log_path),
            "point_count": len(points),
        })
        return result

    def get_point_detail(self, package_index, script_name, point):
        run_result = self.run_package_script(package_index, script_name)
        item = run_result.points.get(point_key_from_point(point)) or {}
        package = self.packages[package_index]
        return {
            "package_index": package_index,
            "package_name": package.package_name,
            "average": item.get("average"),
            "count": item.get("count"),
            "values": item.get("values") or [],
        }

    def get_average(self, package_index, script_name, point):
        detail = self.get_point_detail(package_index, script_name, point)
        average = detail.get("average")
        return float(average) if average is not None else None

    def append_pair_step(self, steps, previous_index, current_index, previous_average, current_average, **extra):
        steps.append({
            "previous_index": previous_index,
            "previous_package": self.packages[previous_index].package_name,
            "previous_average": previous_average,
            "package_index": current_index,
            "package": self.packages[current_index].package_name,
            "average": current_average,
            **extra,
        })

    def locate_point(self, script_name, point):
        package_count = len(self.packages)
        left = 0
        right = package_count - 1
        steps = []
        package_details = []
        details_by_index = {}

        def remember_detail(index, role=None):
            if index in details_by_index:
                if role:
                    details_by_index[index]["role"] = role
                return details_by_index[index]
            detail = self.get_point_detail(index, script_name, point)
            if role:
                detail["role"] = role
            details_by_index[index] = detail
            package_details.append(detail)
            return detail

        def average_at(index, role=None):
            detail = remember_detail(index, role=role)
            average = detail.get("average")
            return float(average) if average is not None else None

        mode = (point.standard_name or self.request.standard_mode or "").lower()
        if mode in ("none", "no_standard", "无标准"):
            for index in range(package_count):
                average = average_at(index, role="sample")
                steps.append({
                    "package_index": index,
                    "package": self.packages[index].package_name,
                    "average": average,
                    "role": "sample",
                })
            baseline = steps[0]["average"] if steps else None
            end_value = steps[-1]["average"] if steps else None
            return self.build_result(
                point, "data_only", baseline, end_value, None, None, steps, package_details,
                "无标准模式，仅采集并展示所有包数据",
            )

        start_average = average_at(0, role="start")
        end_average = average_at(package_count - 1, role="end")
        self.append_pair_step(steps, 0, package_count - 1, start_average, end_average, role="range_check")
        if not is_regression(start_average, end_average, point, self.request):
            return self.build_result(
                point,
                "no_regression",
                start_average,
                end_average,
                None,
                0,
                steps,
                package_details,
                "起始包与终止包未达到衰退标准，无需继续定位",
            )

        while right - left > 1:
            mid = (left + right) // 2
            if mid <= left:
                mid = left + 1
            left_average = average_at(left)
            mid_average = average_at(mid, role="search")
            regressed = is_regression(left_average, mid_average, point, self.request)
            self.append_pair_step(
                steps,
                left,
                mid,
                left_average,
                mid_average,
                regressed=regressed,
                role="search",
            )
            if regressed:
                right = mid
            else:
                left = mid

        left_average = average_at(left)
        right_average = average_at(right, role="culprit")
        self.append_pair_step(steps, left, right, left_average, right_average, role="culprit_pair")
        if not is_regression(left_average, right_average, point, self.request):
            return self.build_result(
                point,
                "unstable",
                left_average,
                right_average,
                None,
                left,
                steps,
                package_details,
                "最终相邻包对比结果不稳定，未达到衰退标准",
            )

        return self.build_result(
            point,
            "located",
            start_average,
            end_average,
            right,
            left,
            steps,
            package_details,
            "已定位相邻包中首次相对前包出现衰退的位置",
            culprit_average=right_average,
        )

    def build_result(
        self,
        point,
        status,
        baseline,
        end_value,
        culprit_index,
        previous_index,
        steps,
        package_details,
        message,
        culprit_average=None,
    ):
        culprit = package_to_dict(self.packages[culprit_index]) if culprit_index is not None else None
        previous = package_to_dict(self.packages[previous_index]) if previous_index is not None else None
        if culprit_average is None and culprit_index is not None:
            for detail in package_details:
                if detail.get("package_index") == culprit_index:
                    culprit_average = detail.get("average")
                    break
        return {
            "script_name": point.script_name,
            "point_name": point.point_name,
            "point_type": point.point_type,
            "status": status,
            "baseline_average": baseline,
            "end_average": end_value,
            "culprit_average": culprit_average,
            "standard": standard_to_dict(point, self.request),
            "previous_package": previous,
            "culprit_package": culprit,
            "package_details": sorted(package_details, key=lambda item: item.get("package_index", 0)),
            "steps": steps,
            "message": message,
        }

    def run(self):
        print(f"[INFO] 开始性能衰退定位：包 {len(self.packages)} 个，性能点 {len(self.request.performance_points)} 个")
        results = []
        for script_name, points in self.grouped_points().items():
            self.task_bus.check_cancelled()
            print(f"[INFO] 定位脚本：{script_name}，性能点 {len(points)} 个")
            for point in points:
                self.task_bus.check_cancelled()
                print(f"[INFO]   定位性能点：{point.point_name}")
                results.append(self.locate_point(script_name, point))
                print(f"[INFO]   性能点 {point.point_name} 结果：{results[-1].get('status')} - {results[-1].get('message')}")

        summary = {
            "package_count": len(self.packages),
            "point_count": len(self.request.performance_points),
            "regression_count": len([item for item in results if item.get("status") == "located"]),
            "generated_at": now_text(),
        }
        return {
            "summary": summary,
            "packages": [package_to_dict(package) for package in self.packages],
            "results": results,
            "run_cache": self.run_records,
        }


def run_regression_location(request, task_bus=None):
    bus = task_bus or LOCATE_TASK_BUS
    bus.check_cancelled()
    result = RegressionLocator(request, task_bus=bus).run()
    output_dir = Path(request.workspace) / "reports"
    print(f"[INFO] 写入定位报告：{output_dir}")
    reports = write_loglocate_reports(output_dir, result)
    print(f"[INFO] 报告已生成：{reports.get('htmlFile')}")
    return reports


def build_request_from_text(
    package_text,
    points_text,
    tests_path,
    workspace,
    run_count=1,
    timeout_seconds=DEFAULT_LOCATE_TIMEOUT_SECONDS,
    standard_mode="platform",
):
    package_sources = [line.strip().strip(",").strip('"') for line in (package_text or "").splitlines() if line.strip()]
    points, standards = parse_points_text(points_text, standard_mode)
    return LocateRequest(
        package_sources=package_sources,
        performance_points=points,
        tests_path=normalize_tests_path(tests_path),
        workspace=Path(workspace),
        run_count=normalize_run_count(run_count),
        timeout_seconds=normalize_timeout_seconds(timeout_seconds),
        standard_mode=standard_mode,
        standards=standards,
    )
