"""Render the method specification as a standalone HTML page.

This is the page that answers: what are the gates, what are the 14 skills,
which of them can be code, how are the six counts separated, how is evidence
graded, and which gate we can actually reach today.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from . import counting, evidence, gates, reachability, skills

CSS = """
:root{--paper:#fbfaf8;--surface:#fff;--surface2:#f4f1ec;--ink:#201e1c;--ink2:#5d5751;--ink3:#8b837b;
--line:#e3ddd6;--line2:#cfc6bd;--brand:#5b4b3f;--brand-soft:#f1ece4;--green:#3e6a53;--green-soft:#e9f0ea;
--amber:#8a6428;--amber-soft:#f7efe0;--red:#994c42;--red-soft:#f8eae7;--blue:#3f5e73;--blue-soft:#e9eff4}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",-apple-system,"Segoe UI",sans-serif;font-size:14.5px;line-height:1.7}
.wrap{width:min(1240px,calc(100% - 36px));margin:0 auto}
header{padding:52px 0 30px;border-bottom:1px solid var(--line)}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--brand);font-weight:700}
h1{font-size:clamp(26px,3.6vw,40px);line-height:1.28;margin:12px 0 14px;font-weight:800;letter-spacing:-.02em;max-width:1000px}
.lede{font-size:16px;color:var(--ink2);max-width:900px}
h2{font-size:24px;margin:0 0 6px;font-weight:800;letter-spacing:-.01em}
section{padding:40px 0;border-bottom:1px solid var(--line)}
.sec-kicker{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);font-weight:700;margin-bottom:8px}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:13px}
th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink3);font-weight:700;background:var(--surface2)}
tr:hover td{background:#fdfbf9}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.pill{display:inline-block;font-size:10.5px;padding:2px 7px;border-radius:999px;border:1px solid var(--line);background:var(--surface2);white-space:nowrap}
.pill.pass{background:var(--green-soft);color:var(--green);border-color:#cfe0d5}
.pill.cond{background:var(--amber-soft);color:var(--amber);border-color:#e7d8b9}
.pill.block{background:var(--red-soft);color:var(--red);border-color:#eccfc9}
.pill.pure{background:var(--green-soft);color:var(--green);border-color:#cfe0d5}
.pill.hybrid{background:var(--blue-soft);color:var(--blue);border-color:#cfdde7}
.pill.human{background:var(--amber-soft);color:var(--amber);border-color:#e7d8b9}
pre{background:#26221f;color:#f4efe8;padding:18px 20px;border-radius:12px;overflow:auto;font-size:12.5px;line-height:1.6}
.note{border-left:3px solid var(--brand);background:var(--brand-soft);padding:12px 16px;border-radius:0 10px 10px 0;margin:16px 0}
.cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:18px 0}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h4{margin:0 0 6px;font-size:14px}
.card p{margin:0;font-size:12.5px;color:var(--ink2)}
.small{font-size:12px;color:var(--ink2)}
ul{margin:8px 0 0;padding-left:20px}
li{margin:4px 0}
@media(max-width:900px){.cols{grid-template-columns:1fr}}
"""


def esc(x: Any) -> str:
    return html.escape(str(x), quote=True)


def pill(text: str, cls: str = "") -> str:
    return f'<span class="pill {cls}">{esc(text)}</span>'


def _source_unit(source: dict[str, Any]) -> str:
    if "field" in source["source"]:
        return f"{source['tables_or_fields']} 字段"
    if source["source"].startswith("tiktok"):
        return f"{source['tables_or_fields']} 张表"
    return f"{source['tables_or_fields']} 个字段"


def status_pill(status: str) -> str:
    key = status.strip().upper()
    if key == "PASS":
        cls = "pass"
    elif key == "HUMAN_REQUIRED":
        cls = "human"
    elif key in {"CONDITIONAL", "PARTIAL"}:
        cls = "cond"
    else:
        cls = "block"
    return pill(status, cls)


def automation_pill(kind: str) -> str:
    cls = {"pure_logic": "pure", "hybrid": "hybrid", "human_required": "human"}[kind]
    return pill(kind, cls)


def render(spec_dir: Path, out_path: Path, run_summary: dict[str, Any] | None = None) -> Path:
    gates_data = gates.gate_spec()
    skills_data = skills.skill_spec()
    auto = skills.automation_summary()
    count_data = counting.counting_spec()
    grade_data = evidence.evidence_spec()
    reach = reachability.build_reachability()

    gate_rows = "".join(
        f"<tr><td><b>{esc(g['gate_id'])}</b><br><span class='small'>{esc(g['name'])}</span></td>"
        f"<td>{'<br>'.join(esc(x) for x in g['entry'])}</td>"
        f"<td>{'<br>'.join(esc(x) for x in g['inputs'])}</td>"
        f"<td>{'<br>'.join(esc(x) for x in g['outputs'])}</td>"
        f"<td>{'<br>'.join(esc(x) for x in g['accept'])}</td>"
        f"<td>{esc(g['rollback'])}</td></tr>"
        for g in gates_data
    )

    skill_rows = "".join(
        f"<tr><td><b>{esc(s['title'])}</b><br><span class='mono small'>{esc(s['name'])}</span><br>"
        f"{status_pill(s['gate'] or 'cross-stage')}{automation_pill(s['automation'])}</td>"
        f"<td>{'<br>'.join(esc(x) for x in s['inputs'])}</td>"
        f"<td><ol style='margin:0;padding-left:16px'>"
        f"{''.join(f'<li>{esc(st['action'])} <span class=small>({esc(st['actor'])})</span></li>' for st in s['steps'])}</ol></td>"
        f"<td>{'<br>'.join(esc(x) for x in s['outputs'])}</td>"
        f"<td>{'<br>'.join(esc(x) for x in s['acceptance'])}</td>"
        f"<td>{esc(s['rollback'])}</td>"
        f"<td>{esc(s['handoff'])}<br><span class='small'>{esc(s['automation_reason'])}</span></td></tr>"
        for s in skills_data
    )

    level_rows = "".join(
        f"<tr><td><b>{esc(level['level'])}</b></td><td>{esc(level['definition'])}</td>"
        f"<td class='mono small'>{esc(level['identity'])}</td><td>{esc(level['judgement_rule'])}</td>"
        f"<td>{esc(level['may_be_counted_as'])}</td><td>{esc('、'.join(level['must_not_be_used_for']))}</td></tr>"
        for level in count_data["levels"]
    )
    deduction_rows = "".join(
        f"<tr><td class='mono'>{esc(d['code'])}</td><td>{esc(d['from'])} → {esc(d['to'])}</td>"
        f"<td>{esc(d['condition'])}</td><td class='mono small'>{esc(d['detect'])}</td><td>{esc(d['action'])}</td></tr>"
        for d in count_data["deduction_rules"]
    )
    grade_rows = "".join(
        f"<tr><td><b>{esc(g['grade'])}</b></td><td>{esc(g['seen'])}</td>"
        f"<td class='mono small'>{esc(g['mechanical_test'])}</td>"
        f"<td>{esc(g['may_be_used_for'])}</td><td>{esc(g['may_not_be_used_for'])}</td><td>{esc(g['upgrade_path'])}</td></tr>"
        for g in grade_data["rules"]
    )
    source_rows = "".join(
        f"<tr><td><b>{esc(s['source'])}</b><br><span class='small'>{_source_unit(s)}</span></td>"
        + "".join(f"<td>{status_pill(s['gates'][g])}</td>" for g in ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"])
        + f"<td>{esc(s['note'])}</td></tr>"
        for s in reach["sources"]
    )

    verdict = reach["verdict"]
    run_line = ""
    if run_summary:
        run_line = (
            f"<div class='note'>本轮实跑：{esc(run_summary.get('corpus', {}).get('canonical_records', 0))} 条 canonical、"
            f"{esc(run_summary.get('claims', 0))} 条结论、{esc(run_summary.get('metric_rows', 0))} 条 metric row。"
            f"报告文件：<span class='mono'>{esc(run_summary.get('report', ''))}</span></div>"
        )

    doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VOC 方法规格 · 门禁 / 技能 / 计数 / 证据</title>
<style>{CSS}</style></head><body><div class="wrap">
<header>
  <div class="kicker">VOC method specification · reverse-engineered from the reference SOP</div>
  <h1>14 个 skill 里只有 {len(auto['pure_logic'])} 个是纯逻辑可代码化，G0 与 G7 是两道无法用工程替代的人工门。</h1>
  <p class="lede">这份规格把参考 SOP 的 G0–G10、14 个原子 skill、六级计数与六级证据状态写成可执行定义，并用本仓库真实表结构与一次真实采集判断“现在能走到哪一关”。</p>
  {run_line}
</header>

<section>
  <div class="sec-kicker">01 / Gate chain</div>
  <h2>每个 gate 的进入条件、输入 artifact、输出 artifact 与失败回滚点</h2>
  <p class="small">gate 是 fail-closed：没有上游 artifact，下游不能开始；回滚要回到最早失效的 gate，并把依赖产物标 stale。</p>
  <table><thead><tr><th>Gate</th><th>进入条件</th><th>输入 artifact</th><th>输出 artifact</th><th>通过条件</th><th>失败回滚点</th></tr></thead>
  <tbody>{gate_rows}</tbody></table>
</section>

<section>
  <div class="sec-kicker">02 / Skills</div>
  <h2>真正的分工是：代码做机械步骤，人做授权、定义与裁决</h2>
  <p class="small">纯逻辑 {len(auto['pure_logic'])} 个：{esc('、'.join(auto['pure_logic']))}。混合 {len(auto['hybrid'])} 个。必须人工 {len(auto['human_required'])} 个：{esc('、'.join(auto['human_required']))}。</p>
  <table><thead><tr><th>Skill</th><th>Inputs</th><th>Steps（actor）</th><th>Outputs</th><th>Acceptance</th><th>Rollback</th><th>Handoff / 为什么</th></tr></thead>
  <tbody>{skill_rows}</tbody></table>
</section>

<section>
  <div class="sec-kicker">03 / Counting</div>
  <h2>六个计数不能混成一个 N，扣减必须带理由码</h2>
  <table><thead><tr><th>层</th><th>定义</th><th>身份键</th><th>判定规则</th><th>可以当什么用</th><th>不能当什么用</th></tr></thead>
  <tbody>{level_rows}</tbody></table>
  <h3>扣减原因分类</h3>
  <table><thead><tr><th>Reason code</th><th>方向</th><th>触发条件</th><th>检测方式</th><th>动作</th></tr></thead>
  <tbody>{deduction_rows}</tbody></table>
</section>

<section>
  <div class="sec-kicker">04 / Evidence</div>
  <h2>证据分级是“看到什么就归哪一级”，不是打分</h2>
  <p class="small">顺序判定，先命中先停：Not authorized &gt; Blocked &gt; Evidence gap &gt; Confirmed &gt; Directional &gt; Supported hypothesis。参考报告实际有六种状态，第六种是医疗与因果禁写区。</p>
  <table><thead><tr><th>等级</th><th>看到什么</th><th>机械判定</th><th>可以用于</th><th>不能用于</th><th>升级路径</th></tr></thead>
  <tbody>{grade_rows}</tbody></table>
</section>

<section>
  <div class="sec-kicker">05 / Reachability</div>
  <h2>仓库里的规范表本身卡在 G1；补上公开一手来源后，这一次跑到了 G6。</h2>
  <div class="cols">
    <div class="card"><h4>TikTok 规范表</h4><p>{len(reach['repo_facts']['tiktok_tables'])} 张（任务书写 20，实际 {reach['repo_facts']['tiktok_table_count']}）。有文本、作者、时间、互动；缺 SKU/variant crosswalk。</p></div>
    <div class="card"><h4>Reddit 76 字段</h4><p>文本、作者、时间、互动齐全；没有任何商品标识，只能回答品类级问题。</p></div>
    <div class="card"><h4>Amazon 商品字段</h4><p>parent/child/variant 与聚合评分可得；评论正文需要登录态，当前是 302。</p></div>
  </div>
  <table><thead><tr><th>来源</th><th>G0</th><th>G1</th><th>G2</th><th>G3</th><th>G4</th><th>G5</th><th>G6</th><th>G7</th><th>卡点</th></tr></thead>
  <tbody>{source_rows}</tbody></table>
  <div class="note"><b>结论。</b>{esc(verdict['with_existing_normalized_tables_only'])}<br>{esc(verdict['with_live_public_collection'])}<br><b>硬阻断：</b>{esc(verdict['hard_block'])}</div>
</section>

<section>
  <div class="sec-kicker">06 / Minimal pipeline</div>
  <h2>最小可运行管线：一个 run 目录、五份 artifact、零个比率</h2>
  <pre>run(run_id, charter, plan):
    identity = amazon_pdp(asins)            # G1: parent/child/variant + sha256
    raw      = reddit_archive(plan)         # G3/G5: inspect -> run -> ledger
    occ      = occurrences(raw)             # source + external_id + frame
    canon    = dedup(occ)                   # exact hash + fuzzy review + deterministic rep
    frames   = assign_frames(canon)         # natural / diagnostic / seed / claim / excluded
    annot    = rule_coder(canon, taxonomy)  # multi-label, unknown != negative
    metric   = materialize(canon, annot)    # only if G7 == PASS, else []
    claims   = grade(claims, evidence_rules, gate_status)
    report   = render(claims, exhibits)     # h2 = claim, Observed/Interpretation/Counter...
    validate(report)                        # structure + behavior + no forbidden output
</pre>
  <p class="small">这条管线在本轮真实跑过：G1 用 Amazon PDP，G3/G5 用 Reddit 归档，G6 对账通过，G7 返回空 metric rows。</p>
</section>

<footer style="padding:28px 0 50px" class="small">
  Generated from <span class="mono">voc_pipeline/voc</span>; all tables are rendered from the same dataclasses the pipeline executes.
</footer>
</div></body></html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path
