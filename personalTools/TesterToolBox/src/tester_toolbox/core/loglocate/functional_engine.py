from pathlib import Path

from tester_toolbox.core.common import now_text
from tester_toolbox.core.paths import resolve_run_test_exe

from .functional_reports import write_functional_locate_reports
from .ini_builder import (
    build_locate_ini_from_error_collection,
    get_error_collection_ini_path,
    list_enabled_ini_sections,
    prepare_functional_collection_ini,
)
from .locate_common import (
    PackageWorkspaceMixin,
    normalize_tests_path,
    normalize_timeout_seconds,
    package_to_dict,
)
from .models import FunctionalLocateRequest, PackageFunctionalRunResult
from .run_bus import LOCATE_TASK_BUS
from .runner import run_and_collect_functional_failures


def format_pass_fail(passed):
    return "通过" if passed else "失败"


def should_apply_mid_to_interval(low, high, mid):
    return low < mid < high


def apply_mid_to_interval(low, high, mid, passed):
    if not should_apply_mid_to_interval(low, high, mid):
        return low, high
    if passed:
        return mid, high
    return low, mid


def pick_shared_mid(active_intervals, package_count, executed_mids):
    if not active_intervals:
        return None

    def interval_bisect_point(low, high):
        mid = (low + high) // 2
        if mid <= low:
            mid = low + 1
        if mid >= high:
            mid = high - 1
        return mid

    candidates = []
    for mid in range(1, package_count - 1):
        if mid in executed_mids:
            continue
        covered = [(low, high) for low, high in active_intervals.values() if should_apply_mid_to_interval(low, high, mid)]
        if not covered:
            continue
        bisect_distance = sum(abs(mid - interval_bisect_point(low, high)) for low, high in covered)
        candidates.append((len(covered), bisect_distance, mid))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][2]


def simulate_shared_binary_locate(regression_scripts, package_count, first_fail_index_by_script):
    end_index = package_count - 1
    intervals = {section: [0, end_index] for section in regression_scripts}
    active_sections = set(regression_scripts)
    located = {}
    executed_mids = {0, end_index}
    run_packages = []

    for section in list(active_sections):
        low, high = intervals[section]
        if high - low == 1:
            located[section] = (low, high)
            active_sections.remove(section)

    def script_failed(section, package_index):
        return package_index >= first_fail_index_by_script[section]

    while active_sections:
        active_intervals = {section: tuple(intervals[section]) for section in active_sections}
        mid = pick_shared_mid(active_intervals, package_count, executed_mids)
        if mid is None:
            break
        executed_mids.add(mid)
        run_packages.append(mid)
        failed_sections = {section for section in active_sections if script_failed(section, mid)}

        completed = []
        for section in list(active_sections):
            low, high = intervals[section]
            if not should_apply_mid_to_interval(low, high, mid):
                continue
            passed = section not in failed_sections
            low, high = apply_mid_to_interval(low, high, mid, passed)
            intervals[section] = [low, high]
            if high - low == 1:
                located[section] = (low, high)
                completed.append(section)

        for section in completed:
            active_sections.remove(section)

    return located, run_packages, active_sections


class FunctionalRegressionLocator(PackageWorkspaceMixin):
    def __init__(self, request, task_bus=None):
        self.request = request
        super().__init__(
            request.package_sources,
            request.workspace,
            task_bus or LOCATE_TASK_BUS,
            feature_name="功能衰退定位",
        )
        self.user_ini = prepare_functional_collection_ini(request.collection_ini, self.workspace)
        self.run_test_exe = resolve_run_test_exe()
        self.package_run_cache = {}
        self.binary_steps = []

    def _cache_key(self, package_index, ini_path):
        ini_path = Path(ini_path).resolve()
        mtime = ini_path.stat().st_mtime if ini_path.exists() else 0
        return package_index, str(ini_path), mtime

    def run_with_ini(self, package_index, ini_path, role="run"):
        ini_path = Path(ini_path).resolve()
        cache_key = self._cache_key(package_index, ini_path)
        if cache_key in self.package_run_cache:
            package = self.packages[package_index]
            print(
                f"[INFO] 复用 RunTest 缓存：包={package.package_name}，"
                f"ini={ini_path.name}，阶段={role}"
            )
            return self.package_run_cache[cache_key]

        package = self.prepared_package(package_index)
        print(
            f"[INFO] 开始 RunTest [{package_index + 1}/{len(self.packages)}]："
            f"包={package.package_name}，ini={ini_path.name}，阶段={role}，ExePath={package.extract_dir}"
        )
        self.task_bus.check_cancelled()
        print(f"[INFO] 使用脚本集合 ini：{ini_path}")
        raw_result, result_log_path, failed_sections = run_and_collect_functional_failures(
            self.run_test_exe,
            package.extract_dir,
            self.request.tests_path,
            self.request.mp_flag,
            ini_path,
            self.request.timeout_seconds,
            task_bus=self.task_bus,
        )
        result = PackageFunctionalRunResult(
            package,
            ini_path,
            Path(result_log_path),
            set(failed_sections),
        )
        self.package_run_cache[cache_key] = result
        self.run_records.append({
            "package_index": package_index,
            "package_name": package.package_name,
            "collection_ini": str(ini_path),
            "role": role,
            "result_log_path": str(result.result_log_path),
            "failed_section_count": len(failed_sections),
            "failed_sections": sorted(failed_sections),
            "summary": raw_result.get("summary") or {},
        })
        return result

    def build_excluded_result(self, section_name, status, message):
        return {
            "section_name": section_name,
            "status": status,
            "previous_package": None,
            "culprit_package": None,
            "package_details": [],
            "steps": [],
            "message": message,
        }

    def build_located_result(self, section_name, low_index, high_index, steps, package_details):
        return {
            "section_name": section_name,
            "status": "located",
            "previous_package": package_to_dict(self.packages[low_index]),
            "culprit_package": package_to_dict(self.packages[high_index]),
            "low_index": low_index,
            "high_index": high_index,
            "package_details": package_details,
            "steps": steps,
            "message": f"已定位：B{low_index} 通过，B{high_index} 首次失败",
        }

    def run_shared_binary_locate(self, regression_scripts, error_collection_ini, end_index):
        package_count = len(self.packages)
        start_index = 0
        intervals = {section: [start_index, end_index] for section in regression_scripts}
        active_sections = set(regression_scripts)
        located_results = {}
        section_steps = {section: [] for section in regression_scripts}
        section_details = {section: [] for section in regression_scripts}
        executed_mids = {start_index, end_index}
        locate_ini = build_locate_ini_from_error_collection(
            error_collection_ini,
            active_sections,
            self.workspace,
        )

        pre_completed = []
        for section in list(active_sections):
            low, high = intervals[section]
            if high - low == 1:
                located_results[section] = self.build_located_result(
                    section,
                    low,
                    high,
                    section_steps[section],
                    section_details[section],
                )
                pre_completed.append(section)
        for section in pre_completed:
            active_sections.remove(section)
        if active_sections:
            locate_ini = build_locate_ini_from_error_collection(
                error_collection_ini,
                active_sections,
                self.workspace,
            )

        while active_sections:
            self.task_bus.check_cancelled()
            active_intervals = {s: tuple(intervals[s]) for s in active_sections}
            mid = pick_shared_mid(active_intervals, package_count, executed_mids)
            if mid is None:
                print("[WARN] 无可用中间包可执行，剩余脚本标记为 unstable")
                for section in list(active_sections):
                    located_results[section] = {
                        "section_name": section,
                        "status": "unstable",
                        "previous_package": None,
                        "culprit_package": None,
                        "package_details": section_details.get(section, []),
                        "steps": section_steps.get(section, []),
                        "message": "中间包已用尽，未能完成二分定位",
                    }
                    active_sections.remove(section)
                break

            executed_mids.add(mid)
            run_result = self.run_with_ini(mid, locate_ini, role="binary_search")
            failed_sections = run_result.failed_sections
            self.binary_steps.append({
                "role": "shared_binary",
                "package_index": mid,
                "package": self.packages[mid].package_name,
                "ini": str(locate_ini),
                "active_sections": sorted(active_sections),
                "failed_sections": sorted(failed_sections),
            })

            completed = []
            for section in list(active_sections):
                low, high = intervals[section]
                if not should_apply_mid_to_interval(low, high, mid):
                    continue
                passed = section not in failed_sections
                section_steps[section].append({
                    "role": "search",
                    "previous_index": low,
                    "previous_package": self.packages[low].package_name,
                    "previous_value": format_pass_fail(True),
                    "package_index": mid,
                    "package": self.packages[mid].package_name,
                    "value": format_pass_fail(passed),
                    "regressed": not passed,
                })
                section_details[section].append({
                    "package_index": mid,
                    "package_name": self.packages[mid].package_name,
                    "passed": passed,
                    "status": format_pass_fail(passed),
                    "role": "search",
                })
                low, high = apply_mid_to_interval(low, high, mid, passed)
                intervals[section] = [low, high]
                if high - low == 1:
                    located_results[section] = self.build_located_result(
                        section,
                        low,
                        high,
                        section_steps[section],
                        section_details[section],
                    )
                    completed.append(section)

            for section in completed:
                active_sections.remove(section)

            if active_sections:
                locate_ini = build_locate_ini_from_error_collection(
                    error_collection_ini,
                    active_sections,
                    self.workspace,
                )

        return located_results

    def run(self):
        package_count = len(self.packages)
        end_index = package_count - 1
        start_index = 0
        enabled_sections = set(list_enabled_ini_sections(self.user_ini))
        if self.request.section_names:
            requested = set(self.request.section_names)
            enabled_sections &= requested
        if not enabled_sections:
            raise ValueError("用户 ini 中未找到需要参与定位的 IsNeedToRun=1 脚本节")

        print(f"[INFO] 开始功能衰退定位：包 {package_count} 个，待测脚本节 {len(enabled_sections)} 个")
        print(f"[INFO] 用户 ini：{self.request.collection_ini}")

        print("[INFO] 步骤1：终止包全量运行 user.ini ...")
        end_run = self.run_with_ini(end_index, self.user_ini, role="end_full_run")
        error_collection_e = get_error_collection_ini_path(end_run.result_log_path)
        end_failed = set(end_run.failed_sections) & enabled_sections
        passed_at_end = enabled_sections - end_failed

        if not end_failed:
            print("[INFO] 终止包全部通过，无功能衰退")
            results = [
                self.build_excluded_result(section, "passed_at_end", "终止包通过，无需定位")
                for section in sorted(enabled_sections)
            ]
            return self.build_output(
                overall_status="all_pass_at_end",
                overall_message="终止包全部通过，无功能衰退",
                enabled_sections=enabled_sections,
                end_failed=set(),
                start_failed=set(),
                regression_scripts=set(),
                passed_at_end=passed_at_end,
                results=results,
            )

        if not error_collection_e.exists():
            raise FileNotFoundError(
                f"终止包存在失败脚本，但未生成 ErrorTestCollection.ini：{error_collection_e}"
            )

        print(f"[INFO] 步骤2：起始包运行终止失败集（共 {len(end_failed)} 个失败节）...")
        start_run = self.run_with_ini(start_index, error_collection_e, role="start_failed_set_run")
        start_failed = set(start_run.failed_sections) & end_failed
        regression_scripts = end_failed - start_failed

        print(f"[INFO] 终止失败 {len(end_failed)} 个，起始同样失败 {len(start_failed)} 个，新增衰退 {len(regression_scripts)} 个")

        results = []
        results.extend(
            self.build_excluded_result(section, "passed_at_end", "终止包通过，无需定位")
            for section in sorted(passed_at_end)
        )
        results.extend(
            self.build_excluded_result(section, "start_failed", "起始包同样失败，非本次新增衰退")
            for section in sorted(start_failed)
        )

        if not regression_scripts:
            print("[INFO] 起始包同样失败，无新增衰退脚本")
            return self.build_output(
                overall_status="no_new_regression",
                overall_message="起始包同样失败，无新增衰退脚本",
                enabled_sections=enabled_sections,
                end_failed=end_failed,
                start_failed=start_failed,
                regression_scripts=set(),
                passed_at_end=passed_at_end,
                results=results,
            )

        print(f"[INFO] 步骤3/4：生成 locate.ini 并对 {len(regression_scripts)} 个新增衰退脚本共享二分定位 ...")
        located_map = self.run_shared_binary_locate(
            sorted(regression_scripts),
            error_collection_e,
            end_index,
        )
        for section in sorted(regression_scripts):
            results.append(located_map.get(section) or self.build_excluded_result(
                section,
                "unstable",
                "未能完成定位",
            ))

        return self.build_output(
            overall_status="located",
            overall_message=f"已完成 {len([item for item in results if item.get('status') == 'located'])} 个脚本的新增衰退定位",
            enabled_sections=enabled_sections,
            end_failed=end_failed,
            start_failed=start_failed,
            regression_scripts=regression_scripts,
            passed_at_end=passed_at_end,
            results=results,
        )

    def build_output(
        self,
        overall_status,
        overall_message,
        enabled_sections,
        end_failed,
        start_failed,
        regression_scripts,
        passed_at_end,
        results,
    ):
        summary = {
            "overall_status": overall_status,
            "overall_message": overall_message,
            "package_count": len(self.packages),
            "enabled_section_count": len(enabled_sections),
            "end_failed_count": len(end_failed),
            "start_failed_count": len(start_failed),
            "regression_count": len([item for item in results if item.get("status") == "located"]),
            "passed_at_end_count": len(passed_at_end),
            "generated_at": now_text(),
        }
        return {
            "summary": summary,
            "packages": [package_to_dict(package) for package in self.packages],
            "collection_ini": str(self.request.collection_ini),
            "prepared_collection_ini": str(self.user_ini),
            "screening": {
                "enabled_sections": sorted(enabled_sections),
                "end_failed_sections": sorted(end_failed),
                "start_failed_sections": sorted(start_failed),
                "regression_scripts": sorted(regression_scripts),
                "passed_at_end_sections": sorted(passed_at_end),
            },
            "binary_steps": self.binary_steps,
            "results": results,
            "run_cache": self.run_records,
        }


def run_functional_regression_location(request, task_bus=None):
    bus = task_bus or LOCATE_TASK_BUS
    bus.check_cancelled()
    result = FunctionalRegressionLocator(request, task_bus=bus).run()
    output_dir = Path(request.workspace) / "reports"
    print(f"[INFO] 写入功能定位报告：{output_dir}")
    reports = write_functional_locate_reports(output_dir, result)
    print(f"[INFO] 报告已生成：{reports.get('htmlFile')}")
    return reports


def build_functional_request_from_inputs(
    package_sources,
    collection_ini,
    section_names,
    tests_path,
    workspace,
    timeout_seconds,
):
    ini_path = Path(collection_ini).resolve()
    if not ini_path.exists():
        raise FileNotFoundError(f"脚本集合 ini 不存在：{ini_path}")
    sections = [item.strip() for item in section_names if item and item.strip()]
    if not sections:
        sections = list_enabled_ini_sections(ini_path)
    if not sections:
        raise ValueError("脚本集合 ini 中未找到 IsNeedToRun=1 的节")
    return FunctionalLocateRequest(
        package_sources=package_sources,
        collection_ini=ini_path,
        section_names=sections,
        tests_path=normalize_tests_path(tests_path),
        workspace=Path(workspace),
        timeout_seconds=normalize_timeout_seconds(timeout_seconds),
    )
