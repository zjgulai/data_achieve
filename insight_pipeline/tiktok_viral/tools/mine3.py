import csv, json, re, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

path = sys.argv[1]
rows = []
with open(path, encoding="utf-8", errors="replace") as f:
    for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(r) != 11: continue
        rows.append({"comment_id":r[0],"video_id":r[1],"digg":int(r[2] or 0),"reply":int(r[3] or 0),
            "author":r[4],"hashtag":r[5],"play":int(r[6] or 0),"vdigg":int(r[7] or 0),
            "vcomments":int(r[8] or 0),"text":r[9],"descr":r[10]})

def L(s): return s.lower().strip()

def q(t):
    if "?" in t or "？" in t: return True
    if re.search(r"^(what|why|how|when|where|who|which|whose|do |does |did |is |are |can |could |should |would |will |anyone|anybody|has |have |was |were )", t): return True
    if re.search(r"^(que |qué |como |cómo |por que|por qué|donde |dónde |cuanto |cuánto |quien |quién |cual |cuál |quando |onde |qual |porque |apa |kenapa |gimana |kapan |dimana |pourquoi |comment |quand |où |est-ce|почему|как|когда|где|что|ليش|كيف|وين|متى|لماذا|berapa|siapa)", t): return True
    if re.search(r"(anyone know|does anyone|can someone|anyone else|what do you|how do you|is there a|are there any|have you tried|did you use)", t): return True
    return False

COMM = {
 "where_to_buy": r"(where (can|could|do|did|would|should) (i|we|you|u) (get|buy|find|order|purchase|grab)|where (did|do) (you|u|she|he|they) (get|buy|find|order|purchase|grab)|where (is|are) (this|that|it|these|those|that one|the [a-z]+|your [a-z]+)[^.!?]{0,45}(from|bought|sold|available|sold out)|where to (buy|get|find|order)|\bw2c\b|dónde (lo|la|los|las) (compraste|consigo|compro|venden|puedo comprar|sacaste)|de dónde (es|sacaste|lo sacaste)|donde (lo|la) compro|onde (compro|comprar|acha|encontro)|beli dimana|dimana beli|di ?mana beli|où (l'|la |le )?(acheter|trouver)|где (купить|заказать|найти)|وين أشتري|مشتري من وين|mua ở đâu|ở đâu bán|dove comprare|wo (kann man|kaufen)|어디서 사|어디서 구|どこで買|ซื้อที่ไหน)",
 "link_request": r"(\b(link please|link pls|send (me )?(the )?link|drop (the )?link|link for|link to|whats the link|what's the link|share the link|anyone got the link|need the link|need links?|link porfavor|link por favor)\b|\b(link|links|enlace)\b\s*(\?|$|pls|please))",
 "brand_name": r"(what brand|which brand|what('s| is) the brand|brand name|que marca|qué marca|qual a marca|qual marca|marca dele|nama produk|produk apa|quelle marque|какой бренд|какая фирма|what product is)",
 "price": r"(\bprice\b|\bprices\b|\bprecio\b|\bprecios\b|\bpreço\b|\bpreços\b|how much (is|does|do|for|are)|cuánto (cuesta|sale|cuesta)|berapa harganya|combien (ça|ca) coûte|сколько стоит|بكم|ราคา|얼마|bao nhiêu|多少钱)",
 "availability": r"(in stock|restock|when.*(back in stock|available again)|do you ship|ship to|available in|envían|hay en|tiene envío)",
}
def c(fam,t): return re.search(COMM[fam], t)

# separate non-commercial identify intents
IDENT = {
 "song": r"(what('s| is)? (the )?(song|audio|sound|music)|song name|audio name|sound name|music name|qué canción|que cancion|cómo se llama la canción|como se llama la cancion|nome da música|qual (é a )?música|lagu apa|quelle chanson|какая песня|اسم الأغنية|bài hát|what song is)",
 "object_or_effect": r"(what app|which app|what filter|what effect|what editor|what do you use|what('s| is) (this|that|it)( called)?|what is the name|name of (this|that|the)|the name of|como se llama|qué es esto|que es esto|nama(nya)? apa|apa itu|как называется|이거 뭐|何これ)",
}

qs = [(i,r) for i,r in enumerate(rows) if q(L(r["text"]))]
print("question candidates:", len(qs), "distinct videos:", len({r['video_id'] for _,r in qs}))

fam = collections.Counter(); comm_rows = []
for i,r in enumerate(rows):
    t=L(r["text"]); hit=None
    for f in ["where_to_buy","link_request","brand_name","price","availability"]:
        if c(f,t):
            fam[f]+=1
            if hit is None: hit=f
    if hit: comm_rows.append((hit,r))
print("commercial asks:", len(comm_rows), "videos:", len({r['video_id'] for _,r in comm_rows}))
print("subfamily counts (multi-label):", dict(fam))
print("primary:", dict(collections.Counter(h for h,_ in comm_rows)))

for f in ["where_to_buy","link_request","brand_name","price","availability"]:
    rs=sorted([r for h,r in comm_rows if h==f], key=lambda r:-r["digg"])[:12]
    print(f"\n-- {f} ({len([1 for h,_ in comm_rows if h==f])})")
    for r in rs: print(f"{r['digg']}\t{r['text'][:150]}\t|| {r['descr'][:55]} | {r['hashtag']}")

# identify intents
print("\n### identify intents")
for f in ["song","object_or_effect"]:
    rs=[r for r in rows if re.search(IDENT[f], L(r["text"]))]
    print(f"-- {f}: {len(rs)} comments, {len({r['video_id'] for r in rs})} videos")
    for r in sorted(rs,key=lambda r:-r["digg"])[:8]:
        print(f"   {r['digg']}\t{r['text'][:120]}\t|| {r['descr'][:50]}")

# themes among question candidates (multi-label)
THEMES = {
 "feeding": r"\b(feed|feeding|formula|breast|breastfeed|nurs(e|ing)|pump|milk|bottle|puree|solids|wean|food|eat)\b|leche|pecho|lactancia|comida|papilla|mamadeira|susu|mpasi",
 "sleep": r"\b(sleep|sleeping|nap|naps|bedtime|crib|bed|wake|waking|night)\b|dormir|siesta|sueño|sono|tidur",
 "diaper_potty": r"\b(diaper|diapers|potty|toilet|wipe|wipes|poop|pee)\b|pañal|pañales|fralda|popok",
 "development": r"\b(month|months|week|weeks|old|crawl|crawling|walk|walking|talk|talking|teeth|teething|milestone|develop|development|head|roll|rolling|sit|sitting)\b|meses|semanas|dentes|bulan",
 "pregnancy_birth": r"\b(pregnan|pregnancy|labor|labour|birth|contraction|epidural|c-section|cesarean|postpartum|due date|trimester|delivery|induction|water broke)\b|embarazo|parto|cesárea|puerperio|gravidez|parto",
 "health_safety": r"\b(safe|safety|danger|dangerous|choke|choking|fever|rash|allergy|allergic|vaccine|doctor|pediatrician|hospital|sick|ill|normal|harm|hurt)\b|seguro|peligro|fiebre|alergia|vacuna|médico|doente|perigo",
 "gear": r"\b(stroller|carrier|car seat|bassinet|crib|bottle|pump|swaddle|sleep sack|wrap|toy|toys|wipe|wipes|diaper bag|high chair|monitor)\b|coche|carrito|andador|cadeirinha|brinquedo",
 "style": r"\b(outfit|dress|shirt|pants|shoes|hair|makeup|lip|lashes|nails|costume|wear|wearing)\b|ropa|vestido|zapatos|cabelo|maquiagem|roupa|baju",
 "relationship": r"\b(husband|wife|partner|boyfriend|girlfriend|mom|mother|dad|father|in-law|marriage|relationship|divorce)\b|esposo|marido|novio|mamá|papá|namorado|marido",
 "creator_tool": r"\b(song|audio|sound|filter|app|edit|editor|effect|template|capcut|preset)\b|canción|música|aplicativo|efeito",
 "money": r"\b(price|cost|expensive|cheap|afford|budget|money|salary|pay)\b|precio|caro|barato|dinero|preço|dinheiro",
}
print("\n### question themes (multi-label, n and share of question candidates)")
for name,pat in THEMES.items():
    hits=[r for _,r in qs if re.search(pat,L(r["text"]))]
    print(f"{name}\t{len(hits)}\t{round(100*len(hits)/len(qs),1)}%\tvideos={len({r['video_id'] for r in hits})}")

# dump question candidates sorted by digg for reading
with open(ROOT / "data" / "questions_sorted.tsv","w",encoding="utf-8") as f:
    for i,r in sorted(qs,key=lambda x:-x[1]["digg"]):
        f.write(f"{r['comment_id']}\t{r['video_id']}\t{r['digg']}\t{r['hashtag']}\t{r['descr'][:100]}\t{r['text'][:250]}\n")

print("\nwrote questions_sorted.tsv")