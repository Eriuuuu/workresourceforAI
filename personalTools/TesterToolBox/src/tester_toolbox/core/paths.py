import sys
from pathlib import Path

from tester_toolbox.config.settings import DEFAULT_RUN_TEST_EXE


def get_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def resolve_run_test_exe() -> Path:
    candidates = [
        get_runtime_root() / DEFAULT_RUN_TEST_EXE,
        Path(__file__).resolve().parents[3] / DEFAULT_RUN_TEST_EXE,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    searched = "\n".join(f"- {item}" for item in candidates)
    raise FileNotFoundError(f"未找到 RunTest_Console.exe，已尝试：\n{searched}")
