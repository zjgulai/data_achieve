#!/usr/bin/env python3
"""Build coded/batch-02.jsonl and assert every span is a verbatim substring."""
import json
import sys
from pathlib import Path

BASE = Path("/Users/lute/Project/data_scrapy/voc_pipeline/artifacts/run-20261029/llm-coding")
SRC = BASE / "batches" / "batch-02.jsonl"
OUT = BASE / "coded" / "batch-02.jsonl"
TAX = BASE / "taxonomy.json"

A = lambda code, pol, span, conf: {
    "code": code, "polarity": pol, "evidence_span": span, "confidence": conf,
}
R = lambda cid, exp, reason, aspects, contexts, journey, outcome, med, notes: {
    "canonical_id": cid, "is_product_experience": exp, "experience_reason": reason,
    "aspects": aspects, "contexts": contexts, "journey": journey,
    "outcome": outcome, "medical_self_report": med, "notes": notes,
}

records = [
    R("c-19rgm8iapnjhc", False, "question", [], [], None, None, False,
      "asks for an example image; no product use or evaluation"),
    R("c-19rjo0npo4yjp", False, "product_mismatch", [], [], None, None, False,
      "evaluates maternity scrubs, not the belly band category"),
    R("c-19rnf7umnzg9x", False, "other", [], [], None, None, True,
      "belly band only listed among tried remedies; no product-specific evaluation"),
    R("c-19rqosa6piby9", False, "product_mismatch", [], [], None, None, False,
      "stroller comparison; different category"),
    R("c-1lijqy4", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "positive", "It really helps!", "high")],
      ["CTX.PREGNANCY_T3", "CTX.ACTIVITY_EXERCISE"], "repeat_use", None, False,
      "belly band used since 17 weeks while running"),
    R("c-1nphgbt", False, "help_seeking", [], [], None, None, False,
      "asks for running belly band recommendations"),
    R("c-1oht78y", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "positive",
         "I just never thought the belly band would make such a difference.", "high"),
       A("ACT.COMPATIBILITY", "positive",
         "I am springing up and down from the couch", "medium")],
      ["CTX.PREGNANCY_T3"], "first_use", "relief", True,
      "first day wearing the band; pelvic pain relief"),
    R("c-1ow447s", False, "product_mismatch", [], [], None, None, False,
      "KT tape skin reaction; different product category"),
    R("c-1pfyruu", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "negative",
         "it doesn’t help much", "high")],
      ["CTX.PREGNANCY_T3", "CTX.BODY_SHORT_TORSO"], "repeat_use", "no_relief", True,
      "blames petite frame for limited effect"),
    R("c-1purbx5", False, "third_party_event", [], [], None, None, True,
      "complains maternity products are unavailable in stores"),
    R("c-1qarw67", False, "question", [], [], None, None, True,
      "asks whether to stop running; belly band mentioned incidentally"),
    R("c-1s1yjs2", False, "other", [], [], None, None, True,
      "pain narrative; belly band only mentioned as owned"),
    R("c-1sg6gqr", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "negative",
         "it doesn't fix the pain", "high")],
      ["CTX.PREGNANCY_T2"], "first_use", "no_relief", True,
      "also asks for advice"),
    R("c-1svoq9k", False, "product_mismatch", [], [], None, None, False,
      "leggings sizing question; different category"),
    R("c-1ti8znp", False, "product_mismatch", [], [], None, None, False,
      "sterilizer accessory question; different category"),
    R("c-1tskim1", False, "product_mismatch", [], [], None, None, False,
      "baby monitor question; different category"),
    R("c-1txcmzz", False, "product_mismatch", [], [], None, None, False,
      "bottle washer experience; different category"),
    R("c-1uaf2x9", False, "product_mismatch", [], [], None, None, False,
      "wearable pump recommendation request; different category"),
    R("c-1uuim67", False, "question", [], [], None, None, True,
      "PGP narrative and advice request; belly band use not evaluated"),
    R("c-1vac6v8", False, "product_mismatch", [], [], None, None, False,
      "breast pump question; different category"),
    R("c-1vpdbxw", False, "product_mismatch", [], [], None, None, False,
      "stroller recommendation request; different category"),
    R("c-1vzh8cy", False, "product_mismatch", [], [], None, None, False,
      "pregnancy pillow comparison; different category"),
    R("c-1wd2rfo", False, "question", [], [], None, None, True,
      "diastasis recti narrative; support band mentioned without evaluation"),
    R("c-1x2pwx9", False, "product_mismatch", [], [], None, None, False,
      "stroller choice question; different category"),
    R("c-1xb64sq", False, "product_mismatch", [], [], None, None, False,
      "title-only question about a bottle washer; different category"),
    R("c-1xhod4n", False, "question", [], [], None, None, True,
      "belly band listed among tried remedies; no product-specific evaluation"),
    R("c-7658445761408780046", True, "first_person_use",
      [A("COM.SOFTNESS", "positive", "super soft", "high"),
       A("SUP.GENERAL", "positive", "I love the support it gives", "high"),
       A("GEN.OVERALL_EVALUATION", "positive",
         "This is exactly what I was hoping it’d be !", "high")],
      [], "first_use", None, False, "none"),
    R("c-7660305549976045325", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "positive", "Amazing product.", "high")],
      [], "first_use", None, False, "none"),
    R("c-7665021905910384398", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "positive", "I love it", "high"),
       A("COM.GENERAL", "positive", "very comfortable", "high"),
       A("FIT.COVERAGE", "positive", "to hide the extra skin from the last kids", "medium")],
      [], "first_use", "relief", True,
      "uses the band to cover postpartum loose skin"),
    R("c-7670289594361071374", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "negative", "Not the best quality.", "high")],
      [], "first_use", None, False, "generic quality complaint"),
    R("c-7674039645484320526", True, "first_person_use",
      [A("FIT.SIZE_ACCURACY", "negative", "I got 2x barely fits me", "high"),
       A("COM.GENERAL", "negative", "not comfortable", "high")],
      ["CTX.BODY_PLUS_SIZE"], "first_use", None, False,
      "garbled first clause; plus-size fit complaint"),
    R("c-7680768165969676046", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "negative", "Didn’t work.", "high"),
       A("ADJ.STRAP_DESIGN", "negative", "Velcro wouldn’t stay latched.", "high")],
      [], "first_use", None, False, "velcro fastener failed"),
    R("c-7688192349947610893", True, "first_person_use",
      [A("GEN.OVERALL_EVALUATION", "mixed",
         "It’s okay. Not sure i feel too much of a difference", "medium")],
      [], "first_use", None, False, "lukewarm; uncertain effect"),
    R("c-7692120308744128270", True, "first_person_use",
      [A("SUP.GENERAL", "positive", "So supportive", "high")],
      [], "first_use", None, False, "none"),
    R("c-7696935989738456846", True, "first_person_use",
      [A("FIT.SIZE_ACCURACY", "negative", "they are not tje same size", "high")],
      [], "first_use", None, False, "inconsistent sizing across pairs in one package"),
    R("c-7700787693628868365", True, "first_person_use",
      [A("SUP.BACK", "negative", "Gives no lower back support", "high"),
       A("STB.STAY_IN_PLACE", "negative", "it ends up sliding back up", "high"),
       A("VAL.PRICE_VALUE", "negative", "Not worth that price at all", "high")],
      [], "first_use", None, False, "band rides up and only covers mid-back"),
    R("c-pdedro1", False, "other", [], [], None, None, False,
      "brand recommendation without stated first-hand use"),
    R("c-pdyeiod", False, "product_mismatch", [], [], None, None, False,
      "pregnancy pillow and belly balm; different category"),
    R("c-pf83bo1", False, "product_mismatch", [], [], None, None, False,
      "baby nail file; different category"),
    R("c-pf9naw8", False, "product_mismatch", [], [], None, None, False,
      "bottle washer and sleep sacks; different category"),
    R("c-pgqfcdj", False, "product_mismatch", [], [], None, None, False,
      "unidentified Momcozy product with special bags; different category"),
    R("c-phzswus", False, "other", [], [], None, None, False,
      "Braxton Hicks explanation; no product evaluation"),
]

src = [json.loads(line) for line in SRC.read_text(encoding="utf-8").splitlines() if line.strip()]
tax = json.loads(TAX.read_text(encoding="utf-8"))
aspect_codes = {x["code"] for x in tax["aspects"]}
context_codes = {x["code"] for x in tax["contexts"]}

errors = []
if len(records) != len(src):
    errors.append(f"record count {len(records)} != source {len(src)}")
if [r["canonical_id"] for r in records] != [s["canonical_id"] for s in src]:
    errors.append("canonical_id order mismatch")

by_id = {s["canonical_id"]: s for s in src}
for r in records:
    s = by_id.get(r["canonical_id"])
    if s is None:
        errors.append(f"unknown id {r['canonical_id']}")
        continue
    title = s.get("title") or ""
    text = s.get("text") or ""
    if not r["is_product_experience"] and r["aspects"]:
        errors.append(f"{r['canonical_id']}: false with aspects")
    if len(r["aspects"]) > 6:
        errors.append(f"{r['canonical_id']}: >6 aspects")
    seen = set()
    for i, a in enumerate(r["aspects"]):
        sp = a["evidence_span"]
        if a["code"] not in aspect_codes:
            errors.append(f"{r['canonical_id']}#{i}: bad code {a['code']}")
        if len(sp) > 120:
            errors.append(f"{r['canonical_id']}#{i}: span {len(sp)} chars")
        if sp in seen:
            errors.append(f"{r['canonical_id']}#{i}: duplicate span")
        seen.add(sp)
        if sp not in title and sp not in text:
            errors.append(f"{r['canonical_id']}#{i}: span not found {sp!r}")
    for c in r["contexts"]:
        if c not in context_codes:
            errors.append(f"{r['canonical_id']}: bad context {c}")

if errors:
    print("BUILD ERRORS:")
    for e in errors:
        print(" ", e)
    sys.exit(1)

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8", newline="\n") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

n_aspects = sum(len(r["aspects"]) for r in records)
n_false = sum(1 for r in records if not r["is_product_experience"])
print(f"wrote {OUT}")
print(f"records={len(records)} aspects={n_aspects} false={n_false}")
