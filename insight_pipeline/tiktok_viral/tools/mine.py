import csv, json, re, sys, collections

path = sys.argv[1]
rows = []
with open(path, encoding="utf-8", errors="replace") as f:
    for r in csv.reader(f, delimiter="\t"):
        if len(r) != 11:
            continue
        rows.append({
            "comment_id": r[0], "video_id": r[1], "digg": int(r[2] or 0),
            "reply": int(r[3] or 0), "author": r[4], "hashtag": r[5],
            "play": int(r[6] or 0), "vdigg": int(r[7] or 0), "vcomments": int(r[8] or 0),
            "text": r[9], "descr": r[10],
        })

def L(s): return s.lower()

buy_words = r"(buy|get|find|from|purchase|order|shop|store|link|sell|stock|comprar|consigo|encuentro|venden|conseguir|precio|achar|encontro|beli|dapat|acheter|trouver|купить|شراء|mua|kaufen|comprare|购买|사|買|ซื้อ|해주세요)"
where_words = r"(where|donde|dónde|onde|aonde|di\s?mana|dimana|où|где|وين|بكم|ở đâu|wo|dove|어디|どこ|ที่ไหน|bawo|from what|which store)"

F = collections.OrderedDict()
F["buy_where"] = lambda t: re.search(where_words, t) and re.search(buy_words, t)
F["link_request"] = lambda t: re.search(r"\b(link|links|enlace|li?nk please|send (me )?(the )?link|link pls|linke)\b", t) and not re.search(r"\blinked\b", t)
F["song_audio"] = lambda t: re.search(r"(what('s| is)? (the )?(song|audio|sound|music)|song name|audio name|sound name|music name|qué canción|que cancion|nome da música|qual (é a )?música|lagu apa|quelle chanson|какая песня|اسم الأغنية|bài hát|노래|曲名|เพลง|what song is)", t)
F["app_effect"] = lambda t: re.search(r"(what app|which app|what filter|what effect|what editor|which editor|app name|what do you use|qué app|que app|qual app|aplikasi apa|quelle app|какое приложение|تطبيق)", t)
F["name_product"] = lambda t: re.search(r"(what('s| is) (this|that|it)|what is the name|name of (this|that|the)|what brand|which brand|what product|brand name|que marca|qué marca|cual es|cuál es|cómo se llama|como se llama|qual o nome|como se chama|nama(nya)? apa|apa itu|comment (ça|ca) s'appelle|как называется|что это|اسمه|ايش هذا|tên gì|cái gì|이거 뭐|何これ|ชื่ออะไร)", t)
F["price"] = lambda t: re.search(r"(how much|cuánto|cuanto|precio|price|cost|berapa|combien|сколько|بكم|quanto|bao nhiêu|ราคา|値段|얼마)", t)
F["howto"] = lambda t: re.search(r"(how (do|did|to|can|should) (you|i|we|u)|how to|tutorial|recipe|step by step|steps|cómo (lo )?(haces|hiciste|se hace)|como (lo )?(haces|hiciste|se hace)|receta|como faz|receita|gimana|caranya|comment (tu )?fais|как (ты )?(делаешь|сделать)|كيف|どうやって|어떻게|วิธี)", t)
F["safety_health"] = lambda t: re.search(r"(is (this|it) (safe|ok|okay)|safe for|is it bad|does (this|it) (work|really)|is this normal|should i (be )?(worried|worry)|is that normal|es seguro|es normal|se puede|faz mal|berbahaya|aman|est-ce (normal|dangereux)|это нормально|нормально ли)", t)
F["availability"] = lambda t: re.search(r"(in stock|restock|when.*(back|available)|do you ship|ship to|available in|sell.*(in|to)|envían|envios|hay en|tiene envío)", t)
F["location"] = lambda t: re.search(r"(where (are|is) (you|this|that)|where is this|where was this|donde es|dónde es|where do you live|what city|que ciudad)", t)
F["general_question"] = lambda t: re.search(r"\?", t) or re.search(r"^(what|why|how|when|where|who|which|do |does |did |is |are |can |could |should |would |will |anyone|anybody|has |have )", t) or re.search(r"^(que |qué |como |cómo |por que|por qué|donde |dónde |cuanto |cuánto |quien |quién |cual |cuál |quando |onde |qual |porque |por que|apa |kenapa |gimana |kapan |dimana |pourquoi |comment |quand |où |est-ce|почему|как|когда|где|что|почему|ليش|كيف|وين|متى|لماذا)", t)

order = list(F.keys())
prim_counts = collections.Counter()
union = set()
fam_rows = collections.defaultdict(list)
for i, r in enumerate(rows):
    t = L(r["text"]).strip()
    if not t:
        continue
    first = None
    for fam in order:
        try:
            if F[fam](t):
                if first is None:
                    first = fam
                if fam != "general_question":
                    union.add(i)
        except Exception as e:
            pass
    if first:
        prim_counts[first] += 1
        fam_rows[first].append(r)

print("TOTAL rows:", len(rows))
print("UNION real question families (excl general):", len(union))
print("PRIMARY family counts:")
for fam in order:
    print(f"  {fam}\t{prim_counts[fam]}\tvideos={len({r['video_id'] for r in fam_rows[fam]})}")

def show(fam, n=25):
    rs = sorted(fam_rows[fam], key=lambda r: -r["digg"])[:n]
    print(f"\n### {fam} top by digg")
    for r in rs:
        print(f"{r['digg']}\t{r['text'][:180]}\t|| vid={r['video_id']} cap={r['descr'][:70]} tag={r['hashtag']}")

for fam in order:
    show(fam, 20)

# exact duplicate normalization among union
def norm(s):
    s = s.lower()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"@\w+", " ", s)
    s = re.sub(r"[^a-z0-9áéíóúñüçãõâêôàèìòùäëïöüßА-Яа-яёЁ؀-ۿ一-鿿぀-ヿ가-힯 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

dups = collections.Counter()
dupmap = collections.defaultdict(list)
for i in union:
    k = norm(rows[i]["text"])
    if len(k) >= 8:
        dups[k] += 1
        dupmap[k].append(rows[i])
rep = [(k, c) for k, c in dups.items() if c >= 3]
rep.sort(key=lambda x: -x[1])
print(f"\n### exact-normalized repeated question texts >=3: {len(rep)}")
for k, c in rep[:40]:
    d = sum(x["digg"] for x in dupmap[k])
    vids = len({x["video_id"] for x in dupmap[k]})
    print(f"{c}x videos={vids} digg_sum={d}\t{k[:120]}")

# product demand videos
prod = set()
for fam in ["buy_where", "link_request", "name_product", "price", "availability"]:
    for r in fam_rows[fam]:
        prod.add(r["comment_id"])
byvid = collections.Counter()
for r in rows:
    if r["comment_id"] in prod:
        byvid[r["video_id"]] += 1
print("\n### videos with most product/link asks")
vidinfo = {r["video_id"]: r for r in rows}
for vid, c in byvid.most_common(15):
    r = vidinfo[vid]
    print(f"{c}\t{vid}\ttag={r['hashtag']}\tcap={r['descr'][:110]}\tplays={r['play']}")

print("\n### product asks by hashtag")
tags = collections.Counter()
for r in rows:
    if r["comment_id"] in prod:
        tags[r["hashtag"]] += 1
for t, c in tags.most_common(20):
    print(f"{c}\t{t}")

print("\n### question-mark share")
qm = sum(1 for r in rows if "?" in r["text"])
print(qm, len(rows), round(100*qm/len(rows), 2))