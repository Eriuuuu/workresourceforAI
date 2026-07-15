import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tests  # noqa: F401

from tester_toolbox.core.loglocate.functional_engine import (
    FunctionalRegressionLocator,
    build_functional_request_from_inputs,
)
from tester_toolbox.core.loglocate.run_options import FUNCTIONAL_RUN_OPTIONS, PERFORMANCE_RUN_OPTIONS

from tests.integration.helpers.functional_locate import (
    build_mock_run_with_ini,
    make_functional_request,
    make_package_sources,
    prime_packages_with_extract_dir,
    write_collection_ini,
)


class FunctionalLocateFlowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name) / "workspace"
        self.tests_path = Path(self._tmp.name) / "tests"
        self.workspace.mkdir()
        self.tests_path.mkdir()
        self.collection_ini = self.workspace / "user.ini"
        write_collection_ini(self.collection_ini, ["S1", "S2", "S3", "S4"])

    def tearDown(self):
        self._tmp.cleanup()

    def _run_locator(self, first_fail, package_count=15, sections=None):
        sections = sections or list(first_fail.keys())
        request = make_functional_request(
            self.workspace,
            self.tests_path,
            self.collection_ini,
            package_count,
            section_names=sections,
        )
        end_index = package_count - 1
        mock_runner = build_mock_run_with_ini(first_fail, set(sections), end_index)

        with patch.object(FunctionalRegressionLocator, "run_with_ini", mock_runner):
            locator = FunctionalRegressionLocator(request)
            prime_packages_with_extract_dir(locator, self.workspace / "extract")
            return locator.run()

    def test_flow_all_pass_at_end(self):
        first_fail = {"S1": 99, "S2": 99, "S3": 99}
        output = self._run_locator(first_fail, sections=["S1", "S2", "S3"])
        self.assertEqual(output["summary"]["overall_status"], "all_pass_at_end")
        self.assertEqual(output["screening"]["end_failed_sections"], [])
        self.assertTrue(all(item["status"] == "passed_at_end" for item in output["results"]))

    def test_flow_no_new_regression(self):
        first_fail = {"S1": 0, "S2": 0, "S3": 99}
        output = self._run_locator(first_fail, sections=["S1", "S2", "S3"])
        self.assertEqual(output["summary"]["overall_status"], "no_new_regression")
        self.assertEqual(set(output["screening"]["end_failed_sections"]), {"S1", "S2"})
        self.assertEqual(set(output["screening"]["start_failed_sections"]), {"S1", "S2"})
        self.assertEqual(output["screening"]["regression_scripts"], [])
        statuses = {item["section_name"]: item["status"] for item in output["results"]}
        self.assertEqual(statuses["S1"], "start_failed")
        self.assertEqual(statuses["S3"], "passed_at_end")

    def test_flow_located_regression_scripts(self):
        first_fail = {"S1": 0, "S2": 5, "S3": 9, "S4": 14}
        output = self._run_locator(first_fail)
        self.assertEqual(output["summary"]["overall_status"], "located")
        self.assertEqual(set(output["screening"]["regression_scripts"]), {"S2", "S3", "S4"})
        located = {
            item["section_name"]: (item["low_index"], item["high_index"])
            for item in output["results"]
            if item["status"] == "located"
        }
        self.assertEqual(located, {"S2": (4, 5), "S3": (8, 9), "S4": (13, 14)})
        self.assertGreater(len(output["binary_steps"]), 0)
        self.assertNotIn(0, [step["package_index"] for step in output["binary_steps"]])
        self.assertNotIn(14, [step["package_index"] for step in output["binary_steps"]])

    def test_flow_two_packages_no_binary_runs(self):
        first_fail = {"S1": 1}
        output = self._run_locator(first_fail, package_count=2, sections=["S1"])
        self.assertEqual(output["summary"]["overall_status"], "located")
        self.assertEqual(output["binary_steps"], [])
        result = output["results"][0]
        self.assertEqual(result["status"], "located")
        self.assertEqual(result["low_index"], 0)
        self.assertEqual(result["high_index"], 1)

    def test_build_functional_request_from_inputs(self):
        request = build_functional_request_from_inputs(
            make_package_sources(3),
            self.collection_ini,
            [],
            self.tests_path,
            self.workspace,
            120,
        )
        self.assertEqual(request.timeout_seconds, 120)
        self.assertEqual(request.section_names, ["S1", "S2", "S3", "S4"])
        self.assertEqual(request.tests_path.name.lower(), "tests")


class RunTestOptionsIntegrationTests(unittest.TestCase):
    def test_functional_and_performance_options_differ(self):
        self.assertEqual(FUNCTIONAL_RUN_OPTIONS.run_again_after_error, "1")
        self.assertEqual(PERFORMANCE_RUN_OPTIONS.run_again_after_error, "0")
        self.assertIn("RunDataAssuranceServiceEndOfJournal", FUNCTIONAL_RUN_OPTIONS.debug_mode)
        self.assertNotIn("RunDataAssuranceServiceEndOfJournal", PERFORMANCE_RUN_OPTIONS.debug_mode)
        self.assertFalse(FUNCTIONAL_RUN_OPTIONS.require_exit_code_zero)
        self.assertTrue(PERFORMANCE_RUN_OPTIONS.require_exit_code_zero)

    @patch("tester_toolbox.core.loglocate.runner.subprocess.Popen")
    def test_run_test_by_ini_command_uses_functional_options(self, popen_mock):
        import tests  # noqa: F401
        from tester_toolbox.core.loglocate.runner import run_test_by_ini

        process = popen_mock.return_value
        process.poll.return_value = 0
        process.wait.return_value = 0

        fake_exe = Path(tempfile.gettempdir()) / "RunTest_Console.exe"
        fake_exe.write_text("", encoding="utf-8")
        fake_result = fake_exe.parent / "TotalJsonResult.json"
        fake_result.write_text(
            '{"summary":{"failedCaseCount":1,"passedCaseCount":0,"totalCaseCount":1},'
            '"resultLogPath":"C:/tmp/log"}',
            encoding="utf-8",
        )

        run_test_by_ini(
            fake_exe,
            "C:/app",
            "C:/repo/tests",
            "0",
            "C:/collection.ini",
            30,
            options=FUNCTIONAL_RUN_OPTIONS,
        )

        command = popen_mock.call_args[0][0]
        joined = " ".join(command)
        self.assertIn("/IsRunAgainAfterError:1", joined)
        self.assertIn("RunDataAssuranceServiceEndOfJournal", joined)


if __name__ == "__main__":
    unittest.main()
