import csv, json, re, collections, math, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "comments_all.tsv"
rows = []
for r in csv.reader(open(PATH, encoding="utf-8", errors="replace"), delimiter="\t", quoting=csv.QUOTE_NONE):
    if len(r) != 11: continue
    rows.append({"comment_id":r[0],"video_id":r[1],"digg":int(r[2] or 0),"reply":int(r[3] or 0),
                 "author":r[4],"hashtag":r[5],"plays":int(r[6] or 0),"vdigg":int(r[7] or 0),
                 "vcomments":int(r[8] or 0),"text":r[9],"descr":r[10]})

def L(r): return r["text"].lower()

buy = r"(where (can|could|do|did|would|should) (i|we|you|u) (get|buy|find|order|purchase|grab)|where (did|do) (you|u|she|he|they) (get|buy|find|order|purchase|grab)|where (is|are) (this|that|it|these|those|that one|the [a-z]+|your [a-z]+)[^.!?]{0,45}(from|bought|sold|available|sold out)|where to (buy|get|find|order)|\bw2c\b|dónde (lo|la|los|las) (compraste|consigo|compro|venden|puedo comprar|sacaste)|de dónde (es|sacaste|lo sacaste)|donde (lo|la) compro|onde (compro|comprar|acha|encontro)|beli dimana|dimana beli|où (l'|la |le )?(acheter|trouver)|где (купить|заказать|найти)|وين أشتري|mua ở đâu|ở đâu bán|dove comprare|wo (kann man|kaufen)|어디서 사|どこで買|ซื้อที่ไหน)"
link = r"(\b(link please|link pls|send (me )?(the )?link|drop (the )?link|link for|link to|whats the link|what's the link|share the link|anyone got the link|need the link|need links?)\b|\b(link|links|enlace)\b\s*(\?|$|pls|please))"
price = r"(how much (is|does|do|for|are) (it|this|that|the|they|you|one|each)?|how much\?|\bprecio\b|\bpreço\b|cuánto (cuesta|sale)|berapa harganya|combien (ça|ca) coûte|сколько стоит|(?<!\S)بكم(?!\S)|ราคา|얼마|bao nhiêu|多少钱)"
brand = r"(what brand|which brand|what('s| is) the brand|brand name|que marca|qué marca|qual a marca|qual marca|nama produk|produk apa|quelle marque|какой бренд)"
prodname = r"(what('s| is) (this|that|it)( called)?|what is the name|name of (this|that|the)|the name of|como se llama|cómo se llama|qué es esto|que es esto|nama(nya)? apa|apa itu|как называется|이거 뭐|何これ|what am i ordering|what is it called)"
song = r"(what('s| is)? (the )?(song|audio|sound|music)|song name|audio name|sound name|music name|qué canción|que cancion|cómo se llama la canción|como se llama la cancion|nome da música|qual (é a )?música|lagu apa|quelle chanson|какая песня|اسم الأغنية|bài hát)"
age = r"(how old (is|are) (your|you|he|she|the|it|this)|how many (months|weeks)|what month|which month|how old\?)"
normal = r"((is|was) (this|it|that|she|he) (safe|normal|ok|okay|alright)\b|is it normal (for|to|that)|should i (be )?(worried|worry)|es (esto|eso) normal|es normal (que|esto)|es seguro\b|é normal\?|é seguro\b|ini normal|apakah aman|aman (gak|nggak|ngga|tidak)\b)"
howto = r"(tutorial|how to (make|do|get|clean|store|prepare|train|cook|bake|order|buy)|how (do|did) (you|u) (make|do|get|clean|store|prepare|train|cook|bake)|can you (show|tell) (me|us) how|cómo (lo )?haces|cómo se hace|como (lo )?faz|como fazer|gimana cara|caranya|receta|recipe|paso a paso|step by step)"
aichk = r"(is (this|it|that|she|he) (ai|fake|real)|ai or real|real or ai|is this ai|fake or real|es ia\b|é ia\b|soy yo o es ia|can (sm1|someone) tell me how is it ai|how is it ai|is this real)"
valid = r"(does anyone else|is it just me|am i the only one|anyone else|who else|is this a thing|did anyone else|tell me i'm not the only)"
ship = r"(ship to|shipping to|not available in|isn't available in|is not available in|available in (the )?(us|usa|canada|italy|mexico|india|my|your)|restock|back in stock|in stock|envían a|hacen envíos|hay envío|se vende en)"
size = r"(what size|which size|size\?|talla|tamanho|tamano|ukuran|quel taille|какой размер|사이즈|サイズ)"
style = r"(outfit|dress|shirt|pants|shoes|hair|makeup|lip|lashes|nails|costume|wear|wearing|clothes|baju|ropa|vestido|cabelo|maquiagem)"

def find(pat):
    rx = re.compile(pat, re.I)
    return [r for r in rows if rx.search(r["text"])]

C = collections.OrderedDict()
C["where_to_buy"] = find(buy)
C["howto"] = find(howto)
C["community_validation"] = find(valid)
C["product_or_object_name"] = find(prodname)
C["price"] = find(price)
C["link_request"] = find(link)
C["ai_authenticity"] = find(aichk)
C["age_months"] = find(age)
C["ship_restock"] = find(ship)
C["normal_or_safe"] = find(normal)
C["song_name"] = find(song)
C["size"] = find(size)

# curated true counts established by manual review
manual = {
 "where_to_buy": (35, 35, 223),
 "howto": (22, 14, 65),
 "community_validation": (20, 20, 65),
 "product_or_object_name": (74, 42, 42),
 "price": (40, 38, 38),
 "link_request": (10, 10, 38),
 "ai_authenticity": (14, 9, 32),
 "age_months": (12, 9, 30),
 "ship_restock": (26, 15, 15),
 "normal_or_safe": (21, 14, 14),
 "song_name": (14, 14, 14),
 "size": (27, 13, 13),
}

def top_examples(rs, n=3):
    out=[]
    for r in sorted(rs, key=lambda x:-x["digg"])[:n]:
        out.append({"digg":r["digg"],"text":r["text"],"video_caption":r["descr"][:120],"hashtag":r["hashtag"]})
    return out

clusters=[]
for name, rs in C.items():
    sn, st, est = manual[name]
    clusters.append({
        "cluster": name,
        "keyword_match_n": len(rs),
        "distinct_videos": len({r["video_id"] for r in rs}),
        "manual_sample_n": sn,
        "manual_sample_true": st,
        "manual_precision": round(st/sn,2) if sn else None,
        "estimated_true_n": est,
        "examples": top_examples(rs),
    })
clusters.sort(key=lambda x:-x["estimated_true_n"])

# commercial union (explicit purchase intent only; product-name asks counted separately)
comm_rx = re.compile("|".join([buy,link,price,brand]), re.I)
comm = [r for r in rows if comm_rx.search(r["text"])]
comm_ids = {r["comment_id"] for r in comm}

# ask rate by content type
def cat(r):
    s=(r["hashtag"]+" "+r["descr"]).lower()
    if re.search(r"(review|comparison|\bvs\b|honest)",s): return "review_compare"
    if re.search(r"(diy|tutorial|how ?to|recipe|craft)",s): return "diy_tutorial"
    if re.search(r"(registry|must ?have|haul|finds|shopping|clearance|walmart|target|amazon|dollartree|gift|boobasket)",s): return "shopping_list"
    if re.search(r"(halloween|costume)",s): return "costume"
    if re.search(r"(mom|baby|newborn|pregnan|toddler|parent|dad|mother|breast|diaper|nursery|birth)",s): return "parenting"
    return "other"
tot=collections.Counter(); cq=collections.Counter()
for r in rows:
    k=cat(r); tot[k]+=1
    if r["comment_id"] in comm_ids: cq[k]+=1
ask_rates=[{"content_type":k,"comments":tot[k],"commercial_asks":cq[k],
            "asks_per_1000_comments":round(1000*cq[k]/tot[k],2)} for k in ["shopping_list","diy_tutorial","review_compare","costume","parenting","other"]]

# top videos by asks
vc=collections.Counter(r["video_id"] for r in comm)
vinfo={r["video_id"]:r for r in rows}
top_ask_videos=[]
for vid,c in vc.most_common(15):
    r=vinfo[vid]
    top_ask_videos.append({"video_id":vid,"asks":c,"plays":r["plays"],"hashtag":r["hashtag"],
                           "caption":r["descr"][:140],"asks_per_100k_plays":round(c/max(r["plays"],1)*100000,2)})

# top videos by comment count
vcount=collections.Counter(r["video_id"] for r in rows)
top_videos=[]
for vid,n in vcount.most_common(20):
    r=vinfo[vid]
    top_videos.append({"video_id":vid,"comments":n,"plays":r["plays"],"hashtag":r["hashtag"],
                       "caption":r["descr"][:140],"total_likes_on_comments":sum(x["digg"] for x in rows if x["video_id"]==vid)})

# top 50 comments by likes
top_comments=[]
for r in sorted(rows, key=lambda x:(-x["digg"], x["comment_id"]))[:50]:
    top_comments.append({"digg":r["digg"],"reply_count":r["reply"],"text":r["text"],
                         "video_id":r["video_id"],"video_caption":r["descr"][:120],"hashtag":r["hashtag"]})

# length histogram
buckets=[("0-9",0,9),("10-24",10,24),("25-49",25,49),("50-99",50,99),("100-199",100,199),("200-499",200,499),("500+",500,10**9)]
lens=[len(r["text"]) for r in rows if r["text"].strip()]
hist=[{"bucket":b,"n":sum(1 for x in lens if lo<=x<=hi),"pct":round(100*sum(1 for x in lens if lo<=x<=hi)/len(lens),2)} for b,lo,hi in buckets]

# monthly
mon=collections.Counter(r["video_id"] and None for r in [])  # placeholder
monthly=collections.OrderedDict()
for r in rows:
    pass
# compute from DB-exported dates not present; use query results already obtained (hardcode from SQL)
monthly_2026={"2026-07":1951,"2026-08":6931,"2026-09":18383,"2026-10":14454}
monthly_all=47073
recent=sum(monthly_2026.values())

# intent samples
labels=json.load(open(ROOT / "tools" / "labels.json"))
def load_sample(path):
    out={}
    for line in open(path,encoding="utf-8"):
        p=line.rstrip("\n").split("\t")
        if len(p)<3: continue
        out[int(p[0])]={"digg":int(p[1]),"text":p[2]}
    return out
top_s=load_sample(ROOT / "top500.tsv"); rnd_s=load_sample(ROOT / "rand500.tsv")
def wilson(k,n,z=1.96):
    p=k/n; d=1+z*z/n; c=(p+z*z/(2*n))/d; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [round(100*(c-h),1), round(100*(c+h),1)]
def sample_stats(name, data):
    cats=collections.Counter()
    for k,v in labels[name].items():
        if k in "QBCEO": cats[k]=len(v)
    cats["R"]=500-sum(cats.values())
    out={"n":500,"counts":{k:cats[k] for k in ["Q","B","C","E","R","O"]},
         "shares_pct":{k:round(100*cats[k]/500,1) for k in ["Q","B","C","E","R","O"]},
         "ci95_pct":{k:wilson(cats[k],500) for k in ["Q","B","C","E","R","O"]},
         "examples":{}}
    for k in ["Q","B","C","E","R"]:
        ex=[]
        if k == "R":
            used={i for kk in ["Q","B","C","E","O"] for i in labels[name][kk]}
            idx=[i for i in range(1,501) if i not in used][:5]
        else:
            idx=labels[name][k][:5]
        for i in idx:
            ex.append(data[i]["text"])
        out["examples"][k]=ex
    return out

intent={
 "method":"人工逐条标注 2 个 500 条样本；每类定义见 categories。反讽/玩笑式问句归 R，只有真实求证信息归 Q。",
 "categories":{
   "Q":"提问（真实求证信息）","B":"求同款/求链接","C":"批评/质疑/纠正",
   "E":"分享自身经历或经验建议","R":"情绪反应（玩笑、共鸣、引用、纯夸赞）","O":"其他（@、刷屏、无法判断）"},
 "sample_likes_weighted_top500": sample_stats("top500", top_s),
 "sample_uniform_random500": sample_stats("rand500", rnd_s),
 "contrast":"按获赞排序的 500 条里 Q 占 3.2%、B 占 0.4%；均匀随机 500 条里 Q 占 8.4%、B 占 4.6%。高赞评论以情绪反应为主，不能用来估计需求占比。"
}

# repeated variants
variants=[
 {"pattern":"where can/could I get/buy/find","n":139,"videos":87},
 {"pattern":"where did/do you get/buy/find","n":83,"videos":55},
 {"pattern":"where is/are X from","n":62,"videos":37},
 {"pattern":"dónde lo/la consigo/compro","n":31,"videos":19},
 {"pattern":"link please / send the link / need the link","n":38,"videos":23},
 {"pattern":"how much / precio / cuánto cuesta","n":46,"videos":30},
 {"pattern":"how old / how many months / weeks","n":40,"videos":29},
 {"pattern":"song name / what song","n":14,"videos":11},
]

# seasonality numbers from SQL
season={
 "comments_on_halloween_tagged_videos":4110,
 "share_pct":8.7,
 "comments_mentioning_halloween":230,
 "mention_share_pct":0.5,
 "deepread288_halloween_videos":60,
 "deepread288_total":288,
 "deepread288_halloween_share_pct":20.8,
 "comments_on_deepread_halloween_videos":1379,
 "deepread_videos_with_any_comments":272,
 "deepread_comment_total":7759,
 "note":"288 条爆款样本里万圣节占 20.8%（60/288），但这 288 条对应的评论只占全部评论的 16.5%（7,759/47,073），其万圣节视频评论 1,379 条。全量评论里只有 8.7% 落在万圣节标签视频下。两个口径都受 10 月采集窗口影响，任何'爆款主题'排序都必须剔除或单列万圣节。"
}

opportunities=[
 {"rank":1,"topic":"每条视频固定『同款清单』（片尾 5 秒 + 置顶评论 + 主页链接）",
  "evidence":"223 条求购买出处，覆盖 124 个视频；nursery tour 视频 2.74 万播放产生 12 条求购，婴儿房/清单类视频求购密度最高（43.8 次/10 万播放）。",
  "format":"30 秒『Everything in this video』快剪 + 图文清单 + 关键词自动回复"},
 {"rank":2,"topic":"教程视频的『续集答疑』：把评论区 Top 5 问题拍成第二条",
  "evidence":"DIY 万圣节教程视频 310 万播放，27 条提问集中在热熔胶是否伤银盘、污渍是否可擦、苔藓是否防火、成品如何收纳；教程/做法类关键词命中 102 条、估计 65 条真实请求。",
  "format":"『你们问最多的 5 个问题』口播 + 演示；每条教程预留 aftercare/安全/收纳 三个机位"},
 {"rank":3,"topic":"『只有我这样吗』共鸣合集",
  "evidence":"65 条社区共鸣式提问（does anyone else / am I the only one / is it just me），覆盖 61 个视频；例如『is it just me or is waking up at 5:30am for school insane?』获 6.07 万赞。",
  "format":"把评论原话做成标题与口播，一条视频回答 5-8 条共鸣提问"},
 {"rank":4,"topic":"『这是什么/什么牌子』物品标注",
  "evidence":"产品/物品名称类关键词命中 74 条，人工抽查约 57% 为真实识别请求（估计 42 条）；典型：口红/腮红色号、喷雾、衣柜系统、发夹、玩具型号。",
  "format":"画面内贴纸标注品牌/型号/色号；或做『视频里出现的 10 样东西』图文"},
 {"rank":5,"topic":"价格透明化",
  "evidence":"38 条真实问价（关键词命中 40 条，人工剔除 2 条俚语/反问），覆盖 26 个视频；西班牙语区多为单词『precio』。",
  "format":"视频内标价格区间/是否含运费；置顶评论放价格表"},
 {"rank":6,"topic":"链接承接与关键词漏斗",
  "evidence":"38 条明确要链接，23 个视频；有视频用『Comment BOO and I'll send you all the details』把 10 条求购集中到一条评论漏斗。",
  "format":"置顶评论 + 关键词自动回复 + 主页 storefront；每条视频只留一个 CTA"},
 {"rank":7,"topic":"『这是 AI 还是实拍』透明化",
  "evidence":"50 条评论在 36 个视频下讨论/追问是否 AI（估计 32 条为真实求证）；「ts song older than her」「Ya no se que es IA y que no」等高赞评论说明信任缺口。",
  "format":"幕后拍摄花絮、原始素材时间戳、AI 使用声明；『真实 vs AI』对比演示"},
 {"rank":8,"topic":"月龄/周龄字幕与『按月龄』系列",
  "evidence":"40 条问年龄/月龄（估计 30 条真实），29 个视频；高赞例『how old is your son.. asking for a friend..』29.2 万赞。",
  "format":"视频开头 1 秒标『X 个月 / Y 周』；按月龄做发育里程碑合集"},
 {"rank":9,"topic":"地区可购性与补货提醒",
  "evidence":"15 条关于 ship to / not available in / restock（关键词命中 26 条，人工抽查精度约 58%），覆盖 19 个视频；涉及加拿大、美国、牙买加、秘鲁、委内瑞拉、卡塔尔。",
  "format":"『哪些国家能买/怎么转运』说明；补货日历与提醒视频"},
 {"rank":10,"topic":"『这正常吗/安全吗』护士或儿科视角答疑",
  "evidence":"21 条关键词命中、估计 14 条真实（如 is it safe to put in the oven、should I worry about tummy time、is it normal for nausea to go away at 9 weeks）；安全类评论总量约 93 条。",
  "format":"护士/儿科视角短视频，固定加『非医疗建议』免责声明"},
 {"rank":11,"topic":"穿搭同款拆解",
  "evidence":"32 条求 outfit/衣服/发饰出处（24 个视频），如『where do you get your pants from???』4408 赞、『where do you buy your clothes!?!?!?』1206 赞。",
  "format":"OOTD 逐件标注 + 『本周穿搭』合集"},
 {"rank":12,"topic":"BGM 标注与歌单",
  "evidence":"14 条问歌名/音频（11 个视频）；『cómo se llama la canción』1138 赞。",
  "format":"视频角标标 BGM 名称；每周 BGM 合集"}
]

caveats=[
 "只读查询 raw.si_tiktok_comment，未修改任何数据。分析在本地对 47,069 行可解析记录进行（4 行因制表符/编码解析失败跳过，占 0.01%）。",
 "评论表每个视频最多 120 条（sample_rank 0-119）：79 个视频触及上限（11,421 条，占 24.3%），1,416 个视频低于上限（35,652 条）。大视频的评论被截断，且截断评论文本偏向高赞；因此意图占比对大视频有偏，商业诉求计数是下限。",
 "样本 ≠ TikTok 全量：392 个 tag × 43 天采样，品类偏母婴/喂养，最后写入 2026-10-28。",
 "语言：拉丁字母 95.3%，其中英语约 96%（粗估）；西语约 2.2%、印尼语 0.7%、法语 0.4%、德语 0.5%；另有西里尔 2.6%、阿拉伯 1.5%。关键词计数以英语为主，非英语诉求会被低估。",
 "万圣节季节性：全量评论 8.7% 落在万圣节标签视频下；288 条爆款样本里万圣节占 20.8%。10 月窗口内的主题排序必须单列万圣节，不能当作全年结论。",
 "所有数字是频率描述，不是因果：『清单类视频求购率高』只说明在这批评论里同时出现，不能推出『做清单就一定爆』。",
 "样本 <8 的结论不出：本报告所有聚类均给出样本量与视频数；未对 n<8 的子类下结论。",
 "评论意图为人工标注（2×500 条），存在标注者偏差；Q/B 占比的 95% 置信区间已在 JSON 中给出。两个 500 条样本都只含非空文本评论；全量中另有 679 条空文本（1.4%）未纳入，因此 O 类的真实占比略高于样本值。",
 "creators 的置顶评论/自动回复混在评论中（如『Comment BOO and I'll send details』），已尽量归入 O 或 E，但可能污染少量统计。"
]

out={
 "meta":{
   "source":"raw.si_tiktok_comment (PostgreSQL abi_migtest/abitest, read-only)",
   "generated_at":"2026-10-31",
   "corpus":{"comments":47073,"videos":1495,"videos_joined_to_video_table":1489,
             "top_level_comments":44419,"replies":2654,"reply_share_pct":5.6,
             "date_range":["2019-10-29","2026-10-28"],
             "comments_2026_07_to_10":recent,"share_2026_07_to_10_pct":round(100*recent/monthly_all,1)},
   "sampling":{"max_comments_per_video":120,"videos_at_cap":79,"videos_below_cap":1416,
               "comments_from_capped_videos":11421,"share_from_capped_pct":24.3},
   "likes":{"median":15,"p90":6819.6,"p99":161779.8,"p999":694551.5,"mean":7545.3,"max":2369866},
   "length":{"median":31,"mean":47.2},
   "language_estimate":{"latin_script_pct":95.3,"english_share_of_latin_pct":95.9,
                        "spanish_pct_of_latin":2.2,"indonesian_pct_of_latin":0.7,
                        "french_pct_of_latin":0.4,"german_pct_of_latin":0.5,
                        "cyrillic_pct":2.6,"arabic_pct":1.5}
 },
 "distribution":{
   "monthly_volume_2026_07_to_10":monthly_2026,
   "top_videos_by_comment_count":top_videos,
   "top_50_comments_by_likes":top_comments,
   "length_histogram":hist,
   "note":"评论量 88.6% 集中在 2026-07 至 2026-10；2019-2025 的评论是长尾历史内容。"
 },
 "intent":intent,
 "questions":{
   "candidate_volume":{"comments_with_question_mark":3676,"qmark_share_pct":7.8,
                       "question_candidates":5976,"candidate_share_pct":12.7,"distinct_videos":1293},
   "commercial_union":{"definition":"where_to_buy ∪ link_request ∪ price ∪ brand（明确购买意图）","comments":len(comm),"distinct_videos":len({r['video_id'] for r in comm}),"share_pct":round(100*len(comm)/len(rows),2)},
   "clusters":clusters,
   "top10":[
  {"rank":1,"intent":"在哪买 / 哪来的（求购买出处）","estimated_n":223,"videos":124,"verbatim":["where can I get one?","where did you get that?","Where is your set from!","dónde lo consigo","where do you buy your clothes!?!?!?"]},
  {"rank":2,"intent":"求教程 / 怎么做","estimated_n":65,"videos":82,"keyword_n":102,"verbatim":["How did you do that so smoothly without the baby crying??","Can you do a tutorial on how to clip coupons?","Yea so yall need to start telling us HOW to make this 😭","Cómo se hacen esas guirnaldas de bolas ?"]},
  {"rank":3,"intent":"只有我这样吗（共鸣求证）","estimated_n":65,"videos":61,"verbatim":["is it just me or is waking up at 5:30am for school insane?","Anyone else seeing tons of viral videos they’ve already seen 😳","Am I the only one who is crying","does anyone else do this for kids"]},
  {"rank":4,"intent":"这是什么 / 什么牌子","estimated_n":42,"videos":66,"keyword_n":74,"verbatim":["what is this","Okay but what is it called? What am I ordering ?","qué marca de gato es?","What is the brand of the clothing set? PLEASE"]},
  {"rank":5,"intent":"多少钱","estimated_n":38,"videos":26,"keyword_n":40,"verbatim":["How much for the clear snoopy cup","precio","cuánto cuesta ??","How much? Where?"]},
  {"rank":6,"intent":"求链接","estimated_n":38,"videos":23,"verbatim":["anyone got the link ?","Can I have the link to the peel and stick trim pls?","I need links to all the outfits. Drop offs included","CAN U LINK THE FEEDING PILLOW?!?"]},
  {"rank":7,"intent":"是不是 AI / 真的假的","estimated_n":32,"videos":36,"keyword_n":50,"verbatim":["Is this real or AI please","Is she AI? Is this AI?","Ya no se que es IA y que no 😳","can sm1 tell me how is it ai😭"]},
  {"rank":8,"intent":"宝宝多大 / 几个月几周","estimated_n":30,"videos":29,"keyword_n":40,"verbatim":["How old is your son.. asking for a friend..","how many weeks?","How many months left?","how old is she"]},
  {"rank":9,"intent":"能寄到我这吗 / 什么时候补货","estimated_n":15,"videos":19,"keyword_n":26,"verbatim":["why this is not available in Canada? 🥺🥺","when is their restock day","How do I ship to Jamaica","Is the 3d printer with all filaments coming back in stock?"]},
  {"rank":10,"intent":"这正常吗 / 安全吗","estimated_n":14,"videos":18,"keyword_n":21,"verbatim":["Is it normal for nausea to go away at 9 weeks?","Should I be worried if he doesn’t want to do tummy time?","Is it safe to put in the oven?","es normal que se vea un árbol en su ojo ?"]}
 ],
 "near_miss":[
  {"intent":"问歌名/音频","estimated_n":14,"videos":11},
  {"intent":"问尺码","estimated_n":13,"videos":22}
 ],
 "repeated_phrasings":variants,
   "ask_rate_by_content_type":ask_rates,
   "top_videos_by_commercial_asks":top_ask_videos,
   "note":"聚类计数为关键词命中；manual_precision 来自人工抽查，estimated_true_n = 关键词命中 × 人工精度（取整）。「求购买出处」是最大单一诉求。"
 },
 "seasonality":season,
 "opportunities":opportunities,
 "caveats":caveats
}

with open(ROOT / "comments.json","w",encoding="utf-8") as f:
    json.dump(out,f,ensure_ascii=False,indent=1)
print("written", ROOT / "comments.json")
print("commercial union",len(comm),len({r['video_id'] for r in comm}))
for c in clusters:
    print(c["cluster"], c["keyword_match_n"], c["distinct_videos"], c["estimated_true_n"])