# -*- coding: utf-8 -*-
import csv, json, re, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'deepread288.tsv'

rows=[]
with open(SRC, encoding='utf-8') as f:
    for r in csv.reader(f, delimiter='\t'):
        rows.append({
            'vid': r[0], 'hashtag': r[1], 'play': int(r[2]),
            'digg': int(r[3]), 'comment': int(r[4]), 'share': int(r[5]),
            'themes': json.loads(r[6]), 'mechs': json.loads(r[7]), 'descr': r[8],
        })

FAMILIES = [
 ('F1','反差反转类','视觉/认知/身份反差、反转、打脸、荒诞、预期违背'),
 ('F2','悬念揭秘类','悬念、揭秘、留白、截断、倒计时、生死危机'),
 ('F3','情绪共鸣类','情绪共鸣/释放、痛点、治愈、萌点、爽感、自嘲'),
 ('F4','节点借势类','节日/时令/热点/趋势/热梗借势与抢跑'),
 ('F5','社交裂变类','社交货币、互动指令、身份认同、模仿裂变、从众'),
 ('F6','教程实用类','教程、实操、干货、清单、低门槛、收藏、比价'),
 ('F7','视听感官类','卡点、快剪、混剪、ASMR、视觉奇观、音画节奏'),
 ('F8','真实实证类','真实纪实、抓拍、原声、背书、实测、验真'),
 ('F9','叙事冲突类','剧情、冲突、POV、挑战、任务、演绎'),
 ('F10','争议猎奇类','争议、猎奇、伦理冲突、恐怖谷、高尺度'),
]

# ordered rules: (family, regex)
RULES = [
 ('F10', r'争议|猎奇|恐怖谷|高尺度|血腥|反伦理|道德审判|审判钩子|禁忌|脑洞|两性警示|伪教程|恐吓|辟谣|AI辨伪|微瑕|审丑|极端反伦理'),
 ('F4',  r'节点|节日|节庆|时令|热点|趋势|热梗|热榜|热搜|热门|爆款音频|季节|档期|开学|万圣|圣诞|新年|春节|双十一'),
 ('F1',  r'反差|反转|打脸|荒诞|荒谬|超现实|错位|错配|认知失调|认知颠覆|认知冲突|预期违背|违背物理|断层|断崖|翻车|先抑后扬|意外笑点|黑色幽默|对称惩罚|选择困境|多轮转折|高频反转|颠覆|巨物|体型反差|肢体尺寸|强弱视觉|正反|极值反差|极端反差|极端视觉反差|极端认知反差|极端视听反差|极致人设反差|极致反差|极限困境反差|名利双重|宿敌破冰|高还原妆造|全图鉴翻转|双关|伪预设|假预设|多角色彩蛋|动作错觉|动态错觉|视听突转'),
 ('F2',  r'悬念|揭秘|解谜|留白|截断|预告|连载|窥探|隐藏|信息差|信息揭秘|二刷|生死|危机|阻碍|蓄势|前奏|倒计时|时限|时间契约|未解|未完待续|开放式|谜'),
 ('F5',  r'社交|互动|转发|裂变|身份|人群|模仿|模因|Meme|评论|嘴替|代嘴|暗号|邀约|共谋|从众|羊群|稀缺|FOMO|情侣|伴侣|索礼|跟跳|指令|提名|货币|关系|绑定|代币'),
 ('F6',  r'教程|实操|干货|清单|SOP|步骤|攻略|低门槛|零门槛|极简|工具|收藏|图鉴|拆解|排雷|试错|指南|方法|技巧|妙招|流程|演示|示范|交付|资源直给|利益点|价格锚点|比价|正误|纠错|对照|时间戳|复刻|量产|高回报|实用|功能|多品类|多场景利益|高复播|硬通货|清单体|清单式'),
 ('F8',  r'真实|纪实|抓拍|去滤镜|监控|现场|实录|档案|原声|无口播|无对白|日常纪录|生活抓包|沉浸|背书|权威|案例实证|数据论证|验真|实测|测试|暴力|破坏|竞品|材质特写|专业符号|素人|原生真诚|去商业化|平视'),
 ('F9',  r'剧情|冲突|POV|视角|第一人称|第一视角|挑战|闯关|任务|时间线|连续剧|群像|角色|叙事|故事|插曲|场景切换|场景硬切|戏剧|剧本|对白|口白|台词|自白|突发人物|对抗|尴尬|开局|黄金3秒|黄金前三秒|强剧情|表演|演绎|喜剧|肢体'),
 ('F3',  r'情绪|共鸣|共情|痛点|治愈|萌点|萌系|自嘲|破防|宣泄|释放|疗愈|温暖|温情|感动|泪|焦虑|爽感|爽点|爽剧|代偿|投射|认同|情感|心态|心理|压力|仪式感|生活向往|情怀|怀旧|回忆|陪伴|成长|保护欲|保护本能|幼崽|婴儿图式|幼态|萌'),
 ('F7',  r'卡点|视听|视觉|奇观|快剪|混剪|快切|ASMR|音效|运镜|特写|节奏|剪辑|蒙太奇|转场|BGM|音乐|音画|声画|原声|多巴胺|解压|高饱和|高颜值|魔性|洗脑|律动|踩点|定格|抽帧|微距|暗光|色彩|构图|镜头|视错觉|感官|听觉|声音|神曲|名曲|氛围感|画面|冲击|刺激|高密|高频|密集|速切|无缝|循环|完播|时长|短平快|信息密度|信息密集|帧|推焦|遮挡|遮镜|双屏|动态贺卡|数字贺卡|排比|快节奏|极速|快闪|视觉遮蔽'),
]
# manual overrides applied BEFORE rules for tricky tags (exact match)
OVERRIDES = {
 '视觉遮蔽':'F2', '极端时间锚点':'F2', '极限倒计时':'F2', '急促倒计时':'F2', '倒计时焦虑':'F2', '倒计时蓄力':'F2',
 '极端难度钩子':'F9', '极致痛点拷问':'F3', '极简降门槛':'F6', '极简低门槛':'F6', '极简单点痛点':'F3',
 '极简流程验证':'F6', '极简快节奏':'F7', '极短完播':'F7','极短完播机制':'F7','极短完播率':'F7','极短循环':'F7','极短无缝循环':'F7',
 '极短时长完播':'F7','极短时长强完播':'F7','超短完播':'F7','超短完播循环':'F7','超短平快':'F7','超短时完播':'F7','短平快完播':'F7','短时长循环':'F7',
 '极速交付':'F6','极速教程':'F6','极速情绪刺激':'F3','极速转场':'F7',
 '模版借势':'F5','名人音频借势':'F4','热门音频借势':'F4','爆款音频借势':'F4','爆款音频拦截':'F4','热梗音频二创':'F4','热榜BGM借势':'F4','影视原声钩子':'F7',
 '视觉休克钩子':'F7','幼态视觉刺激':'F3','萌宝视觉钩子':'F3','高萌动作卡点':'F7',
 '第一视角ASMR':'F7','沉浸式ASMR':'F7','原生ASMR':'F7','感官ASMR':'F7',
 '真实情绪破防':'F3','真实痛点前置':'F3','真实痛点共鸣':'F3',
 '身份标签共鸣':'F5','身份错位反差':'F1','情感嘴替社交':'F5','嘴替共鸣转发':'F5','情绪嘴替':'F5',
 '反焦虑反差情绪':'F1','情绪反差':'F1','情绪反转':'F1','情绪断崖反差':'F1','情绪断崖突变':'F1','情绪极端反转':'F1','情绪极限反转':'F1','情绪神反转':'F1','情绪秒级反转':'F1','情绪反转释放':'F1','情绪爽感反转':'F1','情绪断崖':'F1',
 '反差情绪破防':'F1','反差情绪释放':'F1','反差萌':'F1',
 '时间戳叙事':'F9','时间戳攻略':'F6','时间戳锚点':'F6','时间戳闭环':'F6',
 '高密度交付':'F6','极速交付':'F6','即时预期交付':'F6',
 '视觉治愈种草':'F7','视觉解压':'F7','视听解压':'F7','感官解压开局':'F7','感官解压特写':'F7','物理机关解压':'F7','解压快剪':'F7','渐进解压爽感':'F7','视觉强迫症解压':'F7','微距洁净爽感':'F7','秩序感治愈':'F7',
 '密集多巴胺种草':'F7','多巴胺视听':'F7','多巴胺循环':'F7',
 '无对白跨文化叙事':'F7','去语言化传播':'F7','无对白叙事':'F7',
 '跨语言肢体喜剧':'F9','生活抓包':'F8',
 '多品类全家福':'F6','多场景利益植入':'F6',
 '稀缺资源供给':'F5',
}

def classify(tag):
    if tag in OVERRIDES: return OVERRIDES[tag]
    for fam, pat in RULES:
        if re.search(pat, tag, re.I): return fam
    return None

allmech=Counter(); alltheme=Counter()
for r in rows:
    for m in r['mechs']: allmech[m]+=1
    for t in r['themes']: alltheme[t]+=1

mapping={}; un=[]
for tag in allmech:
    f=classify(tag)
    if f is None: un.append(tag)
    else: mapping[tag]=f
print('unassigned', len(un))
for t in sorted(un): print('UNASSIGNED', t, allmech[t])
print()
buckets=defaultdict(list)
for t,f in mapping.items(): buckets[f].append((t,allmech[t]))
for f,name,desc in FAMILIES:
    tags=buckets.get(f,[])
    print(f, name, 'unique_tags',len(tags),'assignments',sum(c for _,c in tags))
    print('   top:', ', '.join(f'{t}({c})' for t,c in sorted(tags,key=lambda x:(-x[1],x[0]))[:12]))

print('\n\n=== EXTRA OVERRIDES ===')
EXTRA = {
 'IP符号串联':'F5','借口阻断话术':'F6','刀片文案':'F3','利益置换收尾':'F6','利益驱动钩子':'F6',
 '动态突发钩子':'F7','动态递进':'F2','动态道具承接':'F7','即时奖赏':'F3','双钩子叠加':'F2',
 '反向设卡':'F2','反常识钩子':'F1','反私藏钩子':'F6','大单品借势':'F4','定向截流':'F4',
 '实物拉回机制':'F2','幽默神补刀':'F3','强IP预期锁定':'F2','微表情嘲讽':'F3','成品倒推':'F6',
 '成果暴击钩子':'F1','技能惊艳':'F7','拟音二创':'F7','收纳彩蛋拉回':'F2','数据量化复盘':'F8',
 '文化符号唤醒':'F5','文化符号植入':'F5','文字钩子':'F2','概念锚定':'F2','模范行为暗示':'F5',
 '正向激励机制':'F3','毫秒级硬切':'F7','爆点前置':'F2','特效放大':'F7','生活审美化':'F7',
 '画外音推拉':'F7','硬核动作钩子':'F7','私密转藏驱动':'F6','突变截留防流失':'F2','精准人声唤醒':'F7',
 '紧迫感前置':'F2','经典IP唤醒':'F5','经典IP锚定':'F5','结果先行':'F2','结果前置':'F2',
 '网梗表情缓冲':'F5','美学陈列钩子':'F7','视线引导':'F7','触感交互':'F7','触觉代入':'F7',
 '贪婪驱动':'F6','身体指认自测':'F5','迷因借势':'F5','通感钩子':'F7','长尾长效推流':'F4',
 '长视频权重':'F7','阶段告别物证':'F3','静态金句置顶':'F5','静态长文停留':'F7','高光前置':'F2',
 '原声对白卡点':'F7','原声节奏卡点':'F7','原声金句升华':'F5','平视情感共鸣':'F3','无口播氛围感':'F7',
 '身份场景冲突':'F1',
}
OVERRIDES.update(EXTRA)
un2=[]
for tag in allmech:
    if classify(tag) is None: un2.append(tag)
print('unassigned after extra',len(un2), sorted(un2))

mapping={tag:classify(tag) for tag in allmech}
assert all(mapping.values())

FAMNAME={f:n for f,n,d in FAMILIES}
fam_videos=defaultdict(set); fam_plays=defaultdict(list)
video_fams={}
for i,r in enumerate(rows):
    fs=set()
    for m in r['mechs']:
        f=mapping[m]; fs.add(f)
    video_fams[i]=fs
    for f in fs:
        fam_videos[f].add(i); fam_plays[f].append(r['play'])

overall_med=statistics.median(r['play'] for r in rows)
print('\n=== FAMILY STATS (overall median %.0f) ==='%overall_med)
for f,name,desc in FAMILIES:
    ps=fam_plays[f]
    print(f'{f}\t{name}\tn_videos={len(ps)}\tshare={len(ps)/len(rows):.1%}\tmedian={statistics.median(ps):.0f}\tmax={max(ps)}\ttags={len(buckets.get(f,[]))}')

# co-occurrence
print('\n=== TOP CO-OCCUR ===')
co=Counter()
for i,fs in video_fams.items():
    fl=sorted(fs)
    for a in range(len(fl)):
        for b in range(a+1,len(fl)):
            co[(fl[a],fl[b])]+=1
for f,name,desc in FAMILIES:
    tops=sorted([(c,g) for (a,g),c in co.items() if a==f]+[(c,a) for (a,g),c in co.items() if g==f], reverse=True)[:3]
    print(f, name, [(FAMNAME[g],c) for c,g in tops])
print('videos with 0 families', sum(1 for fs in video_fams.values() if not fs))
print('family count per video dist', Counter(len(fs) for fs in video_fams.values()))

print('\n=== RAW THEME MATRIX (theme n>=8) ===')
big_themes=[t for t,c in alltheme.items() if c>=8]
print('big themes',len(big_themes),sorted([(c,t) for t,c in alltheme.items() if c>=8], reverse=True))
cells=[]
for t in big_themes:
    idx=[i for i,r in enumerate(rows) if t in r['themes']]
    line=[]
    for f,name,desc in FAMILIES:
        sub=[rows[i]['play'] for i in idx if f in video_fams[i]]
        if len(sub)>=8:
            cells.append((statistics.median(sub),len(sub),t,name))
            line.append(f'{name[:2]}(n={len(sub)},med={statistics.median(sub):.0f})')
        else:
            line.append(f'{name[:2]}(-)')
    print(t,'n=',len(idx),'|',' '.join(line))
print('\ncells with n>=8:',len(cells))
for med,n,t,name in sorted(cells, reverse=True)[:15]:
    print(f'{t} x {name}: n={n}, median={med:.0f}')

print('\n=== HALLOWEEN FLAG ===')
def is_hw(r):
    s=' '.join(r['themes'])+' '+r['hashtag']+' '+r['descr']
    return ('万圣' in s) or ('halloween' in s.lower())
hw=[r for r in rows if is_hw(r)]; non=[r for r in rows if not is_hw(r)]
print('hw',len(hw),'non',len(non))
print('hw median',statistics.median(r['play'] for r in hw),'non median',statistics.median(r['play'] for r in non))
print('hw share',len(hw)/len(rows))
# family composition hw vs non
for f,name,desc in FAMILIES:
    h=sum(1 for r in hw if f in video_fams[rows.index(r)])
    nn=sum(1 for r in non if f in video_fams[rows.index(r)])
    print(f'{f}\t{name}\thw={h}/{len(hw)}={h/len(hw):.0%}\tnon={nn}/{len(non)}={nn/len(non):.0%}')
