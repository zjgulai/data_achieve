# -*- coding: utf-8 -*-
import csv, json, statistics, collections, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'deepread288.tsv'
SRC_LABEL = 'deepread288.tsv'
THEME = ROOT / 'theme-clusters.json'
MECH = ROOT / 'mech-clusters.json'
OUT = ROOT / 'replicability.json'

rows = []
with open(SRC, encoding='utf-8') as f:
    for r in csv.reader(f, delimiter='\t'):
        rows.append(dict(video_id=r[0], hashtag=r[1], peak=int(r[2]), digg=int(r[3]),
                         comment=int(r[4]), share=int(r[5]), themes=json.loads(r[6]),
                         mechs=json.loads(r[7]), descr=r[8]))
rows.sort(key=lambda r: -r['peak'])  # index order = review file order

tc = json.load(open(THEME)); mp = tc['mapping']
motif_names = [m['name'] for m in tc['motifs']]

# categories, in the same order as rows sorted by peak (1..288)
CATS = """RARE COSPLAY AUTH COMEDY AIGEN TUT COSPLAY COMEDY ANIM RARE
DANCE PROMPT TRICK RARE TUT PROD PROMPT TUT AIGEN FOOTAGE
DANCE TUT AUTH STORY TRICK AIGEN AUTH AUTH AIGEN AUTH
AUTH COSPLAY FOOTAGE COMEDY PROD RARE PROD COMEDY PROD FOOTAGE
TUT PROMPT AUTH PROD COMEDY AUTH CELEB FOOTAGE FOOTAGE CELEB
AIGEN COSPLAY PROD PROD PROD PROD ANIM TUT DANCE AUTH
COMEDY PROMO COSPLAY COMEDY COSPLAY COMEDY AUTH RARE TUT PROD
PROD AUTH PROD TUT AUTH COMEDY COSTUME COSTUME PROD FOOTAGE
TUT COMEDY DANCE TRICK PROD COMEDY COMEDY DANCE FOOTAGE TUT
CELEB CELEB FOOTAGE TUT PROD PROD COMEDY TUT RARE MEME
COSPLAY COSTUME AUTH COMEDY PROD RARE TUT PROD TUT AUTH
COMEDY TUT PROD COSPLAY PROMPT RARE COSTUME TUT FOOTAGE AIGEN
AUTH AUTH PROD PROD TUT CELEB TUT TUT COMEDY COMEDY
COMEDY COMEDY AUTH FOOTAGE AUTH TUT COSPLAY TUT AUTH COMEDY
AUTH RARE AIGEN CELEB AUTH COSPLAY FOOTAGE PROD RARE PROD
AIGEN AUTH PROD PROD COSPLAY TUT PROD TUT COMEDY PROD
PROD PROMPT PROD AIGEN PROD PROD TUT RARE TRICK TUT
ANIM FOOTAGE COMEDY MEME COMEDY PROD AUTH FOOTAGE TUT COMEDY
PROD STORY AUTH STORY COSTUME AUTH TUT AUTH TUT COSTUME
TUT AIGEN TUT AUTH AUTH COMEDY TRICK AUTH AUTH TUT
FOOTAGE COSPLAY AUTH AUTH TRICK ANIM PROD STORY COSTUME PROD
MEME AUTH STORY AIGEN CELEB PROD COMEDY MEME AUTH TUT
TUT AUTH AUTH PROD DANCE RARE FOOTAGE PROD PROD PROMPT
UNKNOWN PROD PROD AUTH RARE AUTH CELEB COMEDY TUT FOOTAGE
TUT COMEDY AUTH TUT AUTH AUTH AUTH AUTH AUTH CELEB
AUTH DANCE PROMPT COMEDY AUTH FOOTAGE FOOTAGE CELEB COSPLAY AUTH
STORY TUT TUT TUT AUTH PROD AUTH AUTH MEME AUTH
PROMPT PROD AUTH AUTH MEME PROD MEME PROD MEME AUTH
AUTH PROMPT COMEDY MEME PROD PROD PROD AUTH""".split()
assert len(CATS) == 288, len(CATS)

TIER = {
 'TUT':'高','PROD':'高','TRICK':'高','DANCE':'高','COSTUME':'高','PROMPT':'高',
 'MEME':'中','PROMO':'中','COMEDY':'中','AUTH':'中','COSPLAY':'中','AIGEN':'中','STORY':'中',
 'RARE':'低','CELEB':'低','FOOTAGE':'低','ANIM':'低','UNKNOWN':'无法判断'
}
RULE = {k:'cat_'+k.lower() for k in TIER}

IP_NAMES = ['Starfire','FNAF','Five Nights','Monster High','Mavis','Avatar','Coraline','My Little Pony','Poison Ivy','Cinderella','jester','clown','Coraline','Little Mermaid','Elsa','Wednesday','Chucky','IT','Harley Quinn']
SCARCE_KWS = ['超早产儿','早产儿','生命奇迹','病童','儿童抗癌','抗癌','多胞胎','四胞胎','quadruplet','生死离别','悼念','离世','去世','意外离世','grief','siblingloss','sibling loss','postpartum psychosis','产后 psychosis','产后心理','真实案件','大案','司法','法院','罪案','911','网红意外','儿童选美','toddlersandtiaras','pageant','真人秀','人工流产','伦理争议','高危妊娠','childhood cancer','pediatric cancer','cancer','premature','preemie','autism','special needs','passed away']
CELEB_KWS = ['明星','名人','网红','celebrity','influencer','访谈','演唱会','现场狂欢','说唱圈层','法庭纪实','明星热点','名人档案','lildurk','lil durk','dolly','whitney','miley','taylor swift']
FOOTAGE_KWS = ['影视切片','影视剪辑','电影','正片','full movie','tvshow','动画正片','纪录片','影视混剪','经典IP混剪','剧集','美剧','韩剧','cartoon','parenthood','coraline','tlc','真人秀','新闻','911']
ANIM_KWS = ['3D动画','3D卡通萌娃','3D早教动画','3D医学动画','3D奇观','定格动画','cartoon','动画儿歌','3D']
PROD_NAMES = ['Momcozy','Dyson','Walmart','Target','Amazon','Jellycat','Babylist','Maxi-Cosi','Thyseed','Dr. Brown','Fisher-Price','Hello Kitty','Little People','Momcozy D8','wearable blanket','sensory bin']
IP_TERMS = ['Starfire','FNAF','Five Nights','Monster High','Mavis','Avatar','Coraline','My Little Pony','Poison Ivy','Cinderella','jester','clown','Little Mermaid','Elsa','Wednesday','Chucky','Harley Quinn','Jack Skellington','Nightmare Before Christmas','Monsters Inc','Gilmore Girls','Godzilla','Disney','Marvel','Pokemon','Pikachu','Sanrio','Hello Kitty','三丽鸥','小马宝莉','鬼妈妈','宝可梦','迪士尼','漫威','哈利波特','星黛露','玲娜贝儿','米奇','米妮','小黄人','海绵宝宝','Peppa','小猪佩奇']
BRAND_TERMS = ['Momcozy','Dyson','Walmart','Target','Amazon','Jellycat','Babylist','Maxi-Cosi','Thyseed','Dr. Brown','Fisher-Price','Comfort Colors','Gilmore Girls','Little People','Hello Kitty','Tokidoki','Hyundai','Dove','Pampers','Huggies','Enfamil','Similac','Medela','Spectra','Elvie','Baby Brezza','Growsy']

def find(text, kws):
    return [k for k in kws if k.lower() in text.lower()]

LABEL = {'childhood cancer':'儿童抗癌','pediatric cancer':'儿童抗癌','cancer':'癌症','premature':'早产儿','preemie':'早产儿','quadruplet':'四胞胎','grief':'丧亲','sibling loss':'手足离世','siblingloss':'手足离世','postpartum psychosis':'产后精神病','passed away':'离世','autism':'自闭症','special needs':'特需儿童','tvshow':'电视剧','full movie':'电影正片','cartoon':'动画','tlc':'TLC 真人秀','reality tv':'真人秀','news':'新闻','3d animation':'3D 动画','stop motion':'定格动画','lildurk':'Lil Durk','lil durk':'Lil Durk','dolly':'Dolly Parton','whitney':'Whitney Houston','miley':'Miley Cyrus','taylor swift':'Taylor Swift','influencer':'网红','celebrity':'名人','pageant':'儿童选美','toddlersandtiaras':'Toddlers & Tiaras','真人秀':'真人秀','儿童选美':'儿童选美','网红':'网红','明星':'明星'}
def lab(k): return LABEL.get(k, k)

def motif_set(r):
    return sorted({mp[t]['name'] for t in r['themes'] if t in mp})

def make_reason(cat, r, text, motifs):
    cap = re.sub(r'\s+',' ', r['descr']).strip()
    cap = cap[:64] + ('…' if len(cap) > 64 else '')
    th = '、'.join(r['themes'][:2]) if r['themes'] else '无主题标签'
    prod = find(text, PROD_NAMES)
    ip = find(text, IP_NAMES)
    scarce = find(text, SCARCE_KWS)
    celeb = find(text, CELEB_KWS)
    foot = find(text, FOOTAGE_KWS)
    anim = find(text, ANIM_KWS)
    if cat == 'PROMO':
        return f'品牌福利/赠品活动型：theme 为「{th}」，需要品牌预算与奖品，形式可学但资源门槛高（"{cap}"）。'
    if cat == 'TUT':
        return f'教程/DIY型：theme 为「{th}」，caption/标签显示可执行的做法或材料（"{cap}"），普通团队可照做。'
    if cat == 'PROD':
        p = prod[0] if prod else None
        return ((f'产品/种草型：{p} 可购买，展示流程可复制' if p else f'产品/种草型：theme 为「{th}」，对应产品可购买，展示流程可复制') + f'（"{cap}"）。')
    if cat == 'TRICK':
        return f'模板/剪辑型：theme 为「{th}」，有公开模板或固定剪辑步骤（"{cap}"），照着套即可。'
    if cat == 'DANCE':
        return f'舞蹈/卡点型：theme 为「{th}」，动作与节奏可学习，普通团队可重拍（"{cap}"）。'
    if cat == 'COSTUME':
        return f'节日穿搭/变装清单型：theme 为「{th}」，服装道具可采购组装（"{cap}"）。'
    if cat == 'PROMPT':
        return f'文字/清单/迷因型：theme 为「{th}」，无稀缺素材，手机即可制作（"{cap}"）。'
    if cat == 'MEME':
        return f'热梗/迷因二创型：theme 为「{th}」，格式公开但依赖时效与表演/妆造（"{cap}"）。'
    if cat == 'COMEDY':
        return f'剧情/整蛊型：theme 为「{th}」，可脚本化重拍，但依赖演员与宝宝配合（"{cap}"）。'
    if cat == 'AUTH':
        return f'真实家庭日常型：theme 为「{th}」，场景可搭，真实反应与人物关系不可复现（"{cap}"）。'
    if cat == 'COSPLAY':
        i = lab(ip[0]) if ip else 'IP 角色'
        return f'IP 妆造型：theme 为「{th}」，绑定 {i}，妆造可学但有角色版权边界（"{cap}"）。'
    if cat == 'AIGEN':
        return f'AI 生成型：theme 为「{th}」，工具可得但需提示词与后期能力，非随手拍（"{cap}"）。'
    if cat == 'STORY':
        return f'个人里程碑型：theme 为「{th}」，同类家庭可拍自己的版本，但事件不可按需重演（"{cap}"）。'
    if cat == 'RARE':
        s = lab(scarce[0]) if scarce else th
        return f'稀缺生命事件/病例：{s}，素材本身不可复制（"{cap}"）。'
    if cat == 'CELEB':
        c = lab(celeb[0]) if celeb else th
        return f'名人/热点人物型：{c}，普通团队没有本人素材（"{cap}"）。'
    if cat == 'FOOTAGE':
        f_ = lab(foot[0]) if foot else th
        return f'影视/真人秀/新闻正片素材：{f_}，无版权且无法重拍（"{cap}"）。'
    if cat == 'ANIM':
        a = lab(anim[0]) if anim else th
        return f'工作室级动画：{a}，个人团队无法同质量重做（"{cap}"）。'
    return f'caption/标签不足以识别核心制作方式（"{cap}"，theme={th}）。'

def basis_for(cat, r, text):
    cap = re.sub(r'\s+',' ', r['descr'])[:80]
    base = dict(theme='、'.join(r['themes'][:3]),
                mechanism='、'.join(r['mechs'][:3]),
                hashtag=r['hashtag'], caption_snippet=cap)
    if cat in ('TUT',):
        base['fields']=['theme_tags','caption']; base['matched']=next(iter([k for k in ['教程','tutorial','how to','DIY','diy','hack','妙招','步骤','craft','trick'] if k.lower() in text.lower()] or ['theme:实用教程与DIY']))
    elif cat in ('PROD','PROMO'):
        base['fields']=['theme_tags','hashtag','caption']; base['matched']=next(iter(find(text,PROD_NAMES) or ['theme:母婴好物种草']))
    elif cat=='TRICK':
        base['fields']=['caption','hashtag','theme_tags']; base['matched']=next(iter([k for k in ['CapCut','capcut','template','pioneertemplate','split image tutorial','make the same video'] if k.lower() in text.lower()] or ['theme:半脸拼接/模板']))
    elif cat=='DANCE':
        base['fields']=['theme_tags','hashtag','caption']; base['matched']=next(iter([k for k in ['dance','舞蹈','卡点','手势舞','trend'] if k.lower() in text.lower()] or ['theme:舞蹈/卡点']))
    elif cat=='COSTUME':
        base['fields']=['theme_tags','hashtag','caption']; base['matched']=next(iter([k for k in ['costume','穿搭','变装','灵感','halloween'] if k.lower() in text.lower()] or ['theme:变装穿搭']))
    elif cat=='PROMPT':
        base['fields']=['theme_tags','hashtag','caption']; base['matched']=next(iter([k for k in ['清单','meme','october1st','生日','祝福','模因','打卡'] if k.lower() in text.lower()] or ['theme:清单/迷因']))
    elif cat=='MEME':
        base['fields']=['theme_tags','mechanism_tags','caption']; base['matched']=next(iter([k for k in ['trend','challenge','makeup','二创','挑战','迷因','热梗'] if k.lower() in text.lower()] or ['theme:热梗二创']))
    elif cat=='COMEDY':
        base['fields']=['theme_tags','mechanism_tags','caption']; base['matched']=next(iter([k for k in ['搞笑','整蛊','prank','POV','pov','反转','剧情'] if k.lower() in text.lower()] or ['theme:家庭搞笑']))
    elif cat=='AUTH':
        base['fields']=['theme_tags','mechanism_tags','caption']; base['matched']=next(iter([k for k in ['真实','纪实','抓拍','原声','日常','vlog','萌娃','育儿'] if k.lower() in text.lower()] or ['theme:家庭日常']))
    elif cat=='COSPLAY':
        base['fields']=['theme_tags','hashtag','caption']; base['matched']=next(iter(find(text,IP_NAMES) or ['theme:IP 角色']))
    elif cat=='AIGEN':
        base['fields']=['theme_tags','caption']; base['matched']=next(iter([k for k in ['AI','ai','AI生成','AI动画','AI萌娃','AI婴儿'] if k in text] or ['theme:AI']))
    elif cat=='STORY':
        base['fields']=['theme_tags','caption']; base['matched']=next(iter([k for k in ['孕期','怀孕','分娩','产后','婚礼','生日','孕产'] if k in text] or ['theme:个人里程碑']))
    elif cat=='RARE':
        base['fields']=['theme_tags','caption']; base['matched']=lab(next(iter(find(text,SCARCE_KWS) or ['theme:罕见事件'])))
    elif cat=='CELEB':
        base['fields']=['theme_tags','hashtag','caption']; base['matched']=lab(next(iter(find(text,CELEB_KWS) or ['theme:名人'])))
    elif cat=='FOOTAGE':
        base['fields']=['theme_tags','hashtag','caption']; base['matched']=lab(next(iter(find(text,FOOTAGE_KWS) or ['theme:影视素材'])))
    elif cat=='ANIM':
        base['fields']=['theme_tags','caption']; base['matched']=lab(next(iter(find(text,ANIM_KWS) or ['theme:动画'])))
    else:
        base['fields']=['caption','theme_tags']; base['matched']='无可用信号'
    return base

videos = []
for i, (r, cat) in enumerate(zip(rows, CATS), 1):
    text = ' '.join([r['hashtag'], r['descr'], ' '.join(r['themes']), ' '.join(r['mechs'])])
    motifs = motif_set(r)
    tier = TIER[cat]
    halloween = ('万圣' in text) or ('halloween' in text.lower())
    rec = dict(
        rank_by_play=i,
        video_id=r['video_id'],
        tier=tier,
        rule=RULE[cat],
        reason=make_reason(cat, r, text, motifs),
        peak_play=r['peak'],
        hashtag=r['hashtag'],
        theme_tags=r['themes'],
        mechanism_tags=r['mechs'],
        motifs=motifs,
        seasonal_halloween=bool(halloween),
        ip_risk=bool(find(text, IP_TERMS)),
        ip_terms=find(text, IP_TERMS),
        brand_terms=find(text, BRAND_TERMS),
        caption=r['descr'],
        engagement=dict(digg_rate=round(r['digg']/r['peak'],5),
                        comment_rate=round(r['comment']/r['peak'],6),
                        share_rate=round(r['share']/r['peak'],5)),
        basis=basis_for(cat, r, text)
    )
    videos.append(rec)

# ---------- stats ----------
def med(xs):
    return int(statistics.median(xs)) if xs else None

def pct(xs,p):
    if not xs: return None
    xs=sorted(xs); k=(len(xs)-1)*p; f=int(k); c=min(f+1,len(xs)-1)
    return int(xs[f]+(xs[c]-xs[f])*(k-f))

tiers = ['高','中','低','无法判断']
stats = {'n_total': len(videos)}
stats['tiers'] = {}
for t in tiers:
    ps = [v['peak_play'] for v in videos if v['tier']==t]
    stats['tiers'][t] = dict(n=len(ps), share=round(len(ps)/len(videos),4),
                             median_play=med(ps),
                             p25_play=pct(ps,0.25), p75_play=pct(ps,0.75),
                             max_play=max(ps) if ps else None)
# high tier motif top5 (multi-label share of high-tier videos)
hi = [v for v in videos if v['tier']=='高']
mc = collections.Counter()
for v in hi:
    for m in v['motifs']:
        mc[m]+=1
stats['high_tier_motifs'] = [dict(motif=m, videos=c, share_of_high=round(c/len(hi),4)) for m,c in mc.most_common()]
# high tier rule counts
stats['high_tier_rules'] = collections.Counter(v['rule'] for v in hi).most_common()
hi_nh = [v for v in hi if not v['seasonal_halloween']]
mcnh = collections.Counter()
for v in hi_nh:
    for m in v['motifs']: mcnh[m]+=1
stats['high_tier_motifs_non_halloween'] = [dict(motif=m, videos=c, share_of_high_nh=round(c/len(hi_nh),4)) for m,c in mcnh.most_common()]
stats['high_tier_non_halloween'] = dict(n=len(hi_nh), median_play=med([v['peak_play'] for v in hi_nh]))
top25=[v for v in videos if v['peak_play']>=10_000_000]
stats['top25_10m'] = dict(n=len(top25), tiers={t: sum(1 for v in top25 if v['tier']==t) for t in tiers})
stats['high_tier_ip_risk'] = dict(n=sum(1 for v in hi if v['ip_risk']), share=round(sum(1 for v in hi if v['ip_risk'])/len(hi),4))
stats['high_tier_brand_terms'] = dict(n=sum(1 for v in hi if v['brand_terms']), share=round(sum(1 for v in hi if v['brand_terms'])/len(hi),4))
# seasonal split
for label, sel in [('halloween', lambda v: v['seasonal_halloween']), ('non_halloween', lambda v: not v['seasonal_halloween'])]:
    sub=[v for v in videos if sel(v)]
    stats[label] = dict(n=len(sub), median_play=med([v['peak_play'] for v in sub]),
                        tiers={t: sum(1 for v in sub if v['tier']==t) for t in tiers},
                        tier_medians={t: med([v['peak_play'] for v in sub if v['tier']==t]) for t in tiers})
# unknown list
stats['unknown_ids'] = [v['video_id'] for v in videos if v['tier']=='无法判断']
# examples
stats['examples'] = {
 'high_top_play': [dict(video_id=v['video_id'],peak=v['peak_play'],reason=v['reason']) for v in sorted(hi,key=lambda z:-z['peak_play'])[:8]],
 'low_top_play': [dict(video_id=v['video_id'],peak=v['peak_play'],reason=v['reason']) for v in sorted([v for v in videos if v['tier']=='低'],key=lambda z:-z['peak_play'])[:8]],
}

out = dict(
  meta=dict(
    source=SRC_LABEL,
    n=len(videos),
    rubric={
      'unit':'一条视频',
      'perspective':'普通内容团队/个人创作者：手机或常规器材、常规剪辑、可购买道具与产品、可找普通家庭/宝宝出镜；不具备罕见素材、名人本人、影视版权、工作室级动画能力',
      'high':'素材普通可得 + 方法显式或格式公开 + 制作在手机/公开模板范围内 + 无版权硬门槛',
      'medium':'核心卖点依赖一项非随手可得但可获得的条件：真实宝宝/家庭的自然反应、表演、妆造、IP 服装、AI/特效、个人里程碑事件',
      'low':'核心卖点来自不可复制素材：罕见生命事件/病例、名人本人、影视/真人秀/新闻正片、工作室动画、真实案件',
      'unknown':'caption 与标签不足以识别核心卖点或制作方式',
      'causality':'播放量只用于描述样本构成，不用于判定可复刻性，也不写因果',
      'seasonality':'万圣节标签单列，不并入可复刻性判定；统计同时给出万圣节/非万圣节拆分'
    },
    generated_at='2026-10-31'
  ),
  videos=videos,
  stats=stats
)
json.dump(out, open(OUT,'w'), ensure_ascii=False, indent=1)
print('wrote', OUT)
print('tier counts', {t:stats['tiers'][t]['n'] for t in tiers})
print('tier medians', {t:stats['tiers'][t]['median_play'] for t in tiers})
print('high motifs top5', stats['high_tier_motifs'][:5])
print('high rules', stats['high_tier_rules'])
print('halloween', stats['halloween']['n'], stats['halloween']['tiers'])
print('non_halloween', stats['non_halloween']['n'], stats['non_halloween']['tiers'])
print('unknown', stats['unknown_ids'])
