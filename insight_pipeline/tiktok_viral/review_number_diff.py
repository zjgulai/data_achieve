import re, html, collections, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_DIR = (ROOT.parent.parent / "tools" / "insight-reports" /
              "tiktok-viral-topic" / "2026-10-31")
src = open(REPORT_DIR / 'report.md', encoding='utf-8').read()
htm = open(REPORT_DIR / 'report.html', encoding='utf-8').read()

# strip style/script/tags from html
h = re.sub(r'<style\b.*?</style>', ' ', htm, flags=re.S|re.I)
h = re.sub(r'<script\b.*?</script>', ' ', h, flags=re.S|re.I)
h = re.sub(r'<[^>]+>', ' ', h)
h = html.unescape(h)

# normalise whitespace
s = re.sub(r'\s+', ' ', src)
h = re.sub(r'\s+', ' ', h)

# number token: digits with optional comma/decimal followed by common unit/percent
pat = re.compile(r'\d[\d,]*(?:\.\d+)?\s*(?:%|％|万|亿|倍|条|天|次|个|人|页|种|类)?')
def toks(t):
    out = []
    for m in pat.finditer(t):
        v = re.sub(r'\s+', '', m.group(0))
        out.append(v)
    return out

st = toks(s)
ht = toks(h)
# normalise comma in thousands: 47,073 vs 47073
def canon(v):
    return v.replace(',', '').replace('％','%')
sc = collections.Counter(canon(x) for x in st)
hc = collections.Counter(canon(x) for x in ht)
missing = sorted([k for k in sc if k not in hc], key=lambda x: (-sc[x], x))
extra = sorted([k for k in hc if k not in sc], key=lambda x: (-hc[x], x))
print('source tokens', len(st), 'unique', len(sc))
print('html tokens', len(ht), 'unique', len(hc))
print('MISSING in html:', len(missing))
for k in missing[:80]:
    print('  ', k, sc[k])
print('EXTRA in html:', len(extra))
for k in extra[:120]:
    print('  ', k, hc[k])
