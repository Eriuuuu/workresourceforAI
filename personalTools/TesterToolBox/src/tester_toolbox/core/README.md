# core

核心业务逻辑目录。这里放不依赖桌面控件的业务能力，便于后续单元测试和复用。

- `log_analysis.py`：功能脚本错误分类。
- `performance.py`：性能日志采集与性能结果对比。
- `loglocate/`：性能衰退定位，包括包管理、临时 ini 生成、RunTest 执行、二分定位和报告输出。
- `text_compare.py`：文本差异计算。
- `reports.py`：JSON/HTML 报告生成。
- `common.py`：文件读写、编码兼容、JSON 写入、转义和数值处理。
