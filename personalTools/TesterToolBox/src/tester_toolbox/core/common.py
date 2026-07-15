import html
import json
import re
import sys
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def now_text():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def read_text_with_fallback(path):
    for encoding in ("utf-8", "gbk", sys.getfilesystemencoding() or "gbk"):
        try:
            return Path(path).read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise exc
    return Path(path).read_text(encoding="utf-8", errors="replace")


def split_lines_like_groovy(text):
    return re.split(r"\r?\n", text)


def read_all_lines_with_fallback(file_path):
    try:
        return split_lines_like_groovy(read_text_with_fallback(file_path))
    except OSError as exc:
        print(f"[WARN] 读取性能日志失败：{Path(file_path).absolute()} - {exc}")
        return []


def read_file_tail(file_path, max_lines):
    try:
        lines = split_lines_like_groovy(read_text_with_fallback(file_path))
        if len(lines) <= max_lines * 2:
            return lines
        return lines[-max_lines:]
    except OSError as exc:
        print(f"[WARN] 读取文件失败(编码问题): {Path(file_path).name} - {exc}")
        return []


def write_json_file(file_path, data):
    path = Path(file_path)
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] 结果已写入：{path.absolute()}")
    except OSError as exc:
        print(f"[ERROR] 写入文件失败：{path.absolute()} - {exc}")


def write_html_text_file(html_file, content, label):
    path = Path(html_file)
    try:
        path.write_text(content, encoding="utf-8")
        print(f"[INFO] {label}已写入：{path.absolute()}")
    except OSError as exc:
        print(f"[ERROR] 写入{label}失败：{path.absolute()} - {exc}")


def round_double(value, scale):
    quant = Decimal("1").scaleb(-scale)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def js_escape(value):
    if value is None:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("\t", "\\t")
    )


def escape_html(value):
    if value is None:
        return ""
    return html.escape(str(value), quote=True).replace("&#x27;", "&#39;")
