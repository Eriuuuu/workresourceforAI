#!/usr/bin/env python3
"""Run all regression tests under tests/unit and tests/integration."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import tests  # noqa: E402, F401


def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    tests_root = Path(__file__).resolve().parent
    for folder in ("unit", "integration"):
        discovered = loader.discover(str(tests_root / folder), pattern="test_*.py")
        suite.addTests(discovered)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
