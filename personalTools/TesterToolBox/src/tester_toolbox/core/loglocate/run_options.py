from dataclasses import dataclass


@dataclass(frozen=True)
class RunTestOptions:
    run_again_after_error: str = "0"
    debug_mode: str = "DisableRestoreIndicator;"
    require_exit_code_zero: bool = True


PERFORMANCE_RUN_OPTIONS = RunTestOptions(
    run_again_after_error="0",
    debug_mode="DisableRestoreIndicator;",
    require_exit_code_zero=True,
)

FUNCTIONAL_RUN_OPTIONS = RunTestOptions(
    run_again_after_error="1",
    debug_mode="DisableRestoreIndicator;RunDataAssuranceServiceEndOfJournal;",
    require_exit_code_zero=False,
)
