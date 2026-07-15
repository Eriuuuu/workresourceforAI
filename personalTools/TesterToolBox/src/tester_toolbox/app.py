import sys
import time

from tester_toolbox.core.log_analysis import run_analysis
from tester_toolbox.core.loglocate.engine import build_request_from_text, run_regression_location
from tester_toolbox.core.loglocate.run_bus import LOCATE_TASK_BUS, LocateTaskBusy
from tester_toolbox.core.performance import run_performance_analysis, run_performance_compare
from tester_toolbox.core.toolbox_log import summarize_operation_result, toolbox_log
from tester_toolbox.ui.main_window import start_gui


def print_usage():
    print("用法: python tester_toolbox.py <根目录路径>")
    print("性能分析: python tester_toolbox.py --performance <根目录路径>")
    print("性能对比: python tester_toolbox.py --compare <基线JSON> <当前JSON>")
    print("衰退定位: python tester_toolbox.py --locate <包列表txt> <性能点txt> <testsPath> <workspace>")
    print(r'例如: python tester_toolbox.py "I:\001程序测试\tests\脚本错误类型分析\2775"')


def _cli_run(feature, input_data, func):
    started_at = time.monotonic()
    try:
        result = func()
        toolbox_log.record(
            feature,
            "success",
            input_data=input_data,
            result_data=summarize_operation_result(result),
            duration_ms=int((time.monotonic() - started_at) * 1000),
            source="cli",
        )
        return result
    except Exception as exc:
        toolbox_log.record(
            feature,
            "failed",
            input_data=input_data,
            error=str(exc),
            duration_ms=int((time.monotonic() - started_at) * 1000),
            source="cli",
        )
        raise


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print_usage()
        return 0
    if not args or args[0] in ("--gui", "-gui"):
        start_gui()
        return 0
    if args[0] in ("--performance", "-performance", "--perf", "-perf"):
        if len(args) < 2:
            print("用法: python tester_toolbox.py --performance <根目录路径>")
            return 1
        try:
            _cli_run("性能日志分析", {"input_path": args[1]}, lambda: run_performance_analysis(args[1]))
            return 0
        except Exception as exc:
            print(f"[ERROR] {exc}")
            return 1
    if args[0] in ("--compare", "-compare"):
        if len(args) < 3:
            print("用法: python tester_toolbox.py --compare <基线JSON> <当前JSON>")
            return 1
        try:
            _cli_run(
                "性能结果对比",
                {"benchmark_path": args[1], "current_path": args[2]},
                lambda: run_performance_compare(args[1], args[2]),
            )
            return 0
        except Exception as exc:
            print(f"[ERROR] {exc}")
            return 1
    if args[0] in ("--locate", "-locate"):
        if len(args) < 5:
            print("用法: python tester_toolbox.py --locate <包列表txt> <性能点txt> <testsPath> <workspace>")
            return 1
        try:
            with open(args[1], "r", encoding="utf-8-sig") as file:
                package_text = file.read()
            with open(args[2], "r", encoding="utf-8-sig") as file:
                points_text = file.read()
            request = build_request_from_text(
                package_text=package_text,
                points_text=points_text,
                tests_path=args[3],
                workspace=args[4],
            )

            def run_locate():
                LOCATE_TASK_BUS.begin_task()
                try:
                    return run_regression_location(request, task_bus=LOCATE_TASK_BUS)
                finally:
                    LOCATE_TASK_BUS.end_task()

            _cli_run(
                "性能衰退定位",
                {
                    "package_list_file": args[1],
                    "points_file": args[2],
                    "tests_path": args[3],
                    "workspace": args[4],
                    "package_count": len(request.package_sources),
                    "point_count": len(request.performance_points),
                },
                run_locate,
            )
            return 0
        except LocateTaskBusy as exc:
            print(f"[ERROR] {exc}")
            return 1
        except Exception as exc:
            print(f"[ERROR] {exc}")
            return 1
    try:
        _cli_run("功能错误分析", {"input_path": args[0]}, lambda: run_analysis(args[0]))
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
