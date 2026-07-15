from tester_toolbox.core.performance import compare_performance_data


def resolve_standard(point, request):
    standard = request.standards.get(point.key) or request.standards.get(point.point_name)
    if standard:
        return standard.name, standard.threshold
    return point.standard_name or request.standard_mode, point.threshold


def is_regression(baseline_average, current_average, point, request):
    if baseline_average is None or current_average is None:
        return False

    mode, threshold = resolve_standard(point, request)
    mode = (mode or "platform").lower()
    current = float(current_average)
    baseline = float(baseline_average)

    if mode in ("none", "no_standard", "无标准"):
        return False
    if mode in ("platform", "平台标准"):
        return compare_performance_data(current, baseline, point.point_type) is False
    if mode in ("diff", "difference", "差值标准"):
        if threshold is None:
            raise ValueError(f"{point.script_name}.{point.point_name} 未设置差值阈值")
        return current - baseline > float(threshold)
    if mode in ("absolute", "abs", "绝对值标准"):
        if threshold is None:
            raise ValueError(f"{point.script_name}.{point.point_name} 未设置绝对值阈值")
        return current > float(threshold)
    raise ValueError(f"未知衰退标准：{mode}")


def standard_to_dict(point, request):
    mode, threshold = resolve_standard(point, request)
    return {"mode": mode, "threshold": threshold}
