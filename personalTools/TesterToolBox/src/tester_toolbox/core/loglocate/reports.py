from tester_toolbox.core.common import escape_html, write_html_text_file, write_json_file
from tester_toolbox.core.reports import build_report_script, build_report_style


def locate_result_to_dict(result):
    return {
        "summary": result.get("summary") or {},
        "packages": result.get("packages") or [],
        "results": result.get("results") or [],
        "run_cache": result.get("run_cache") or [],
    }


def format_step_role(role):
    mapping = {
        "range_check": "起始包 vs 终止包",
        "search": "二分搜索",
        "culprit_pair": "最终相邻包",
        "sample": "采样",
        "end_pair": "末对相邻包",
    }
    return mapping.get(role, role or "")


def render_package_sequence(packages):
    items = []
    for package in packages:
        index = package.get("index")
        name = escape_html(package.get("package_name"))
        author = escape_html(package.get("author") or "-")
        items.append(f"<li><span class='num'>#{index + 1}</span> {name} <span class='muted'>（{author}）</span></li>")
    if not items:
        return "<div class='muted'>无包数据</div>"
    return f"<ol class='package-sequence'>{''.join(items)}</ol>"


def render_package_average_rows(package_details):
    rows = []
    for item in package_details or []:
        values = item.get("values") or []
        values_text = ", ".join(escape_html(v) for v in values) if values else "-"
        rows.append(
            f"<tr><td class='num'>{escape_html(item.get('package_index'))}</td>"
            f"<td>{escape_html(item.get('package_name'))}</td>"
            f"<td class='num'>{escape_html(item.get('average'))}</td>"
            f"<td class='num'>{escape_html(item.get('count'))}</td>"
            f"<td>{values_text}</td></tr>"
        )
    if not rows:
        return "<div class='muted'>暂无各包性能数据</div>"
    return (
        "<table class='subtable'><thead><tr>"
        "<th>序号</th><th>包名</th><th>均值</th><th>次数</th><th>每次结果</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_step_rows(steps):
    rows = []
    for step in steps or []:
        previous_value = step.get("previous_average", step.get("previous_value"))
        current_value = step.get("average", step.get("value"))
        rows.append(
            f"<tr><td>{escape_html(format_step_role(step.get('role')))}</td>"
            f"<td class='num'>{escape_html(step.get('previous_index'))}</td>"
            f"<td>{escape_html(step.get('previous_package'))}</td>"
            f"<td class='num'>{escape_html(previous_value)}</td>"
            f"<td class='num'>{escape_html(step.get('package_index'))}</td>"
            f"<td>{escape_html(step.get('package'))}</td>"
            f"<td class='num'>{escape_html(current_value)}</td>"
            f"<td>{escape_html(step.get('regressed'))}</td></tr>"
        )
    if not rows:
        return "<div class='muted'>暂无定位过程</div>"
    return (
        "<table class='subtable'><thead><tr>"
        "<th>阶段</th><th>前序号</th><th>前包</th><th>前均值</th>"
        "<th>当前序号</th><th>当前包</th><th>当前均值</th><th>是否衰退</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_point_detail(item):
    standard = item.get("standard") or {}
    return f"""
<div class="detail-section"><div class="detail-title">说明</div><div>{escape_html(item.get('message'))}</div></div>
<div class="detail-section"><div class="detail-title">衰退标准</div><div>{escape_html(standard)}</div></div>
<div class="detail-section"><div class="detail-title">各包性能数据</div>{render_package_average_rows(item.get('package_details'))}</div>
<div class="detail-section"><div class="detail-title">定位过程</div>{render_step_rows(item.get('steps'))}</div>
"""


def write_loglocate_html_report(html_file, data):
    rows = []
    for index, item in enumerate(data.get("results") or []):
        culprit = item.get("culprit_package") or {}
        previous = item.get("previous_package") or {}
        rows.append(f"""<tr>
<td>{escape_html(item.get('script_name'))}</td>
<td>{escape_html(item.get('point_name'))}</td>
<td>{escape_html(item.get('point_type'))}</td>
<td>{escape_html(item.get('status'))}</td>
<td class="num">{escape_html(item.get('baseline_average'))}</td>
<td class="num">{escape_html(item.get('end_average'))}</td>
<td>{escape_html(previous.get('package_name'))}</td>
<td>{escape_html(culprit.get('package_name'))}</td>
<td>{escape_html(culprit.get('author'))}</td>
<td>{escape_html(culprit.get('sdk_commit'))}</td>
<td>{escape_html(culprit.get('product_commit'))}</td>
<td><button class="detail-btn" onclick="toggleDetail('locate_detail_{index}', this)">详情</button></td>
</tr>
<tr id="locate_detail_{index}" class="detail-row hidden">
<td colspan="12"><div class="detail-box">{render_point_detail(item)}</div></td>
</tr>""")

    summary = data.get("summary") or {}
    extra_style = """
.package-sequence { margin: 0; padding-left: 22px; line-height: 1.8; }
.package-sequence .num { color: #1976d2; font-weight: 600; margin-right: 6px; }
.muted { color: #667085; }
.detail-section { margin-bottom: 12px; }
.detail-title { font-weight: 600; color: #344054; margin-bottom: 6px; }
.subtable { width: 100%; margin-top: 4px; box-shadow: none; }
.subtable th, .subtable td { font-size: 12px; padding: 6px 8px; }
"""
    content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>性能衰退定位报告</title>
{build_report_style()}
<style>{extra_style}</style>
</head>
<body>
<h1>性能衰退定位报告</h1>
<div class="summary">
  <div class="stat"><div class="num">{escape_html(summary.get('package_count') or 0)}</div><div class="label">包数量</div></div>
  <div class="stat"><div class="num">{escape_html(summary.get('point_count') or 0)}</div><div class="label">性能点</div></div>
  <div class="stat danger"><div class="num">{escape_html(summary.get('regression_count') or 0)}</div><div class="label">定位到衰退</div></div>
  <div class="stat wide"><div class="num small">{escape_html(summary.get('generated_at') or '')}</div><div class="label">生成时间</div></div>
</div>
<div class="meta">
  <h2>包序列 <span>按输入顺序：起始包 → 结束包</span></h2>
  {render_package_sequence(data.get('packages') or [])}
</div>
<div class="toolbar">
  <input id="searchInput" type="text" placeholder="搜索脚本、性能点、提交人或 commit..." oninput="filterTable()">
  <span id="searchCount"></span>
</div>
<table id="resultTable">
<thead>
<tr><th>脚本</th><th>性能点</th><th>类型</th><th>状态</th><th>起始均值</th><th>终止均值</th><th>前一包</th><th>衰退包</th><th>提交人</th><th>SDK commit</th><th>产品 commit</th><th>详情</th></tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
{build_report_script()}
</body>
</html>
"""
    write_html_text_file(html_file, content, "性能衰退定位HTML报告")


def write_loglocate_reports(output_dir, result):
    output_dir.mkdir(parents=True, exist_ok=True)
    json_file = output_dir / "performance_regression_location_result.json"
    html_file = output_dir / "performance_regression_location_result.html"
    data = locate_result_to_dict(result)
    write_json_file(json_file, data)
    write_loglocate_html_report(html_file, data)
    return {"jsonFile": json_file, "htmlFile": html_file, "summary": data.get("summary") or {}}
