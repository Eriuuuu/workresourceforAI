from tester_toolbox.core.common import escape_html, write_html_text_file, write_json_file
from tester_toolbox.core.reports import build_report_script, build_report_style

from .reports import render_package_sequence


OVERALL_STATUS_LABELS = {
    "all_pass_at_end": "终止包全部通过",
    "no_new_regression": "无新增衰退",
    "located": "已完成定位",
}


def functional_result_to_dict(result):
    return {
        "summary": result.get("summary") or {},
        "packages": result.get("packages") or [],
        "collection_ini": result.get("collection_ini") or "",
        "prepared_collection_ini": result.get("prepared_collection_ini") or "",
        "screening": result.get("screening") or {},
        "binary_steps": result.get("binary_steps") or [],
        "results": result.get("results") or [],
        "run_cache": result.get("run_cache") or [],
    }


STATUS_LABELS = {
    "located": "已定位",
    "passed_at_end": "终止包通过",
    "start_failed": "起始包已失败",
    "unstable": "不稳定",
    "no_regression": "无衰退",
    "start_failed_legacy": "起始包已失败",
}


def render_section_list(title, sections):
    if not sections:
        return f"<div class='detail-section'><div class='detail-title'>{escape_html(title)}</div><div class='muted'>无</div></div>"
    items = "".join(f"<li>{escape_html(item)}</li>" for item in sections)
    return f"<div class='detail-section'><div class='detail-title'>{escape_html(title)}（{len(sections)}）</div><ul class='section-list'>{items}</ul></div>"


def render_screening_summary(data):
    screening = data.get("screening") or {}
    summary = data.get("summary") or {}
    overall = OVERALL_STATUS_LABELS.get(summary.get("overall_status"), summary.get("overall_status") or "")
    return f"""
<div class="meta">
  <h2>筛查结论</h2>
  <div><strong>{escape_html(overall)}</strong>：{escape_html(summary.get('overall_message') or '')}</div>
  <div class="muted" style="margin-top:8px;">
    待测脚本 {escape_html(summary.get('enabled_section_count'))} 个；
    终止失败 {escape_html(summary.get('end_failed_count'))} 个；
    起始同样失败 {escape_html(summary.get('start_failed_count'))} 个；
    新增衰退 {escape_html(len(screening.get('regression_scripts') or []))} 个；
    终止包通过 {escape_html(summary.get('passed_at_end_count'))} 个
  </div>
</div>
{render_section_list("终止包通过（无需关注）", screening.get("passed_at_end_sections") or [])}
{render_section_list("起始包同样失败（非本次引入）", screening.get("start_failed_sections") or [])}
{render_section_list("新增衰退脚本（参与二分定位）", screening.get("regression_scripts") or [])}
"""


def render_binary_steps(steps):
    rows = []
    for step in steps or []:
        rows.append(
            f"<tr><td class='num'>{escape_html(step.get('package_index'))}</td>"
            f"<td>{escape_html(step.get('package'))}</td>"
            f"<td>{escape_html(len(step.get('active_sections') or []))}</td>"
            f"<td>{escape_html(len(step.get('failed_sections') or []))}</td>"
            f"<td>{escape_html(step.get('ini'))}</td></tr>"
        )
    if not rows:
        return "<div class='muted'>未进入共享二分阶段</div>"
    return (
        "<table class='subtable'><thead><tr>"
        "<th>包序号</th><th>包名</th><th>活跃脚本数</th><th>本次失败数</th><th>locate.ini</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_package_status_rows(package_details):
    rows = []
    for item in package_details or []:
        rows.append(
            f"<tr><td class='num'>{escape_html(item.get('package_index'))}</td>"
            f"<td>{escape_html(item.get('package_name'))}</td>"
            f"<td>{escape_html(item.get('status'))}</td>"
            f"<td>{escape_html(item.get('role'))}</td></tr>"
        )
    if not rows:
        return "<div class='muted'>暂无各包运行状态</div>"
    return (
        "<table class='subtable'><thead><tr>"
        "<th>序号</th><th>包名</th><th>状态</th><th>角色</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_step_rows(steps):
    rows = []
    for step in steps or []:
        rows.append(
            f"<tr><td>{escape_html(step.get('role'))}</td>"
            f"<td class='num'>{escape_html(step.get('previous_index'))}</td>"
            f"<td>{escape_html(step.get('previous_package'))}</td>"
            f"<td>{escape_html(step.get('previous_value'))}</td>"
            f"<td class='num'>{escape_html(step.get('package_index'))}</td>"
            f"<td>{escape_html(step.get('package'))}</td>"
            f"<td>{escape_html(step.get('value'))}</td>"
            f"<td>{escape_html(step.get('regressed'))}</td></tr>"
        )
    if not rows:
        return "<div class='muted'>暂无定位过程</div>"
    return (
        "<table class='subtable'><thead><tr>"
        "<th>阶段</th><th>前序号</th><th>前包</th><th>前状态</th>"
        "<th>当前序号</th><th>当前包</th><th>当前状态</th><th>是否衰退</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def render_section_detail(item):
    return f"""
<div class="detail-section"><div class="detail-title">说明</div><div>{escape_html(item.get('message'))}</div></div>
<div class="detail-section"><div class="detail-title">各包运行状态</div>{render_package_status_rows(item.get('package_details'))}</div>
<div class="detail-section"><div class="detail-title">定位过程</div>{render_step_rows(item.get('steps'))}</div>
"""


def write_functional_locate_html_report(html_file, data):
    rows = []
    for index, item in enumerate(data.get("results") or []):
        culprit = item.get("culprit_package") or {}
        previous = item.get("previous_package") or {}
        status_label = STATUS_LABELS.get(item.get("status"), item.get("status"))
        rows.append(f"""<tr>
<td>{escape_html(item.get('section_name'))}</td>
<td>{escape_html(status_label)}</td>
<td>{escape_html(previous.get('package_name'))}</td>
<td>{escape_html(culprit.get('package_name'))}</td>
<td>{escape_html(culprit.get('author'))}</td>
<td>{escape_html(culprit.get('sdk_commit'))}</td>
<td>{escape_html(culprit.get('product_commit'))}</td>
<td><button class="detail-btn" onclick="toggleDetail('func_detail_{index}', this)">详情</button></td>
</tr>
<tr id="func_detail_{index}" class="detail-row hidden">
<td colspan="8"><div class="detail-box">{render_section_detail(item)}</div></td>
</tr>""")

    summary = data.get("summary") or {}
    overall = OVERALL_STATUS_LABELS.get(summary.get("overall_status"), summary.get("overall_status") or "")
    extra_style = """
.package-sequence { margin: 0; padding-left: 22px; line-height: 1.8; }
.package-sequence .num { color: #1976d2; font-weight: 600; margin-right: 6px; }
.section-list { margin: 0; padding-left: 22px; line-height: 1.7; max-height: 220px; overflow: auto; }
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
<title>功能衰退定位报告</title>
{build_report_style()}
<style>{extra_style}</style>
</head>
<body>
<h1>功能衰退定位报告</h1>
<div class="summary">
  <div class="stat"><div class="num">{escape_html(summary.get('package_count') or 0)}</div><div class="label">包数量</div></div>
  <div class="stat"><div class="num">{escape_html(summary.get('enabled_section_count') or 0)}</div><div class="label">待测脚本</div></div>
  <div class="stat danger"><div class="num">{escape_html(summary.get('regression_count') or 0)}</div><div class="label">定位到衰退</div></div>
  <div class="stat wide"><div class="num small">{escape_html(overall)}</div><div class="label">总体结论</div></div>
  <div class="stat wide"><div class="num small">{escape_html(summary.get('generated_at') or '')}</div><div class="label">生成时间</div></div>
</div>
<div class="meta">
  <h2>包序列 <span>按输入顺序：起始包 B0 → 终止包 Bn</span></h2>
  {render_package_sequence(data.get('packages') or [])}
  <h2>用户 ini</h2>
  <div>{escape_html(data.get('collection_ini') or '')}</div>
</div>
{render_screening_summary(data)}
<div class="detail-section"><div class="detail-title">共享二分运行记录</div>{render_binary_steps(data.get('binary_steps'))}</div>
<div class="toolbar">
  <input id="searchInput" type="text" placeholder="搜索脚本节、提交人或 commit..." oninput="filterTable()">
  <span id="searchCount"></span>
</div>
<table id="resultTable">
<thead>
<tr><th>脚本节</th><th>状态</th><th>前一包</th><th>衰退包</th><th>提交人</th><th>SDK commit</th><th>产品 commit</th><th>详情</th></tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
{build_report_script()}
</body>
</html>
"""
    write_html_text_file(html_file, content, "功能衰退定位HTML报告")


def write_functional_locate_reports(output_dir, result):
    output_dir.mkdir(parents=True, exist_ok=True)
    json_file = output_dir / "functional_regression_location_result.json"
    html_file = output_dir / "functional_regression_location_result.html"
    data = functional_result_to_dict(result)
    write_json_file(json_file, data)
    write_functional_locate_html_report(html_file, data)
    return {"jsonFile": json_file, "htmlFile": html_file, "summary": data.get("summary") or {}}
