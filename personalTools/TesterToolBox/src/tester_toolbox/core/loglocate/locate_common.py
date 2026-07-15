from dataclasses import replace
from pathlib import Path

from tester_toolbox.config.settings import DEFAULT_LOCATE_TIMEOUT_SECONDS

from .packages import parse_package_source, prepare_package, resolve_extract_dir


def normalize_tests_path(tests_path):
    path = Path(tests_path).resolve()
    if path.name.lower() != "tests":
        raise ValueError(f"testsPath 必须指向 tests 目录：{tests_path}")
    return path


def normalize_timeout_seconds(timeout_seconds):
    value = int(str(timeout_seconds).strip())
    if value <= 0:
        raise ValueError("超时秒数必须是正整数")
    return value


def package_to_dict(package):
    return {
        "index": package.index,
        "source": package.source,
        "product": package.product,
        "date": package.date,
        "package_name": package.package_name,
        "archive_name": package.archive_name,
        "author": package.author,
        "sdk_commit": package.sdk_commit,
        "product_commit": package.product_commit,
        "local_archive": str(package.local_archive) if package.local_archive else "",
        "extract_dir": str(package.extract_dir) if package.extract_dir else "",
    }


class PackageWorkspaceMixin:
    def __init__(self, package_sources, workspace, task_bus, min_packages=2, feature_name="衰退定位"):
        self.task_bus = task_bus
        self.workspace = Path(workspace)
        self.packages = [parse_package_source(source, index) for index, source in enumerate(package_sources)]
        if len(self.packages) < min_packages:
            raise ValueError(f"{feature_name}至少需要 {min_packages} 个包")
        self.cache = {}
        self.run_records = []

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


def append_pair_step(steps, packages, previous_index, current_index, previous_value, current_value, **extra):
    steps.append({
        "previous_index": previous_index,
        "previous_package": packages[previous_index].package_name,
        "previous_value": previous_value,
        "package_index": current_index,
        "package": packages[current_index].package_name,
        "value": current_value,
        **extra,
    })


def run_binary_locate(package_count, packages, is_regressed_between, record_step=None):
    left = 0
    right = package_count - 1
    steps = []

    def remember(left_index, right_index, regressed, role):
        previous_value, current_value = None, None
        if record_step:
            previous_value, current_value = record_step(left_index, right_index)
        append_pair_step(
            steps,
            packages,
            left_index,
            right_index,
            previous_value,
            current_value,
            regressed=regressed,
            role=role,
        )

    while right - left > 1:
        mid = (left + right) // 2
        if mid <= left:
            mid = left + 1
        regressed = is_regressed_between(left, mid)
        remember(left, mid, regressed, role="search")
        if regressed:
            right = mid
        else:
            left = mid

    if not is_regressed_between(left, right):
        remember(left, right, False, role="culprit_pair")
        return "unstable", left, right, steps

    remember(left, right, True, role="culprit_pair")
    return "located", left, right, steps


def build_locate_request_defaults(timeout_seconds=DEFAULT_LOCATE_TIMEOUT_SECONDS):
    return {
        "timeout_seconds": normalize_timeout_seconds(timeout_seconds),
    }
