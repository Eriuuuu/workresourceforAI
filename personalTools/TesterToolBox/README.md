# TesterToolBox

TesterToolBox面向开发、测试和交付验证场景，提供日志分析、性能数据采集、性能结果对比、文本文件对比等效率工具。当前版本已切换为 Python 技术栈，并以综合工具箱为目标进行结构改造。

设计原则：

- 所有既有输入规则保持不变。
- 既有 JSON/HTML 输出文件名、字段和报告内容保持不变。
- 桌面 UI 以 ribbon 作为唯一主导航，ribbon 页签切换时同步切换所属功能页面。
- 打包结果按时间版本归档，便于回溯和分发。

## 主要功能

- 支持桌面界面选择本地脚本日志根目录。
- 支持一键运行功能脚本错误分类分析。
- 支持从性能脚本 `.js` 日志中提取 `JrnDbg.TimeEnd` 耗时数据。
- 支持从性能脚本 `.js` 日志中提取 `JrnDbg.MemoryEnd` 内存消耗数据。
- 支持把 `name/name_2/name_3` 等多次运行记录按同一日志名统计均值。
- 支持选择两个性能分析 JSON，并按均值判断性能衰退、优化或无显著差异。
- 支持生成 `error_classification_result.json` 和 `error_classification_result.html`。
- 支持生成 `performance_analysis_result.json` 和 `performance_analysis_result.html`。
- 支持生成 `performance_compare_result.json` 和 `performance_compare_result.html`。
- 支持“性能衰退定位”：按包序列串行运行 RunTest，复用下载/解压/执行缓存，用相邻包动态基准 + 二分法定位首次衰退包并输出提交人和 commit。
- 支持粗归类、细归类、搜索脚本名、展开/折叠错误详情。
- 支持 `.ifc`、`.gfc`、`.txt` 等文本文件选择或拖拽导入，按行对齐并对字符级差异高亮显示。
- 支持中文界面、中文日志和中文报告内容。

## 目录结构

```text
.
├─ tester_toolbox.py                根入口，转发到 src\tester_toolbox\app.py
├─ src\tester_toolbox               工具箱源码包
│  ├─ app.py                        CLI 编排入口
│  ├─ core                          核心业务逻辑：日志、性能、衰退定位、文本对比、报告生成
│  ├─ ui                            桌面 UI、ribbon 主窗口、历史记录
│  └─ config                        应用配置、规则和可调参数
├─ tests
│  ├─ unit                          单元测试
│  └─ integration                   集成测试
├─ third_party                      第三方程序或外部工具
├─ tools\build                      构建工具说明和后续构建脚本归档
├─ build-exe.ps1                    Windows 打包入口
├─ build-exe.bat                    可双击运行的 Windows 打包入口
├─ requirements.txt                 Python 打包依赖
└─ build
   └─ releases\yyyyMMdd-HHmmss      按时间版本保存的编译结果
```

当前 `tester_toolbox.py` 仅作为根入口，CLI 编排位于 `src\tester_toolbox\app.py`，核心业务在 `core`，桌面界面在 `ui`，配置参数在 `config`。后续新增工具也应按这个边界放置。

## 对外接口

### 桌面接口

```powershell
python .\tester_toolbox.py
python .\tester_toolbox.py --gui
```

不传参数或传入 `--gui` 时启动桌面界面。界面使用 ribbon 作为唯一功能导航；切换 ribbon 页签时，主页面会同步切换到该页签所属功能。

### 命令行接口

功能错误分析：

```powershell
python .\tester_toolbox.py <脚本日志根目录>
```

性能日志分析：

```powershell
python .\tester_toolbox.py --performance <脚本日志根目录>
```

性能结果对比：

```powershell
python .\tester_toolbox.py --compare <基线performance_analysis_result.json> <当前performance_analysis_result.json>
```

性能衰退定位：

```powershell
python .\tester_toolbox.py --locate <包列表txt> <性能点txt> <testsPath> <workspace>
```

`包列表txt` 每行一个本地、NAS 或 FTP 压缩包地址（`.zip`），按起始包到结束包顺序排列。`性能点txt` 每行一个性能点，推荐格式：

```text
脚本名.js::性能点名|time|平台标准
脚本名.js::性能点名|time|差值标准|0.5
脚本名.js::性能点名|memory|绝对值标准|1024
脚本名.js::性能点名|time|无标准
```

命令行接口会直接在输入目录或当前性能 JSON 所在目录生成既有 JSON/HTML 输出文件。

## 文件作用

```text
tester_toolbox.py                  根入口，只负责加载 src 并调用 tester_toolbox.app.main()
src\tester_toolbox\app.py          CLI 编排入口，分发 GUI、日志分析、性能分析、性能对比命令
src\tester_toolbox\__main__.py     包启动入口，后续支持 python -m tester_toolbox
src\tester_toolbox\__init__.py     包元信息
src\tester_toolbox\core\common.py  通用文件读写、编码兼容、JSON 写入、HTML/JS 转义
src\tester_toolbox\core\log_analysis.py
                                    功能脚本错误分类核心逻辑
src\tester_toolbox\core\performance.py
                                    性能日志采集、性能均值和性能结果对比
src\tester_toolbox\core\loglocate   性能衰退定位：包解析、下载/解压、ini 生成、RunTest 执行、二分定位、报告
src\tester_toolbox\core\reports.py JSON/HTML 报告生成
src\tester_toolbox\core\text_compare.py
                                    文本对比和字符级差异计算
src\tester_toolbox\core\toolbox_log.py
                                    操作审计日志：主机名、时间、功能、输入摘要、结果与报错
src\tester_toolbox\ui\main_window.py
                                    桌面主窗口、ribbon、功能页面和展示逻辑
src\tester_toolbox\ui\history.py   GUI 历史记录和本地偏好设置
src\tester_toolbox\config\settings.py
                                    应用标题、历史限制、错误匹配规则、正则配置、受限 ribbon 页签配置
tests\unit                         单元测试目录
tests\integration                  集成测试目录
third_party                        第三方程序目录
tools\build                        构建工具说明和后续构建脚本归档
build-exe.ps1                      Windows 打包脚本
build-exe.bat                      可双击运行的 Windows 打包入口
requirements.txt                   Python 依赖
build\releases                     按时间版本保存的编译结果
```

## 操作审计日志

工具箱会将 GUI 与 CLI 的主要操作写入本地审计日志，便于出问题时追溯。

**默认位置（与程序同目录）：**

```text
{TesterToolBox.exe 所在目录}\logs\toolbox-YYYYMMDD.jsonl
```

若程序目录不可写（如安装在受保护路径），则回退到：

```text
%APPDATA%\personalTools\errorLogClassification\logs\
```

GUI 中可通过右上角或运行日志区域的「打开审计日志 / 打开目录」直接进入该文件夹。下方运行日志区显示任务实时进度；审计日志为按天保存的 JSONL 文件，记录主机名、时间、功能、输入摘要、结果与报错。

## 目录输入要求

功能错误分析时，需要输入“脚本日志根目录”。工具会按以下规则获取待分析脚本列表：

1. 如果根目录下存在 `ErrorTestCollection.ini`，优先解析其中的 `JsFiles=` 配置，提取脚本名。
2. 如果不存在 `ErrorTestCollection.ini`，则使用根目录下的一级子目录名作为脚本名。
3. 对每个脚本，工具会在对应子目录中查找同名 `.js` 日志文件，例如：

```text
根目录
├─ ErrorTestCollection.ini
├─ ScriptA
│  └─ ScriptA.js
├─ ScriptB
│  └─ ScriptB.js
```

性能日志分析时，同样选择根目录。工具会递归扫描该目录下 `.js` 文件，但会跳过文件名以 `_full.js` 结尾的日志，提取以下日志行：

```text
JrnDbg.TimeEnd("性能点名", ...);//本次耗时:03.500s
JrnDbg.TimeEnd("性能点名", ...);//本次耗时:01m04.610s
JrnDbg.MemoryEnd("内存监控点名", ...);//...,本次耗内存:-96348KB,...
```

性能分析输出中的 `point_type` 取值为：

```text
time
memory
```

性能数据统一输出为数字，不带单位。时间会统一转换为秒，内存单位为 KB。

## 桌面程序使用方法

打包结果会输出到按时间命名的版本目录：

```text
build\releases\yyyyMMdd-HHmmss\TesterToolBox\TesterToolBox.exe
```

打包脚本还会自动生成一个快捷方式：

```text
build\TesterToolBox.lnk
```

使用步骤：

1. 双击运行 `TesterToolBox.exe`。
2. 在顶部 ribbon 工具带选择“日志与性能”“衰退定位”或“文本工具”。
3. 受限页签会在标题中显示状态图标，`●` 表示锁定，`✓` 表示已解锁；当前 `衰退定位`、`文本工具`、`扩展中心` 需要输入密码后才能访问。
4. 在“日志分析”页输入或选择待分析目录。
5. 点击“运行功能错误分析”生成错误分类结果，或点击“运行性能日志数据收集”生成性能均值结果。
6. 分析完成后，界面会显示生成的结果文件路径。
7. 点击“打开结果”查看结果文件，或点击“打开结果目录”查看全部输出文件。

性能对比步骤：

1. 先分别对基线目录和当前目录运行“性能日志数据收集”，得到两个 `performance_analysis_result.json`。
2. 在 ribbon 工具带中切换到“性能结果对比”功能。
3. 选择“基线性能 JSON”和“当前性能 JSON”。
4. 点击“运行性能对比”。
5. 查看生成的 `performance_compare_result.json` 和 `performance_compare_result.html`。

性能衰退定位步骤：

1. 在 ribbon 工具带选择“衰退定位”。
2. 选择本地工作空间。工具会在该目录下复用已下载压缩包、已解压目录、临时 ini（`locate_temp_ini/`）和执行缓存。
3. 选择或确认 `testsPath`（必须指向 `tests` 目录）。`RunTest_Console.exe` 由程序在后台自动解析，无需在界面配置。
4. 在“包地址列表”中逐个添加本地、NAS 或 FTP 压缩包地址（支持“选择”浏览本地 `.zip`，输入框也支持下拉历史），并用上移/下移确保顺序为起始包到结束包。
5. 在“性能点与衰退标准”中逐条添加脚本名、性能点名、类型、标准和阈值。
6. 设置运行次数与超时秒数（默认 360 秒），点击“运行性能衰退定位”。任务执行期间 RunTest 串行运行，可用“终止定位”随时取消；需等待当前任务完全结束后再启动下一次。
7. 查看 `performance_regression_location_result.json` 和 `performance_regression_location_result.html`。

衰退定位输入历史与易用性：

- 工作空间、`testsPath`、运行次数、超时秒数、包地址、脚本名、性能点名、阈值均支持下拉历史，最多保留 20 项。
- 性能点配置会保存为历史预设，可通过“历史性能点配置”一键加载。
- 启动时会自动恢复上次使用的完整配置；包列表支持双击回填编辑、回车快速添加、清空列表。
- 定位算法先比较起始包与终止包；若未达到衰退标准则停止。若存在整体衰退，再对中间包二分搜索，最终收敛到相邻两包并确认首次相对前包出现衰退的位置。

性能点阈值规则：

- `平台标准`：不需要输入阈值，使用性能结果对比中的平台标准。
- `无标准`：不需要输入阈值，仅采集并展示各包数据。
- `差值标准`：阈值支持正数、负数、0 和浮点数，按 `当前包均值 - 前一相邻包均值 > 阈值` 判定。
- `绝对值标准`：阈值支持正数、负数、0 和浮点数，按 `当前均值 > 阈值` 判定。

文本对比步骤：

1. 在 ribbon 工具带选择“文本工具”。
2. 主页面会切换到“文本对比”功能。
3. 分别选择左侧和右侧文本文件，也可以把文件拖拽到对应路径框或文本区域。
4. 点击“运行文本对比”。
5. 左右文本会按行展示并同步滚动；`!` 表示该行存在差异，红色表示左侧删除/差异，绿色表示右侧新增/差异，橙色表示替换片段，`-` 表示该侧缺失行。

分发给其他人使用时，请复制整个版本目录：

```text
build\releases\yyyyMMdd-HHmmss\TesterToolBox
```

不要只复制单个 exe 文件，因为该目录中还包含 Python 运行时和程序依赖。

## 输出文件说明

功能错误分析会在输入的脚本日志根目录下生成以下文件：

```text
error_classification_result.json
error_classification_result.html
```

`error_classification_result.json` 是结构化结果，适合后续程序读取或二次处理。

`error_classification_result.html` 是可直接打开的报告页面，适合人工查看分类结果、脚本列表和错误日志片段。

性能日志分析会在输入的脚本日志根目录下生成：

```text
performance_analysis_result.json
performance_analysis_result.html
```

核心字段：

```text
summary      汇总信息
points       按 日志名 + 性能点名 + 性能点类型 聚合后的均值数据
```

`points` 中每条记录包含：

```text
log_name          归并后的日志名，例如 name_2 会归并为 name
point_name        性能点名
point_type        time 或 memory
average           多次运行均值
count             参与统计的数据条数
values            每次运行的原始数值
```

性能结果对比会在“当前性能 JSON”所在目录下生成：

```text
performance_compare_result.json
performance_compare_result.html
```

HTML 文件用于界面“打开结果”查看，JSON 文件用于后续程序读取或二次处理。对比结果包含衰退点、优化点、未找到基线点和无显著差异点；每个性能点会保留当前与基线的原始 `values`，HTML 中可点击“详情”查看。

## 开发运行环境

如果只是使用已打包好的桌面程序，用户不需要安装任何环境。

如果需要开发、调试或重新打包，需要以下环境：

- Windows 10 或更高版本。
- Python 3.10 或更高版本，需包含 `python` 或 `py` 命令。
- `pip`。打包脚本会自动创建虚拟环境并安装 `requirements.txt` 中的依赖。
- `tkinterdnd2` 用于桌面界面的文件拖拽能力，由 `requirements.txt` 自动安装。

环境检查命令：

```powershell
python --version
py --version
python -m pip --version
```

## 命令行运行

命令行模式适合开发调试或批处理调用。

```powershell
cd j:\personalTools\errorlogclassification
python .\tester_toolbox.py "I:\001程序测试\tests\脚本错误类型分析\2775"
```

性能日志分析：

```powershell
python .\tester_toolbox.py --performance "I:\001程序测试\tests\性能日志目录"
```

性能结果对比：

```powershell
python .\tester_toolbox.py --compare "I:\baseline\performance_analysis_result.json" "I:\current\performance_analysis_result.json"
```

启动桌面界面：

```powershell
python .\tester_toolbox.py --gui
```

不传参数时，也会默认启动桌面界面：

```powershell
python .\tester_toolbox.py
```

## 编译与打包方法

在项目根目录执行：

```powershell
cd j:\personalTools\errorlogclassification
.\build-exe.ps1
```

如果希望双击打包，可以直接双击：

```text
build-exe.bat
```

打包脚本会执行以下工作：

1. 检查本机 Python。
2. 创建或复用 `build\.venv` 虚拟环境。
3. 安装 `requirements.txt` 中的 PyInstaller 和 tkinterdnd2。
4. 调用 PyInstaller 生成免安装 Windows 桌面程序。
5. 在 `build` 根目录自动生成 `TesterToolBox.lnk` 快捷方式。
6. 输出到 `build\releases\yyyyMMdd-HHmmss\TesterToolBox`。

也可以手动指定版本目录名：

```powershell
.\build-exe.ps1 -VersionStamp "20260709-113000"
```

成功后会看到类似输出：

```text
Done.
Release version: 20260709-113000
Portable executable: J:\personalTools\errorlogclassification\build\releases\20260709-113000\TesterToolBox\TesterToolBox.exe
Shortcut: J:\personalTools\errorlogclassification\build\TesterToolBox.lnk
```

## 常见问题

### 运行 exe 时中文显示异常

请确认使用的是最新打包结果。程序使用 Windows 常见中文字体，并使用 UTF-8 读写 JSON 与 HTML。如果仍有问题，优先在 Windows 中安装或启用 `Microsoft YaHei UI` / `Microsoft YaHei` 字体。

### 打包时报找不到 Python

说明当前命令行环境没有找到 Python。请确认已安装 Python 3.10 或更高版本，并且 `python` 或 `py` 可以在 PowerShell 中运行。

如果 Python 已安装但脚本仍找不到，可以临时设置：

```powershell
$env:Path="C:\Users\你的用户名\AppData\Local\Programs\Python\Python312;$env:Path"
.\build-exe.ps1
```

### 最终交付时能否只发 exe

不能。请交付整个目录：

```text
build\releases\yyyyMMdd-HHmmss\TesterToolBox
```

该目录中的 exe、Python 运行时和依赖文件需要放在一起。
