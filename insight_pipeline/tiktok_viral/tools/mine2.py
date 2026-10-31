import csv, json, re, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

path = sys.argv[1]
rows = []
with open(path, encoding="utf-8", errors="replace") as f:
    for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(r) != 11:
            continue
        rows.append({
            "comment_id": r[0], "video_id": r[1], "digg": int(r[2] or 0),
            "reply": int(r[3] or 0), "author": r[4], "hashtag": r[5],
            "play": int(r[6] or 0), "vdigg": int(r[7] or 0), "vcomments": int(r[8] or 0),
            "text": r[9], "descr": r[10],
        })
print("rows", len(rows))

def L(s): return s.lower().strip()

COMM = {
 "buy_where": r"(where (can|could|do|did|would|should) (i|we|you|u) (get|buy|find|order|purchase|grab)|where (is|are) (this|that|it|these|those|the|your|that one)[^.!?]{0,50}(from|bought|sold|available|sold out)|where did (you|u|she|he) (get|buy|find)|where to (buy|get|find)|where.*\b(amazon|etsy|target|walmart|shop|store|website)\b|w2c|where can i get|where do i get|dónde (lo|la|los|las) (compraste|consigo|compro|venden|puedo comprar|sacaste)|de dónde (es|sacaste|lo sacaste)|donde lo compro|dónde comprar|onde (compro|comprar|acha|encontro)|qual o link|link do|beli dimana|dimana beli|di ?mana beli|où (l'|la |le )?(acheter|trouver)|où est-ce que je peux|где (купить|заказать|найти)|من وين|وين أشتري|مشتري من وين|mua ở đâu|ở đâu bán|dove comprare|wo (kann man|kaufen)|어디서 사|어디서 구|どこで買|ซื้อที่ไหน)",
 "link_request": r"(\b(link|links|enlace|링크|ลิงก์|ссылка|لينك)\b|link please|link pls|send (me )?(the )?link|drop (the )?link|link for|link to|whats the link|what's the link|share the link|link porfavor|link por favor)",
 "song_audio": r"(what('s| is)? (the )?(song|audio|sound|music)|song name|audio name|sound name|music name|qué canción|que cancion|nome da música|qual (é a )?música|lagu apa|quelle chanson|какая песня|اسم الأغنية|bài hát|노래|曲名|เพลง|what song is)",
 "app_effect": r"(what app|which app|what filter|what effect|what editor|which editor|app name|what do you use|qué app|que app|qual app|aplikasi apa|quelle app|какое приложение|تطبيق)",
 "name_product": r"(what('s| is) (this|that|it) (\?|$|called|from)|what is the name|name of (this|that|the)|what brand|which brand|what product|brand name|que marca|qué marca|cómo se llama|como se llama|qual o nome|como se chama|nama(nya)? apa|apa itu|comment (ça|ca) s'appelle|как называется|اسمه|ايش هذا|tên gì|cái gì|이거 뭐|何これ|ชื่ออะไร)",
 "price": r"(how much (is|does|do|for|are)|price|precio|preço|berapa harganya|combien (ça|ca) coûte|сколько стоит|بكم|ราคา|얼마|bao nhiêu|多少钱)",
 "howto": r"(how (do|did|to|can|should) (you|i|we|u)|how to|tutorial|recipe|step by step|cómo (lo )?(haces|hiciste|se hace)|como (lo )?(haces|hiciste|se hace)|receta|como faz|receita|gimana|caranya|comment (tu )?fais|как (ты )?(делаешь|сделать)|كيف|どうやって|어떻게|วิธี)",
 "safety_health": r"(is (this|it) (safe|ok|okay|normal)|safe for|is it bad|does (this|it) (work|really)|should i (be )?(worried|worry)|is that normal|es seguro|es normal|se puede|faz mal|berbahaya|aman|est-ce (normal|dangereux)|это нормально|нормально ли)",
 "availability": r"(in stock|restock|when.*(back|available)|do you ship|ship to|available in|sell.*(in|to)|envían|envios|hay en|tiene envío)",
 "location": r"(where (are|is) (you|this|that)|where is this|where was this|donde es|dónde es|where do you live|what city|que ciudad)",
}
COMM["any_commercial"] = None

def match(fam, t):
    return re.search(COMM[fam], t)

def any_question(t):
    if "?" in t or "？" in t:
        return True
    if re.search(r"^(what|why|how|when|where|who|which|whose|do |does |did |is |are |can |could |should |would |will |anyone|anybody|has |have |was |were )", t):
        return True
    if re.search(r"^(que |qué |como |cómo |por que|por qué|donde |dónde |cuanto |cuánto |quien |quién |cual |cuál |quando |onde |qual |porque |apa |kenapa |gimana |kapan |dimana |pourquoi |comment |quand |où |est-ce|почему|как|когда|где|что|ليش|كيف|وين|متى|لماذا|aimar|kak|berapa|siapa)", t):
        return True
    if re.search(r"(anyone know|does anyone|can someone|anyone else|what do you|how do you|is there a|are there any|have you tried|did you use)", t):
        return True
    return False

qs = [(i, r) for i, r in enumerate(rows) if any_question(L(r["text"]))]
print("question candidates:", len(qs), "videos:", len({r['video_id'] for _, r in qs}))

commercial = []
fam_hits = collections.Counter()
for i, r in enumerate(rows):
    t = L(r["text"])
    hit = None
    for fam in ["buy_where","link_request","name_product","price","availability"]:
        if match(fam, t):
            fam_hits[fam] += 1
            if hit is None: hit = fam
    if hit:
        commercial.append((hit, r))
print("commercial asks:", len(commercial), "videos:", len({r['video_id'] for _, r in commercial}))
print("commercial sub-families (comments may match several):", dict(fam_hits))
prim = collections.Counter(h for h, _ in commercial)
print("commercial primary:", dict(prim))

print("\n### commercial examples by subfamily (top digg)")
for fam in ["buy_where","link_request","name_product","price","availability"]:
    rs = sorted([r for h, r in commercial if h == fam], key=lambda r: -r["digg"])[:15]
    print(f"-- {fam}")
    for r in rs:
        print(f"{r['digg']}\t{r['text'][:150]}\t|| cap={r['descr'][:60]} tag={r['hashtag']}")

print("\n### videos with most commercial asks")
byvid = collections.Counter(r["video_id"] for _, r in commercial)
vinfo = {r["video_id"]: r for r in rows}
for vid, c in byvid.most_common(20):
    r = vinfo[vid]
    print(f"{c}\t{vid}\tplays={r['play']}\ttag={r['hashtag']}\tcap={r['descr'][:100]}")

print("\n### commercial asks by hashtag")
tags = collections.Counter(r["hashtag"] for _, r in commercial)
for t, c in tags.most_common(20): print(f"{c}\t{t}")

# normalized duplicates among question candidates
def norm(s):
    s = s.lower()
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"@\w+", " ", s)
    s = re.sub(r"[^0-9a-záéíóúñüçãõâêôàèìòùäëïöüßА-Яа-яёЁ؀-ۿ一-鿿぀-ヿ가-힯 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
dups = collections.Counter(); dupmap = collections.defaultdict(list)
for i, r in qs:
    k = norm(r["text"])
    if len(k) >= 8:
        dups[k] += 1; dupmap[k].append(r)
rep = sorted([(k, c) for k, c in dups.items() if c >= 3], key=lambda x: -x[1])
print(f"\n### exact-normalized repeated question texts >=3: {len(rep)}")
for k, c in rep[:50]:
    d = sum(x["digg"] for x in dupmap[k]); vids = len({x["video_id"] for x in dupmap[k]})
    print(f"{c}x vids={vids} digg={d}\t{k[:130]}")

# dump question candidates for manual reading
with open(ROOT / "data" / "questions.tsv","w",encoding="utf-8") as f:
    for i, r in qs:
        f.write(f"{r['comment_id']}\t{r['video_id']}\t{r['digg']}\t{r['hashtag']}\t{r['descr'][:120]}\t{r['text'][:300]}\n")
print("\nwrote", ROOT / "data" / "questions.tsv")