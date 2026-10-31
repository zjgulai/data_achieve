#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assemble the report HTML from parts/ and inline the six chart SVGs.

The final report uses the frozen SVGs in parts/figures/. The fig1()..fig6()
functions below are the earlier chart draft and only serve as a fallback when a
figure file is missing.
"""
import argparse
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "parts"
DEFAULT_OUT = (ROOT.parent.parent / "tools" / "insight-reports" /
               "tiktok-viral-topic" / "2026-10-31" / "report.html")

GOLD = "#B8860B"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def t(x, y, s, cls="svg-ink", anchor="start", size=None, weight=None, mono=False, opacity=None):
    classes = cls + (" svg-mono" if mono else "")
    attrs = [
        f'x="{x:.1f}"',
        f'y="{y:.1f}"',
        f'class="{classes}"',
        f'text-anchor="{anchor}"',
        'dominant-baseline="middle"',
    ]
    if size is not None:
        attrs.append(f'font-size="{size}"')
    if weight is not None:
        attrs.append(f'font-weight="{weight}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    return f'<text {" ".join(attrs)}>{esc(s)}</text>'


def tspans(x, y, parts, anchor="start"):
    """parts: list of (text, cls, size, weight, mono)"""
    inner = []
    for text, cls, size, weight, mono in parts:
        classes = cls + (" svg-mono" if mono else "")
        style = f'class="{classes}" font-size="{size}"'
        if weight:
            style += f' font-weight="{weight}"'
        inner.append(f'<tspan {style}>{esc(text)}</tspan>')
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'dominant-baseline="middle">{"".join(inner)}</text>'
    )


# ---------------------------------------------------------------- Figure 1
def fig1():
    W, H = 920, 360
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="可复刻性三档对比：高 116 条、中 126 条、低 45 条；播放中位分别为 250 万、230 万、310 万，低档中位反而最高">']
    panels = [
        dict(x=20, tier="高", desc="可直接复刻", n=116, share="40.3%", med=250,
             p25="158–490 万", top="2380 万", panel="panel", tag=None, bar="bar-muted"),
        dict(x=320, tier="中", desc="有条件复刻", n=126, share="43.8%", med=230,
             p25="140–523 万", top="2720 万", panel="panel", tag=None, bar="bar-muted"),
        dict(x=620, tier="低", desc="难以复刻", n=45, share="15.6%", med=310,
             p25="160–690 万", top="1.88 亿", panel="panel-highlight", tag="↑ 中位反而最高", bar="bar-main"),
    ]
    for p in panels:
        x = p["x"]
        w = 280
        out.append(f'<rect x="{x}" y="12" width="{w}" height="316" rx="2" class="{p["panel"]}"/>')
        out.append(t(x + 20, 45, p["tier"], "svg-ink", size=23, weight=700))
        out.append(t(x + 20, 68, p["desc"], "svg-weak", size=11))
        if p["tag"]:
            out.append(t(x + w - 16, 45, p["tag"], "svg-accent", anchor="end", size=10.5, weight=650))
        out.append(tspans(x + 20, 112, [
            (str(p["n"]), "svg-ink", 36, 700, True),
            (" 条", "svg-sec", 13, None, False),
        ]))
        out.append(t(x + 20, 140, f'{p["share"]} · 样本占比', "svg-sec", size=12))
        out.append(f'<line x1="{x+20}" y1="160" x2="{x+w-20}" y2="160" class="grid-line"/>')
        out.append(t(x + 20, 182, "播放中位", "svg-weak", size=11))
        out.append(tspans(x + 20, 216, [
            (str(p["med"]), "svg-accent", 30, 700, True),
            (" 万", "svg-accent", 15, None, False),
        ]))
        out.append(t(x + 20, 242, f'P25–P75 {p["p25"]}', "svg-sec", size=11))
        out.append(t(x + 20, 264, f'最高 {p["top"]}', "svg-weak", size=11))
        out.append(f'<rect x="{x+20}" y="292" width="200" height="6" rx="3" class="bar-track"/>')
        bw = p["med"] / 310 * 200
        out.append(f'<rect x="{x+20}" y="292" width="{bw:.1f}" height="6" rx="3" class="{p["bar"]}"/>')
    out.append(t(20, 345, "无法判断 1 条（0.3%），播放中位 140 万，不纳入结论。", "svg-weak", size=10.5))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- Figure 2
def fig2():
    W, H = 920, 520
    x0, bw, maxv = 170, 430, 350
    y0, rh = 46, 37
    motifs = [
        ("萌娃治愈", 49, 350, "22.7%"),
        ("节点借势", 103, 300, "46.2%"),
        ("家庭搞笑", 84, 280, "19.5%"),
        ("家庭情感与关系", 108, 280, "17.7%"),
        ("变装穿搭与视觉奇观", 83, 270, "28.6%"),
        ("实用教程与DIY", 60, 250, "59.0%"),
        ("育儿焦虑与痛点", 49, 240, "14.3%"),
        ("热梗音乐与二创", 81, 240, "28.8%"),
        ("身份共鸣", 81, 230, "26.3%"),
        ("母婴好物种草", 63, 220, "64.4%"),
        ("生活方式与居家美学", 39, 190, "15.6%"),
        ("孕产喂养与护理", 57, 190, "35.1%"),
    ]
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="十二个母题的播放中位排行，萌娃治愈 350 万最高，节点借势 300 万，孕产喂养与护理 190 万最低">']
    out.append(t(x0, 10, "播放中位（万）", "svg-weak", size=10))
    # legend
    out.append('<rect x="650" y="5" width="9" height="9" class="bar-main"/>')
    out.append(t(664, 10, "其余母题", "svg-weak", size=10))
    out.append('<rect x="744" y="5" width="9" height="9" class="bar-gold"/>')
    out.append(t(758, 10, "节点借势（季节桶）", "svg-weak", size=10))
    for v in (0, 100, 200, 300):
        x = x0 + v / maxv * bw
        out.append(f'<line x1="{x:.1f}" y1="28" x2="{x:.1f}" y2="{y0 + 12 * rh - 8}" class="grid-line"/>')
        out.append(t(x, 23, str(v), "svg-weak", anchor="middle", size=10, mono=True))
    for i, (name, n, med, ratio) in enumerate(motifs):
        y = y0 + i * rh
        seasonal = name == "节点借势"
        label_cls = "svg-gold-ink" if seasonal else "svg-ink"
        bar_cls = "bar-gold" if seasonal else "bar-main"
        out.append(t(156, y + rh / 2 - 1, name, label_cls, anchor="end", size=13))
        w = med / maxv * bw
        out.append(f'<rect x="{x0}" y="{y+7.5:.1f}" width="{w:.1f}" height="20" class="{bar_cls}"/>')
        out.append(t(x0 + w + 8, y + rh / 2 - 1, f"{med} 万", "svg-ink", size=11.5, mono=True))
        out.append(t(660, y + rh / 2 - 1, f"n={n} · 常青高档占比 {ratio}", "svg-weak", size=10.5))
    out.append(f'<line x1="{x0}" y1="{y0 + 12 * rh - 8}" x2="{x0 + bw}" y2="{y0 + 12 * rh - 8}" class="axis-line"/>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- Figure 3
def fig3():
    W, H = 920, 340
    base, top = 280, 50
    scale = (base - top) / 50.0
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="季节校正对比：全样本高档占比 40.3%，去万圣节常青 31.7%，相差 8.6 个百分点">']
    out.append(t(220, 28, "高档占比", "svg-weak", size=10))
    for v in range(0, 51, 10):
        y = base - v * scale
        out.append(f'<line x1="220" y1="{y:.1f}" x2="780" y2="{y:.1f}" class="grid-line"/>')
        out.append(t(208, y, f"{v}%", "svg-weak", anchor="end", size=10, mono=True))
    bars = [
        dict(x=240, val=40.3, label="全样本", sub="288 条 · 高档 116", fill="bar-main", color="svg-accent"),
        dict(x=540, val=31.7, label="常青（去万圣节）", sub="224 条 · 高档 71", fill="bar-green", color="svg-green"),
    ]
    tops = []
    for b in bars:
        h = b["val"] * scale
        y = base - h
        tops.append(y)
        out.append(f'<rect x="{b["x"]}" y="{y:.1f}" width="140" height="{h:.1f}" class="{b["fill"]}"/>')
        out.append(t(b["x"] + 70, y - 18, f'{b["val"]}%', b["color"], anchor="middle", size=25, weight=700, mono=True))
        out.append(t(b["x"] + 70, base + 24, b["label"], "svg-ink", anchor="middle", size=13, weight=600))
        out.append(t(b["x"] + 70, base + 44, b["sub"], "svg-weak", anchor="middle", size=10.5))
    # bracket
    y1, y2 = tops
    out.append(f'<line x1="380" y1="{y1:.1f}" x2="700" y2="{y1:.1f}" class="ref-line"/>')
    out.append(f'<line x1="680" y1="{y2:.1f}" x2="700" y2="{y2:.1f}" class="ref-line"/>')
    out.append(f'<line x1="700" y1="{y1:.1f}" x2="700" y2="{y2:.1f}" class="svg-accent" stroke="currentColor" stroke-width="1.5"/>')
    out.append(t(712, (y1 + y2) / 2, "−8.6 个百分点", "svg-accent", size=13, weight=650))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- Figure 4
def fig4():
    W, H = 960, 830
    rows = [
        "萌娃治愈", "节点借势", "家庭搞笑", "家庭情感与关系",
        "变装穿搭与视觉奇观", "实用教程与DIY", "育儿焦虑与痛点",
        "热梗音乐与二创", "身份共鸣", "母婴好物种草",
        "生活方式与居家美学", "孕产喂养与护理",
    ]
    cols = [
        "反差反转类", "情绪共鸣类", "社交裂变类", "悬念揭秘类",
        "叙事冲突类", "视听感官类", "教程实用类", "节点借势类", "真实实证类",
    ]
    data = {
        ("萌娃治愈", "社交裂变类"): (515, 8, False),
        ("萌娃治愈", "悬念揭秘类"): (550, 11, False),
        ("实用教程与DIY", "情绪共鸣类"): (460, 14, False),
        ("家庭搞笑", "叙事冲突类"): (500, 11, False),
        ("家庭搞笑", "社交裂变类"): (395, 18, False),
        ("热梗音乐与二创", "悬念揭秘类"): (420, 16, False),
        ("生活方式与居家美学", "社交裂变类"): (390, 10, False),
        ("身份共鸣", "真实实证类"): (385, 8, False),
        ("身份共鸣", "悬念揭秘类"): (175, 20, True),
        ("变装穿搭与视觉奇观", "视听感官类"): (160, 38, True),
        ("变装穿搭与视觉奇观", "情绪共鸣类"): (355, 14, False),
        ("家庭情感与关系", "社交裂变类"): (210, 27, True),
        ("育儿焦虑与痛点", "反差反转类"): (220, 37, True),
    }

    def heat(v):
        tt = max(0.0, min(1.0, (v - 160) / 390.0))
        r = round(242 + (142 - 242) * tt)
        g = round(220 + (47 - 220) * tt)
        b = round(212 + (31 - 212) * tt)
        return f"#{r:02X}{g:02X}{b:02X}", tt

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="母题与机制族热力矩阵：12 个母题，只填 4.3 与 4.4 节有 n 大于等于 8 数据的格子，其余留空表示样本不足">']
    out.append('<defs><linearGradient id="heatGrad" x1="0" y1="0" x2="1" y2="0">'
               '<stop offset="0" stop-color="#F2DCD4"/><stop offset="1" stop-color="#8E2F1F"/>'
               '</linearGradient></defs>')
    out.append(t(168, 15, "颜色 = 播放中位（万）", "svg-weak", size=10))
    out.append('<rect x="330" y="11" width="150" height="8" rx="1" fill="url(#heatGrad)"/>')
    for xx, lab in ((330, "160"), (380, "250"), (430, "400"), (480, "550")):
        out.append(t(xx, 29, lab, "svg-weak", anchor="middle", size=9, mono=True))
    out.append('<rect x="548" y="9" width="10" height="10" rx="1" class="heat-blank"/>')
    out.append(t(564, 15, "留空 = 样本不足", "svg-weak", size=9.5))
    out.append(t(564, 28, "（n<8 或源文件未列出）", "svg-weak", size=8.5))
    out.append('<rect x="758" y="9" width="10" height="10" rx="1" class="heat-red"/>')
    out.append(t(774, 15, "金框 = 红海格", "svg-weak", size=9.5))
    out.append(t(774, 28, "（4.3 节：n≥20 且低于两个边际）", "svg-weak", size=8.5))

    x0, cw, gap = 168, 82, 4
    y0, rh = 108, 54
    # column headers
    for c, name in enumerate(cols):
        cx = x0 + c * (cw + gap) + cw / 2
        out.append(t(cx, 80, name, "svg-sec", anchor="middle", size=10.5))
    out.append(f'<line x1="{x0}" y1="100" x2="{x0 + 9 * (cw + gap) - gap}" y2="100" class="axis-line"/>')
    # rows
    for r, name in enumerate(rows):
        y = y0 + r * rh
        out.append(t(156, y + rh / 2, name, "svg-ink", anchor="end", size=12))
        for c, mech in enumerate(cols):
            x = x0 + c * (cw + gap)
            cell = data.get((name, mech))
            if cell is None:
                out.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{rh}" rx="1.5" class="heat-blank"/>')
                continue
            v, n, red = cell
            color, tt = heat(v)
            out.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{rh}" rx="1.5" fill="{color}" class="heat-cell">'
                       f'<title>{esc(name)} × {esc(mech)}：中位 {v} 万，n={n}</title></rect>')
            if red:
                out.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{rh}" rx="1.5" class="heat-red"/>')
            txt_cls = "heat-white" if tt >= 0.8 else "heat-ink"
            out.append(tspans(x + cw / 2, y + 21, [
                (str(v), txt_cls, 13, 700, True),
                (" 万", txt_cls, 8.5, None, False),
            ], anchor="middle"))
            out.append(t(x + cw / 2, y + 38, f"n={n}", txt_cls, anchor="middle", size=8.5, opacity=0.85))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- Figure 5
def fig5():
    W, H = 920, 500
    x0, x1 = 170, 700
    logmin, logmax = math.log10(500), math.log10(100000)
    accounts = [
        ("grownsy", 31, 63600, "6.36 万", False),
        ("fridamom", 14, 33200, "3.32 万", False),
        ("philipsavent", 13, 15000, "1.50 万", False),
        ("motifmedical", 1, 12200, "1.22 万", True),
        ("spectrababyusa", 15, 4583, "4,583", False),
        ("medela_official", 16, 1788, "1,788", False),
        ("elvieofficial", 15, 1227, "1,227", False),
        ("babybrezza", 16, 821, "821", False),
        ("willowpump", 15, 756, "756", False),
    ]
    y0, rh = 64, 40
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="9 个竞品账号播放中位对数刻度条形图，grownsy 6.36 万最高，willowpump 756 最低，相差约 84 倍">']
    out.append(t(x0, 28, "播放中位（对数刻度）", "svg-weak", size=10))
    for tick in (500, 1000, 5000, 10000, 50000, 100000):
        xx = x0 + (math.log10(tick) - logmin) / (logmax - logmin) * (x1 - x0)
        lab = {500: "500", 1000: "1,000", 5000: "5,000", 10000: "1 万", 50000: "5 万", 100000: "10 万"}[tick]
        out.append(f'<line x1="{xx:.1f}" y1="42" x2="{xx:.1f}" y2="{y0 + 9 * rh - 6}" class="grid-line"/>')
        out.append(t(xx, 40, lab, "svg-weak", anchor="middle", size=9.5, mono=True))
    for i, (name, n, val, disp, small) in enumerate(accounts):
        y = y0 + i * rh
        cy = y + rh / 2
        out.append(t(156, cy - 6, name, "svg-ink", anchor="end", size=11.5))
        sub = f"n={n}" + (" · 样本不足" if small else "")
        out.append(t(156, cy + 8, sub, "svg-gold-ink" if small else "svg-weak", anchor="end", size=8.5))
        xx = x0 + (math.log10(val) - logmin) / (logmax - logmin) * (x1 - x0)
        bar_cls = "bar-main" if name == "grownsy" else "bar-muted"
        out.append(f'<rect x="{x0}" y="{cy-10:.1f}" width="{xx-x0:.1f}" height="20" class="{bar_cls}"/>')
        out.append(t(xx + 8, cy, disp, "svg-ink", size=11, mono=True))
    # 84x bracket
    y_top = y0 + rh / 2
    y_bot = y0 + 8 * rh + rh / 2
    out.append(f'<path d="M 752 {y_top:.1f} L 762 {y_top:.1f} L 762 {y_bot:.1f} L 752 {y_bot:.1f}" fill="none" stroke="{GOLD}" stroke-width="1.3"/>')
    out.append(f'<text x="778" y="{(y_top+y_bot)/2:.1f}" class="svg-gold-ink" font-size="12" font-weight="650" text-anchor="middle" dominant-baseline="middle" transform="rotate(-90 778 {(y_top+y_bot)/2:.1f})">≈ 84 倍</text>')
    out.append(t(x0, 462, "缺粉丝量 / 曝光 / 投流，不能把差距归因于母题、机制或发帖量。", "svg-weak", size=10.5))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- Figure 6
def fig6():
    W, H = 920, 340
    x0, width = 270, 520
    logmin, logmax = math.log10(0.1), math.log10(100)
    rows = [
        ("大爆款 · 下限", 0.3, "0.3", "bar-muted"),
        ("大爆款 · 上限", 0.8, "0.8", "bar-muted"),
        ("清单类小视频", 43.8, "43.8", "bar-main"),
    ]
    y0, rh = 78, 66
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="求购密度对比：清单类小视频 43.8 次每 10 万播放，大爆款 0.3 到 0.8 次每 10 万播放，相差约 55 到 146 倍">']
    out.append(t(x0, 32, "次 / 10 万播放（对数刻度）", "svg-weak", size=10))
    for tick in (0.1, 1, 10, 100):
        xx = x0 + (math.log10(tick) - logmin) / (logmax - logmin) * width
        lab = {0.1: "0.1", 1: "1", 10: "10", 100: "100"}[tick]
        out.append(f'<line x1="{xx:.1f}" y1="46" x2="{xx:.1f}" y2="268" class="grid-line"/>')
        out.append(t(xx, 44, lab, "svg-weak", anchor="middle", size=10, mono=True))
    ends = {}
    for i, (name, val, disp, bar_cls) in enumerate(rows):
        y = y0 + i * rh
        cy = y + rh / 2
        out.append(t(256, cy, name, "svg-ink", anchor="end", size=12.5))
        xx = x0 + (math.log10(val) - logmin) / (logmax - logmin) * width
        ends[name] = xx
        out.append(f'<rect x="{x0}" y="{cy-13:.1f}" width="{xx-x0:.1f}" height="26" class="{bar_cls}"/>')
        out.append(t(xx + 10, cy, disp, "svg-accent" if i == 2 else "svg-ink", size=15, weight=700, mono=True))
    # bracket between 0.8 and 43.8
    a = ends["大爆款 · 上限"]
    b = ends["清单类小视频"]
    out.append(f'<path d="M {a:.1f} 268 L {a:.1f} 276 L {b:.1f} 276 L {b:.1f} 268" fill="none" stroke="#A8422F" stroke-width="1.3"/>')
    out.append(t((a + b) / 2, 296, "约 55–146 倍", "svg-accent", anchor="middle", size=12.5, weight=650))
    out.append(t(x0, 322, "大爆款 0.3–0.8 为区间；清单类 43.8 来自 nursery tour 2.74 万播放 / 12 条求购。", "svg-weak", size=10))
    out.append("</svg>")
    return "".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="output report.html path")
    args = parser.parse_args()
    order = ["_head.html", "_s01.html", "_s02.html", "_s03.html", "_s04.html",
             "_s05.html", "_s06.html", "_s07_foot.html"]
    chunks = []
    for name in order:
        with open(os.path.join(PARTS, name), "r", encoding="utf-8") as f:
            chunks.append(f.read())
    html = "".join(chunks)
    fig_dir = PARTS / "figures"
    charts = {}
    for key in ("FIG1", "FIG2", "FIG3", "FIG4", "FIG5", "FIG6"):
        fig_path = fig_dir / f"{key}.svg"
        if fig_path.exists():
            charts[key] = fig_path.read_text(encoding="utf-8")
        else:
            charts[key] = globals()[f"fig{key[3:]}" ]()
    for key, svg in charts.items():
        marker = f"<!--{key}-->"
        if marker not in html:
            raise SystemExit(f"missing marker {marker}")
        html = html.replace(marker, svg)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {args.out}: {len(html.encode('utf-8'))} bytes")


if __name__ == "__main__":
    main()
