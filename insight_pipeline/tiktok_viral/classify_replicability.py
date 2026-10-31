# -*- coding: utf-8 -*-
import csv, json, re, statistics, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'deepread288.tsv'
THEME = ROOT / 'theme-clusters.json'
OUT = ROOT / 'data' / '_classified_first.json'

rows = []
with open(SRC, encoding='utf-8') as f:
    for r in csv.reader(f, delimiter='\t'):
        rows.append(dict(video_id=r[0], hashtag=r[1], peak=int(r[2]), digg=int(r[3]),
                         comment=int(r[4]), share=int(r[5]), themes=json.loads(r[6]),
                         mechs=json.loads(r[7]), descr=r[8]))

tc = json.load(open(THEME))
mp = tc['mapping']

def hits(text, kws):
    return sorted({k for k in kws if k.lower() in text.lower()})

# ---------- signal vocabularies ----------
SCARCE_EVENT = [
    '超早产儿','早产儿','24周','25周','26周','生命奇迹','医疗纪实','病童','儿童抗癌','抗癌',
    '罕见病','罕见','多胞胎','四胞胎','quadruplet','生死离别','悼念','离世','去世','意外离世',
    'grief','siblingloss','产后 psychosis','产后心理','精神警示','真实案件','大案','司法','法院',
    '罪案','911','真实影像','新闻','网红意外','明星','名人','网红','celebrity','访谈','演唱会',
    '现场狂欢','说唱圈层','法庭纪实','明星热点','名人档案',
]
SCARCE_TRAIT = ['混血宝宝','发量王者','萌娃才艺','儿童选美','toddlersandtiaras','pageant','真人秀','TLC']
FOOTAGE = ['影视切片','影视剪辑','电影','正片','full movie','tvshow','动画正片','纪录片','影视混剪','经典IP混剪','影视IP','剧集','美剧','韩剧','动漫','动画角色','鬼妈妈','coraline','FNAF','fivenightsatfreddys','avatar','monsterhigh','mavis','小马宝莉','mlp','三丽鸥','hellokitty','hello kitty','迪士尼','漫威','宝可梦','哈利波特']
STUDIO_ANIM = ['3D动画','3D卡通萌娃','3D早教动画','3D医学动画','3D奇观','定格动画','动画','cartoon','动漫','AI动画','AI短剧','AI拟真','AI视觉奇观']
AI_TEMPLATE = ['capcut','capcutpioneer','pioneertemplate','模板','template','make the same video','同款','特效Meme']
METHOD = ['教程','tutorial','how to','diy','hack','妙招','技巧','步骤','清单','攻略','配方','食谱',
          '跟练','教学','learn','模板','template','同款','复刻','手作','craft','改造','收纳','测评',
          'review','开箱','unbox','种草','must have','essentials','好物','推荐','对比','横评','实测',
          '演示','示范','trick','easy to','申请','做法','教程','链接','link in bio','shop my','shop the']
PRODUCT = ['好物','种草','推荐','测评','开箱','必备','essential','must have','链接','link','同款',
           '购买','shop','礼盒','神器','用品','品牌','momcozy','dyson','walmart','target','amazon',
           'fisherprice','maxicosi','jellycat','babylist','thyseed','drbrown','商品','带货','选品']
FORMAT = ['pov','对口型','卡点','舞蹈','dance','trend','挑战','challenge','整蛊','prank','短剧',
          '剧情','反转','模仿','合拍','duet','变装','cosplay','仿妆','grwm','vlog','日常','反应',
          'reaction','合辑','混剪','跟拍','手势舞','街拍','walk','变脸','换装','穿搭','灵感',
          '清单','拼贴','ootd']
AUTHENTIC = ['真实','纪实','抓拍','原声','亲历','我的','我家','妈妈','爸爸','宝宝','孩子','产后',
             '孕期','怀孕','分娩','新生儿','带娃','家庭','夫妻','父女','母子','手足','亲情','萌娃',
             '人类幼崽','育儿','宝妈','新手妈妈','新手爸妈','宝妈日常','生活切片','成长记录']
IP = ['cosplay','ip','角色扮演','仿妆','影视','动漫','电影','动画角色','三丽鸥','hello kitty',
      '小马宝莉','鬼妈妈','coraline','fnaf','avatar','monster high','mavis','迪士尼','漫威','任天堂',
      '宝可梦','星黛露','玲娜贝儿','哈利波特','变形金刚','ip角色','ip联名']
HALLOWEEN = ['万圣','halloween','spooky','boo','october1st','october','鬼','南瓜','trick or treat','31daysofhalloween','costume']

# generic captions with no format info
def text_of(r):
    return ' '.join([r['hashtag'], r['descr'], ' '.join(r['themes']), ' '.join(r['mechs'])])

def motif_set(r):
    return sorted({mp[t]['name'] for t in r['themes'] if t in mp})

def classify(r):
    t = text_of(r)
    th = ' '.join(r['themes']); me = ' '.join(r['mechs']); cap = r['descr']; ht = r['hashtag']
    has = lambda kws: hits(t, kws)
    scarce = has(SCARCE_EVENT)
    trait = has(SCARCE_TRAIT)
    footage = has(FOOTAGE)
    studio = has(STUDIO_ANIM)
    ai_tpl = has(AI_TEMPLATE)
    method = has(METHOD)
    product = has(PRODUCT)
    fmt = has(FORMAT)
    auth = has(AUTHENTIC)
    ip = has(IP)
    seasonal = has(HALLOWEEN)
    motive = motif_set(r)

    tier = None; rule = None; reason = None; basis = []
    def set_(t_, ru, re_, b):
        nonlocal tier, rule, reason, basis
        tier, rule, reason, basis = t_, ru, re_, b

    # 1 footage / celebrity / rare event
    if footage and any(k in t for k in ['电影','正片','full movie','影视切片','影视剪辑','真人秀','演唱会','访谈','新闻','案件','911','tlc','动画正片']):
        set_('低','scarce_footage','核心是影视/真人秀/新闻正片素材，普通团队既无版权也无法重拍',
             [f'hashtag:{ht}', f'caption:{cap[:60]}', f'footage:{",".join(footage[:4])}'])
    elif any(k in t for k in ['超早产儿','24周','25周','26周','生命奇迹','病童','儿童抗癌','抗癌','生死离别','悼念','离世','去世','意外离世','grief','siblingloss','真实案件','大案','司法','法院','罪案','911','网红意外']) :
        set_('低','scarce_life_event','核心是罕见生命事件/真实案件/逝者故事，素材本身不可复制',
             [f'hashtag:{ht}', f'caption:{cap[:60]}', f'scarce:{",".join([k for k in scarce if any(x in t for x in [k])][:4])}'])
    elif any(k in t for k in ['多胞胎','四胞胎','quadruplet','儿童选美','toddlersandtiaras','pageant','真人秀','tlc']) :
        set_('低','scarce_subject','核心依赖多胞胎/选美儿童/真人秀人物等稀缺主体',
             [f'hashtag:{ht}', f'caption:{cap[:60]}', f'trait:{",".join(trait[:4]) or ",".join([k for k in scarce if k in t][:4])}'])
    # 2 studio animation not template
    elif any(k in t for k in ['3D动画','3D卡通萌娃','3D早教动画','3D医学动画','定格动画','cartoon','动漫']) and not ai_tpl:
        set_('低','studio_animation','核心是工作室级动画/3D制作，个人团队无法按同质量重做',
             [f'hashtag:{ht}', f'theme:{th}', f'prod:{",".join(studio[:4])}'])
    # 3 explicit method / template
    elif ai_tpl and any(k in t for k in ['capcut','模板','template','make the same video','pioneertemplate']):
        set_('高','template','有平台模板/CapCut 同款入口，照着套模板即可复刻',
             [f'hashtag:{ht}', f'caption:{cap[:70]}', f'template:{",".join(ai_tpl[:4])}'])
    elif method and not scarce:
        # tutorials / DIY / hacks / product lists
        if any(k in t for k in ['测评','review','开箱','unbox','好物','种草','must have','essentials','推荐','清单','横评','实测','神���','用品']) and product:
            set_('高','product_or_method','产品/清单型内容，产品可购买、拍摄流程可复制',
                 [f'hashtag:{ht}', f'theme:{th}', f'mech:{me}', f'method:{",".join(method[:4])}'])
        else:
            set_('高','explicit_method','caption 给出可执行方法/步骤/材料，拍摄门槛低',
                 [f'hashtag:{ht}', f'theme:{th}', f'method:{",".join(method[:4])}'])
    # 4 product demo without explicit method words
    elif product and any(k in t for k in ['momcozy','dyson','walmart','target','amazon','fisherprice','maxicosi','jellycat','thyseed','drbrown','shop','link','礼盒','神器','用品','好物']):
        set_('高','product_demo','核心是可购买产品的展示/种草，产品到手即可拍',
             [f'hashtag:{ht}', f'theme:{th}', f'product:{",".join(product[:4])}'])
    # 5 family comedy / scripted formats
    elif any(k in t for k in ['家庭搞笑','育儿幽默','搞笑','整蛊','prank','短剧','剧情','反转','pov','对口型','合拍','duet','模仿']) and not scarce:
        # scripted comedy is medium: needs cast/acting, but no scarce asset
        set_('中','scripted_format','可脚本化重拍，但依赖演员/宝宝配合与表演，形似容易神似难',
             [f'hashtag:{ht}', f'theme:{th}', f'mech:{me}'])
    # 6 dance / trend / costume
    elif any(k in t for k in ['舞蹈','dance','手势舞','卡点','跟拍','trend','挑战','challenge','变装','cosplay','仿妆','穿搭','灵感']) and not scarce:
        if any(k in t for k in ['cosplay','仿妆','角色扮演','ip','鬼妈妈','coraline','fnaf','mavis','monster high']):
            set_('中','ip_costume','妆造/服装可学，但绑定 IP 角色，需服装化妆能力且有版权边界',
                 [f'hashtag:{ht}', f'theme:{th}', f'ip:{",".join(ip[:4])}'])
        else:
            set_('高','copyable_format','卡点/舞蹈/穿搭格式公开，普通团队可练习后重拍',
                 [f'hashtag:{ht}', f'theme:{th}', f'mech:{me}'])
    # 7 authentic family moment / vlog
    elif auth:
        set_('中','authentic_moment','依赖真实家庭/宝宝的自然反应，场景可搭但瞬间不可复现',
             [f'hashtag:{ht}', f'theme:{th}', f'mech:{me}'])
    else:
        set_('无法判断','insufficient_signal','caption/tag 未给出可识别的制作方式或素材类型',
             [f'hashtag:{ht}', f'theme:{th}', f'caption:{cap[:60]}'])

    return dict(video_id=r['video_id'], tier=tier, rule=rule, reason=reason, basis=basis,
                hashtag=ht, peak=r['peak'], motifs=motive, themes=r['themes'], mechs=r['mechs'],
                seasonal=bool(seasonal), caption=cap,
                digg_rate=round(r['digg']/r['peak'],5), comment_rate=round(r['comment']/r['peak'],6),
                share_rate=round(r['share']/r['peak'],5))

out = [classify(r) for r in rows]
cnt = collections.Counter(x['tier'] for x in out)
print(cnt)
for tier in ['高','中','低','无法判断']:
    ps = sorted(x['peak'] for x in out if x['tier']==tier)
    print(tier, len(ps), 'median', statistics.median(ps) if ps else None,
          'p25', ps[len(ps)//4] if ps else None, 'p75', ps[3*len(ps)//4] if ps else None)
json.dump(out, open(OUT,'w'), ensure_ascii=False, indent=1)
# print table
for i,x in enumerate(sorted(out,key=lambda z:-z['peak']),1):
    print(f"{i:03d} {x['tier']:4s} {x['rule']:20s} {x['video_id']} {x['peak']/1e4:8.0f}万 {x['hashtag']} | {x['caption'][:50]}")
