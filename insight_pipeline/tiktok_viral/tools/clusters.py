import csv, re, collections, random, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows=[]
for r in csv.reader(open(ROOT / 'data' / 'comments_all.tsv',encoding='utf-8',errors='replace'),delimiter='\t',quoting=csv.QUOTE_NONE):
    if len(r)!=11: continue
    rows.append({'id':r[0],'vid':r[1],'digg':int(r[2] or 0),'tag':r[5],'plays':int(r[6] or 0),'cap':r[10],'text':r[9]})
T=[r['text'].lower() for r in rows]

def hit(pat): return [rows[i] for i,t in enumerate(T) if re.search(pat,t)]

buy = r"(where (can|could|do|did|would|should) (i|we|you|u) (get|buy|find|order|purchase|grab)|where (did|do) (you|u|she|he|they) (get|buy|find|order|purchase|grab)|where (is|are) (this|that|it|these|those|that one|the [a-z]+|your [a-z]+)[^.!?]{0,45}(from|bought|sold|available|sold out)|where to (buy|get|find|order)|\bw2c\b|dónde (lo|la|los|las) (compraste|consigo|compro|venden|puedo comprar|sacaste)|de dónde (es|sacaste|lo sacaste)|donde (lo|la) compro|onde (compro|comprar|acha|encontro)|beli dimana|dimana beli|di ?mana beli|où (l'|la |le )?(acheter|trouver)|где (купить|заказать|найти)|وين أشتري|مشتري من وين|mua ở đâu|ở đâu bán|dove comprare|wo (kann man|kaufen)|어디서 사|어디서 구|どこで買|ซื้อที่ไหน)"
link = r"(\b(link please|link pls|send (me )?(the )?link|drop (the )?link|link for|link to|whats the link|what's the link|share the link|anyone got the link|need the link|need links?|link porfavor|link por favor)\b|\b(link|links|enlace)\b\s*(\?|$|pls|please))"
price = r"(how much (is|does|do|for|are) (it|this|that|the|they|you|one|each)?|how much\?|\bprecio\b|\bpreço\b|cuánto (cuesta|sale)|berapa harganya|combien (ça|ca) coûte|сколько стоит|بكم|ราคา|얼마|bao nhiêu|多少钱|price\?)"
brand = r"(what brand|which brand|what('s| is) the brand|brand name|que marca|qué marca|qual a marca|qual marca|nama produk|produk apa|quelle marque|какой бренд)"
nameobj = r"(what('s| is) (this|that|it)( called)?|what is the name|name of (this|that|the)|the name of|como se llama|cómo se llama|qué es esto|que es esto|nama(nya)? apa|apa itu|как называется|이거 뭐|何これ|what am i ordering|what is it called)"
song = r"(what('s| is)? (the )?(song|audio|sound|music)|song name|audio name|sound name|music name|qué canción|que cancion|cómo se llama la canción|como se llama la cancion|nome da música|qual (é a )?música|lagu apa|quelle chanson|какая песня|اسم الأغنية|bài hát)"
app = r"(what app|which app|what filter|what effect|what editor|which editor|app name|what do you use to edit|qué app|que app|qual app|aplikasi apa|quelle app|какое приложение|تطبيق)"
age = r"(how old (is|are) (your|you|he|she|the|it|this)|how many (months|weeks)|what month|which month|how old\?)"
gear = r"(stroller|carrier|car seat|bassinet|swaddle|sleep sack|sleepsack|bottle|pump|wipe|wipes|diaper bag|high chair|monitor|playpen|bouncer|crib|nursery|bumper sticker|headband|feeding pillow|blanket|pillow|dresser|chair|cup|toy)"
style = r"(outfit|dress|shirt|pants|shoes|hair|makeup|lip|lashes|nails|costume|wear|wearing|clothes|baju|ropa|vestido|cabelo|maquiagem)"
normal = r"(is (this|it|that|that one) normal|is that normal|is it ok|is this ok|is this okay|is it safe|is this safe|should i worry|is this a thing|is that ok|es normal|es seguro|é normal|aman|berbahaya)"
ship = r"(do you ship|ship to|available in|not available in|restock|in stock|when.*available|soy de|envían|hay en|tiene envío|in my country|in canada|in the us|in uganda|in italy|in mexico|in india)"
howto = r"(how (do|did|to|can|should) (you|i|we|u)|how to|tutorial|recipe|step by step|cómo (lo )?(haces|hiciste|se hace)|como (lo )?(haces|hiciste|se hace)|receta|como faz|receita|gimana|caranya|comment (tu )?fais|как (ты )?(делаешь|сделать)|كيف|どうやって|어떻게|วิธี)"

clusters = [('buy_where',buy),('link',link),('price',price),('brand',brand),('name_object',nameobj),('song',song),('app_effect',app),('age',age),('normal_safety',normal),('ship_availability',ship),('howto',howto)]
print("cluster\tn\tvideos\ttop_examples")
res={}
for name,pat in clusters:
    hs=hit(pat)
    res[name]=hs
    print(f"{name}\t{len(hs)}\t{len({r['vid'] for r in hs})}")
print()
for name,pat in clusters:
    hs=res[name]
    print(f"== {name}")
    for r in sorted(hs,key=lambda r:-r['digg'])[:10]:
        print(f"   {r['digg']}\t{r['text'][:130]}\t| {r['cap'][:45]} | {r['tag']}")

# style / gear subsets of buy
b=res['buy_where']
sty=[r for r in b if re.search(style,r['text'].lower())]
gr=[r for r in b if re.search(gear,r['text'].lower())]
print("\nbuy+style:",len(sty),"videos",len({r['vid'] for r in sty}))
print("buy+gear:",len(gr),"videos",len({r['vid'] for r in gr}))
print("\n-- buy+style examples")
for r in sorted(sty,key=lambda r:-r['digg'])[:10]: print(f"   {r['digg']}\t{r['text'][:130]}\t| {r['cap'][:40]}")
print("\n-- buy+gear examples")
for r in sorted(gr,key=lambda r:-r['digg'])[:10]: print(f"   {r['digg']}\t{r['text'][:130]}\t| {r['cap'][:40]}")

# unique videos with any commercial ask
comm=set()
for n in ['buy_where','link','price','brand','name_object','ship_availability']:
    for r in res[n]: comm.add(r['id'])
print("\nany commercial-ish (buy/link/price/brand/name/ship):", len(comm))
vw={r['vid'] for r in rows if r['id'] in comm}
print("videos:", len(vw))
# top videos by commercial asks
cnt=collections.Counter(r['vid'] for r in rows if r['id'] in comm)
info={r['vid']:r for r in rows}
print("\ntop videos by commercial asks:")
for v,c in cnt.most_common(12):
    r=info[v]; print(f"{c}\t{v}\tplays={r['plays']}\t{r['tag']}\t{r['cap'][:90]}")