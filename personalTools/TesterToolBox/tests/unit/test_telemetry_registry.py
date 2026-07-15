import unittest

from tester_toolbox.core.telemetry.registry import resolve_feature_config, should_collect


class TelemetryRegistryTests(unittest.TestCase):
    def test_launch_event_not_collected(self):
        self.assertFalse(should_collect("应用启动", "launch"))

    def test_run_event_collected(self):
        self.assertTrue(should_collect("功能错误分析", "run"))

    def test_unknown_feature_defaults_to_collect(self):
        config = resolve_feature_config("未来新功能")
        self.assertEqual(config.feature_id, "unknown")
        self.assertTrue(should_collect("未来新功能", "run"))


if __name__ == "__main__":
    unittest.main()
