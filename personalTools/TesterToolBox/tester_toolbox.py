"""TesterToolBox 根入口。

实际应用代码位于 `src/tester_toolbox/app.py`。本文件只负责把项目的 `src`
目录加入模块搜索路径，并转发到包内主函数。
"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from tester_toolbox.app import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
