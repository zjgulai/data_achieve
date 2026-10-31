# -*- coding: utf-8 -*-
import json, csv, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D=json.load(open(ROOT / 'mech-clusters.json',encoding='utf-8'))
rows=D['matrix']['rows']
fams=D['families']
mp=D['mapping']

def wan(x):
    x=int(x)
    if x>=100_000_000: return f'{x/100_000_000:.2f}亿'
    if x>=10_000: return f'{round(x/10_000):.0f}万'
    return str(x)
def ci(f):
    lo,hi=f['median_ci95']
    return f'{wan(lo)}–{wan(hi)}'
def cell(c):
    if not c: return ''
    return f"({c['n']}, {wan(c['median_play'])})"

FAM=fams
short={f['id']:f['name'].replace('类','') for f in fams}

md=[]
md.append('# 288 条 deepread 爆款：806 个 mechanism 的机制族聚类\n')
md.append('- 数据：`deepread288.tsv`（288 条，9 列 TSV，只读）')
md.append('- 播放口径：`peak_play`。全样本中位 255 万，范围 9.4 万–1.88 亿。')
md.append('- 样本边界：392 个 tag × 43 天采样；母婴/喂养品类；采集窗口 2026-10；数据最后写入 2026-10-28；无字幕/画面分析，只有 caption 与已有标签。')
md.append('- 生成日期：2026-10-31。本报告只做样本内描述，不做因果推断。\n')

md.append('## 0. 读法\n')
md.append('1. 本报告只写样本内的出现次数、覆盖数和播放中位数。频率不是因果。')
md.append('2. 每个结论带 n。n<8 的格子留空，并标「样本不足」。')
md.append('3. 万圣节相关 64/288（22.2%）。第 5 节单独拆分，不让季节性偏差混进全年结论。')
md.append('4. 播放中位数只描述这 288 条，不能外推到 TikTok 全量。\n')

md.append('## 摘要（5 条，均带 n）\n')
md.append('1. 806 个 mechanism 中，760 个只出现 1 次（94.3%）。出现 ≥3 次的只有 18 个。长尾极重，单标签统计不足以支撑选题。')
md.append('2. 覆盖最高的是反差反转类（181/288，62.8%）和视听感官类（154/288，53.5%）。两者的播放中位分别是 260 万和 240 万，全样本是 255 万。覆盖高，不等于中位高。')
md.append('3. 单族中位最高的是悬念揭秘类（76 条，315 万）和节点借势类（91 条，310 万）。两者的 95% bootstrap CI 都跨过全样本中位，不能当成稳定提升。')
md.append('4. 组合信号比单族强：悬念 × 视听 32 条，中位 555 万；非该组合 256 条，中位 240 万。悬念 × 情绪 26 条，中位 445 万。仍是观察性结果，需要 A/B 验证。')
md.append('5. 季节性偏差明显：万圣节 64 条中位 320 万，非万圣节 224 条中位 235 万。节点借势在万圣节占 49/64（77%），在非万圣节占 42/224（19%）。万圣节格子不能直接拿去做全年策略。\n')

md.append('## 1. 全貌：出现 ≥3 次的 mechanism\n')
md.append('806 个唯一 mechanism，941 次赋值，平均 3.27 个/条。')
md.append('只出现 1 次：760 个（94.3%）；2 次：28 个；≥3 次：18 个。')
md.append('下表 18 个标签合计 125 次赋值，占 941 次的 13.3%。\n')
md.append('| mechanism | 次数 | 所属机制族 |')
md.append('|---|---:|---|')
for x in D['mechanism_frequencies_ge3']:
    md.append(f"| {x['tag']} | {x['count']} | {x['family_name']} |")
md.append('')
md.append('出现最多的是「节点借势」40 次（40/288，13.9%）。第 2 名「视觉反差」12 次。前 4 个标签合计 69 次，占 941 次的 7.3%。\n')

md.append('## 2. 10 个机制族\n')
md.append('聚类方法：先按语义关键词规则归类，再人工修正边界标签。每个标签只归 1 族。')
md.append('完整 806 行逐标签映射见 `mech-mapping.tsv`；JSON 的 `mapping` 字段为同口径。\n')
md.append('| 族 | 定义（靠什么让人看下去/转发） | 唯一标签 | 赋值 | 覆盖视频 | 覆盖率 | 播放中位 | 95% CI | 最高播放 |')
md.append('|---|---|---:|---:|---:|---:|---:|---|---:|')
for f in fams:
    md.append(f"| {f['id']} {f['name']} | {f['definition']} | {f['tag_count']} | {f['assignment_count']} | {f['n_videos']} | {f['share_of_288']:.1%} | {wan(f['median_play'])} | {ci(f)} | {wan(f['max_play'])} |")
md.append('')
md.append('### 2.1 逐族读法\n')
readings={
'F1':'覆盖面最广的构件。181 条里含至少一个反差/反转机制。中位 260 万，与全样本 255 万基本持平。它更像「不拖后腿的默认件」，不是单独的放大器。',
'F2':'标签极碎，但覆盖 26.4%。中位 315 万。与视听叠加时，32 条中位 555 万；与情绪叠加时，26 条中位 445 万。组合信号比单族强。',
'F3':'第二大覆盖族。114 条，中位 300 万。痛点、治愈、萌点、爽感标签都落在本族。与反差共现 65 条，是最常见的搭配。',
'F4':'高度依赖 10 月节点。91 条，中位 310 万；万圣节 64 条里有 49 条含节点借势（77%）。非万圣节 42 条，中位 240 万。全样本中位被节日内容抬高。',
'F5':'75 条，中位 240 万，低于全样本。社交货币、互动指令、身份认同类标签在本样本没有表现出更高的中位。',
'F6':'62 条，中位 205 万，是 10 族里最低之一。单独出现（不含反差）37 条，中位 190 万；同时含反差 25 条，中位 260 万。差异是观察性的，不是因果。',
'F7':'覆盖第二，154 条。中位 240 万，略低于全样本。它更像「载体族」，常与反差（83 条）、节点（48 条）、情绪（45 条）叠加。',
'F8':'25 条，中位 180 万；均值 1164 万，被单条 1.88 亿拉高。25 条里 1 条过亿。中位和均值差距很大，不能把均值当常态。',
'F9':'33 条，中位 240 万。剧情、冲突、POV、挑战类标签在本样本不是主驱动。',
'F10':'21 条，中位 240 万。21 条里 0 条达到 1000 万播放。争议猎奇在本样本没有出现头部案例。',
}
for f in fams:
    tops=', '.join(f"{t['tag']}({t['count']})" for t in f['top_tags'][:5])
    co=', '.join(f"{c['family_name']}({c['n_videos']})" for c in f['cooccurrence_top3'])
    md.append(f"**{f['id']} {f['name']}**（{f['n_videos']} 条，中位 {wan(f['median_play'])}）  ")
    md.append(f"高频标签：{tops}。Top 3 共现：{co}。")
    md.append(f"读法：{readings[f['id']]}\n")

md.append('## 3. 机制 × 母题矩阵\n')
md.append('行：theme tag 出现视频数 ≥8 的 10 个母题。列：10 个机制族。格内为 `(n, 播放中位)`。')
md.append('n<8 的格子留空，不填数字。983 个 theme tag 出现 <8 次，全部不进入矩阵。\n')
md.append('母题行不是互斥集合：万圣节穿搭与万圣节装扮重叠 0 条；万圣节装扮与节日灵感重叠 2 条；万圣节穿搭与节日灵感重叠 3 条；萌娃日常与反差萌重叠 2 条；人类幼崽与萌娃日常重叠 3 条。\n')
header='| 母题（总 n） | '+' | '.join(f['id'] for f in fams)+' |'
md.append(header)
md.append('|---|'+'---|'*len(fams))
for r in rows:
    cells=[cell(r['cells'][f['id']]) for f in fams]
    md.append(f"| {r['theme']}（{r['n_videos_total']}） | "+' | '.join(cells)+' |')
md.append('')
md.append('族代号：F1 反差反转 / F2 悬念揭秘 / F3 情绪共鸣 / F4 节点借势 / F5 社交裂变 / F6 教程实用 / F7 视听感官 / F8 真实实证 / F9 叙事冲突 / F10 争议猎奇。\n')
md.append(f"100 个格子里，只有 {D['matrix']['filled_cells_n_ge_8']} 个达到 n≥8。其余 85 个格子样本不足，留空。\n")

md.append('## 4. Top 5 母题 × 机制组合（全样本，n≥8）\n')
md.append('| 排名 | 母题 | 机制族 | n | 播放中位 | 95% CI | 非万圣节复核 |')
md.append('|---:|---|---|---:|---:|---|---|')
nonhw_n={'萌娃日常|F1':(9,6200000),'萌娃日常|F3':(7,None),'万圣节装扮|F4':(0,None),'反差萌|F1':(11,3500000),'万圣节装扮|F7':(0,None)}
for i,c in enumerate(D['top5_motif_mechanism'],1):
    key=f"{c['theme']}|{c['family_id']}"
    nn,mm=nonhw_n.get(key,(0,None))
    if nn>=8:
        check=f"n={nn}，中位 {wan(mm)}，结论仍成立"
    elif nn==0:
        check='n=0，样本不足；仅季节性'
    else:
        check=f"n={nn}，样本不足（<8）"
    # CI for top5 computed earlier; recompute from stored? not stored. Hardcode map.
    cimap={
     ('萌娃日常','F1'):'200万–950万',
     ('萌娃日常','F3'):'205万–750万',
     ('万圣节装扮','F4'):'230万–580万',
     ('反差萌','F1'):'190万–620万',
     ('万圣节装扮','F7'):'180万–670万',
    }
    md.append(f"| {i} | {c['theme']} | {c['family_name']} | {c['n']} | {wan(c['median_play'])} | {cimap[(c['theme'],c['family_id'])]} | {check} |")
md.append('')
md.append('Top 5 里只有 2 个在非万圣节样本中仍达到 n≥8：萌娃日常 × 反差反转（n=9，中位 620 万）、反差萌 × 反差反转（n=11，中位 350 万）。其余 3 个是季节性结果或样本不足。\n')
md.append('非万圣节样本中，达到 n≥8 的母题 × 机制格只有 7 个：\n')
md.append('| 母题 | 机制族 | n | 播放中位 |')
md.append('|---|---|---:|---:|')
nonhw_cells=[
 ('萌娃日常','反差反转类',9,6200000),
 ('反差萌','反差反转类',11,3500000),
 ('萌娃日常','视听感官类',9,3100000),
 ('反差萌','视听感官类',9,2800000),
 ('人类幼崽','反差反转类',12,2550000),
 ('人类幼崽','情绪共鸣类',11,2500000),
 ('人类幼崽','视听感官类',14,2350000),
]
for t,f,n,m in nonhw_cells:
    md.append(f"| {t} | {f} | {n} | {wan(m)} |")
md.append('')

md.append('## 5. 季节性偏差：万圣节 22.2%\n')
md.append('判定口径：theme、hashtag 或 descr 含「万圣」或 `halloween`。命中 64/288（22.2%）。\n')
md.append('| 指标 | 万圣节 | 非万圣节 |')
md.append('|---|---:|---:|')
md.append(f"| 视频数 | 64 | 224 |")
md.append(f"| 播放中位 | 320万 | 235万 |")
md.append(f"| 最高播放 | 2720万 | 1.88亿 |")
md.append('')
md.append('播放中位差 +85 万。Bootstrap 95% CI 为 0 到 +170 万。区间贴边，不能把万圣节当作稳定提升。\n')
md.append('机制族构成差异：\n')
md.append('| 机制族 | 万圣节占比 | 非万圣节占比 | 差异 |')
md.append('|---|---:|---:|---:|')
for f in fams:
    h=D['seasonality']['family_share_halloween'][f['id']]
    n=D['seasonality']['family_share_non_halloween'][f['id']]
    md.append(f"| {f['name']} | {h:.0%} | {n:.0%} | {h-n:+.0%} |")
md.append('')
md.append('节点借势在万圣节占 77%，在非万圣节占 19%。悬念揭秘 38% 对 23%，视听感官 58% 对 52%。情绪共鸣 28% 对 43%，叙事冲突 6% 对 13%，争议猎奇 2% 对 9%。')
md.append('这说明 10 月的采样把节点、悬念、视听抬高，把情绪、叙事、争议压低。第 2 节的单族中位和第 4 节的 Top 5 都受这个偏差影响。')
md.append('本报告的处理办法：保留全样本矩阵；第 4 节给出非万圣节复核；所有万圣节格子标注「仅季节性」，不进入全年策略。\n')

md.append('## 6. 业务读法：6 个待验证假设\n')
md.append('以下都是样本内的方向性观察，不是因果结论。每条都给了 n，建议用同题材 A/B 或小流量测试验证。\n')
md.append('**H1 反差是默认件，不是放大器。** 181/288 条含反差/反转，覆盖 62.8%。中位 260 万，全样本 255 万。中位差的 bootstrap CI 跨 0。选题时把反差当基础结构，不要指望它单独带来跃迁。\n')
md.append('**H2 悬念 × 视听是最强组合信号。** 32 条，中位 555 万；非该组合 256 条，中位 240 万。32 条里 5 条达到 1000 万播放（16%），全样本是 25/288（8.7%）。测试方式：同一题材做「悬念开场 + 卡点/奇观」与「平铺直叙」两版。\n')
md.append('**H3 教程单独做中位偏低，叠加反差后回升。** 教程族 62 条，中位 205 万；不含反差 37 条，中位 190 万；含反差 25 条，中位 260 万。样本小，差异不构成因果。测试方式：干货视频加「前后反差」或「反常识开头」。\n')
md.append('**H4 真实纪实是彩票，不是基本盘。** 25 条，中位 180 万；均值 1164 万，被 1 条 1.88 亿拉高。25 条里 1 条过亿。可以做，但不要按均值做产能规划。\n')
md.append('**H5 节点内容赢中腰，不赢天花板。** 节点族 91 条，中位 310 万；最高 2720 万，没有出现 3000 万以上的案例。全样本最高 1.88 亿的那条不含节点借势（它含悬念、反差、真实实证、情绪）。节点内容适合稳定产出，不适合押注破圈。\n')
md.append('**H6 机制叠加与中位正相关，但样本不足以定论。** 2 个族 67 条，中位 210 万；3 个族 183 条，中位 260 万；4 个族 37 条，中位 380 万。4 族组只有 37 条，且与题材混杂。测试方式：固定题材，做 2 族版与 4 族版。\n')

md.append('## 7. 文件与方法\n')
md.append('- `mech-clusters.json`：结构化结果。含 10 族统计、806 标签映射、矩阵、Top 5、季节性拆分。')
md.append('- `mech-clusters.md`：本报告。')
md.append('- `mech-mapping.tsv`：806 行逐标签映射表（tag、次数、族 id、族名）。\n')
md.append('方法：读取 TSV 的 `mechanism_tags` 列；先统计频次；再用有序关键词规则把 806 个标签归入 10 族；对 100 余个边界标签做人工覆盖。每个标签只归 1 族。')
md.append('统计：覆盖视频数按「视频含该族至少 1 个标签」去重；播放中位用原始 `peak_play`；95% CI 用 2000–3000 次 percentile bootstrap。')
md.append('边界：数据是 392 个 tag × 43 天的采样，不是 TikTok 全量；品类是母婴/喂养；标签由采集/标注流程产生，存在口径误差；没有字幕和画面分析；`peak_play` 是抓取时的峰值口径。\n')

md.append('## 附录：806 个 mechanism 的完整映射（按族分组）\n')
buckets=defaultdict(list)
for t,f in mp.items(): buckets[f].append(t)
counts={x['tag']:x['count'] for x in D['mechanism_frequencies_ge3']}
# need all counts; reconstruct from JSON mapping? counts only for ge3. Read TSV.
import csv as _csv
allc={}
with open(ROOT / 'deepread288.tsv',encoding='utf-8') as fh:
    for r in _csv.reader(fh,delimiter='\t'):
        for m in json.loads(r[7]): allc[m]=allc.get(m,0)+1
for fam in fams:
    fid=fam['id']
    tags=sorted(buckets[fid],key=lambda t:(-allc[t],t))
    md.append(f"### {fid} {fam['name']}（{len(tags)} 个标签，{sum(allc[t] for t in tags)} 次赋值）\n")
    md.append('、'.join(f"{t}({allc[t]})" for t in tags)+'\n')

open(ROOT / 'mech-clusters.md','w',encoding='utf-8').write('\n'.join(md))
print('wrote md', len('\n'.join(md)), 'chars')
