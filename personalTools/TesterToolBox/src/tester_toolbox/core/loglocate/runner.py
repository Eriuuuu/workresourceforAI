import json
import subprocess
import time
from pathlib import Path

from tester_toolbox.core.performance import build_performance_averages, collect_js_files, extract_performance_records

from .ini_builder import collect_failed_ini_sections
from .run_bus import RunTestCancelled
from .run_options import FUNCTIONAL_RUN_OPTIONS, PERFORMANCE_RUN_OPTIONS, RunTestOptions


def format_exit_code(return_code):
    unsigned = return_code & 0xFFFFFFFF
    return f"{return_code}（0x{unsigned:08X}）"


def run_test_by_ini(
    run_test_exe,
    app_exe_path,
    tests_path,
    mp_flag,
    ini_file,
    max_seconds,
    task_bus=None,
    options=None,
):
    run_options = options or PERFORMANCE_RUN_OPTIONS
    exe = Path(run_test_exe)
    if not exe.exists():
        raise FileNotFoundError(f"RunTest_Console.exe 不存在：{exe}")
    command = [
        str(exe),
        f"/ExePath:{app_exe_path}",
        f"/TestDir:{tests_path}",
        f"/RunTestCollectionFile:{ini_file}",
        "/MsecInterval:0",
        f"/OpenMP:{mp_flag}",
        f"/IsRunAgainAfterError:{run_options.run_again_after_error}",
        "/IsResultJson:1",
        f"/MaxSeconds:{max_seconds}",
        f"/DebugMode:{run_options.debug_mode}",
    ]
    print("[INFO] 执行 RunTest：" + " ".join(command))
    if task_bus:
        task_bus.check_cancelled()
    print(f"[INFO] RunTest 运行中，超时上限 {max_seconds} 秒...")
    process = subprocess.Popen(command)
    if task_bus:
        task_bus.attach_process(process)
    deadline = time.monotonic() + max_seconds + 60
    started_at = time.monotonic()
    last_report_at = started_at
    try:
        return_code = None
        while return_code is None:
            if task_bus:
                task_bus.check_cancelled()
            now = time.monotonic()
            if now - last_report_at >= 10:
                elapsed = int(now - started_at)
                print(f"[INFO] RunTest 仍在运行，已耗时 {elapsed} 秒...")
                last_report_at = now
            if now > deadline:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                raise TimeoutError(f"RunTest 超时：{ini_file}")
            try:
                return_code = process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                continue
    except RunTestCancelled:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        raise
    finally:
        if task_bus:
            task_bus.detach_process()
    if task_bus:
        task_bus.check_cancelled()
    if return_code != 0:
        print(f"[ERROR] RunTest 退出码：{format_exit_code(return_code)}")
    else:
        print(f"[INFO] RunTest 已完成，退出码：{return_code}")
    return return_code


def read_total_json_result(run_test_exe, previous_mtime=None):
    result_file = Path(run_test_exe).parent / "TotalJsonResult.json"
    if not result_file.exists():
        raise FileNotFoundError(f"RunTest 未生成结果 JSON：{result_file}")
    current_mtime = result_file.stat().st_mtime
    if previous_mtime is not None and current_mtime <= previous_mtime:
        raise RuntimeError(f"RunTest 结果 JSON 未更新，可能仍在使用历史结果：{result_file}")
    return json.loads(result_file.read_text(encoding="utf-8-sig"))


def validate_run_test_result(result, allow_failures=False):
    summary = result.get("summary") or {}
    failed = int(summary.get("failedCaseCount") or 0) + int(summary.get("timeoutCaseCount") or 0) + int(summary.get("killedCaseCount") or 0)
    passed = int(summary.get("passedCaseCount") or 0)
    total = int(summary.get("totalCaseCount") or 0)
    print(f"[INFO] RunTest 用例统计：通过 {passed}，失败/超时/被杀 {failed}，总计 {total}")
    if total <= 0:
        raise RuntimeError("RunTest 未执行任何用例，结果无效")
    if failed and not allow_failures:
        print(f"[WARN] RunTest 存在失败/超时/被杀用例：{failed}")
    elif failed:
        print(f"[INFO] RunTest 存在失败用例：{failed}（功能定位模式允许失败）")
    result_log_path = result.get("resultLogPath")
    if not result_log_path:
        raise ValueError("TotalJsonResult.json 中缺少 resultLogPath")
    log_dir = Path(result_log_path)
    if not log_dir.exists():
        raise FileNotFoundError(f"RunTest 结果日志目录不存在：{log_dir}")
    return result_log_path


def collect_log_performance_points(result_log_path, task_bus=None):
    root_dir = Path(result_log_path)
    raw_records = []
    js_files = collect_js_files(root_dir)
    total = len(js_files)
    if total == 0:
        raise FileNotFoundError(f"RunTest 结果日志目录中未找到性能 .js 日志：{root_dir}")
    for index, js_file in enumerate(js_files, 1):
        if task_bus:
            task_bus.check_cancelled()
        if index == 1 or index == total or index % max(1, total // 5) == 0:
            print(f"[INFO] 解析日志文件进度：{index}/{total}")
        raw_records.extend(extract_performance_records(js_file, root_dir))
    return build_performance_averages(raw_records)


def _read_run_test_result(run_test_exe, previous_mtime, return_code, options):
    if options.require_exit_code_zero and return_code != 0:
        raise RuntimeError(f"RunTest 执行失败，退出码：{format_exit_code(return_code)}")
    try:
        return read_total_json_result(run_test_exe, previous_mtime=previous_mtime)
    except Exception as exc:
        if return_code != 0:
            raise RuntimeError(f"RunTest 执行失败，退出码：{format_exit_code(return_code)}") from exc
        raise


def run_and_collect_points(run_test_exe, app_exe_path, tests_path, mp_flag, ini_file, max_seconds, task_bus=None):
    result_file = Path(run_test_exe).parent / "TotalJsonResult.json"
    previous_mtime = result_file.stat().st_mtime if result_file.exists() else None

    return_code = run_test_by_ini(
        run_test_exe,
        app_exe_path,
        tests_path,
        mp_flag,
        ini_file,
        max_seconds,
        task_bus=task_bus,
        options=PERFORMANCE_RUN_OPTIONS,
    )
    if task_bus:
        task_bus.check_cancelled()
    print("[INFO] 读取 RunTest 结果 JSON...")
    result = _read_run_test_result(run_test_exe, previous_mtime, return_code, PERFORMANCE_RUN_OPTIONS)
    result_log_path = validate_run_test_result(result, allow_failures=False)
    print(f"[INFO] 解析性能日志：{result_log_path}")
    points = collect_log_performance_points(result_log_path, task_bus=task_bus)
    print(f"[INFO] 解析完成，共 {len(points)} 个性能点")
    return result, points


def run_and_collect_functional_failures(run_test_exe, app_exe_path, tests_path, mp_flag, ini_file, max_seconds, task_bus=None):
    result_file = Path(run_test_exe).parent / "TotalJsonResult.json"
    previous_mtime = result_file.stat().st_mtime if result_file.exists() else None

    return_code = run_test_by_ini(
        run_test_exe,
        app_exe_path,
        tests_path,
        mp_flag,
        ini_file,
        max_seconds,
        task_bus=task_bus,
        options=FUNCTIONAL_RUN_OPTIONS,
    )
    if task_bus:
        task_bus.check_cancelled()
    print("[INFO] 读取 RunTest 结果 JSON...")
    result = _read_run_test_result(run_test_exe, previous_mtime, return_code, FUNCTIONAL_RUN_OPTIONS)
    result_log_path = validate_run_test_result(result, allow_failures=True)
    failed_sections = collect_failed_ini_sections(result_log_path)
    print(f"[INFO] 解析功能失败脚本：{result_log_path}，共 {len(failed_sections)} 个失败节")
    return result, result_log_path, failed_sections
