import unittest

import tests  # noqa: F401 — bootstrap src on sys.path

from tester_toolbox.core.loglocate.functional_engine import (
    apply_mid_to_interval,
    pick_shared_mid,
    should_apply_mid_to_interval,
    simulate_shared_binary_locate,
)

from tests.unit.helpers.binary_locate_helpers import (
    expected_boundaries,
    naive_total_binary_runs,
)


class FunctionalBinaryLocateTests(unittest.TestCase):
    def _run_case(self, scripts, package_count, first_fail, max_runs=None, max_vs_naive=None):
        located, run_packages, remaining = simulate_shared_binary_locate(scripts, package_count, first_fail)
        expected = expected_boundaries(first_fail)

        self.assertEqual(remaining, set(), f"未定位完成：{remaining}")
        self.assertEqual(located, expected)
        self.assertNotIn(0, run_packages)
        self.assertNotIn(package_count - 1, run_packages)
        self.assertEqual(len(run_packages), len(set(run_packages)), "不应重复运行同一中间包")

        naive_total = naive_total_binary_runs(first_fail, package_count)
        self.assertLessEqual(
            len(run_packages),
            naive_total,
            f"共享二分 {len(run_packages)} 次应不多于逐脚本独立总和 {naive_total} 次",
        )
        self.assertLessEqual(len(run_packages), package_count - 2, "中间包运行次数不应超过可选中间包数量")

        if max_runs is not None:
            self.assertLessEqual(len(run_packages), max_runs)
        if max_vs_naive is not None:
            self.assertLessEqual(len(run_packages), int(naive_total * max_vs_naive))

        return run_packages, naive_total

    def test_apply_mid_skips_outside_interval(self):
        self.assertEqual(apply_mid_to_interval(0, 6, 8, False), (0, 6))
        self.assertEqual(apply_mid_to_interval(7, 14, 6, True), (7, 14))

    def test_apply_mid_updates_inside_interval(self):
        self.assertEqual(apply_mid_to_interval(0, 14, 7, False), (0, 7))
        self.assertEqual(apply_mid_to_interval(0, 14, 7, True), (7, 14))

    def test_pick_shared_mid_prefers_useful_candidate(self):
        active = {"S1": (0, 6), "S3": (7, 14)}
        mid = pick_shared_mid(active, 15, {0, 14, 7})
        self.assertTrue(
            should_apply_mid_to_interval(*active["S1"], mid)
            or should_apply_mid_to_interval(*active["S3"], mid)
        )

    def test_scenario_scattered_four_on_fifteen(self):
        """4 脚本分别在第 3/6/10/15 包衰退，边界分散。"""
        first_fail = {"S1": 2, "S2": 5, "S3": 9, "S4": 14}
        runs, naive = self._run_case(list(first_fail), 15, first_fail, max_runs=13)
        self.assertLessEqual(len(runs), naive)

    def test_scenario_same_culprit_all_at_last_package(self):
        """4 脚本均在最后一包首次失败，应高度共享，RunTest 次数接近 log2(n)。"""
        first_fail = {"S1": 14, "S2": 14, "S3": 14, "S4": 14}
        runs, _naive = self._run_case(list(first_fail), 15, first_fail, max_runs=5)
        self.assertLessEqual(len(runs), 4)

    def test_scenario_clustered_adjacent_culprits(self):
        """4 脚本在第 3/4/5/6 包连续衰退，区间高度重叠。"""
        first_fail = {"S1": 2, "S2": 3, "S3": 4, "S4": 5}
        runs, naive = self._run_case(list(first_fail), 15, first_fail, max_runs=8)
        self.assertLess(len(runs), naive)

    def test_scenario_single_script_large_range(self):
        """单脚本 32 包，中间引入失败。"""
        first_fail = {"Only": 16}
        runs, _naive = self._run_case(["Only"], 32, first_fail, max_runs=6)
        self.assertLessEqual(len(runs), 5)

    def test_scenario_two_scripts_symmetric(self):
        """2 脚本对称分布在序列前段/后段。"""
        first_fail = {"Early": 4, "Late": 20}
        runs, naive = self._run_case(list(first_fail), 31, first_fail)
        self.assertLessEqual(len(runs), naive)
        self.assertLessEqual(len(runs), 10)

    def test_scenario_eight_scripts_evenly_spaced(self):
        """8 脚本在 64 包上均匀分布。"""
        scripts = [f"S{i}" for i in range(8)]
        first_fail = {name: (i + 1) * 8 - 1 for i, name in enumerate(scripts)}
        runs, naive = self._run_case(scripts, 64, first_fail)
        self.assertLessEqual(len(runs), naive)
        self.assertLessEqual(len(runs), 40)

    def test_scenario_minimal_two_packages(self):
        """仅 2 包时区间已相邻，筛查后直接完成，无需中间 RunTest。"""
        first_fail = {"S1": 1, "S2": 1}
        located, runs, remaining = simulate_shared_binary_locate(list(first_fail), 2, first_fail)
        self.assertEqual(located, {"S1": (0, 1), "S2": (0, 1)})
        self.assertEqual(runs, [])
        self.assertEqual(remaining, set())

    def test_scenario_three_packages_one_script(self):
        """3 包 1 脚本，culprit 在第 2 包，1 次中间 RunTest 即可。"""
        first_fail = {"S1": 1}
        located, runs, remaining = simulate_shared_binary_locate(["S1"], 3, first_fail)
        self.assertEqual(located, {"S1": (0, 1)})
        self.assertEqual(remaining, set())
        self.assertEqual(len(runs), 1)

    def test_scenario_many_scripts_same_early_culprit(self):
        """10 脚本同在第 5 包首次失败。"""
        scripts = [f"S{i}" for i in range(10)]
        first_fail = {name: 4 for name in scripts}
        runs, naive = self._run_case(scripts, 20, first_fail, max_runs=4)
        self.assertLess(len(runs), naive // 2)

    def test_scenario_staggered_pairs(self):
        """6 脚本成对衰退：第 4/5、8/9、12/13 包。"""
        first_fail = {"A": 3, "B": 4, "C": 7, "D": 8, "E": 11, "F": 12}
        runs, naive = self._run_case(list(first_fail), 16, first_fail)
        self.assertLessEqual(len(runs), naive)

    def test_scenario_one_early_one_late(self):
        """一前一后极端分布。"""
        first_fail = {"Front": 1, "Back": 49}
        runs, naive = self._run_case(list(first_fail), 50, first_fail)
        self.assertLessEqual(len(runs), naive)


class FunctionalBinaryEfficiencyReport(unittest.TestCase):
    """输出关键场景效率对比，便于人工审阅。"""

    def test_print_efficiency_summary(self):
        scenarios = [
            ("分散4/15", {"S1": 2, "S2": 5, "S3": 9, "S4": 14}, 15),
            ("同culprit", {f"S{i}": 14 for i in range(4)}, 15),
            ("连续3-6", {"S1": 2, "S2": 3, "S3": 4, "S4": 5}, 15),
            ("均匀8/64", {f"S{i}": (i + 1) * 8 - 1 for i in range(8)}, 64),
        ]
        lines = []
        for name, first_fail, n in scenarios:
            _located, runs, remaining = simulate_shared_binary_locate(list(first_fail), n, first_fail)
            naive = naive_total_binary_runs(first_fail, n)
            lines.append(
                f"{name}: shared={len(runs)}, naive_sum={naive}, "
                f"saved={naive - len(runs)}, remaining={len(remaining)}"
            )
        summary = "\n".join(lines)
        self.assertIn("shared=", summary)


if __name__ == "__main__":
    unittest.main()
