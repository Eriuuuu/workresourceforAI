import contextlib
import io
import os
import shutil
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from tkinter import BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, X, filedialog, messagebox, simpledialog
import tkinter as tk
from tkinter import ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

from tester_toolbox.config.settings import (
    APP_TITLE,
    DEFAULT_LOCATE_TIMEOUT_SECONDS,
    LOCATE_HISTORY_LIMIT,
    LOCATE_RUN_COUNT_OPTIONS,
    LOG_UI_FLUSH_MS,
    LOG_UI_MAX_LINES,
    RESTRICTED_RIBBON_LOCKED_ICON,
    RESTRICTED_RIBBON_PASSWORD,
    RESTRICTED_RIBBON_TABS,
    RESTRICTED_RIBBON_UNLOCKED_ICON,
)
from tester_toolbox.core.common import read_text_with_fallback, split_lines_like_groovy
from tester_toolbox.core.loglocate.engine import build_request_from_text, run_regression_location
from tester_toolbox.core.loglocate.functional_engine import build_functional_request_from_inputs, run_functional_regression_location
from tester_toolbox.core.loglocate.ini_builder import list_enabled_ini_sections
from tester_toolbox.core.loglocate.packages import is_remote_package_source, validate_local_package_archive
from tester_toolbox.core.loglocate.run_bus import LOCATE_TASK_BUS, LocateTaskBusy, RunTestCancelled
from tester_toolbox.core.log_analysis import run_analysis
from tester_toolbox.core.performance import run_performance_analysis, run_performance_compare
from tester_toolbox.core.text_compare import compare_text_lines
from tester_toolbox.core.toolbox_log import get_log_dir, summarize_operation_result, toolbox_log
from .history import HistoryStore


class LiveLogWriter(io.TextIOBase):
    def __init__(self, buffer, on_write):
        self.buffer = buffer
        self.on_write = on_write
        self._pending = ""

    def write(self, text):
        if not text:
            return 0
        self.buffer.write(text)
        self._pending += text
        if "\r" in self._pending and "\n" not in self._pending:
            chunk = self._pending.split("\r")[-1]
            self._pending = ""
            self.on_write(chunk, replace_last=True)
            return len(text)
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self.on_write(line + "\n", replace_last=False)
        return len(text)

    def flush(self):
        if self._pending:
            replace_last = "\r" in self._pending
            chunk = self._pending.split("\r")[-1] if replace_last else self._pending
            self.on_write(chunk, replace_last=replace_last)
            self._pending = ""


class LogAnalyzerApp:
    def __init__(self):
        self.root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
        self.root.title(APP_TITLE)
        self.root.minsize(900, 520)
        self.store = HistoryStore()
        self.last_result = {}
        self.last_compare_result = {}
        self.last_locate_result = {}
        self.last_func_locate_result = {}
        self.locate_sub_mode = "perf"
        self.drop_supported = TkinterDnD is not None
        self.authorized_ribbon_tabs = set()
        self.restricted_ribbon_tabs = set(RESTRICTED_RIBBON_TABS)
        self.ribbon_tab_titles = {}
        self.current_ribbon_index = 0
        self.suppress_ribbon_guard = False
        self._log_pending = []
        self._log_flush_job = None
        self._build_ui()
        toolbox_log.record(
            "应用启动",
            "success",
            {"mode": "gui", "log_dir": str(get_log_dir())},
            source="gui",
            action="launch",
        )

    def _build_ui(self):
        self.root.option_add("*Font", ("Microsoft YaHei UI", 9))
        style = ttk.Style()
        style.configure("Tool.TButton", padding=(14, 7))
        style.configure("Accent.TButton", padding=(14, 7))

        header = ttk.Frame(self.root, padding=(12, 10, 12, 0))
        header.pack(fill=X)
        ttk.Label(header, text=APP_TITLE, font=("Microsoft YaHei UI", 15, "bold")).pack(side=LEFT)
        ttk.Label(header, text="开发与测试效率工具箱", foreground="#667085").pack(side=LEFT, padx=(12, 0))

        self.ribbon = ttk.Notebook(self.root)
        self.ribbon.pack(fill=X, padx=12, pady=(10, 8))

        log_ribbon = ttk.Frame(self.ribbon, padding=8)
        locate_ribbon = ttk.Frame(self.ribbon, padding=8)
        text_ribbon = ttk.Frame(self.ribbon, padding=8)
        extend_ribbon = ttk.Frame(self.ribbon, padding=8)
        self.ribbon.add(log_ribbon, text="日志与性能")
        self.ribbon.add(locate_ribbon, text="衰退定位")
        self.ribbon.add(text_ribbon, text="文本工具")
        self.ribbon.add(extend_ribbon, text="扩展中心")
        self.ribbon_tab_titles = {
            0: "日志与性能",
            1: "衰退定位",
            2: "文本工具",
            3: "扩展中心",
        }
        self.update_all_ribbon_permission_markers()

        self.content_container = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        self.content_container.pack(fill=X)

        analyze_panel = ttk.Frame(self.content_container, padding=(0, 0, 0, 0))
        compare_panel = ttk.Frame(self.content_container, padding=(0, 0, 0, 0))
        locate_panel = ttk.Frame(self.content_container, padding=(0, 0, 0, 0))
        text_compare_panel = ttk.Frame(self.content_container, padding=(0, 0, 0, 0))
        extend_panel = ttk.Frame(self.content_container, padding=(0, 0, 0, 0))
        self.content_panels = [analyze_panel, compare_panel, locate_panel, text_compare_panel, extend_panel]

        ttk.Button(log_ribbon, text="日志分析", style="Tool.TButton", command=lambda: self.switch_content_tab(0)).pack(side=LEFT, padx=(0, 8))
        ttk.Button(log_ribbon, text="性能结果对比", style="Tool.TButton", command=lambda: self.switch_content_tab(1)).pack(side=LEFT, padx=(0, 8))
        ttk.Button(locate_ribbon, text="性能衰退定位", style="Tool.TButton", command=lambda: self.switch_locate_subtab("perf")).pack(side=LEFT, padx=(0, 8))
        ttk.Button(locate_ribbon, text="功能衰退定位", style="Tool.TButton", command=lambda: self.switch_locate_subtab("func")).pack(side=LEFT, padx=(0, 8))
        ttk.Label(locate_ribbon, text="按包序列二分定位首次引入失败的提交，复用本地包和 RunTest 缓存", foreground="#667085").pack(side=LEFT, padx=(8, 0))
        ttk.Button(text_ribbon, text="文本对比", style="Tool.TButton", command=lambda: self.switch_content_tab(3)).pack(side=LEFT, padx=(0, 8))
        ttk.Label(text_ribbon, text="支持 .ifc / .gfc / .txt，可选择或拖拽文件，按行内差异高亮", foreground="#667085").pack(side=LEFT, padx=(8, 0))
        ttk.Label(extend_ribbon, text="后续工具可按模块注册到这里，例如接口调试、批量处理、测试数据生成。", foreground="#667085").pack(side=LEFT)
        ttk.Label(extend_panel, text="扩展中心", font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(extend_panel, text="后续新增工具会以子页面方式接入 ribbon。", foreground="#667085").pack(anchor="w")

        input_group = ttk.LabelFrame(analyze_panel, text="输入本地日志根目录", padding=8)
        input_group.pack(fill=X, pady=(0, 8))
        self.path_combo = ttk.Combobox(input_group, values=self.store.get_list("directoryHistory"))
        self.path_combo.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(input_group, text="选择目录", command=self.choose_directory).pack(side=RIGHT, padx=(8, 0))

        action_panel = ttk.Frame(analyze_panel)
        action_panel.pack(fill=X, pady=(0, 8))
        self.run_error_button = ttk.Button(action_panel, text="运行功能错误分析", command=self.run_error_analysis)
        self.run_perf_button = ttk.Button(action_panel, text="运行性能日志数据收集", command=self.run_performance_analysis)
        self.open_report_button = ttk.Button(action_panel, text="打开结果", command=self.open_last_report, state=DISABLED)
        self.open_folder_button = ttk.Button(action_panel, text="打开结果目录", command=self.open_last_folder, state=DISABLED)
        for button in (self.run_error_button, self.run_perf_button, self.open_report_button, self.open_folder_button):
            button.pack(side=LEFT, padx=(0, 8))

        result_group = ttk.LabelFrame(analyze_panel, text="生成结果", padding=8)
        result_group.pack(fill=X)
        ttk.Label(result_group, text="结果文件：").pack(side=LEFT)
        self.result_var = tk.StringVar()
        ttk.Entry(result_group, textvariable=self.result_var, state="readonly").pack(side=LEFT, fill=X, expand=True)

        benchmark_group = ttk.LabelFrame(compare_panel, text="基线性能 JSON", padding=8)
        benchmark_group.pack(fill=X, pady=(0, 8))
        self.benchmark_combo = ttk.Combobox(benchmark_group, values=self.store.get_list("jsonFileHistory"))
        self.benchmark_combo.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(benchmark_group, text="选择基线 JSON", command=lambda: self.choose_json_file(self.benchmark_combo, "选择基线性能 JSON")).pack(side=RIGHT, padx=(8, 0))

        current_group = ttk.LabelFrame(compare_panel, text="当前性能 JSON", padding=8)
        current_group.pack(fill=X, pady=(0, 8))
        self.current_combo = ttk.Combobox(current_group, values=self.store.get_list("jsonFileHistory"))
        self.current_combo.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(current_group, text="选择当前 JSON", command=lambda: self.choose_json_file(self.current_combo, "选择当前性能 JSON")).pack(side=RIGHT, padx=(8, 0))

        compare_actions = ttk.Frame(compare_panel)
        compare_actions.pack(fill=X, pady=(0, 8))
        self.compare_button = ttk.Button(compare_actions, text="运行性能对比", command=self.run_compare)
        self.open_compare_button = ttk.Button(compare_actions, text="打开对比结果", command=self.open_compare_result, state=DISABLED)
        self.open_compare_folder_button = ttk.Button(compare_actions, text="打开结果目录", command=self.open_compare_folder, state=DISABLED)
        for button in (self.compare_button, self.open_compare_button, self.open_compare_folder_button):
            button.pack(side=LEFT, padx=(0, 8))

        compare_result_group = ttk.LabelFrame(compare_panel, text="对比结果", padding=8)
        compare_result_group.pack(fill=X)
        ttk.Label(compare_result_group, text="结果文件：").pack(side=LEFT)
        self.compare_result_var = tk.StringVar()
        ttk.Entry(compare_result_group, textvariable=self.compare_result_var, state="readonly").pack(side=LEFT, fill=X, expand=True)

        locate_env_row = ttk.Frame(locate_panel)
        locate_env_row.pack(fill=X, pady=(0, 4))
        workspace_group = ttk.LabelFrame(locate_env_row, text="工作空间", padding=(6, 4))
        workspace_group.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        self.locate_workspace_combo = ttk.Combobox(workspace_group, values=self.store.get_list("locateWorkspaceHistory", LOCATE_HISTORY_LIMIT))
        self.locate_workspace_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        ttk.Button(workspace_group, text="选择", command=self.choose_locate_workspace).pack(side=LEFT, padx=(0, 4))
        ttk.Button(workspace_group, text="清理", command=self.clear_locate_workspace).pack(side=LEFT)

        tests_group = ttk.LabelFrame(locate_env_row, text="testsPath（tests 目录）", padding=(6, 4))
        tests_group.pack(side=LEFT, fill=X, expand=True)
        self.locate_tests_combo = ttk.Combobox(tests_group, values=self.store.get_list("locateTestsHistory", LOCATE_HISTORY_LIMIT))
        self.locate_tests_combo.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))
        ttk.Button(tests_group, text="选择", command=self.choose_locate_tests_path).pack(side=LEFT)

        locate_option_group = ttk.LabelFrame(locate_panel, text="定位参数", padding=(6, 4))
        locate_option_group.pack(fill=X, pady=(0, 4))
        self.locate_run_count_label = ttk.Label(locate_option_group, text="运行次数 m")
        self.locate_run_count_label.pack(side=LEFT)
        self.locate_run_count_var = tk.StringVar(value="1")
        self.locate_run_count_combo = ttk.Combobox(
            locate_option_group,
            textvariable=self.locate_run_count_var,
            values=list(LOCATE_RUN_COUNT_OPTIONS),
            width=8,
            state="readonly",
        )
        self.locate_run_count_combo.pack(side=LEFT, padx=(6, 16))
        ttk.Label(locate_option_group, text="超时秒数").pack(side=LEFT)
        self.locate_timeout_var = tk.StringVar(value=str(DEFAULT_LOCATE_TIMEOUT_SECONDS))
        self.locate_timeout_combo = ttk.Combobox(
            locate_option_group,
            textvariable=self.locate_timeout_var,
            values=self.store.get_list("locateTimeoutHistory", LOCATE_HISTORY_LIMIT) or [str(DEFAULT_LOCATE_TIMEOUT_SECONDS)],
            width=10,
        )
        self.locate_timeout_combo.pack(side=LEFT, padx=(6, 0))

        packages_frame = ttk.LabelFrame(locate_panel, text="包地址列表（起始包 -> 结束包，支持本地/NAS/FTP）", padding=(6, 4))
        packages_frame.pack(fill=X, pady=(0, 4))
        package_edit = ttk.Frame(packages_frame)
        package_edit.pack(fill=X, pady=(0, 4))
        package_edit.columnconfigure(0, weight=1)
        self.locate_package_var = tk.StringVar()
        self.locate_package_combo = ttk.Combobox(
            package_edit,
            textvariable=self.locate_package_var,
            values=self.store.get_list("locatePackageHistory", LOCATE_HISTORY_LIMIT),
        )
        self.locate_package_combo.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.locate_package_combo.bind("<Return>", lambda _event: self.add_locate_package())
        package_buttons = ttk.Frame(package_edit)
        package_buttons.grid(row=1, column=0, sticky="w")
        ttk.Button(package_buttons, text="选择", command=self.choose_locate_package_zip).pack(side=LEFT, padx=(0, 6))
        ttk.Button(package_buttons, text="添加", command=self.add_locate_package).pack(side=LEFT, padx=(0, 6))
        ttk.Button(package_buttons, text="删除", command=self.remove_locate_package).pack(side=LEFT, padx=(0, 6))
        ttk.Button(package_buttons, text="上移", command=lambda: self.move_locate_package(-1)).pack(side=LEFT, padx=(0, 6))
        ttk.Button(package_buttons, text="下移", command=lambda: self.move_locate_package(1)).pack(side=LEFT, padx=(0, 6))
        ttk.Button(package_buttons, text="清空", command=self.clear_locate_packages).pack(side=LEFT)
        package_list_frame = ttk.Frame(packages_frame)
        package_list_frame.pack(fill=X)
        self.locate_packages_listbox = tk.Listbox(package_list_frame, height=3, activestyle="dotbox", exportselection=False, font=("Consolas", 9))
        package_scroll = ttk.Scrollbar(package_list_frame, orient="vertical", command=self.locate_packages_listbox.yview)
        package_xscroll = ttk.Scrollbar(packages_frame, orient="horizontal", command=self.locate_packages_listbox.xview)
        self.locate_packages_listbox.configure(yscrollcommand=package_scroll.set, xscrollcommand=package_xscroll.set)
        self.locate_packages_listbox.pack(side=LEFT, fill=X, expand=True)
        package_scroll.pack(side=RIGHT, fill="y")
        package_xscroll.pack(fill=X, pady=(2, 0))
        self.locate_packages_listbox.bind("<Double-Button-1>", self.edit_locate_package_from_list)

        points_frame = ttk.LabelFrame(locate_panel, text="性能点与衰退标准", padding=(6, 4))
        points_frame.pack(fill=X, pady=(0, 4))
        self.locate_points_frame = points_frame
        point_preset = ttk.Frame(points_frame)
        point_preset.pack(fill=X, pady=(0, 4))
        ttk.Label(point_preset, text="历史配置").pack(side=LEFT)
        self.locate_point_preset_combo = ttk.Combobox(point_preset, state="readonly", width=36)
        self.locate_point_preset_combo.pack(side=LEFT, fill=X, expand=True, padx=(6, 6))
        ttk.Button(point_preset, text="加载", command=self.load_locate_point_preset).pack(side=LEFT, padx=(0, 6))
        ttk.Button(point_preset, text="清空", command=self.clear_locate_points).pack(side=LEFT)
        point_editor = ttk.Frame(points_frame)
        point_editor.pack(fill=X, pady=(0, 4))
        ttk.Label(point_editor, text="脚本").pack(side=LEFT)
        self.locate_point_script_var = tk.StringVar()
        self.locate_point_script_combo = ttk.Combobox(
            point_editor,
            textvariable=self.locate_point_script_var,
            values=self.store.get_list("locateScriptHistory", LOCATE_HISTORY_LIMIT),
            width=24,
        )
        self.locate_point_script_combo.pack(side=LEFT, padx=(6, 10))
        ttk.Label(point_editor, text="性能点").pack(side=LEFT)
        self.locate_point_name_var = tk.StringVar()
        self.locate_point_name_combo = ttk.Combobox(
            point_editor,
            textvariable=self.locate_point_name_var,
            values=self.store.get_list("locatePointNameHistory", LOCATE_HISTORY_LIMIT),
            width=24,
        )
        self.locate_point_name_combo.pack(side=LEFT, padx=(6, 10))
        ttk.Label(point_editor, text="类型").pack(side=LEFT)
        self.locate_point_type_var = tk.StringVar(value="time")
        ttk.Combobox(point_editor, textvariable=self.locate_point_type_var, values=["time", "memory"], width=8, state="readonly").pack(side=LEFT, padx=(6, 10))
        ttk.Label(point_editor, text="标准").pack(side=LEFT)
        self.locate_point_standard_var = tk.StringVar(value="平台标准")
        self.locate_point_standard_combo = ttk.Combobox(
            point_editor,
            textvariable=self.locate_point_standard_var,
            values=["平台标准", "差值标准", "绝对值标准", "无标准"],
            width=12,
            state="readonly",
        )
        self.locate_point_standard_combo.pack(side=LEFT, padx=(6, 10))
        self.locate_point_standard_combo.bind("<<ComboboxSelected>>", lambda _event: self.on_locate_standard_changed())
        ttk.Label(point_editor, text="阈值").pack(side=LEFT)
        self.locate_point_threshold_var = tk.StringVar()
        self.locate_point_threshold_combo = ttk.Combobox(
            point_editor,
            textvariable=self.locate_point_threshold_var,
            values=self.store.get_list("locateThresholdHistory", LOCATE_HISTORY_LIMIT),
            width=10,
        )
        self.locate_point_threshold_combo.pack(side=LEFT, padx=(6, 10))
        ttk.Button(point_editor, text="添加/更新", command=self.upsert_locate_point).pack(side=LEFT, padx=(0, 6))
        ttk.Button(point_editor, text="删除", command=self.remove_locate_point).pack(side=LEFT)
        point_table_frame = ttk.Frame(points_frame)
        point_table_frame.pack(fill=X)
        self.locate_points_tree = ttk.Treeview(
            point_table_frame,
            columns=("script", "point", "type", "standard", "threshold"),
            show="headings",
            height=4,
        )
        for column, title, width in (
            ("script", "脚本", 180),
            ("point", "性能点", 180),
            ("type", "类型", 70),
            ("standard", "标准", 90),
            ("threshold", "阈值", 90),
        ):
            self.locate_points_tree.heading(column, text=title)
            self.locate_points_tree.column(column, width=width, anchor="w")
        point_scroll = ttk.Scrollbar(point_table_frame, orient="vertical", command=self.locate_points_tree.yview)
        self.locate_points_tree.configure(yscrollcommand=point_scroll.set)
        self.locate_points_tree.pack(side=LEFT, fill=X, expand=True)
        point_scroll.pack(side=RIGHT, fill="y")
        self.locate_points_tree.bind("<<TreeviewSelect>>", self.on_locate_point_selected)
        self.on_locate_standard_changed()
        self.refresh_locate_preset_combos()
        self.restore_locate_session()

        locate_actions = ttk.Frame(locate_panel)
        locate_actions.pack(fill=X, pady=(0, 4))
        self.locate_actions_frame = locate_actions
        self.locate_button = ttk.Button(locate_actions, text="运行性能衰退定位", command=self.run_loglocate)
        self.locate_stop_button = ttk.Button(locate_actions, text="终止定位", command=self.stop_loglocate, state=DISABLED)
        self.open_locate_button = ttk.Button(locate_actions, text="打开定位结果", command=self.open_locate_result, state=DISABLED)
        self.open_locate_folder_button = ttk.Button(locate_actions, text="打开结果目录", command=self.open_locate_folder, state=DISABLED)
        for button in (self.locate_button, self.locate_stop_button, self.open_locate_button, self.open_locate_folder_button):
            button.pack(side=LEFT, padx=(0, 8))
        self.locate_result_var = tk.StringVar()
        ttk.Entry(locate_actions, textvariable=self.locate_result_var, state="readonly").pack(side=LEFT, fill=X, expand=True)

        self.locate_func_frame = ttk.Frame(locate_panel)
        ini_frame = ttk.LabelFrame(self.locate_func_frame, text="脚本集合 ini（IsNeedToRun=1 的节将参与定位）", padding=(6, 4))
        ini_frame.pack(fill=X, pady=(0, 4))
        ini_input_row = ttk.Frame(ini_frame)
        ini_input_row.pack(fill=X, pady=(0, 4))
        ini_input_row.columnconfigure(0, weight=1)
        self.locate_func_ini_var = tk.StringVar()
        self.locate_func_ini_combo = ttk.Combobox(
            ini_input_row,
            textvariable=self.locate_func_ini_var,
            values=self.store.get_list("locateFunctionalIniHistory", LOCATE_HISTORY_LIMIT),
        )
        self.locate_func_ini_combo.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(ini_input_row, text="选择 ini", command=self.choose_functional_ini).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(ini_input_row, text="加载脚本节", command=self.load_functional_sections).grid(row=0, column=2)
        section_list_frame = ttk.Frame(ini_frame)
        section_list_frame.pack(fill=X)
        self.locate_func_sections_listbox = tk.Listbox(
            section_list_frame,
            height=6,
            activestyle="dotbox",
            exportselection=False,
            font=("Consolas", 9),
        )
        section_scroll = ttk.Scrollbar(section_list_frame, orient="vertical", command=self.locate_func_sections_listbox.yview)
        self.locate_func_sections_listbox.configure(yscrollcommand=section_scroll.set)
        self.locate_func_sections_listbox.pack(side=LEFT, fill=X, expand=True)
        section_scroll.pack(side=RIGHT, fill="y")

        func_actions = ttk.Frame(self.locate_func_frame)
        func_actions.pack(fill=X, pady=(0, 4))
        self.locate_func_button = ttk.Button(func_actions, text="运行功能衰退定位", command=self.run_functional_loglocate)
        self.locate_func_stop_button = ttk.Button(func_actions, text="终止定位", command=self.stop_loglocate, state=DISABLED)
        self.open_func_locate_button = ttk.Button(func_actions, text="打开定位结果", command=self.open_func_locate_result, state=DISABLED)
        self.open_func_locate_folder_button = ttk.Button(func_actions, text="打开结果目录", command=self.open_func_locate_folder, state=DISABLED)
        for button in (self.locate_func_button, self.locate_func_stop_button, self.open_func_locate_button, self.open_func_locate_folder_button):
            button.pack(side=LEFT, padx=(0, 8))
        self.locate_func_result_var = tk.StringVar()
        ttk.Entry(func_actions, textvariable=self.locate_func_result_var, state="readonly").pack(side=LEFT, fill=X, expand=True)
        self.restore_functional_locate_session()
        self.switch_locate_subtab("perf", focus=False)

        left_file_group = ttk.LabelFrame(text_compare_panel, text="左侧文本文件", padding=8)
        left_file_group.pack(fill=X, pady=(0, 8))
        self.left_text_file_var = tk.StringVar()
        self.left_text_file_entry = ttk.Entry(left_file_group, textvariable=self.left_text_file_var)
        self.left_text_file_entry.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(left_file_group, text="选择文件", command=lambda: self.choose_compare_text_file(self.left_text_file_var)).pack(side=RIGHT, padx=(8, 0))

        right_file_group = ttk.LabelFrame(text_compare_panel, text="右侧文本文件", padding=8)
        right_file_group.pack(fill=X, pady=(0, 8))
        self.right_text_file_var = tk.StringVar()
        self.right_text_file_entry = ttk.Entry(right_file_group, textvariable=self.right_text_file_var)
        self.right_text_file_entry.pack(side=LEFT, fill=X, expand=True)
        ttk.Button(right_file_group, text="选择文件", command=lambda: self.choose_compare_text_file(self.right_text_file_var)).pack(side=RIGHT, padx=(8, 0))

        text_compare_actions = ttk.Frame(text_compare_panel)
        text_compare_actions.pack(fill=X, pady=(0, 8))
        ttk.Button(text_compare_actions, text="运行文本对比", command=self.run_text_compare).pack(side=LEFT, padx=(0, 8))
        drop_tip = "可将文件拖拽到路径框或对应文本区域。" if self.drop_supported else "当前环境未启用拖拽，请使用“选择文件”。"
        self.text_compare_summary_var = tk.StringVar(value=f"请选择两个文本文件后开始对比。{drop_tip}")
        ttk.Label(text_compare_actions, textvariable=self.text_compare_summary_var, foreground="#667085").pack(side=LEFT)

        legend_frame = ttk.Frame(text_compare_panel)
        legend_frame.pack(fill=X, pady=(0, 8))
        ttk.Label(legend_frame, text="标识：").pack(side=LEFT)
        tk.Label(legend_frame, text="! 差异行正文", background="#fff0a6").pack(side=LEFT, padx=(0, 8))
        tk.Label(legend_frame, text="红色 左侧删除/差异字符", background="#ff8a80").pack(side=LEFT, padx=(0, 8))
        tk.Label(legend_frame, text="绿色 右侧新增/差异字符", background="#8ee6a2").pack(side=LEFT, padx=(0, 8))
        tk.Label(legend_frame, text="橙色 替换字符", background="#ffb74d").pack(side=LEFT, padx=(0, 8))
        tk.Label(legend_frame, text="- 缺失行正文", background="#ffccd5").pack(side=LEFT, padx=(0, 8))

        compare_view = ttk.Panedwindow(text_compare_panel, orient="horizontal")
        compare_view.pack(fill=BOTH, expand=True)
        left_text_frame = ttk.LabelFrame(compare_view, text="左侧内容", padding=4)
        right_text_frame = ttk.LabelFrame(compare_view, text="右侧内容", padding=4)
        compare_view.add(left_text_frame, weight=1)
        compare_view.add(right_text_frame, weight=1)

        self.left_text_view = tk.Text(left_text_frame, wrap="none", font=("Consolas", 10), height=14)
        self.right_text_view = tk.Text(right_text_frame, wrap="none", font=("Consolas", 10), height=14)
        self.syncing_text_scroll = False
        text_widgets = []
        for text_view, parent in ((self.left_text_view, left_text_frame), (self.right_text_view, right_text_frame)):
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(0, weight=1)
            y_scroll = ttk.Scrollbar(parent, orient="vertical", command=text_view.yview)
            x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=text_view.xview)
            text_view.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
            text_view.tag_configure("line_diff", background="#fff0a6", foreground="#111827")
            text_view.tag_configure("diff_replace", background="#ffb74d", foreground="#000000")
            text_view.tag_configure("diff_delete", background="#ff8a80", foreground="#000000")
            text_view.tag_configure("diff_insert", background="#8ee6a2", foreground="#000000")
            text_view.tag_configure("missing", background="#ffccd5", foreground="#7f1d1d")
            text_view.grid(row=0, column=0, sticky="nsew")
            y_scroll.grid(row=0, column=1, sticky="ns")
            x_scroll.grid(row=1, column=0, sticky="ew")
            text_view.tag_raise("line_diff")
            text_view.tag_raise("missing")
            text_view.tag_raise("diff_replace")
            text_view.tag_raise("diff_delete")
            text_view.tag_raise("diff_insert")
            text_widgets.append((text_view, y_scroll, x_scroll))

        self.left_y_scroll = text_widgets[0][1]
        self.left_x_scroll = text_widgets[0][2]
        self.right_y_scroll = text_widgets[1][1]
        self.right_x_scroll = text_widgets[1][2]
        self.left_y_scroll.configure(command=self.sync_text_yview)
        self.right_y_scroll.configure(command=self.sync_text_yview)
        self.left_x_scroll.configure(command=self.sync_text_xview)
        self.right_x_scroll.configure(command=self.sync_text_xview)
        self.left_text_view.configure(
            yscrollcommand=lambda first, last: self.on_text_y_scroll(self.left_text_view, first, last),
            xscrollcommand=lambda first, last: self.on_text_x_scroll(self.left_text_view, first, last),
        )
        self.right_text_view.configure(
            yscrollcommand=lambda first, last: self.on_text_y_scroll(self.right_text_view, first, last),
            xscrollcommand=lambda first, last: self.on_text_x_scroll(self.right_text_view, first, last),
        )
        for text_view in (self.left_text_view, self.right_text_view):
            text_view.bind("<MouseWheel>", self.on_synced_mousewheel)
            text_view.bind("<Shift-MouseWheel>", self.on_synced_shift_mousewheel)

        self.enable_file_drop(self.left_text_file_entry, self.left_text_file_var)
        self.enable_file_drop(self.right_text_file_entry, self.right_text_file_var)
        self.enable_file_drop(self.left_text_view, self.left_text_file_var)
        self.enable_file_drop(self.right_text_view, self.right_text_file_var)

        self.log_header = ttk.Frame(self.root, padding=(12, 4, 12, 0))
        self.audit_log_dir_var = tk.StringVar(value=f"审计日志目录：{get_log_dir()}")
        ttk.Label(self.log_header, text="运行日志", font=("Microsoft YaHei UI", 9, "bold")).pack(side=LEFT)
        ttk.Label(self.log_header, textvariable=self.audit_log_dir_var, foreground="#667085").pack(side=LEFT, padx=(12, 0))
        ttk.Button(self.log_header, text="打开日志", command=self.open_audit_log_dir).pack(side=RIGHT)

        self.log_frame = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        log_body = ttk.Frame(self.log_frame)
        log_body.pack(fill=BOTH, expand=True)
        self.log_area = tk.Text(log_body, wrap="none", font=("Consolas", 9), height=8)
        log_y_scroll = ttk.Scrollbar(log_body, orient="vertical", command=self.log_area.yview)
        log_x_scroll = ttk.Scrollbar(self.log_frame, orient="horizontal", command=self.log_area.xview)
        self.log_area.configure(yscrollcommand=log_y_scroll.set, xscrollcommand=log_x_scroll.set)
        self.log_area.grid(row=0, column=0, sticky="nsew")
        log_y_scroll.grid(row=0, column=1, sticky="ns")
        log_body.columnconfigure(0, weight=1)
        log_body.rowconfigure(0, weight=1)
        log_x_scroll.pack(fill=X)
        self.write_log(
            "[INFO] 下方为运行日志，执行任务时会实时显示进度与报错。\n"
            f"[INFO] 审计日志（操作追溯）目录：{get_log_dir()}\n"
            "[INFO] 可点击「打开日志」查看 toolbox-YYYYMMDD.jsonl 文件。\n"
        )
        self.ribbon.bind("<<NotebookTabChanged>>", self.on_ribbon_tab_changed)
        self.switch_content_tab(0)

    def update_combo_history(self, combo, values, selected):
        combo["values"] = values
        combo.set(selected)

    def on_text_y_scroll(self, source, first, last):
        if source is self.left_text_view:
            self.left_y_scroll.set(first, last)
            other = self.right_text_view
        else:
            self.right_y_scroll.set(first, last)
            other = self.left_text_view
        if self.syncing_text_scroll:
            return
        self.syncing_text_scroll = True
        other.yview_moveto(first)
        self.syncing_text_scroll = False

    def on_text_x_scroll(self, source, first, last):
        if source is self.left_text_view:
            self.left_x_scroll.set(first, last)
            other = self.right_text_view
        else:
            self.right_x_scroll.set(first, last)
            other = self.left_text_view
        if self.syncing_text_scroll:
            return
        self.syncing_text_scroll = True
        other.xview_moveto(first)
        self.syncing_text_scroll = False

    def sync_text_yview(self, *args):
        self.syncing_text_scroll = True
        self.left_text_view.yview(*args)
        self.right_text_view.yview(*args)
        self.syncing_text_scroll = False

    def sync_text_xview(self, *args):
        self.syncing_text_scroll = True
        self.left_text_view.xview(*args)
        self.right_text_view.xview(*args)
        self.syncing_text_scroll = False

    def on_synced_mousewheel(self, event):
        units = -1 * int(event.delta / 120) if event.delta else 0
        if units:
            self.sync_text_yview("scroll", units, "units")
        return "break"

    def on_synced_shift_mousewheel(self, event):
        units = -1 * int(event.delta / 120) if event.delta else 0
        if units:
            self.sync_text_xview("scroll", units, "units")
        return "break"

    def on_ribbon_tab_changed(self, _event=None):
        selected_index = self.ribbon.index(self.ribbon.select())
        if self.suppress_ribbon_guard:
            return
        selected_title = self.get_ribbon_tab_title(selected_index)
        if self.is_restricted_ribbon_tab(selected_index) and selected_title not in self.authorized_ribbon_tabs:
            if not self.verify_restricted_ribbon_access(selected_index):
                self.suppress_ribbon_guard = True
                self.ribbon.select(self.current_ribbon_index)
                self.suppress_ribbon_guard = False
                self.switch_content_tab({0: 0, 1: 2, 2: 3, 3: 4}.get(self.current_ribbon_index, 0))
                return
            self.authorized_ribbon_tabs.add(selected_title)
            self.update_ribbon_permission_marker(selected_index)
        default_pages = {0: 0, 1: 2, 2: 3, 3: 4}
        self.current_ribbon_index = selected_index
        self.switch_content_tab(default_pages.get(selected_index, 0))

    def get_ribbon_tab_title(self, tab_index):
        return self.ribbon_tab_titles.get(tab_index, self.ribbon.tab(tab_index, "text"))

    def is_restricted_ribbon_tab(self, tab_index):
        return self.get_ribbon_tab_title(tab_index) in self.restricted_ribbon_tabs

    def update_ribbon_permission_marker(self, tab_index):
        title = self.get_ribbon_tab_title(tab_index)
        if title not in self.restricted_ribbon_tabs:
            self.ribbon.tab(tab_index, text=title)
            return
        icon = RESTRICTED_RIBBON_UNLOCKED_ICON if title in self.authorized_ribbon_tabs else RESTRICTED_RIBBON_LOCKED_ICON
        self.ribbon.tab(tab_index, text=f"{icon} {title}")

    def update_all_ribbon_permission_markers(self):
        for tab_index in self.ribbon_tab_titles:
            self.update_ribbon_permission_marker(tab_index)

    def verify_restricted_ribbon_access(self, tab_index):
        tab_name = self.get_ribbon_tab_title(tab_index)
        password = simpledialog.askstring("权限验证", f"请输入访问“{tab_name}”的密码(付费功能)：", show="*", parent=self.root)
        if password == RESTRICTED_RIBBON_PASSWORD:
            return True
        if password is not None:
            messagebox.showwarning("权限不足", "密码错误，暂不能访问该功能。")
        return False

    def switch_locate_subtab(self, mode, focus=True):
        self.locate_sub_mode = mode
        if focus:
            self.switch_content_tab(2)
        if mode == "func":
            self.locate_points_frame.pack_forget()
            self.locate_actions_frame.pack_forget()
            self.locate_run_count_label.pack_forget()
            self.locate_run_count_combo.pack_forget()
            self.locate_func_frame.pack(fill=X, pady=(0, 4))
        else:
            self.locate_func_frame.pack_forget()
            self.locate_run_count_label.pack(side=LEFT)
            self.locate_run_count_combo.pack(side=LEFT, padx=(6, 16))
            self.locate_points_frame.pack(fill=X, pady=(0, 4))
            self.locate_actions_frame.pack(fill=X, pady=(0, 4))

    def switch_content_tab(self, index):
        for panel in self.content_panels:
            panel.pack_forget()
        self.content_panels[index].pack(fill=BOTH, expand=True)
        if index in (0, 1, 2):
            self.content_container.pack_configure(fill=X, expand=False)
            if not self.log_frame.winfo_ismapped():
                self.log_header.pack(fill=X)
                self.log_frame.pack(fill=BOTH, expand=True)
        else:
            self.log_header.pack_forget()
            self.log_frame.pack_forget()
            self.content_container.pack_configure(fill=BOTH, expand=True)

    def choose_directory(self):
        initial = self.preferred_directory()
        selected = filedialog.askdirectory(title="选择待分析的根目录", initialdir=initial or None)
        if selected:
            history = self.store.remember("directoryHistory", "lastDirectory", selected)
            self.update_combo_history(self.path_combo, history, selected)

    def preferred_directory(self):
        candidates = [self.store.get_last("lastDirectory"), self.path_combo.get(), *self.store.get_list("directoryHistory")]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate if Path(candidate).is_dir() else str(Path(candidate).parent)
        return None

    def preferred_json_directory(self):
        candidates = [self.store.get_last("lastJsonFile"), self.benchmark_combo.get(), self.current_combo.get(), *self.store.get_list("jsonFileHistory")]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                path = Path(candidate)
                return str(path.parent if path.is_file() else path)
        return None

    def choose_json_file(self, combo, title):
        selected = filedialog.askopenfilename(title=title, initialdir=self.preferred_json_directory() or None, filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")])
        if selected:
            history = self.store.remember("jsonFileHistory", "lastJsonFile", selected)
            self.update_combo_history(self.benchmark_combo, history, self.benchmark_combo.get())
            self.update_combo_history(self.current_combo, history, self.current_combo.get())
            combo.set(selected)

    def preferred_locate_directory(self):
        candidates = [
            self.store.get_last("lastLocateWorkspace"),
            self.locate_workspace_combo.get(),
            self.store.get_last("lastLocateTests"),
            self.locate_tests_combo.get(),
            *self.store.get_list("locateWorkspaceHistory"),
            *self.store.get_list("locateTestsHistory"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                path = Path(candidate)
                return str(path if path.is_dir() else path.parent)
        return None

    def choose_locate_workspace(self):
        selected = filedialog.askdirectory(title="选择衰退定位工作空间", initialdir=self.preferred_locate_directory() or None)
        if selected:
            history = self.store.remember("locateWorkspaceHistory", "lastLocateWorkspace", selected, LOCATE_HISTORY_LIMIT)
            self.update_combo_history(self.locate_workspace_combo, history, selected)

    def clear_locate_workspace(self):
        workspace = self.locate_workspace_combo.get().strip()
        if not workspace:
            messagebox.showwarning("提示", "请先选择工作空间。")
            return
        path = Path(workspace)
        if not path.exists() or not path.is_dir():
            messagebox.showwarning("提示", "工作空间不存在或不是有效目录。")
            return
        if not messagebox.askyesno("确认清理", f"将清空工作空间内的全部文件和子目录：\n{path}\n\n此操作不可恢复，是否继续？"):
            return
        try:
            for child in path.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        except OSError as exc:
            toolbox_log.record(
                "清理工作空间",
                "failed",
                {"workspace": str(path)},
                error=str(exc),
                source="gui",
                action="clear",
            )
            messagebox.showerror("清理失败", str(exc))
            return
        toolbox_log.record(
            "清理工作空间",
            "success",
            {"workspace": str(path)},
            source="gui",
            action="clear",
        )
        messagebox.showinfo("完成", "工作空间已清空。")

    def choose_locate_tests_path(self):
        selected = filedialog.askdirectory(title="选择 tests 目录（testsPath）", initialdir=self.preferred_locate_directory() or None)
        if selected:
            if Path(selected).name.lower() != "tests":
                messagebox.showwarning("提示", "testsPath 必须指向 tests 目录。")
                return
            history = self.store.remember("locateTestsHistory", "lastLocateTests", selected, LOCATE_HISTORY_LIMIT)
            self.update_combo_history(self.locate_tests_combo, history, selected)

    def choose_locate_package_zip(self):
        selected = filedialog.askopenfilename(
            title="选择本地压缩包（.zip）",
            initialdir=self.preferred_locate_directory() or None,
            filetypes=[("ZIP 压缩包", "*.zip"), ("所有文件", "*.*")],
        )
        if selected:
            self.locate_package_var.set(selected)
            self.add_locate_package()

    def choose_functional_ini(self):
        selected = filedialog.askopenfilename(
            title="选择脚本集合 ini",
            initialdir=self.preferred_locate_directory() or None,
            filetypes=[("INI 文件", "*.ini"), ("所有文件", "*.*")],
        )
        if selected:
            history = self.store.remember_value("locateFunctionalIniHistory", selected, LOCATE_HISTORY_LIMIT)
            self.locate_func_ini_combo["values"] = history
            self.locate_func_ini_var.set(selected)

    def load_functional_sections(self):
        ini_path = self.locate_func_ini_var.get().strip()
        if not ini_path:
            messagebox.showwarning("提示", "请先选择脚本集合 ini。")
            return
        try:
            sections = list_enabled_ini_sections(ini_path)
        except Exception as exc:
            messagebox.showerror("加载失败", str(exc))
            return
        if not sections:
            messagebox.showwarning("提示", "未找到 IsNeedToRun=1 的脚本节。")
            return
        self.set_functional_sections(sections)
        self.save_functional_locate_session()

    def set_functional_sections(self, sections):
        self.locate_func_sections_listbox.delete(0, END)
        for section in sections:
            self.locate_func_sections_listbox.insert(END, section)

    def collect_functional_sections(self):
        return list(self.locate_func_sections_listbox.get(0, END))

    def restore_functional_locate_session(self):
        session = self.store.get_object("functionalLocateSession") or {}
        ini_path = session.get("collectionIni")
        if ini_path:
            self.locate_func_ini_var.set(ini_path)
        sections = session.get("sections") or []
        if sections:
            self.set_functional_sections(sections)

    def save_functional_locate_session(self):
        self.store.set_object(
            "functionalLocateSession",
            {
                "collectionIni": self.locate_func_ini_var.get().strip(),
                "sections": self.collect_functional_sections(),
            },
        )

    def build_functional_locate_log_input(self, workspace, tests_path, timeout_seconds):
        packages = list(self.locate_packages_listbox.get(0, END))
        sections = self.collect_functional_sections()
        return {
            "workspace": workspace,
            "tests_path": tests_path,
            "timeout_seconds": timeout_seconds,
            "collection_ini": self.locate_func_ini_var.get().strip(),
            "package_count": len(packages),
            "packages_preview": packages[:3],
            "section_count": len(sections),
            "sections_preview": sections[:3],
        }

    def format_point_preset_label(self, points):
        if not points:
            return ""
        first = points[0]
        script = first.get("script") or first.get("script_name") or ""
        point = first.get("point") or first.get("point_name") or ""
        if len(points) == 1:
            return f"{script} :: {point}（1 个性能点）"
        return f"{script} :: {point} 等 {len(points)} 个性能点"

    def refresh_locate_preset_combos(self):
        point_snapshots = self.store.get_snapshots("locatePointSetHistory", LOCATE_HISTORY_LIMIT)
        point_labels = [self.format_point_preset_label(item) for item in point_snapshots]
        self.locate_point_preset_combo["values"] = point_labels
        if point_labels and not self.locate_point_preset_combo.get():
            self.locate_point_preset_combo.current(0)

    def set_locate_packages(self, packages):
        self.locate_packages_listbox.delete(0, END)
        for package in packages or []:
            text = str(package).strip()
            if text:
                self.locate_packages_listbox.insert(END, text)

    def set_locate_points(self, points):
        for item_id in self.locate_points_tree.get_children():
            self.locate_points_tree.delete(item_id)
        for point in points or []:
            script = point.get("script") or point.get("script_name") or ""
            name = point.get("point") or point.get("point_name") or ""
            point_type = point.get("type") or point.get("point_type") or "time"
            standard = point.get("standard") or point.get("standard_name") or "平台标准"
            threshold = point.get("threshold") or ""
            if script and name:
                self.locate_points_tree.insert("", END, values=(script, name, point_type, standard, threshold))

    def collect_locate_points(self):
        points = []
        for item_id in self.locate_points_tree.get_children():
            script, point, point_type, standard, threshold = self.locate_points_tree.item(item_id, "values")
            points.append({
                "script": script,
                "point": point,
                "type": point_type,
                "standard": standard,
                "threshold": threshold,
            })
        return points

    def restore_locate_session(self):
        session = self.store.get_object("lastLocateSession", {})
        if not isinstance(session, dict):
            session = {}
        workspace = session.get("workspace") or self.store.get_last("lastLocateWorkspace")
        tests_path = session.get("testsPath") or self.store.get_last("lastLocateTests")
        if workspace:
            self.locate_workspace_combo.set(workspace)
        if tests_path:
            self.locate_tests_combo.set(tests_path)
        if session.get("runCount") and str(session.get("runCount")) in LOCATE_RUN_COUNT_OPTIONS:
            self.locate_run_count_var.set(str(session.get("runCount")))
        if session.get("timeout"):
            self.locate_timeout_var.set(str(session.get("timeout")))
        if session.get("packages"):
            self.set_locate_packages(session.get("packages"))
        if session.get("points"):
            self.set_locate_points(session.get("points"))

    def save_locate_session(self):
        packages = list(self.locate_packages_listbox.get(0, END))
        points = self.collect_locate_points()
        session = {
            "workspace": self.locate_workspace_combo.get().strip(),
            "testsPath": self.locate_tests_combo.get().strip(),
            "runCount": self.locate_run_count_var.get().strip(),
            "timeout": self.locate_timeout_var.get().strip(),
            "packages": packages,
            "points": points,
        }
        self.store.set_object("lastLocateSession", session)
        if points:
            self.store.remember_snapshot("locatePointSetHistory", points, LOCATE_HISTORY_LIMIT)
        self.refresh_locate_preset_combos()
        self.save_functional_locate_session()

    def remember_locate_input_histories(self):
        workspace = self.locate_workspace_combo.get().strip()
        tests_path = self.locate_tests_combo.get().strip()
        if workspace:
            self.store.remember("locateWorkspaceHistory", "lastLocateWorkspace", workspace, LOCATE_HISTORY_LIMIT)
        if tests_path:
            self.store.remember("locateTestsHistory", "lastLocateTests", tests_path, LOCATE_HISTORY_LIMIT)
        run_count = self.locate_run_count_var.get().strip()
        timeout = self.locate_timeout_var.get().strip()
        if timeout:
            self.store.remember_value("locateTimeoutHistory", timeout, LOCATE_HISTORY_LIMIT)
            self.locate_timeout_combo["values"] = self.store.get_list("locateTimeoutHistory", LOCATE_HISTORY_LIMIT)
        for package in self.locate_packages_listbox.get(0, END):
            self.store.remember_value("locatePackageHistory", package, LOCATE_HISTORY_LIMIT)
        self.locate_package_combo["values"] = self.store.get_list("locatePackageHistory", LOCATE_HISTORY_LIMIT)
        for point in self.collect_locate_points():
            self.store.remember_value("locateScriptHistory", point["script"], LOCATE_HISTORY_LIMIT)
            self.store.remember_value("locatePointNameHistory", point["point"], LOCATE_HISTORY_LIMIT)
            if point.get("threshold"):
                self.store.remember_value("locateThresholdHistory", point["threshold"], LOCATE_HISTORY_LIMIT)
        self.locate_point_script_combo["values"] = self.store.get_list("locateScriptHistory", LOCATE_HISTORY_LIMIT)
        self.locate_point_name_combo["values"] = self.store.get_list("locatePointNameHistory", LOCATE_HISTORY_LIMIT)
        self.locate_point_threshold_combo["values"] = self.store.get_list("locateThresholdHistory", LOCATE_HISTORY_LIMIT)

    def load_locate_point_preset(self):
        label = self.locate_point_preset_combo.get().strip()
        if not label:
            messagebox.showinfo("提示", "请先选择一条历史性能点配置。")
            return
        snapshots = self.store.get_snapshots("locatePointSetHistory", LOCATE_HISTORY_LIMIT)
        labels = [self.format_point_preset_label(item) for item in snapshots]
        if label not in labels:
            messagebox.showwarning("提示", "未找到对应的历史性能点配置。")
            return
        points = snapshots[labels.index(label)]
        self.set_locate_points(points)

    def clear_locate_packages(self):
        self.locate_packages_listbox.delete(0, END)

    def clear_locate_points(self):
        for item_id in self.locate_points_tree.get_children():
            self.locate_points_tree.delete(item_id)

    def add_locate_package(self):
        value = self.locate_package_var.get().strip().strip('"')
        if not value:
            messagebox.showwarning("提示", "请先输入包地址。")
            return
        try:
            if is_remote_package_source(value):
                normalized = value.strip()
            else:
                normalized = validate_local_package_archive(value)
        except (FileNotFoundError, ValueError, OSError) as exc:
            messagebox.showerror("包地址无效", str(exc))
            return
        existing = self.locate_packages_listbox.get(0, END)
        if normalized in existing:
            messagebox.showinfo("提示", "该包地址已存在。")
            return
        self.locate_packages_listbox.insert(END, normalized)
        history = self.store.remember_value("locatePackageHistory", normalized, LOCATE_HISTORY_LIMIT)
        self.locate_package_combo["values"] = history
        self.locate_package_var.set("")

    def edit_locate_package_from_list(self, _event=None):
        selection = self.locate_packages_listbox.curselection()
        if not selection:
            return
        self.locate_package_var.set(self.locate_packages_listbox.get(selection[0]))

    def remove_locate_package(self):
        selection = list(self.locate_packages_listbox.curselection())
        for index in reversed(selection):
            self.locate_packages_listbox.delete(index)

    def move_locate_package(self, direction):
        selection = self.locate_packages_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        target = index + direction
        if target < 0 or target >= self.locate_packages_listbox.size():
            return
        value = self.locate_packages_listbox.get(index)
        self.locate_packages_listbox.delete(index)
        self.locate_packages_listbox.insert(target, value)
        self.locate_packages_listbox.selection_set(target)
        self.locate_packages_listbox.activate(target)

    def on_locate_standard_changed(self):
        standard = self.locate_point_standard_var.get()
        needs_threshold = standard in ("差值标准", "绝对值标准")
        self.locate_point_threshold_combo.configure(state=NORMAL if needs_threshold else DISABLED)
        if not needs_threshold:
            self.locate_point_threshold_var.set("")

    def validate_locate_threshold(self, standard, threshold_text):
        if standard not in ("差值标准", "绝对值标准"):
            return ""
        text = threshold_text.strip()
        if text == "":
            raise ValueError(f"{standard}需要输入阈值")
        try:
            float(text)
        except ValueError as exc:
            raise ValueError("阈值必须是数字，支持正数、负数、0 和浮点数") from exc
        return text

    def upsert_locate_point(self):
        script = self.locate_point_script_var.get().strip()
        point = self.locate_point_name_var.get().strip()
        point_type = self.locate_point_type_var.get().strip() or "time"
        standard = self.locate_point_standard_var.get().strip() or "平台标准"
        try:
            threshold = self.validate_locate_threshold(standard, self.locate_point_threshold_var.get())
        except ValueError as exc:
            messagebox.showwarning("提示", str(exc))
            return
        if not script or not point:
            messagebox.showwarning("提示", "脚本和性能点名称不能为空。")
            return
        if not script.lower().endswith(".js"):
            script += ".js"

        selected = self.locate_points_tree.selection()
        values = (script, point, point_type, standard, threshold)
        if selected:
            self.locate_points_tree.item(selected[0], values=values)
        else:
            self.locate_points_tree.insert("", END, values=values)
        self.store.remember_value("locateScriptHistory", script, LOCATE_HISTORY_LIMIT)
        self.store.remember_value("locatePointNameHistory", point, LOCATE_HISTORY_LIMIT)
        if threshold:
            self.store.remember_value("locateThresholdHistory", threshold, LOCATE_HISTORY_LIMIT)
        self.locate_point_script_combo["values"] = self.store.get_list("locateScriptHistory", LOCATE_HISTORY_LIMIT)
        self.locate_point_name_combo["values"] = self.store.get_list("locatePointNameHistory", LOCATE_HISTORY_LIMIT)
        self.locate_point_threshold_combo["values"] = self.store.get_list("locateThresholdHistory", LOCATE_HISTORY_LIMIT)
        self.locate_point_name_var.set("")
        self.locate_point_threshold_var.set("")
        self.locate_point_script_var.set(script)
        self.on_locate_standard_changed()

    def remove_locate_point(self):
        for item_id in self.locate_points_tree.selection():
            self.locate_points_tree.delete(item_id)

    def on_locate_point_selected(self, _event=None):
        selected = self.locate_points_tree.selection()
        if not selected:
            return
        script, point, point_type, standard, threshold = self.locate_points_tree.item(selected[0], "values")
        self.locate_point_script_var.set(script)
        self.locate_point_name_var.set(point)
        self.locate_point_type_var.set(point_type)
        self.locate_point_standard_var.set(standard)
        self.locate_point_threshold_var.set(threshold)
        self.on_locate_standard_changed()

    def build_locate_package_text(self):
        return "\n".join(self.locate_packages_listbox.get(0, END))

    def build_locate_points_text(self):
        lines = []
        for item_id in self.locate_points_tree.get_children():
            script, point, point_type, standard, threshold = self.locate_points_tree.item(item_id, "values")
            line = f"{script}::{point}|{point_type}|{standard}"
            if threshold != "":
                line += f"|{threshold}"
            lines.append(line)
        return "\n".join(lines)

    def preferred_text_directory(self):
        candidates = [
            self.store.get_last("lastTextFile"),
            self.left_text_file_var.get(),
            self.right_text_file_var.get(),
            *self.store.get_list("textFileHistory"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                path = Path(candidate)
                return str(path.parent if path.is_file() else path)
        return None

    def choose_compare_text_file(self, target_var):
        selected = filedialog.askopenfilename(
            title="选择待对比文本文件",
            initialdir=self.preferred_text_directory() or None,
            filetypes=[
                ("支持的文本文件", "*.ifc *.gfc *.txt"),
                ("IFC 文件", "*.ifc"),
                ("GFC 文件", "*.gfc"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*"),
            ],
        )
        if selected:
            target_var.set(selected)
            self.store.remember("textFileHistory", "lastTextFile", selected)

    def enable_file_drop(self, widget, target_var):
        if not self.drop_supported:
            return
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", lambda event: self.handle_file_drop(event.data, target_var))

    def handle_file_drop(self, raw_data, target_var):
        paths = self.root.tk.splitlist(raw_data)
        if not paths:
            return
        path = Path(paths[0])
        if path.exists() and path.is_file():
            target_var.set(str(path))
            self.store.remember("textFileHistory", "lastTextFile", str(path))
            self.text_compare_summary_var.set(f"已载入拖拽文件：{path}")
        else:
            messagebox.showwarning("提示", "拖拽内容不是有效文件。")

    def fill_text_view(self, text_view, lines, highlights, markers):
        text_view.configure(state=NORMAL)
        text_view.delete("1.0", END)
        text_view.tag_remove("line_diff", "1.0", END)
        text_view.tag_remove("diff_replace", "1.0", END)
        text_view.tag_remove("diff_delete", "1.0", END)
        text_view.tag_remove("diff_insert", "1.0", END)
        text_view.tag_remove("missing", "1.0", END)
        for index, line in enumerate(lines, start=1):
            marker = markers.get(index, " ")
            line_start = text_view.index(END)
            text_view.insert(END, f"{index:>5} {marker} | ")
            content_start = text_view.index(END)
            text_view.insert(END, line)
            content_end = text_view.index(END)
            text_view.insert(END, "\n")
            line_end = text_view.index(END)
            if marker == "!":
                text_view.tag_add("line_diff", content_start, content_end)
            elif marker == "-":
                text_view.tag_add("missing", content_start, content_end)
            for start_col, end_col, tag in highlights.get(index, []):
                if start_col is None:
                    text_view.tag_add(tag, content_start, content_end)
                elif end_col > start_col:
                    text_view.tag_add(tag, f"{content_start}+{start_col}c", f"{content_start}+{end_col}c")
        text_view.configure(state=DISABLED)

    def build_locate_log_input(self, workspace, tests_path, run_count, timeout_seconds):
        packages = list(self.locate_packages_listbox.get(0, END))
        points = self.collect_locate_points()
        return {
            "workspace": workspace,
            "tests_path": tests_path,
            "run_count": run_count,
            "timeout_seconds": timeout_seconds,
            "package_count": len(packages),
            "packages_preview": packages[:3],
            "first_package": packages[0] if packages else None,
            "last_package": packages[-1] if packages else None,
            "point_count": len(points),
            "points_preview": points[:3],
        }

    def run_text_compare(self):
        left_path = Path(self.left_text_file_var.get().strip())
        right_path = Path(self.right_text_file_var.get().strip())
        if not left_path.exists() or not left_path.is_file():
            messagebox.showwarning("提示", "请先选择有效的左侧文本文件。")
            return
        if not right_path.exists() or not right_path.is_file():
            messagebox.showwarning("提示", "请先选择有效的右侧文本文件。")
            return

        started_at = time.monotonic()
        input_data = {"left_path": str(left_path), "right_path": str(right_path)}
        try:
            left_lines = split_lines_like_groovy(read_text_with_fallback(left_path))
            right_lines = split_lines_like_groovy(read_text_with_fallback(right_path))
        except OSError as exc:
            toolbox_log.record(
                "文本对比",
                "failed",
                input_data=input_data,
                error=str(exc),
                duration_ms=int((time.monotonic() - started_at) * 1000),
                source="gui",
            )
            messagebox.showerror("读取失败", str(exc))
            return

        compare_result = compare_text_lines(left_lines, right_lines)
        self.fill_text_view(
            self.left_text_view,
            compare_result["left_display_lines"],
            compare_result["left_highlights"],
            compare_result["left_markers"],
        )
        self.fill_text_view(
            self.right_text_view,
            compare_result["right_display_lines"],
            compare_result["right_highlights"],
            compare_result["right_markers"],
        )
        self.store.remember("textFileHistory", "lastTextFile", str(left_path))
        self.store.remember("textFileHistory", "lastTextFile", str(right_path))
        self.text_compare_summary_var.set(f"对比完成：左侧 {len(left_lines)} 行，右侧 {len(right_lines)} 行，差异 {compare_result['diff_count']} 行。")
        toolbox_log.record(
            "文本对比",
            "success",
            input_data=input_data,
            result_data={
                "left_line_count": len(left_lines),
                "right_line_count": len(right_lines),
                "diff_count": compare_result["diff_count"],
            },
            duration_ms=int((time.monotonic() - started_at) * 1000),
            source="gui",
        )

    def set_busy(self, busy):
        state = DISABLED if busy else NORMAL
        for button in (self.run_error_button, self.run_perf_button, self.compare_button):
            button.configure(state=state)

    def set_locate_busy(self, busy):
        self.locate_button.configure(state=DISABLED if busy else NORMAL)
        self.locate_func_button.configure(state=DISABLED if busy else NORMAL)
        self.locate_stop_button.configure(state=NORMAL if busy else DISABLED)
        self.locate_func_stop_button.configure(state=NORMAL if busy else DISABLED)

    def _log_at_bottom(self):
        try:
            _first, last = self.log_area.yview()
            return float(last) >= 0.98
        except tk.TclError:
            return True

    def _trim_log_area(self):
        line_count = int(self.log_area.index("end-1c").split(".")[0])
        if line_count <= LOG_UI_MAX_LINES:
            return
        delete_to = line_count - LOG_UI_MAX_LINES
        self.log_area.delete("1.0", f"{delete_to + 1}.0")

    def _apply_log_chunk(self, text, replace_last=False):
        if replace_last:
            end_index = self.log_area.index("end-1c")
            if str(end_index) != "1.0":
                line_start = self.log_area.index("end-1c linestart")
                self.log_area.delete(line_start, END)
        if text:
            self.log_area.insert(END, text)
        self._trim_log_area()

    def _flush_log_pending(self):
        self._log_flush_job = None
        if not self._log_pending:
            return
        autoscroll = self._log_at_bottom()
        pending = self._log_pending
        self._log_pending = []
        for text, replace_last in pending:
            self._apply_log_chunk(text, replace_last=replace_last)
        if autoscroll:
            self.log_area.see(END)

    def append_log(self, text, replace_last=False):
        if not text:
            return
        self._log_pending.append((text, replace_last))
        if self._log_flush_job is None:
            self._log_flush_job = self.root.after(LOG_UI_FLUSH_MS, self._flush_log_pending)

    def write_log(self, text):
        if self._log_flush_job is not None:
            self.root.after_cancel(self._log_flush_job)
            self._log_flush_job = None
        self._log_pending.clear()
        self.log_area.delete("1.0", END)
        if text:
            self.log_area.insert(END, text)
        self._trim_log_area()
        self.log_area.see(END)

    def run_with_capture(self, start_message, func, on_success, failure_title, feature=None, input_data=None):
        self.set_busy(True)
        self.write_log(start_message)
        started_at = time.monotonic()

        def worker():
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = func()
                captured = output.getvalue()
                if feature:
                    toolbox_log.record(
                        feature,
                        "success",
                        input_data=input_data,
                        result_data=summarize_operation_result(result),
                        duration_ms=int((time.monotonic() - started_at) * 1000),
                        source="gui",
                    )
                self.root.after(0, lambda: on_success(result, captured))
            except Exception as exc:
                captured = output.getvalue() + f"\n[ERROR] {exc}\n"
                error_message = str(exc)
                if feature:
                    toolbox_log.record(
                        feature,
                        "failed",
                        input_data=input_data,
                        error=error_message,
                        duration_ms=int((time.monotonic() - started_at) * 1000),
                        source="gui",
                    )
                self.root.after(0, lambda: self.on_failure(captured, error_message, failure_title))

        threading.Thread(target=worker, daemon=True).start()

    def on_failure(self, log_text, message, title):
        self.set_busy(False)
        self.write_log(log_text)
        messagebox.showerror(title, message)

    def run_error_analysis(self):
        input_path = self.path_combo.get().strip()
        if not input_path:
            messagebox.showwarning("提示", "请先输入或选择本地日志根目录。")
            return
        self.result_var.set("")
        self.open_report_button.configure(state=DISABLED)
        self.open_folder_button.configure(state=DISABLED)
        self.run_with_capture(
            "[INFO] 正在进行功能错误分析，请稍候...\n",
            lambda: run_analysis(input_path),
            lambda result, captured: self.on_analysis_success(result, captured, input_path, "功能错误分析完成。"),
            "分析失败",
            feature="功能错误分析",
            input_data={"input_path": input_path},
        )

    def run_performance_analysis(self):
        input_path = self.path_combo.get().strip()
        if not input_path:
            messagebox.showwarning("提示", "请先输入或选择本地日志根目录。")
            return
        self.result_var.set("")
        self.open_report_button.configure(state=DISABLED)
        self.open_folder_button.configure(state=DISABLED)
        self.run_with_capture(
            "[INFO] 正在进行性能日志分析，请稍候...\n",
            lambda: run_performance_analysis(input_path),
            lambda result, captured: self.on_analysis_success(result, captured, input_path, "性能日志分析完成。"),
            "分析失败",
            feature="性能日志分析",
            input_data={"input_path": input_path},
        )

    def on_analysis_success(self, result, captured, input_path, message):
        self.set_busy(False)
        self.last_result = result
        history = self.store.remember("directoryHistory", "lastDirectory", input_path)
        self.update_combo_history(self.path_combo, history, input_path)
        html_file = result.get("htmlFile")
        json_file = result.get("jsonFile")
        self.result_var.set(str(Path(html_file).absolute()))
        self.open_report_button.configure(state=NORMAL if html_file and Path(html_file).exists() else DISABLED)
        self.open_folder_button.configure(state=NORMAL if json_file and Path(json_file).parent.exists() else DISABLED)
        self.write_log(captured + f"\n[SUCCESS] {message}\n")

    def run_compare(self):
        benchmark_path = self.benchmark_combo.get().strip()
        current_path = self.current_combo.get().strip()
        if not benchmark_path or not current_path:
            messagebox.showwarning("提示", "请先选择基线 JSON 和当前 JSON。")
            return
        self.compare_result_var.set("")
        self.open_compare_button.configure(state=DISABLED)
        self.open_compare_folder_button.configure(state=DISABLED)
        self.run_with_capture(
            "[INFO] 正在进行性能结果对比，请稍候...\n",
            lambda: run_performance_compare(benchmark_path, current_path),
            lambda result, captured: self.on_compare_success(result, captured, benchmark_path, current_path),
            "对比失败",
            feature="性能结果对比",
            input_data={"benchmark_path": benchmark_path, "current_path": current_path},
        )

    def on_compare_success(self, result, captured, benchmark_path, current_path):
        self.set_busy(False)
        self.last_compare_result = result
        history = self.store.remember("jsonFileHistory", "lastJsonFile", benchmark_path)
        history = self.store.remember("jsonFileHistory", "lastJsonFile", current_path)
        self.update_combo_history(self.benchmark_combo, history, benchmark_path)
        self.update_combo_history(self.current_combo, history, current_path)
        html_file = result.get("htmlFile")
        json_file = result.get("jsonFile")
        self.compare_result_var.set(str(Path(html_file).absolute()))
        self.open_compare_button.configure(state=NORMAL if html_file and Path(html_file).exists() else DISABLED)
        self.open_compare_folder_button.configure(state=NORMAL if json_file and Path(json_file).parent.exists() else DISABLED)
        self.write_log(captured + "\n[SUCCESS] 性能结果对比完成。\n")

    def run_loglocate(self):
        if LOCATE_TASK_BUS.is_running:
            messagebox.showwarning("提示", "已有衰退定位任务正在运行，请等待完成后再启动。")
            return
        workspace = self.locate_workspace_combo.get().strip()
        tests_path = self.locate_tests_combo.get().strip()
        run_count = self.locate_run_count_var.get().strip()
        if run_count not in LOCATE_RUN_COUNT_OPTIONS:
            messagebox.showwarning("提示", "运行次数 m 请选择 1 到 5。")
            return
        if tests_path and Path(tests_path).name.lower() != "tests":
            messagebox.showwarning("提示", "testsPath 必须指向 tests 目录。")
            return
        try:
            timeout_seconds = int(self.locate_timeout_var.get().strip())
            if timeout_seconds <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "超时秒数必须是正整数。")
            return
        package_text = self.build_locate_package_text()
        points_text = self.build_locate_points_text()
        if not workspace:
            messagebox.showwarning("提示", "请先选择性能衰退定位工作空间。")
            return
        if not tests_path:
            messagebox.showwarning("提示", "请先选择 testsPath。")
            return
        if self.locate_packages_listbox.size() < 2:
            messagebox.showwarning("提示", "请至少添加起始包和结束包两个包地址。")
            return
        if not self.locate_points_tree.get_children():
            messagebox.showwarning("提示", "请至少添加一个性能点。")
            return
        try:
            LOCATE_TASK_BUS.begin_task()
        except LocateTaskBusy as exc:
            messagebox.showwarning("提示", str(exc))
            return

        self.locate_result_var.set("")
        self.open_locate_button.configure(state=DISABLED)
        self.open_locate_folder_button.configure(state=DISABLED)
        self.save_locate_session()
        self.remember_locate_input_histories()
        self.set_locate_busy(True)
        self.append_log("\n[INFO] ========== 开始性能衰退定位 ==========\n")
        self.append_log("[INFO] RunTest 将串行执行，历史输出会保留在本面板中。\n")
        locate_input = self.build_locate_log_input(workspace, tests_path, run_count, timeout_seconds)

        def worker():
            output = io.StringIO()

            def emit_log(text, replace_last=False):
                self.root.after(0, lambda t=text, r=replace_last: self.append_log(t, replace_last=r))

            live_writer = LiveLogWriter(output, emit_log)
            with toolbox_log.operation("性能衰退定位", locate_input, source="gui") as op:
                try:
                    with contextlib.redirect_stdout(live_writer), contextlib.redirect_stderr(live_writer):
                        request = build_request_from_text(
                            package_text=package_text,
                            points_text=points_text,
                            tests_path=tests_path,
                            workspace=workspace,
                            run_count=self.locate_run_count_var.get(),
                            timeout_seconds=timeout_seconds,
                            standard_mode="平台标准",
                        )
                        result = run_regression_location(request, task_bus=LOCATE_TASK_BUS)
                    live_writer.flush()
                    op.success(result)
                    self.root.after(0, lambda r=result, w=workspace, t=tests_path: self.on_loglocate_success(r, w, t))
                except RunTestCancelled as exc:
                    live_writer.flush()
                    op.cancelled(str(exc))
                    message = str(exc)
                    self.root.after(0, lambda m=message: self.on_loglocate_cancelled(m))
                except Exception as exc:
                    live_writer.flush()
                    op.failed(str(exc))
                    error_message = str(exc)
                    trace = traceback.format_exc()
                    self.root.after(0, lambda m=error_message, t=trace: self.on_loglocate_failure(m, t))
                finally:
                    LOCATE_TASK_BUS.end_task()
                    self.root.after(0, lambda: self.set_locate_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_log_flush(self):
        if self._log_flush_job is not None:
            self.root.after_cancel(self._log_flush_job)
            self._log_flush_job = None
        self._flush_log_pending()

    def stop_loglocate(self):
        if not LOCATE_TASK_BUS.is_running:
            return
        LOCATE_TASK_BUS.cancel()
        self.append_log("\n[INFO] 已请求终止衰退定位任务...\n")

    def run_functional_loglocate(self):
        if LOCATE_TASK_BUS.is_running:
            messagebox.showwarning("提示", "已有衰退定位任务正在运行，请等待完成后再启动。")
            return
        workspace = self.locate_workspace_combo.get().strip()
        tests_path = self.locate_tests_combo.get().strip()
        ini_path = self.locate_func_ini_var.get().strip()
        if tests_path and Path(tests_path).name.lower() != "tests":
            messagebox.showwarning("提示", "testsPath 必须指向 tests 目录。")
            return
        try:
            timeout_seconds = int(self.locate_timeout_var.get().strip())
            if timeout_seconds <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "超时秒数必须是正整数。")
            return
        if not workspace:
            messagebox.showwarning("提示", "请先选择工作空间。")
            return
        if not tests_path:
            messagebox.showwarning("提示", "请先选择 testsPath。")
            return
        if not ini_path:
            messagebox.showwarning("提示", "请先选择脚本集合 ini。")
            return
        if self.locate_packages_listbox.size() < 2:
            messagebox.showwarning("提示", "请至少添加起始包和结束包两个包地址。")
            return
        if not self.collect_functional_sections():
            messagebox.showwarning("提示", "请先加载至少一个 IsNeedToRun=1 的脚本节。")
            return
        try:
            LOCATE_TASK_BUS.begin_task()
        except LocateTaskBusy as exc:
            messagebox.showwarning("提示", str(exc))
            return

        self.locate_func_result_var.set("")
        self.open_func_locate_button.configure(state=DISABLED)
        self.open_func_locate_folder_button.configure(state=DISABLED)
        self.save_locate_session()
        self.remember_locate_input_histories()
        ini_history = self.store.remember_value("locateFunctionalIniHistory", ini_path, LOCATE_HISTORY_LIMIT)
        self.locate_func_ini_combo["values"] = ini_history
        self.set_locate_busy(True)
        self.append_log("\n[INFO] ========== 开始功能衰退定位 ==========\n")
        self.append_log("[INFO] RunTest 将串行执行，历史输出会保留在本面板中。\n")
        locate_input = self.build_functional_locate_log_input(workspace, tests_path, timeout_seconds)
        package_sources = [line.strip().strip(",").strip('"') for line in self.build_locate_package_text().splitlines() if line.strip()]
        section_names = self.collect_functional_sections()

        def worker():
            output = io.StringIO()

            def emit_log(text, replace_last=False):
                self.root.after(0, lambda t=text, r=replace_last: self.append_log(t, replace_last=r))

            live_writer = LiveLogWriter(output, emit_log)
            with toolbox_log.operation("功能衰退定位", locate_input, source="gui") as op:
                try:
                    with contextlib.redirect_stdout(live_writer), contextlib.redirect_stderr(live_writer):
                        request = build_functional_request_from_inputs(
                            package_sources=package_sources,
                            collection_ini=ini_path,
                            section_names=section_names,
                            tests_path=tests_path,
                            workspace=workspace,
                            timeout_seconds=timeout_seconds,
                        )
                        result = run_functional_regression_location(request, task_bus=LOCATE_TASK_BUS)
                    live_writer.flush()
                    op.success(result)
                    self.root.after(0, lambda r=result, w=workspace, t=tests_path: self.on_functional_loglocate_success(r, w, t))
                except RunTestCancelled as exc:
                    live_writer.flush()
                    op.cancelled(str(exc))
                    message = str(exc)
                    self.root.after(0, lambda m=message: self.on_loglocate_cancelled(m))
                except Exception as exc:
                    live_writer.flush()
                    op.failed(str(exc))
                    error_message = str(exc)
                    trace = traceback.format_exc()
                    self.root.after(0, lambda m=error_message, t=trace: self.on_loglocate_failure(m, t))
                finally:
                    LOCATE_TASK_BUS.end_task()
                    self.root.after(0, lambda: self.set_locate_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def on_functional_loglocate_success(self, result, workspace, tests_path):
        self._finish_log_flush()
        self.last_func_locate_result = result
        workspace_history = self.store.remember("locateWorkspaceHistory", "lastLocateWorkspace", workspace, LOCATE_HISTORY_LIMIT)
        tests_history = self.store.remember("locateTestsHistory", "lastLocateTests", tests_path, LOCATE_HISTORY_LIMIT)
        self.update_combo_history(self.locate_workspace_combo, workspace_history, workspace)
        self.update_combo_history(self.locate_tests_combo, tests_history, tests_path)
        self.save_locate_session()
        self.remember_locate_input_histories()
        html_file = result.get("htmlFile")
        json_file = result.get("jsonFile")
        self.locate_func_result_var.set(str(Path(html_file).absolute()))
        self.open_func_locate_button.configure(state=NORMAL if html_file and Path(html_file).exists() else DISABLED)
        self.open_func_locate_folder_button.configure(state=NORMAL if json_file and Path(json_file).parent.exists() else DISABLED)
        self.append_log("\n[SUCCESS] 功能衰退定位完成。\n")

    def on_loglocate_cancelled(self, message):
        self._finish_log_flush()
        self.append_log(f"\n[INFO] {message}\n")
        messagebox.showinfo("定位已终止", message)

    def on_loglocate_failure(self, message, trace):
        self._finish_log_flush()
        self.append_log(f"\n[ERROR] {message}\n{trace}\n")
        messagebox.showerror("定位失败", message)

    def on_loglocate_success(self, result, workspace, tests_path):
        self._finish_log_flush()
        self.last_locate_result = result
        workspace_history = self.store.remember("locateWorkspaceHistory", "lastLocateWorkspace", workspace, LOCATE_HISTORY_LIMIT)
        tests_history = self.store.remember("locateTestsHistory", "lastLocateTests", tests_path, LOCATE_HISTORY_LIMIT)
        self.update_combo_history(self.locate_workspace_combo, workspace_history, workspace)
        self.update_combo_history(self.locate_tests_combo, tests_history, tests_path)
        self.save_locate_session()
        self.remember_locate_input_histories()
        html_file = result.get("htmlFile")
        json_file = result.get("jsonFile")
        self.locate_result_var.set(str(Path(html_file).absolute()))
        self.open_locate_button.configure(state=NORMAL if html_file and Path(html_file).exists() else DISABLED)
        self.open_locate_folder_button.configure(state=NORMAL if json_file and Path(json_file).parent.exists() else DISABLED)
        self.append_log("\n[SUCCESS] 性能衰退定位完成。\n")

    def open_path(self, path):
        if not path:
            return
        path = str(Path(path).absolute())
        if hasattr(os, "startfile"):
            os.startfile(path)
        else:
            webbrowser.open(Path(path).as_uri())

    def open_audit_log_dir(self):
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_dir_var.set(f"审计日志目录：{log_dir}")
        self.open_path(log_dir)

    def open_last_report(self):
        result_file = self.last_result.get("htmlFile") or self.last_result.get("jsonFile")
        if result_file and Path(result_file).exists():
            self.open_path(result_file)

    def open_last_folder(self):
        json_file = self.last_result.get("jsonFile")
        if json_file and Path(json_file).parent.exists():
            self.open_path(Path(json_file).parent)

    def open_compare_result(self):
        result_file = self.last_compare_result.get("htmlFile") or self.last_compare_result.get("jsonFile")
        if result_file and Path(result_file).exists():
            self.open_path(result_file)

    def open_compare_folder(self):
        json_file = self.last_compare_result.get("jsonFile")
        if json_file and Path(json_file).parent.exists():
            self.open_path(Path(json_file).parent)

    def open_func_locate_result(self):
        result_file = self.last_func_locate_result.get("htmlFile") or self.last_func_locate_result.get("jsonFile")
        if result_file and Path(result_file).exists():
            self.open_path(result_file)

    def open_func_locate_folder(self):
        json_file = self.last_func_locate_result.get("jsonFile")
        if json_file and Path(json_file).parent.exists():
            self.open_path(Path(json_file).parent)

    def open_locate_result(self):
        result_file = self.last_locate_result.get("htmlFile") or self.last_locate_result.get("jsonFile")
        if result_file and Path(result_file).exists():
            self.open_path(result_file)

    def open_locate_folder(self):
        json_file = self.last_locate_result.get("jsonFile")
        if json_file and Path(json_file).parent.exists():
            self.open_path(Path(json_file).parent)

    def run(self):
        self.root.mainloop()


def start_gui():
    LogAnalyzerApp().run()

