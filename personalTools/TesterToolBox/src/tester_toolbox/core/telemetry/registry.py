from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryFeatureConfig:
    feature_id: str
    display_name: str
    collect: bool = True
    collect_input: bool = True
    collect_result: bool = True


TELEMETRY_FEATURES = {
    "应用启动": TelemetryFeatureConfig("app_launch", "应用启动", collect=False),
    "清理工作空间": TelemetryFeatureConfig("clear_workspace", "清理工作空间"),
    "功能错误分析": TelemetryFeatureConfig("error_analysis", "功能错误分析"),
    "性能日志分析": TelemetryFeatureConfig("perf_log_analysis", "性能日志分析"),
    "性能结果对比": TelemetryFeatureConfig("perf_compare", "性能结果对比"),
    "性能衰退定位": TelemetryFeatureConfig("perf_regression_locate", "性能衰退定位"),
    "功能衰退定位": TelemetryFeatureConfig("functional_regression_locate", "功能衰退定位"),
    "文本对比": TelemetryFeatureConfig("text_compare", "文本对比"),
}

DEFAULT_FEATURE_CONFIG = TelemetryFeatureConfig("unknown", "未知功能")


def resolve_feature_config(feature_name: str) -> TelemetryFeatureConfig:
    return TELEMETRY_FEATURES.get(feature_name, DEFAULT_FEATURE_CONFIG)


def should_collect(feature_name: str, action: str = "run") -> bool:
    config = resolve_feature_config(feature_name)
    if not config.collect:
        return False
    if action == "launch":
        return False
    return True
