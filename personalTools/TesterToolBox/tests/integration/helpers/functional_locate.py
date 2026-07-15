"""Helpers for functional locate integration tests."""

import configparser
from pathlib import Path

from tester_toolbox.core.loglocate.models import FunctionalLocateRequest, PackageFunctionalRunResult


def write_collection_ini(path, sections):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    for section in sections:
        parser[section] = {
            "IsNeedToRun": "1",
            "JsFiles": f"{section}.js",
            "Count": "1",
        }
    with path.open("w", encoding="utf-8") as file:
        parser.write(file, space_around_delimiters=False)


def write_error_collection_ini(path, failed_sections, all_sections):
    parser = configparser.ConfigParser()
    parser.optionxform = str
    for section in all_sections:
        if section in failed_sections:
            parser[section] = {
                "IsNeedToRun": "1",
                "JsFiles": f"{section}.js",
                "Count": "1",
            }
    with path.open("w", encoding="utf-8") as file:
        parser.write(file, space_around_delimiters=False)


def make_package_sources(count):
    return [
        f"C:\\packages\\GAP\\20260101\\GAP_20260101_a_b_c_{index}.zip"
        for index in range(count)
    ]


def make_functional_request(workspace, tests_path, collection_ini, package_count, section_names=None):
    return FunctionalLocateRequest(
        package_sources=make_package_sources(package_count),
        collection_ini=Path(collection_ini),
        section_names=section_names or [],
        tests_path=Path(tests_path),
        workspace=Path(workspace),
        timeout_seconds=60,
        mp_flag="0",
    )


def failed_sections_at_package(first_fail_index_by_script, package_index, candidate_sections):
    return {
        section
        for section in candidate_sections
        if first_fail_index_by_script.get(section, 10**9) <= package_index
    }


def build_mock_run_with_ini(first_fail_index_by_script, enabled_sections, end_index):
    def mock_run_with_ini(locator, package_index, ini_path, role="run"):
        log_dir = locator.workspace / "mock_logs" / f"{package_index}_{role}"
        log_dir.mkdir(parents=True, exist_ok=True)

        if role == "end_full_run":
            failed = failed_sections_at_package(first_fail_index_by_script, end_index, enabled_sections)
        elif role == "start_failed_set_run":
            failed = failed_sections_at_package(first_fail_index_by_script, 0, enabled_sections)
        else:
            parser = configparser.ConfigParser()
            parser.optionxform = str
            parser.read(ini_path, encoding="utf-8-sig")
            active = {section for section in parser.sections() if parser.get(section, "IsNeedToRun", fallback="0") == "1"}
            failed = failed_sections_at_package(first_fail_index_by_script, package_index, active)

        write_error_collection_ini(log_dir / "ErrorTestCollection.ini", failed, enabled_sections)
        package = locator.packages[package_index]
        return PackageFunctionalRunResult(
            package=package,
            collection_ini=Path(ini_path),
            result_log_path=log_dir,
            failed_sections=failed,
        )

    return mock_run_with_ini


def prime_packages_with_extract_dir(locator, extract_root):
    for index, package in enumerate(locator.packages):
        package_dir = extract_root / f"pkg_{index}"
        package_dir.mkdir(parents=True, exist_ok=True)
        locator.packages[index] = package.__class__(
            **{**package.__dict__, "extract_dir": package_dir}
        )
