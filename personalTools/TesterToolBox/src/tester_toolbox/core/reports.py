import json
from pathlib import Path

from .common import escape_html, js_escape, write_html_text_file


def build_report_style():
    return """<style>
* { box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; margin: 0; padding: 14px; background: #f4f6f8; color: #222; font-size: 13px; }
h1 { margin: 0 0 10px; font-size: 20px; }
h2 { margin: 14px 0 7px; font-size: 15px; }
h2 span { color: #666; font-size: 13px; }
.summary { background: #fff; padding: 10px 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
.stat { min-width: 74px; text-align: left; }
.stat.wide { min-width: 170px; }
.stat .num { font-size: 20px; line-height: 1.15; font-weight: 700; color: #1976d2; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stat.danger .num { color: #d32f2f; }
.stat.good .num { color: #2e7d32; }
.stat.warn .num { color: #ed6c02; }
.stat .num.small { font-size: 13px; }
.stat .label { color: #888; margin-top: 2px; font-size: 11px; line-height: 1.2; }
.meta { background: #fff; border-radius: 7px; padding: 9px 12px; line-height: 1.65; box-shadow: 0 1px 3px rgba(0,0,0,0.07); margin-bottom: 10px; word-break: break-all; }
.toolbar { background: #fff; border-radius: 7px; padding: 8px 10px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.07); display: flex; gap: 10px; align-items: center; }
.toolbar input { width: 300px; max-width: 100%; padding: 6px 9px; border: 1px solid #d0d5dd; border-radius: 6px; outline: none; }
.toolbar input:focus { border-color: #1976d2; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 7px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.07); margin-bottom: 10px; }
th, td { padding: 7px 9px; border-bottom: 1px solid #eef0f3; text-align: left; vertical-align: top; }
th { background: #f8fafc; color: #475467; font-weight: 600; white-space: nowrap; }
tr:last-child td { border-bottom: none; }
tr.hidden { display: none; }
.num { text-align: left; font-variant-numeric: tabular-nums; white-space: nowrap; }
.detail-btn { padding: 3px 10px; border: 1px solid #d0d5dd; border-radius: 5px; background: #fff; color: #1976d2; cursor: pointer; font-family: inherit; font-size: 12px; }
.detail-btn:hover { background: #eef6ff; border-color: #90caf9; }
.detail-row td { background: #fbfcfe; }
.detail-box { display: grid; gap: 6px; padding: 6px 8px; color: #444; word-break: break-all; line-height: 1.6; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 999px; color: #fff; font-size: 12px; }
.tag.time { background: #1976d2; }
.tag.memory { background: #7b1fa2; }
.danger { color: #d32f2f; }
.good { color: #2e7d32; }
.warn { color: #ed6c02; }
</style>"""


def build_report_script():
    return """<script>
function filterTable(){
  var keyword=document.getElementById('searchInput').value.trim().toLowerCase();
  var rows=document.querySelectorAll('tbody tr');
  var match=0;
  rows.forEach(function(row){
    if(row.classList.contains('detail-row')){
      if(row.dataset.open==='true'){
        var prev=row.previousElementSibling;
        row.classList.toggle('hidden', prev && prev.classList.contains('hidden'));
      }
      return;
    }
    var hit=!keyword || row.textContent.toLowerCase().indexOf(keyword)!==-1;
    row.classList.toggle('hidden', !hit);
    if(hit) match++;
  });
  document.getElementById('searchCount').textContent=keyword ? ('匹配 '+match+' 行') : '';
}
function toggleDetail(id, btn){
  var row=document.getElementById(id);
  if(!row)return;
  var nextOpen=row.classList.contains('hidden');
  row.dataset.open=nextOpen ? 'true' : 'false';
  row.classList.toggle('hidden', !nextOpen);
  if(btn)btn.textContent=nextOpen ? '收起' : '详情';
}
</script>"""


def write_performance_html_report(html_file, data):
    summary = data.get("summary") or {}
    rows = "\n".join(
        f"""<tr>
<td>{escape_html(point.get('log_name'))}</td>
<td>{escape_html(point.get('point_name'))}</td>
<td><span class="tag {'memory' if point.get('point_type') == 'memory' else 'time'}">{escape_html(point.get('point_type'))}</span></td>
<td class="num">{escape_html(point.get('average'))}</td>
<td class="num">{escape_html(point.get('count'))}</td>
<td>{escape_html(', '.join(str(v) for v in (point.get('values') or [])))}</td>
</tr>"""
        for point in data.get("points") or []
    )
    content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>性能日志分析报告</title>
{build_report_style()}
</head>
<body>
<h1>性能日志分析报告</h1>
<div class="summary">
  <div class="stat"><div class="num">{summary.get('total_js_files') or 0}</div><div class="label">JS 文件数</div></div>
  <div class="stat"><div class="num">{summary.get('total_records') or 0}</div><div class="label">原始记录数</div></div>
  <div class="stat"><div class="num">{summary.get('total_points') or 0}</div><div class="label">统计点数</div></div>
  <div class="stat wide"><div class="num small">{escape_html(summary.get('generated_at') or '')}</div><div class="label">生成时间</div></div>
</div>
<div class="toolbar">
  <input id="searchInput" type="text" placeholder="搜索日志名或性能点..." oninput="filterTable()">
  <span id="searchCount"></span>
</div>
<table id="resultTable">
<thead>
<tr><th>日志名</th><th>性能点名</th><th>类型</th><th>均值</th><th>次数</th><th>原始值</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
{build_report_script()}
</body>
</html>
"""
    write_html_text_file(html_file, content, "性能HTML报告")


def build_compare_section(title, level_class, items):
    rows = []
    for index, item in enumerate(items):
        detail_id = f"detail_{abs(java_string_hashcode(title))}_{index}"
        current_values = escape_html(", ".join(str(v) for v in (item.get("current_values") or [])))
        benchmark_values = escape_html(", ".join(str(v) for v in (item.get("benchmark_values") or [])))
        rows.append(f"""<tr>
<td>{escape_html(item.get('log_name'))}</td>
<td>{escape_html(item.get('point_name'))}</td>
<td><span class="tag {'memory' if item.get('point_type') == 'memory' else 'time'}">{escape_html(item.get('point_type'))}</span></td>
<td class="num">{escape_html(item.get('current_average') or '')}</td>
<td class="num">{escape_html(item.get('benchmark_average') or item.get('benchmark') or '')}</td>
<td class="num">{escape_html(item.get('diff') or '')}</td>
<td><button class="detail-btn" onclick="toggleDetail('{detail_id}', this)">详情</button></td>
</tr>
<tr id="{detail_id}" class="detail-row hidden">
<td colspan="7">
  <div class="detail-box">
    <div><b>当前原始值：</b>{current_values or '-'}</div>
    <div><b>基线原始值：</b>{benchmark_values or '-'}</div>
  </div>
</td>
</tr>""")
    return f"""<section>
<h2 class="{level_class}">{escape_html(title)} <span>({len(items)})</span></h2>
<table class="result-section">
<thead>
<tr><th>日志名</th><th>性能点名</th><th>类型</th><th>当前均值</th><th>基线均值</th><th>差值</th><th>详情</th></tr>
</thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>
</section>"""


def java_string_hashcode(text):
    value = 0
    for ch in text:
        value = (31 * value + ord(ch)) & 0xFFFFFFFF
    if value & 0x80000000:
        value -= 0x100000000
    return value


def write_performance_compare_html_report(html_file, data):
    summary = data.get("summary") or {}
    content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>性能结果对比报告</title>
{build_report_style()}
</head>
<body>
<h1>性能结果对比报告</h1>
<div class="summary">
  <div class="stat danger"><div class="num">{summary.get('regression_count') or 0}</div><div class="label">衰退点</div></div>
  <div class="stat good"><div class="num">{summary.get('improvement_count') or 0}</div><div class="label">优化点</div></div>
  <div class="stat warn"><div class="num">{summary.get('not_found_count') or 0}</div><div class="label">未找到基线</div></div>
  <div class="stat"><div class="num">{summary.get('unchanged_count') or 0}</div><div class="label">无显著差异</div></div>
</div>
<div class="meta">
  <div><b>基线文件：</b>{escape_html(summary.get('benchmark_file') or '')}</div>
  <div><b>当前文件：</b>{escape_html(summary.get('current_file') or '')}</div>
  <div><b>容差规则：</b>{escape_html(summary.get('tolerance') or '')}</div>
  <div><b>生成时间：</b>{escape_html(summary.get('generated_at') or '')}</div>
</div>
<div class="toolbar">
  <input id="searchInput" type="text" placeholder="搜索日志名或性能点..." oninput="filterTable()">
  <span id="searchCount"></span>
</div>
{build_compare_section('衰退点', 'danger', data.get('衰退points') or [])}
{build_compare_section('优化点', 'good', data.get('优化points') or [])}
{build_compare_section('未找到基线的点', 'warn', data.get('未找到基线的points') or [])}
{build_compare_section('无显著差异点', '', data.get('无显著差异points') or [])}
{build_report_script()}
</body>
</html>
"""
    write_html_text_file(html_file, content, "性能对比HTML报告")


def _serialize_comparison_images(images):
    if not images:
        return "[]"
    parts = []
    for image in images:
        parts.append(
            f'{{"label":"{js_escape(image.get("label"))}","filename":"{js_escape(image.get("filename"))}",'
            f'"relative_path":"{js_escape(image.get("relative_path"))}","found":{str(bool(image.get("found"))).lower()}}}'
        )
    return f"[{','.join(parts)}]"


def write_html_report(html_file, data):
    summary = data.get("summary") or {}
    categories = data.get("categories") or []
    cat_json_parts = []
    for cat in categories:
        scripts_json_parts = []
        for script in cat.get("scripts") or []:
            errorinfo = script.get("errorinfo")
            if isinstance(errorinfo, dict):
                errorinfo_text = "; ".join(f"{k}: {v}" for k, v in errorinfo.items())
            else:
                errorinfo_text = str(errorinfo) if errorinfo is not None else ""
            log_lines = ""
            if script.get("rawerrorlogtxt"):
                log_lines = "\\n".join(escape_html(line) for line in script.get("rawerrorlogtxt"))
            scripts_json_parts.append(
                f"""{{"testname":"{js_escape(script.get('testname'))}","errortype":"{js_escape(script.get('errortype'))}","errorinfo":"{js_escape(errorinfo_text)}","log":"{log_lines}","comparison_images":{_serialize_comparison_images(script.get('comparison_images'))}}}"""
            )
        cat_json_parts.append(
            f"""{{"category_name":"{js_escape(cat.get('category_name'))}","base_type":"{js_escape(cat.get('base_type') or cat.get('category_name'))}","script_count":{cat.get('script_count')},"scripts":[{','.join(scripts_json_parts)}]}}"""
        )
    cat_json = f"[{','.join(cat_json_parts)}]"
    total_scripts = summary.get("total_scripts") or 0
    analyzed_scripts = summary.get("analyzed_scripts") or 0
    content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>脚本错误分类报告</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "Microsoft YaHei", "Segoe UI", sans-serif; background: #f0f2f5; color: #333; padding: 16px; font-size: 13px; }}
h1 {{ font-size: 18px; color: #1a1a2e; margin-bottom: 10px; }}
.toolbar {{ background: #fff; padding: 10px 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }}
.toolbar .stat {{ font-size: 20px; font-weight: 700; color: #1976d2; }}
.toolbar .label {{ font-size: 11px; color: #888; }}
.level-switch {{ display: flex; gap: 0; margin-left: auto; border: 1px solid #d0d5dd; border-radius: 6px; overflow: hidden; }}
.level-btn {{ padding: 5px 14px; font-size: 12px; cursor: pointer; background: #fff; color: #333; border: none; font-family: inherit; }}
.level-btn.active {{ background: #1976d2; color: #fff; }}
.level-btn:hover:not(.active) {{ background: #f0f0f0; }}
.card {{ background: #fff; margin-bottom: 6px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.07); overflow: hidden; }}
.card-header {{ padding: 8px 14px; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: background 0.15s; }}
.card-header:hover {{ background: #fafafa; }}
.card-name {{ font-weight: 600; font-size: 13px; flex: 1; color: #1a1a2e; }}
.card-count {{ background: #1976d2; color: #fff; border-radius: 10px; padding: 1px 10px; font-size: 11px; font-weight: 600; min-width: 24px; text-align: center; }}
.card-arrow {{ color: #bbb; font-size: 9px; transition: transform 0.2s; }}
.card-arrow.open {{ transform: rotate(90deg); color: #1976d2; }}
.card-body {{ display: none; border-top: 1px solid #f0f0f0; }}
.card-body.open {{ display: block; }}
.item {{ padding: 8px 14px; border-bottom: 1px solid #f8f8f8; }}
.item:last-child {{ border-bottom: none; }}
.item-name {{ font-weight: 600; color: #1a1a2e; font-size: 12px; }}
.item-meta {{ font-size: 11px; color: #888; margin-top: 2px; line-height: 1.5; }}
.item-meta b {{ color: #555; }}
.log-box {{ background: #1e1e2e; color: #cdd6f4; padding: 8px 12px; border-radius: 5px; margin-top: 6px; font-family: Consolas, "Courier New", monospace; font-size: 11px; line-height: 1.5; max-height: 220px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }}
.sub-count {{ font-size: 11px; color: #999; font-weight: 400; }}
.tag-crash .card-name {{ color: #d32f2f; }}
.tag-crash .card-count {{ background: #d32f2f; }}
.tag-nolog .card-name {{ color: #9e9e9e; }}
.tag-nolog .card-count {{ background: #9e9e9e; }}
.tag-other .card-name {{ color: #757575; }}
.tag-other .card-count {{ background: #757575; }}
.search-box {{ display: flex; align-items: center; gap: 6px; }}
.search-box input {{ padding: 5px 10px; border: 1px solid #d0d5dd; border-radius: 6px; font-size: 12px; width: 200px; outline: none; transition: border-color 0.2s; }}
.search-box input:focus {{ border-color: #1976d2; }}
.search-box .search-count {{ font-size: 11px; color: #888; white-space: nowrap; }}
.action-btns {{ display: flex; gap: 4px; }}
.action-btn {{ padding: 5px 12px; font-size: 12px; cursor: pointer; background: #fff; color: #333; border: 1px solid #d0d5dd; border-radius: 6px; font-family: inherit; }}
.action-btn:hover {{ background: #f0f0f0; }}
.item.highlight .item-name {{ background: #fff3cd; padding: 0 2px; border-radius: 2px; }}
.card.hidden {{ display: none; }}
.root-meta {{ background: #fff; padding: 10px 16px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); line-height: 1.6; word-break: break-all; }}
.root-meta b {{ color: #555; }}
.image-row {{ display: flex; gap: 12px; margin-top: 8px; flex-wrap: wrap; }}
.image-cell {{ flex: 1; min-width: 180px; max-width: calc(33.333% - 8px); text-align: center; }}
.image-cell img {{ max-width: 100%; max-height: 260px; border: 1px solid #ddd; border-radius: 4px; background: #fff; cursor: zoom-in; transition: box-shadow 0.15s, transform 0.15s; }}
.image-cell img:hover {{ box-shadow: 0 2px 10px rgba(25,118,210,0.25); transform: translateY(-1px); }}
.image-label {{ font-size: 11px; color: #666; margin-bottom: 4px; font-weight: 600; }}
.image-missing {{ color: #d32f2f; font-size: 11px; padding: 20px 8px; background: #fff5f5; border: 1px dashed #f5c2c2; border-radius: 4px; line-height: 1.5; word-break: break-all; }}
.image-lightbox {{ display: none; position: fixed; inset: 0; z-index: 10000; background: rgba(0,0,0,0.88); }}
.image-lightbox.open {{ display: block; }}
.image-lightbox-close {{ position: fixed; top: 14px; right: 18px; z-index: 10002; width: 36px; height: 36px; border: none; border-radius: 50%; background: rgba(255,255,255,0.16); color: #fff; font-size: 24px; line-height: 1; cursor: pointer; }}
.image-lightbox-close:hover {{ background: rgba(255,255,255,0.28); }}
.image-lightbox-caption {{ position: fixed; top: 16px; left: 20px; z-index: 10002; color: #fff; font-size: 14px; font-weight: 600; text-shadow: 0 1px 4px rgba(0,0,0,0.5); }}
.image-lightbox-scroll {{ width: 100%; height: 100%; overflow: auto; padding: 56px 24px 24px; box-sizing: border-box; display: flex; align-items: flex-start; justify-content: center; }}
.image-lightbox-inner {{ display: inline-block; max-width: none; }}
.image-lightbox-scroll img {{ width: auto; height: auto; max-width: none; max-height: none; border-radius: 4px; box-shadow: 0 6px 28px rgba(0,0,0,0.45); vertical-align: top; display: block; }}
.image-lightbox-hint {{ position: fixed; bottom: 14px; left: 50%; transform: translateX(-50%); z-index: 10002; color: rgba(255,255,255,0.72); font-size: 12px; }}
</style>
</head>
<body>
<h1>脚本错误分类报告</h1>
<div class="root-meta"><b>日志根目录：</b>{escape_html(summary.get('root_path') or '')}</div>
<div class="toolbar">
    <div><div class="stat">{total_scripts}</div><div class="label">总脚本</div></div>
    <div><div class="stat">{analyzed_scripts}</div><div class="label">已分析</div></div>
    <div><div class="stat">{total_scripts - analyzed_scripts}</div><div class="label">无日志</div></div>
    <div><div class="stat" id="catCount">{summary.get('categories_count') or 0}</div><div class="label">分类数</div></div>
    <div class="action-btns">
        <button class="action-btn" onclick="expandAll()">全部展开</button>
        <button class="action-btn" onclick="collapseAll()">全部折叠</button>
    </div>
    <div class="search-box">
        <input type="text" id="searchInput" placeholder="搜索脚本名..." oninput="onSearch()">
        <span class="search-count" id="searchCount"></span>
    </div>
    <div class="level-switch">
        <button class="level-btn" data-level="coarse" onclick="switchLevel('coarse')">粗归类</button>
        <button class="level-btn active" data-level="fine" onclick="switchLevel('fine')">细归类</button>
    </div>
</div>
<div id="cardContainer"></div>
<div id="imageLightbox" class="image-lightbox" onclick="closeImagePreview(event)">
    <button type="button" class="image-lightbox-close" onclick="closeImagePreview(event)" title="关闭">&times;</button>
    <div class="image-lightbox-caption" id="imageLightboxCaption"></div>
    <div class="image-lightbox-scroll">
        <div class="image-lightbox-inner" onclick="event.stopPropagation()">
            <img id="imageLightboxImg" alt="">
        </div>
    </div>
    <div class="image-lightbox-hint">按 Esc 或点击空白处关闭 · 大图可滚动查看</div>
</div>
<script>
var rawCategories = {cat_json};
var currentLevel = 'fine';

function escapeHtml(s){{if(!s)return '';return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}}

function getTag(name){{
    if(name==='Crash')return 'tag-crash';
    if(name==='NoLog')return 'tag-nolog';
    if(name.startsWith('OtherReason'))return 'tag-other';
    return '';
}}

function compareScriptNames(a,b){{
    return (a||'').localeCompare(b||'', 'zh-CN', {{numeric:true, sensitivity:'base'}});
}}

function sortScripts(scripts){{
    return scripts.slice().sort(function(a,b){{return compareScriptNames(a.testname,b.testname)}});
}}

function buildImageRowHtml(images){{
    if(!images||!images.length)return '';
    var h='<div class="image-row">';
    images.forEach(function(img){{
        h+='<div class="image-cell">';
        h+='<div class="image-label">'+escapeHtml(img.label)+'</div>';
        if(img.found&&img.relative_path){{
            h+='<img src="'+escapeHtml(img.relative_path)+'" alt="'+escapeHtml(img.label)+'" loading="lazy" onclick="openImagePreview(this)" title="点击查看原图">';
        }}else{{
            h+='<div class="image-missing">未找到<br>'+escapeHtml(img.filename||'')+'</div>';
        }}
        h+='</div>';
    }});
    h+='</div>';
    return h;
}}

function openImagePreview(img){{
    if(!img||!img.src)return;
    var overlay=document.getElementById('imageLightbox');
    var fullImg=document.getElementById('imageLightboxImg');
    var caption=document.getElementById('imageLightboxCaption');
    var scroll=document.querySelector('.image-lightbox-scroll');
    if(!overlay||!fullImg)return;
    fullImg.src=img.src;
    fullImg.alt=img.alt||'';
    if(caption)caption.textContent=img.alt||'';
    if(scroll)scroll.scrollTop=0;
    overlay.classList.add('open');
    document.body.style.overflow='hidden';
}}

function closeImagePreview(event){{
    var overlay=document.getElementById('imageLightbox');
    var fullImg=document.getElementById('imageLightboxImg');
    if(!overlay||!overlay.classList.contains('open'))return;
    overlay.classList.remove('open');
    document.body.style.overflow='';
    if(fullImg)fullImg.removeAttribute('src');
}}

document.addEventListener('keydown',function(event){{
    if(event.key==='Escape')closeImagePreview();
}});

function buildCardHtml(cat,idx,isFine){{
    var displayName=isFine?cat.category_name:cat.base_type;
    var tag=getTag(displayName);
    var subInfo='';
    if(!isFine&&cat._subCount>1)subInfo=' <span class="sub-count">('+cat._subCount+'个子类)</span>';
    var h='<div class="card '+tag+'">';
    h+='<div class="card-header" onclick="toggle('+idx+')">';
    h+='<span class="card-arrow" id="a'+idx+'">&#9654;</span>';
    h+='<span class="card-name">'+escapeHtml(displayName)+subInfo+'</span>';
    h+='<span class="card-count">'+cat.script_count+'</span>';
    h+='</div>';
    h+='<div class="card-body" id="b'+idx+'">';
    cat.scripts.forEach(function(s){{
        h+='<div class="item">';
        h+='<div class="item-name">'+escapeHtml(s.testname)+'</div>';
        h+='<div class="item-meta"><b>errortype:</b> '+escapeHtml(s.errortype)+'<br><b>errorinfo:</b> '+escapeHtml(s.errorinfo)+'</div>';
        if(s.log)h+='<div class="log-box">'+s.log+'</div>';
        h+=buildImageRowHtml(s.comparison_images);
        h+='</div>';
    }});
    h+='</div></div>';
    return h;
}}

function renderFine(){{
    var container=document.getElementById('cardContainer');
    var html='';
    rawCategories.forEach(function(cat,i){{html+=buildCardHtml(cat,i,true)}});
    container.innerHTML=html;
    document.getElementById('catCount').textContent=rawCategories.length;
}}

function renderCoarse(){{
    var merged={{}};
    var order=[];
    rawCategories.forEach(function(cat){{
        var bt=cat.base_type;
        if(!merged[bt]){{
            merged[bt]={{base_type:bt,category_name:bt,script_count:0,scripts:[],_subCount:0}};
            order.push(bt);
        }}
        merged[bt].script_count+=cat.script_count;
        merged[bt].scripts=merged[bt].scripts.concat(cat.scripts);
        merged[bt]._subCount++;
    }});
    Object.keys(merged).forEach(function(bt){{
        merged[bt].scripts=sortScripts(merged[bt].scripts);
    }});
    var crash=[],nolog=[],otherReason=[],rest=[];
    order.forEach(function(bt){{
        var m=merged[bt];
        if(bt==='Crash')crash.push(m);
        else if(bt==='NoLog')nolog.push(m);
        else if(bt.startsWith('OtherReason'))otherReason.push(m);
        else rest.push(m);
    }});
    rest.sort(function(a,b){{return b.script_count-a.script_count||a.base_type.localeCompare(b.base_type)}});
    otherReason.sort(function(a,b){{return b.script_count-a.script_count||a.base_type.localeCompare(b.base_type)}});
    var sorted=crash.concat(rest).concat(otherReason).concat(nolog);

    var container=document.getElementById('cardContainer');
    var html='';
    sorted.forEach(function(cat,i){{html+=buildCardHtml(cat,i,false)}});
    container.innerHTML=html;
    document.getElementById('catCount').textContent=sorted.length;
}}

function switchLevel(level){{
    currentLevel=level;
    document.querySelectorAll('.level-btn').forEach(function(btn){{
        btn.classList.toggle('active',btn.getAttribute('data-level')===level);
    }});
    document.getElementById('searchInput').value='';
    document.getElementById('searchCount').textContent='';
    if(level==='fine')renderFine();
    else renderCoarse();
}}

function toggle(i){{var b=document.getElementById('b'+i),a=document.getElementById('a'+i);b.classList.toggle('open');a.classList.toggle('open')}}

function expandAll(){{
    document.querySelectorAll('.card-body').forEach(function(b){{b.classList.add('open')}});
    document.querySelectorAll('.card-arrow').forEach(function(a){{a.classList.add('open')}});
}}

function collapseAll(){{
    document.querySelectorAll('.card-body').forEach(function(b){{b.classList.remove('open')}});
    document.querySelectorAll('.card-arrow').forEach(function(a){{a.classList.remove('open')}});
}}

function onSearch(){{
    var keyword=document.getElementById('searchInput').value.trim().toLowerCase();
    var cards=document.querySelectorAll('#cardContainer .card');
    var matchCount=0;
    cards.forEach(function(card){{
        if(!keyword){{
            card.classList.remove('hidden');
            card.querySelectorAll('.item').forEach(function(it){{it.classList.remove('highlight')}});
            return;
        }}
        var hasMatch=false;
        card.querySelectorAll('.item').forEach(function(it){{
            var name=it.querySelector('.item-name');
            if(name&&name.textContent.toLowerCase().indexOf(keyword)!==-1){{
                it.classList.add('highlight');
                hasMatch=true;
                matchCount++;
            }}else{{
                it.classList.remove('highlight');
            }}
        }});
        if(hasMatch){{
            card.classList.remove('hidden');
            var body=card.querySelector('.card-body');
            var arrow=card.querySelector('.card-arrow');
            if(body)body.classList.add('open');
            if(arrow)arrow.classList.add('open');
        }}else{{
            card.classList.add('hidden');
        }}
    }});
    var countEl=document.getElementById('searchCount');
    if(keyword){{
        countEl.textContent='匹配 '+matchCount+' 个脚本';
    }}else{{
        countEl.textContent='';
    }}
}}

renderFine();
</script>
</body>
</html>
"""
    try:
        Path(html_file).write_text(content, encoding="utf-8")
        print(f"[INFO] 结果已写入：{Path(html_file).absolute()}")
    except OSError as exc:
        print(f"[ERROR] 写入HTML文件失败：{Path(html_file).absolute()} - {exc}")

