"""Shared helpers for functional shared-binary locate unit tests."""


def expected_boundaries(first_fail_index_by_script):
    return {
        section: (index - 1, index)
        for section, index in first_fail_index_by_script.items()
    }


def isolated_binary_run_count(first_fail_index, package_count):
    low, high = 0, package_count - 1
    runs = 0
    while high - low > 1:
        mid = (low + high) // 2
        if mid <= low:
            mid = low + 1
        if mid >= high:
            mid = high - 1
        runs += 1
        if first_fail_index > mid:
            low = mid
        else:
            high = mid
    return runs


def naive_total_binary_runs(first_fail_index_by_script, package_count):
    return sum(
        isolated_binary_run_count(index, package_count)
        for index in first_fail_index_by_script.values()
    )
