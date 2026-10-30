#!/usr/bin/env python3
"""Full document shell: head, inline CSS, topbar, main, footer, inline JS."""
from __future__ import annotations

from templates import components as c
from styles import CSS
import ir_contract as C


def _nav(report: dict, present_ids: list[str]) -> str:
    labels = {
        "answer": "答案", "experience": "体验", "aspects": "签名", "frames": "镜头",
        "mixed": "混合", "contexts": "场景", "journey": "旅程", "social": "社媒",
        "variant": "适用性", "agenda": "行动", "evidence": "证据",
    }
    links = []
    first = True
    for sid in C.SECTION_ORDER:
        if sid not in present_ids:
            continue
        current = ' aria-current="page"' if first else ""
        links.append(f'<a{current} href="#{sid}">{labels.get(sid, sid)}</a>')
        first = False
    links.append('<a href="#omissions">省略</a>')
    links.append('<a href="#prohibited">禁止</a>')
    return (
        '<nav class="navlinks" aria-label="报告导航">'
        + "".join(links)
        + '<button type="button" id="evidenceViewBtn" aria-pressed="false">证据视图</button>'
        '<button type="button" id="printBtn">打印</button>'
        '<button class="icon-btn" id="themeBtn" type="button" aria-label="切换明暗主题" title="切换明暗主题">◐</button>'
        "</nav>"
    )


def _footer(data: dict, counts: dict) -> str:
    report = data.get("report", {})
    meta = report.get("meta", {})
    return (
        '<footer class="report-footer"><div class="shell"><div class="footer-grid">'
        f'<div><b>{c.esc(meta.get("title"))}</b><br>report_id: {c.esc(data.get("report_id"))} · '
        f'mode: {c.esc(data.get("report_mode"))}</div>'
        f'<div>as_of: {c.esc(data.get("as_of"))}<br>generated_at: {c.esc(data.get("generated_at"))}</div>'
        f'<div>{counts["sections"]} sections · {counts["exhibits"]} exhibits · {counts["claims"]} claims<br>'
        f'{counts["gaps"]} explicit gaps</div>'
        "</div>"
        '<p class="footer-note">本报告是 G6 进度快照，不是对外报告。所有数字来自同一次 run 的 artifacts；'
        "缺失值保留为 [Evidence gap] 或 [BLOCKED]，不补零、不跨 variant 推断。</p>"
        "</div></footer>"
    )


def render_shell(data: dict, hero_html: str, sections_html: str, omissions_html: str, prohibited_html: str) -> str:
    report = data.get("report", {})
    meta = report.get("meta", {})
    present_ids = [s.get("id") for s in report.get("sections", [])]
    claims = report.get("claims", [])
    exhibits = [b for s in report.get("sections", []) for b in s.get("blocks", []) if b.get("type") == "exhibit"]
    gaps = [b for s in report.get("sections", []) for b in s.get("blocks", []) if b.get("type") == "gap"]
    counts = {"sections": len(present_ids), "exhibits": len(exhibits), "claims": len(claims), "gaps": len(gaps)}
    nav = _nav(report, present_ids)
    script = r"""
(function(){
  var root=document.documentElement;
  var themeBtn=document.getElementById('themeBtn');
  var printBtn=document.getElementById('printBtn');
  var evBtn=document.getElementById('evidenceViewBtn');
  try{var saved=localStorage.getItem('voc-report-theme');if(saved){root.setAttribute('data-theme',saved);}}catch(e){}
  function themeLabel(){
    var dark=root.getAttribute('data-theme')==='dark';
    themeBtn.setAttribute('aria-label',dark?'切换到亮色主题':'切换到暗色主题');
    themeBtn.setAttribute('title',dark?'切换到亮色主题':'切换到暗色主题');
  }
  themeBtn.addEventListener('click',function(){
    var next=root.getAttribute('data-theme')==='dark'?'light':'dark';
    root.setAttribute('data-theme',next);
    try{localStorage.setItem('voc-report-theme',next);}catch(e){}
    themeLabel();
  });
  themeLabel();
  printBtn.addEventListener('click',function(){window.print();});
  evBtn.addEventListener('click',function(){
    var on=evBtn.getAttribute('aria-pressed')==='true';
    evBtn.setAttribute('aria-pressed',String(!on));
    document.body.classList.toggle('evidence-view',!on);
    evBtn.textContent=!on?'收起证据':'证据视图';
  });
})();
"""
    return (
        "<!doctype html>"
        f'<html lang="{c.esc(meta.get("lang") or data.get("language"))}" data-theme="light">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f'<meta name="description" content="{c.esc(meta.get("description"))}">'
        f'<title>{c.esc(meta.get("title"))}</title>'
        f"<style>{CSS}</style>"
        "</head><body>"
        '<a class="skip" href="#main">跳到主要内容</a>'
        '<header class="topbar"><div class="shell">'
        f'<a class="brand" href="#top" aria-label="{c.esc(meta.get("title"))}"><span class="brand-mark" aria-hidden="true"></span>'
        f'<span>{c.esc(meta.get("brand_wordmark"))}</span></a>'
        f'<span class="micro">{c.esc(meta.get("report_type"))} · {c.esc(data.get("report_id"))}</span>'
        f"{nav}</div></header>"
        '<main id="main">'
        f"{hero_html}{sections_html}{omissions_html}{prohibited_html}"
        "</main>"
        f'{_footer(data, counts)}'
        '<div class="toast" role="status" aria-live="polite" hidden></div>'
        f"<script>{script}</script>"
        "</body></html>"
    )
