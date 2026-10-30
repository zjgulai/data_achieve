"""styles.py — the single inline stylesheet for the report.

No external fonts, images, CDNs, @import or url(). The token palette is taken
from ref/extract/report.css; the layout is rebuilt for the exhibit contract.
"""

CSS = r"""
:root{
  --brand:#9b626c;--brand-deep:#744650;--brand-ink:#52323a;--brand-soft:#f7ecee;
  --oyster:#f3e5df;--sand:#efe7df;--paper:#fbfaf8;--surface:#fff;--surface-2:#f5f2ef;
  --ink:#252321;--ink-2:#625c58;--ink-3:#857d78;--line:#e3ddd8;--line-strong:#cec4bd;
  --love:#547867;--love-soft:#eaf1ed;--risk:#a55b52;--risk-soft:#f8ebe8;
  --amber:#a87332;--amber-soft:#f7f0e4;--blue:#4f6f84;--blue-soft:#eaf0f4;
  --shadow:0 18px 50px rgba(62,43,39,.08);--radius:18px;--radius-sm:12px;
  --content:1180px;--nav:64px;
}
html[data-theme="dark"]{
  --paper:#1e1b1a;--surface:#292523;--surface-2:#332e2b;--ink:#f7f3ef;--ink-2:#d0c6c0;
  --ink-3:#aa9d95;--line:#443c38;--line-strong:#5b4f49;--brand:#c08a94;--brand-deep:#d9a8b0;
  --brand-ink:#f0cdd3;--brand-soft:#402d32;--oyster:#352a28;--sand:#2e2926;
  --love-soft:#283b32;--risk-soft:#432d2a;--amber-soft:#403426;--blue-soft:#293943;
  --shadow:0 18px 55px rgba(0,0,0,.22);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:calc(var(--nav) + 16px);color-scheme:light dark}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Avenir Next","PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,-apple-system,sans-serif;font-size:15px;line-height:1.68;font-variant-numeric:tabular-nums}
.num,td.num,.value,.chart-meta-item b,.diverge-value,.coverage-label .num{font-variant-numeric:tabular-nums}
h1,h2,h3,h4{margin:0;font-weight:700;letter-spacing:-.02em}
p{margin:0}
a{color:inherit}
.shell{width:min(var(--content),calc(100% - 48px));margin:0 auto}
.skip{position:absolute;left:-9999px;top:8px;background:var(--surface);color:var(--ink);padding:10px 14px;border:1px solid var(--line-strong);border-radius:8px;z-index:99}
.skip:focus{left:12px}
:focus-visible{outline:3px solid var(--brand);outline-offset:3px}
/* topbar */
.topbar{position:sticky;top:0;z-index:40;background:color-mix(in srgb,var(--paper) 88%,transparent);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}
.topbar .shell{display:flex;align-items:center;gap:20px;height:var(--nav)}
.brand{display:flex;align-items:center;gap:9px;text-decoration:none;font-weight:800;letter-spacing:-.02em}
.brand-mark{width:14px;height:14px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 4px var(--brand-soft);display:inline-block}
.micro{font-size:11px;color:var(--ink-3);letter-spacing:.08em;text-transform:uppercase;white-space:nowrap}
.navlinks{margin-left:auto;display:flex;align-items:center;gap:12px;font-size:12px;flex-wrap:nowrap;min-width:0;overflow-x:auto;scrollbar-width:none}
.navlinks a{text-decoration:none;color:var(--ink-2);padding:6px 2px;border-bottom:1px solid transparent;white-space:nowrap;flex:0 0 auto}
.navlinks a:hover{color:var(--ink);border-color:var(--brand)}
.navlinks button,.icon-btn{white-space:nowrap;flex:0 0 auto;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);border-radius:999px;padding:6px 11px;font:inherit;font-size:12px;font-weight:700;cursor:pointer}
.navlinks button[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
/* hero */
.hero{padding:64px 0 46px;position:relative;overflow:hidden}
.hero:before{content:"";position:absolute;width:520px;height:520px;right:-220px;top:-260px;border-radius:50%;background:radial-gradient(circle,var(--brand-soft),transparent 68%);pointer-events:none}
.report-hero{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.72fr);gap:56px;align-items:center;position:relative}
.eyebrow{font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--brand-deep)}
h1{font-size:clamp(36px,4.7vw,60px);line-height:1.08;letter-spacing:-.045em;margin:16px 0 20px;max-width:900px;text-wrap:balance}
h1 .accent{color:var(--brand);white-space:nowrap}
.hero-lead{font-size:16px;color:var(--ink-2);max-width:760px}
.hero-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:24px}
.hero-actions a{display:inline-flex;align-items:center;border:1px solid var(--line-strong);background:var(--surface);color:var(--ink);border-radius:999px;padding:9px 15px;text-decoration:none;font-weight:750;font-size:13px}
.hero-actions a.primary{background:var(--ink);border-color:var(--ink);color:var(--paper)}
.decision-compass{position:relative;border-left:1px solid var(--line-strong);padding:8px 0 8px 32px}
.compass-item{padding:15px 0;border-bottom:1px solid var(--line)}
.compass-item:last-child{border-bottom:0}
.compass-item b{display:block;color:var(--brand-deep);font-size:11px;letter-spacing:.14em;text-transform:uppercase}
.compass-item strong{display:block;font-size:20px;line-height:1.25;margin-top:4px}
.compass-item p{margin-top:4px;color:var(--ink-2);font-size:13px}
.truth-ribbon{display:grid;grid-template-columns:auto repeat(4,1fr);border:1px solid var(--line);margin-top:34px;background:var(--surface);overflow:hidden}
.truth-label{background:var(--ink);color:var(--paper);display:flex;align-items:center;padding:13px 16px;font-weight:800;font-size:11px;letter-spacing:.1em}
.truth-ribbon div:not(.truth-label){padding:12px 15px;border-left:1px solid var(--line);font-size:12px}
.truth-ribbon b{display:block;font-size:13px}
.truth-ribbon span{color:var(--ink-3)}
.decision-evidence{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-top:34px}
.decision-proof{padding:21px 22px;border-right:1px solid var(--line)}
.decision-proof:last-child{border-right:0}
.decision-proof .value{font-size:36px;letter-spacing:-.05em;font-weight:780;line-height:1.1}
.decision-proof .label{font-weight:760;font-size:14px;margin-top:3px}
.decision-proof .note{font-size:12px;color:var(--ink-3);margin-top:6px}
/* sections */
main section{padding:74px 0}
.report-section{border-top:1px solid var(--line)}
.section-head{margin-bottom:32px}
.section-index{display:inline-flex;align-items:center;gap:10px;color:var(--brand);font-size:11px;font-weight:850;letter-spacing:.14em}
.section-index:after{content:"";width:42px;height:1px;background:var(--brand)}
.section-head h2{font-size:clamp(29px,3.8vw,43px);max-width:900px;margin-top:10px;line-height:1.18}
.section-deck{font-size:14px;color:var(--ink-2);max-width:760px;margin-top:12px}
/* answer stack */
.answer-stack{border-top:1px solid var(--line-strong)}
.answer-row{display:grid;grid-template-columns:120px minmax(0,1.1fr) minmax(260px,.9fr);gap:26px;padding:24px 0;border-bottom:1px solid var(--line)}
.answer-row .label{color:var(--brand-deep);font-weight:850;letter-spacing:.08em;font-size:11px;text-transform:uppercase}
.answer-row h3{font-size:21px;line-height:1.34}
.answer-row p{color:var(--ink-2);font-size:14px}
.confidence-band{display:grid;grid-template-columns:repeat(6,1fr);gap:2px;margin-top:24px;background:var(--line)}
.band-cell{background:var(--surface);padding:12px 13px;font-size:11px}
.band-cell b{display:block;font-size:12px}
.band-cell .num{display:block;font-size:24px;font-weight:800;line-height:1.2}
.band-cell small{color:var(--ink-3);display:block;margin-top:3px;line-height:1.35}
.band-cell.confirmed b{color:#3f6b57}.band-cell.directional b{color:#744650}.band-cell.hypothesis b{color:#a87332}
.band-cell.gap b{color:#857d78}.band-cell.blocked b{color:#a5534b}.band-cell.not-authorized b{color:#756078}
/* exhibit */
.exhibit{margin:8px 0 12px;padding:0}
.exhibit-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;align-items:start;border-bottom:1px solid var(--line-strong);padding-bottom:16px}
.exhibit-number{font-size:11px;font-weight:850;color:var(--brand);letter-spacing:.12em}
.exhibit-title{font-size:clamp(22px,2.7vw,29px);line-height:1.27;letter-spacing:-.025em;margin:5px 0 0}
.exhibit-scope{text-align:right;font-size:12px;color:var(--ink-3);max-width:380px;line-height:1.5}
.exhibit-scope .evidence-badge{display:flex;width:fit-content;margin-left:auto}
.evidence-badge{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:4px;padding:4px 7px;font-size:10px;font-weight:850;letter-spacing:.08em;margin-top:7px;white-space:nowrap}
.evidence-badge.confirmed{color:#3f6b57;border-color:#3f6b57;background:#e8f0eb}
.evidence-badge.directional{color:#744650;border-color:#9b626c;background:#f7ecee}
.evidence-badge.hypothesis{color:#a87332;border-color:#a87332;background:#f7f0e4}
.evidence-badge.gap{color:#857d78;border-color:#cec4bd;background:#f5f2ef}
.evidence-badge.blocked{color:#a5534b;border-color:#a5534b;background:#f7e9e6}
.evidence-badge.not-authorized{color:#756078;border-color:#756078;background:#eee9ef}
html[data-theme="dark"] .evidence-badge.confirmed{color:#9ec9b1;border-color:#9ec9b1;background:#23342b}
html[data-theme="dark"] .evidence-badge.directional{color:#e0b0b9;border-color:#b9808b;background:#3d292d}
html[data-theme="dark"] .evidence-badge.hypothesis{color:#e0b878;border-color:#c39752;background:#3e3322}
html[data-theme="dark"] .evidence-badge.gap{color:#c9bdb4;border-color:#6a5c54;background:#332e2b}
html[data-theme="dark"] .evidence-badge.blocked{color:#e6a49d;border-color:#c07c73;background:#432d2a}
html[data-theme="dark"] .evidence-badge.not-authorized{color:#c6aec9;border-color:#98799c;background:#382d3a}
.exhibit-body{padding:26px 0 8px}
.exhibit-readout{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;border-top:1px solid var(--line);padding-top:18px;margin-top:22px}
.readout-item b{display:block;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.readout-item p{margin-top:5px;font-size:13.5px;line-height:1.55}
.readout-incomplete{background:var(--risk-soft);border:1px solid var(--risk);border-radius:8px;padding:10px}
.evidence-incomplete{color:var(--risk);font-weight:850;letter-spacing:.04em}
.source-foot{border-top:1px dotted var(--line-strong);padding-top:11px;margin-top:16px;color:var(--ink-3);font-size:11.5px;display:flex;flex-wrap:wrap;gap:6px 20px;line-height:1.5}
.source-foot b{color:var(--ink-2)}
.source-missing em{color:var(--risk);font-style:normal;font-weight:800}
.evidence-drawer{margin-top:12px;border-top:1px solid var(--line);padding-top:9px;font-size:12px;color:var(--ink-2)}
.evidence-drawer summary{cursor:pointer;font-weight:750;color:var(--brand-deep)}
.evidence-drawer>div{padding-top:8px}
.drawer-content{margin-bottom:8px}
.exhibit-definitions{margin:8px 0 0;padding-left:18px}
.exhibit-definitions li{margin:3px 0}
/* claim */
.claim{margin-top:26px;border:1px solid var(--line);background:var(--surface);border-radius:var(--radius-sm);padding:20px 22px}
.claim-head{display:flex;flex-wrap:wrap;align-items:flex-start;gap:10px 14px}
.claim-id{font-size:11px;font-weight:850;color:var(--brand);letter-spacing:.1em;padding-top:4px}
.claim-headline{font-size:19px;line-height:1.35;flex:1;min-width:240px}
.claim .evidence-badge{margin-top:2px}
.claim .exhibit-readout{grid-template-columns:repeat(4,1fr);margin-top:14px;padding-top:14px}
.claim-numbers{margin-top:12px;font-size:12px;color:var(--ink-2)}
.claim-numbers summary{cursor:pointer;font-weight:750;color:var(--brand-deep)}
.table-wrap{max-width:100%;overflow-x:auto}
.data-table{width:100%;border-collapse:collapse;margin-top:8px;font-size:11.5px}
.data-table caption{text-align:left;font-weight:800;color:var(--ink-2);padding:4px 0}
.data-table th,.data-table td{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}
.data-table th{background:var(--surface-2);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3)}
.source-path{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;word-break:break-all;color:var(--ink-3)}
.provenance{color:var(--ink-3);font-size:10px;display:block;margin-top:6px}
/* chart shell */
.chart{position:relative}
.chart-canvas{padding:4px 0 0}
.chart-caption{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--brand-deep);margin-bottom:12px}
.chart-notes{margin:14px 0 0;padding-left:16px;color:var(--ink-3);font-size:11px;line-height:1.5}
.chart-notes li{margin:2px 0}
.chart-meta{display:flex;flex-wrap:wrap;gap:4px 14px;border-top:1px dashed var(--line-strong);margin-top:10px;padding-top:8px;font-size:10.5px;color:var(--ink-3)}
.chart-meta-item b{color:var(--ink-2);margin-right:3px}
.chart-meta-unknown{color:var(--risk)}
.chart-meta-unknown b{color:var(--risk)}
body.evidence-view .chart-meta{background:var(--surface-2);border:1px solid var(--line);border-radius:6px;padding:7px 9px}
body.evidence-view .source-path{color:var(--ink)}
/* nested bar */
.nested-row{display:grid;grid-template-columns:minmax(190px,.9fr) minmax(260px,3fr) 86px;gap:14px;align-items:center;padding:12px 0;border-bottom:1px solid var(--line)}
.nested-label b{display:block;font-size:13px}
.nested-label span{color:var(--ink-3);font-size:11px}
.nested-track{height:30px;border-radius:6px;background:var(--surface-2);border:1px solid var(--line);display:flex;overflow:hidden;position:relative}
.nested-fill{background:var(--risk);background:linear-gradient(90deg,var(--risk),#b97a72);color:#fff;font-size:11px;font-weight:750;display:flex;align-items:center;padding:0 8px;white-space:nowrap;min-width:0}
.nested-rest{flex:1;display:flex;align-items:center;padding:0 8px;color:var(--ink-3);font-size:11px;white-space:nowrap;overflow:hidden}
.nested-gap{display:flex;align-items:center;justify-content:center;color:var(--risk);background:repeating-linear-gradient(135deg,var(--surface-2) 0 8px,var(--risk-soft) 8px 16px);font-size:11px;font-weight:750}
.nested-counts{text-align:right;font-size:12px;color:var(--ink-2)}
.nested-row.is-gap .nested-label span{color:var(--risk);font-weight:800}
/* diverging */
.diverge-axis{display:grid;grid-template-columns:minmax(190px,.9fr) 1fr 1px 1fr 92px;gap:10px;font-size:10px;color:var(--ink-3);margin-bottom:6px}
.diverge-axis span:nth-child(2){text-align:right}
.diverge-row{display:grid;grid-template-columns:minmax(190px,.9fr) 1fr 1px 1fr 92px;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
.diverge-label b{font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.diverge-half{height:24px;display:flex}
.diverge-neg{flex-direction:row-reverse;justify-content:flex-start}
.diverge-pos{justify-content:flex-start}
.diverge-bar{display:flex;align-items:center;min-width:2px;font-size:10px;font-weight:800;color:#fff;padding:0 5px;border-radius:3px}
.diverge-bar.neg{background:var(--risk)}
.diverge-bar.pos{background:var(--love)}
.diverge-zero{width:1px;height:24px;background:var(--line-strong)}
.diverge-value{text-align:right;font-size:11px;color:var(--ink-3)}
/* frame grid */
.frame-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.lens-card{border:1px solid var(--line);background:var(--surface);border-radius:var(--radius-sm);padding:16px}
.lens-head{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:8px}
.lens-head b{font-size:15px}
.lens-head span{font-size:12px;color:var(--brand-deep);font-weight:800}
.lens-block{margin-top:10px}
.lens-block h4{font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3)}
.lens-list{list-style:none;margin:5px 0 0;padding:0}
.lens-list li{display:grid;grid-template-columns:1fr auto;gap:4px 8px;padding:5px 0;border-bottom:1px dotted var(--line)}
.lens-list li small{grid-column:1/-1;color:var(--ink-3);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:9.5px}
.lens-list.love b{color:var(--love)}
.lens-list.complaint b{color:var(--risk)}
.lens-note{font-size:10.5px;color:var(--ink-3);margin-top:10px;border-top:1px solid var(--line);padding-top:8px}
.lens-list.empty{color:var(--risk);font-size:11px}
/* matrix */
.matrix{width:100%;border-collapse:collapse;font-size:12px}
.matrix th,.matrix td{border:1px solid var(--line);padding:8px;text-align:center}
.matrix th[scope="row"]{text-align:left;background:var(--surface-2);font-weight:750}
.matrix thead th{background:var(--surface-2);font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
.matrix .row-total,.matrix .col-total,.matrix .grand-total{background:var(--surface-2);font-weight:800}
.heat{font-weight:750}
.heat-0{background:#f5f2ef;color:#a79d96}.heat-1{background:#f7ecee;color:#7b4b55}.heat-2{background:#f2dfe2;color:#744650}
.heat-3{background:#ecd1d6;color:#6a3f48}.heat-4{background:#e4c2c8;color:#603740}.heat-5{background:#dcb2ba;color:#572f38}
.heat-6{background:#d2a1ab;color:#4e2932}.heat-7{background:#c88f9b;color:#fff}.heat-8{background:#bd7d8b;color:#fff}
html[data-theme="dark"] .heat-0{background:#332e2b;color:#8d827a}html[data-theme="dark"] .heat-1{background:#3a2a2e;color:#d7b4ba}
html[data-theme="dark"] .heat-2{background:#452f34;color:#ecc7cd}html[data-theme="dark"] .heat-3{background:#51353b;color:#f2d3d8}
html[data-theme="dark"] .heat-4{background:#5d3b42;color:#f7dde1}html[data-theme="dark"] .heat-5{background:#6a424a;color:#fbe7ea}
html[data-theme="dark"] .heat-6{background:#774952;color:#fff}html[data-theme="dark"] .heat-7{background:#85515b;color:#fff}
html[data-theme="dark"] .heat-8{background:#955c67;color:#fff}
/* quadrant */
.quad-y,.quad-x{font-size:11px;font-weight:800;letter-spacing:.06em;color:var(--brand-deep);text-transform:uppercase}
.quad-y{margin-bottom:8px}.quad-x{margin-top:8px;text-align:right}
.quad-grid{display:grid;grid-template-columns:1fr 1fr;grid-template-areas:"q2 q1" "q4 q3";gap:10px}
.quad-cell{border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:14px;min-height:150px}
.quad-q1{grid-area:q1}.quad-q2{grid-area:q2}.quad-q3{grid-area:q3}.quad-q4{grid-area:q4}
.quad-meta{display:flex;justify-content:space-between;align-items:center}
.quad-code{font-size:10px;font-weight:850;letter-spacing:.1em;color:var(--brand)}
.quad-badge{font-size:9px;font-weight:850;letter-spacing:.08em;color:var(--amber);border:1px solid var(--amber);border-radius:3px;padding:2px 5px;background:var(--amber-soft)}
.quad-cell h4{font-size:16px;margin-top:8px}
.quad-cell p{font-size:12px;color:var(--ink-2);margin-top:5px}
.quad-signal{font-size:11px;color:var(--ink-3);border-top:1px dotted var(--line);padding-top:6px}
.quad-cell.empty{display:flex;flex-direction:column;justify-content:center;color:var(--risk);background:var(--risk-soft)}
/* coverage */
.coverage-row{display:grid;grid-template-columns:minmax(180px,.85fr) minmax(240px,3fr);gap:14px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
.coverage-label{display:flex;justify-content:space-between;gap:10px;font-size:12px}
.coverage-track{height:22px;background:var(--surface-2);border:1px solid var(--line);border-radius:4px;overflow:hidden}
.coverage-track span{display:block;height:100%;background:var(--blue);opacity:.82}
.coverage-unknown{font-size:11px;color:var(--ink-3);margin-top:10px}
/* social flow */
.social-flow{display:grid;grid-template-columns:1fr 2fr 1fr;gap:14px;align-items:stretch}
.flow-total,.flow-metric{border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:14px;text-align:center}
.flow-total span,.flow-metric span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3)}
.flow-total b,.flow-metric b{display:block;font-size:30px;line-height:1.2}
.flow-parts{display:flex;flex-wrap:wrap;gap:8px;align-content:center}
.flow-chip{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:8px 10px;font-size:11px;display:flex;gap:8px;align-items:center}
/* variant grid */
.variant-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}
.variant-card{border:1px solid var(--line);background:var(--surface);border-radius:8px;padding:9px;font-size:10.5px;min-width:0}
.variant-card.is-target{border-color:var(--brand);box-shadow:inset 0 0 0 1px var(--brand)}
.variant-head{display:flex;justify-content:space-between;gap:4px;align-items:flex-start}
.variant-head b{font-size:11px;line-height:1.3;word-break:break-word}
.target-tag{background:var(--brand);color:#fff;border-radius:3px;padding:1px 4px;font-size:8px;font-weight:850;letter-spacing:.06em;white-space:nowrap}
.variant-id{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:9px;color:var(--ink-3);margin:5px 0 6px;word-break:break-all}
.variant-facts{margin:0;display:grid;gap:2px}
.variant-facts div{display:flex;justify-content:space-between;gap:4px}
.variant-facts dt{color:var(--ink-3);font-size:9px}
.variant-facts dd{margin:0;font-size:10px}
.missing{color:var(--risk);font-size:9px;font-weight:800}
/* maturity */
.maturity{width:100%;border-collapse:collapse;font-size:11px}
.maturity th,.maturity td{border:1px solid var(--line);padding:7px;vertical-align:middle}
.maturity thead th{background:var(--surface-2);font-size:9.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-3)}
.maturity th[scope="row"]{text-align:left;background:var(--surface-2);min-width:170px}
.maturity th[scope="row"] span{display:block;color:var(--ink-3);font-size:10px;font-weight:500}
.status-cell{text-align:center;min-width:72px}
.status-cell.active{font-weight:850;font-size:10px}
.status-cell .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;background:currentColor}
.status-cell.confirmed{color:#3f6b57;background:#e8f0eb}.status-cell.directional{color:#744650;background:#f7ecee}
.status-cell.hypothesis{color:#a87332;background:#f7f0e4}.status-cell.evidence-gap{color:#857d78;background:#f5f2ef}
.status-cell.blocked{color:#a5534b;background:#f7e9e6}.status-cell.not-authorized{color:#756078;background:#eee9ef}
/* lineage */
.lineage-group{border:1px solid var(--line);border-radius:10px;padding:14px;margin-bottom:14px;background:var(--surface)}
.lineage-group h4{font-size:13px;display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:7px;margin-bottom:6px}
.lineage-group h4 small{font-size:10px;color:var(--ink-3);font-weight:500}
.lineage-row{display:grid;grid-template-columns:minmax(150px,.8fr) minmax(180px,2fr) 60px 50px;gap:8px;align-items:center;padding:6px 0;border-bottom:1px dotted var(--line)}
.lineage-label{font-size:12px}
.lineage-track{height:18px;background:var(--surface-2);border:1px solid var(--line);border-radius:3px;overflow:hidden}
.lineage-track span{display:block;height:100%;background:var(--blue);opacity:.75}
.lineage-value{text-align:right;font-weight:800;font-size:12px}
.delta{font-size:10px;font-weight:850;text-align:center;border-radius:3px;padding:2px 4px}
.delta.up{color:var(--love);background:var(--love-soft)}.delta.down{color:var(--risk);background:var(--risk-soft)}.delta.flat{color:var(--ink-3);background:var(--surface-2)}
.delta-reason{grid-column:1/-1;color:var(--ink-3);font-size:10px}
/* legend */
.status-legend{width:100%;border-collapse:collapse;margin-top:22px;font-size:12px}
.status-legend th,.status-legend td{border:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}
.status-legend thead th{background:var(--surface-2);font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
/* gate rail */
.gate-rail{display:flex;flex-wrap:wrap;gap:6px;margin-top:20px}
.gate-chip{border:1px solid var(--line);border-radius:5px;padding:4px 7px;font-size:10px;font-weight:750;background:var(--surface)}
.gate-chip.PASS{color:#3f6b57;border-color:#3f6b57}.gate-chip.CONDITIONAL{color:#a87332;border-color:#a87332}
.gate-chip.BLOCKED{color:#a5534b;border-color:#a5534b}.gate-chip.NOT_STARTED{color:var(--ink-3)}
/* prohibited + omissions */
.prohibited-block{border-top:2px solid var(--ink);padding:56px 0 48px}
.prohibited-block h2{font-size:clamp(28px,3.5vw,40px);max-width:820px;margin-top:8px}
.prohibited-list{list-style:none;padding:0;margin:24px 0 0;border-top:1px solid var(--line-strong)}
.prohibited-list li{display:grid;grid-template-columns:54px minmax(0,1fr) 90px;gap:16px;padding:14px 0;border-bottom:1px solid var(--line);align-items:start}
.prohibited-list .po-id{font-size:11px;font-weight:850;color:var(--brand)}
.prohibited-list b{display:block;font-size:14px}
.prohibited-list span{display:block;font-size:12px;color:var(--ink-2);margin-top:3px}
.prohibited-list .po-gate{text-align:right;font-size:10px;color:var(--ink-3);font-weight:800}
.omissions-block{border-top:1px solid var(--line);padding:42px 0}
.omissions-block h2{font-size:clamp(24px,3vw,32px);margin-top:8px}
.omission-list{margin:18px 0 0;padding-left:20px;font-size:14px;color:var(--ink-2)}
.omission-list li{margin:8px 0}
.omission-list b{color:var(--ink)}
/* footer */
.report-footer{border-top:1px solid var(--line);padding:30px 0 52px;color:var(--ink-3);font-size:11.5px}
.footer-grid{display:flex;flex-wrap:wrap;justify-content:space-between;gap:18px}
.footer-grid b{color:var(--ink-2)}
.toast{position:fixed;right:18px;bottom:18px;background:var(--ink);color:var(--paper);border-radius:8px;padding:10px 14px;font-size:12px;z-index:80}
/* responsive */
@media(max-width:1100px){.variant-grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:980px){
  .report-hero{grid-template-columns:1fr;gap:30px}
  .decision-compass{border-left:0;border-top:1px solid var(--line-strong);padding:10px 0 0}
  .truth-ribbon{grid-template-columns:1fr 1fr}.truth-label{grid-column:1/-1}
  .decision-evidence{grid-template-columns:repeat(2,1fr)}.decision-proof:nth-child(2){border-right:0}
  .exhibit-readout,.claim .exhibit-readout{grid-template-columns:repeat(2,1fr)}
  .frame-grid{grid-template-columns:1fr}
  .answer-row{grid-template-columns:90px 1fr}.answer-row p{grid-column:2}
  .confidence-band{grid-template-columns:repeat(3,1fr)}
  .flow-total,.flow-metric{display:flex;justify-content:space-between;align-items:center}
}
@media(max-width:680px){
  .shell{width:calc(100% - 28px)}
  .topbar .shell{height:auto;padding:10px 0;flex-wrap:wrap;gap:8px}
  .navlinks{width:100%;justify-content:flex-start;overflow-x:auto;padding-bottom:4px}
  .micro{display:none}
  h1{font-size:clamp(32px,9vw,44px)}
  main section{padding:50px 0}
  .exhibit-head{grid-template-columns:1fr}.exhibit-scope{text-align:left}
  .exhibit-readout,.claim .exhibit-readout{grid-template-columns:1fr}
  .nested-row,.diverge-row,.diverge-axis{grid-template-columns:1fr;}
  .nested-counts,.diverge-value{text-align:left}
  .variant-grid{grid-template-columns:repeat(2,1fr)}
  .matrix,.maturity,.status-legend{display:block;overflow-x:auto;white-space:nowrap;width:100%;max-width:100%}
  .coverage-row{grid-template-columns:1fr}
  .exhibit-scope{max-width:100%}
  .evidence-badge{white-space:normal;max-width:100%;text-align:left}
  .exhibit-scope .evidence-badge{margin-left:0}
  .prohibited-list li{grid-template-columns:40px 1fr}.prohibited-list .po-gate{text-align:left;grid-column:2}
  .lineage-row{grid-template-columns:1fr 1fr}.lineage-track{grid-column:1/-1}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*,*:before,*:after{transition:none!important;animation:none!important}}
@media print{
  @page{margin:14mm}
  html,html[data-theme="dark"]{color-scheme:light;--paper:#fff;--surface:#fff;--surface-2:#f5f2ef;--ink:#111;--ink-2:#444;--ink-3:#666;--line:#ddd;--line-strong:#bbb;--brand:#9b626c;--brand-deep:#744650;--brand-ink:#52323a;--brand-soft:#f7ecee;--love:#547867;--risk:#a55b52;--amber:#a87332;--blue:#4f6f84;--love-soft:#eaf1ed;--risk-soft:#f8ebe8;--amber-soft:#f7f0e4;--blue-soft:#eaf0f4}
  body{font-size:10.5px;background:#fff;color:#111}
  .topbar,.hero-actions,.navlinks,.toast{display:none!important}
  .shell{width:100%}
  .hero,main section{padding:24px 0}
  .report-hero{grid-template-columns:1.4fr .6fr;gap:28px}
  .decision-compass{border-left:1px solid #ccc;border-top:0;padding:8px 0 8px 26px}
  .exhibit,.claim,.lens-card,.quad-cell,.variant-card{break-inside:avoid;page-break-inside:avoid}
  details>div{display:block!important}
  .evidence-drawer summary{list-style:none}
  .report-footer{page-break-before:auto}
}
"""
