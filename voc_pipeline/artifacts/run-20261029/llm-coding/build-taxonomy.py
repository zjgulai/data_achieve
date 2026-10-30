#!/usr/bin/env python3
"""Export the frozen aspect taxonomy into a coder-facing checklist.

Reads voc/taxonomy.py without importing the package (the module has no
heavy dependencies, but loading it by path keeps this script runnable from
any cwd).  Definitions, labels, include/exclude rules are copied verbatim.
The frozen module has no examples, so positive_example / negative_example
are derived from the lexicon and prefixed with "[derived]".
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
VOC_ROOT = HERE.parents[2]  # artifacts/run-.../llm-coding -> voc_pipeline
TAXONOMY_PY = VOC_ROOT / "voc" / "taxonomy.py"
OUT = HERE / "taxonomy.json"

FAMILY_LABELS = {
    "SUP": "Support",
    "FIT": "Fit and sizing",
    "ADJ": "Adjustment and structure",
    "STB": "Stability",
    "COM": "Comfort",
    "APP": "Appearance under clothing",
    "MAT": "Material and durability",
    "VAL": "Value for money",
    "CX": "Returns and service",
    "FUL": "Fulfillment condition",
    "GEN": "Overall evaluation",
    "USE": "Wearing style",
    "ACT": "Activity compatibility",
    "SAF": "Safety of pressure placement",
}

# Each positive example should be coded with this aspect and a positive
# polarity.  Each negative example is a near-miss that must NOT receive this
# code (it falls under the taxonomy exclude rule).  Both are derived from the
# frozen lexicon, not from any labelled corpus.
EXAMPLES = {
    "SUP.GENERAL": (
        "This belly band gives me the support I need to stay on my feet.",
        "The fabric feels soft and cozy against my skin.",
    ),
    "SUP.BACK": (
        "The back support is firm and my lower back pain has eased.",
        "I do prenatal yoga to keep my back flexible.",
    ),
    "SUP.PRESSURE_OFFLOAD": (
        "It takes the weight off my hips so I can stand longer.",
        "The straps are easy to tighten.",
    ),
    "SUP.BELLY_LIFT": (
        "It lifts my belly and holds up my bump nicely.",
        "It gives good overall support.",
    ),
    "FIT.SIZE_ACCURACY": (
        "I ordered my usual medium and it is true to size.",
        "Which size should I order at 30 weeks?",
    ),
    "FIT.BODY_SHAPE": (
        "As a plus size mom with a short torso, this still fits well.",
        "I bought a large because the size chart said so.",
    ),
    "FIT.GROWTH_RANGE": (
        "It still fits now that my bump has grown at 34 weeks.",
        "I wore it once for a short walk.",
    ),
    "FIT.COVERAGE": (
        "The coverage is wide enough to cover my whole lower belly.",
        "The black color matches everything I wear.",
    ),
    "ADJ.STRAP_DESIGN": (
        "The velcro straps let me set the band exactly where I want it.",
        "It supports my back well.",
    ),
    "ADJ.DONNING": (
        "It is easy to put on and take off by myself.",
        "I bought it during my second trimester.",
    ),
    "ADJ.RANGE_TENSION": (
        "I can adjust the tension so it is snug but not too tight.",
        "The band has no buckles or straps to adjust.",
    ),
    "STB.STAY_IN_PLACE": (
        "It stays in place and does not slip down when I walk.",
        "It does not give enough support.",
    ),
    "STB.STRAP_POSITION": (
        "The straps sit comfortably and do not dig into my ribs.",
        "It feels a little tight around my waist.",
    ),
    "COM.SOFTNESS": (
        "The fabric is soft and cozy against my bump.",
        "It gives great support.",
    ),
    "COM.BREATHABILITY_HEAT": (
        "It is breathable and I do not sweat under it.",
        "The room was hot that day.",
    ),
    "COM.SKIN_CHAFE": (
        "It does not rub or leave a rash on my skin.",
        "It presses on one spot.",
    ),
    "COM.PRESSURE_DIGGING": (
        "It does not dig into my sides or leave marks.",
        "The seam rubs against my skin.",
    ),
    "COM.WEAR_TOLERANCE": (
        "I can wear it all day without discomfort.",
        "I wore it for ten minutes to try it on.",
    ),
    "COM.GENERAL": (
        "It is comfortable overall.",
        "The lower back support is excellent.",
    ),
    "APP.UNDER_CLOTHING": (
        "It is invisible under my clothes and does not show through.",
        "I wear it over a dress at home.",
    ),
    "APP.LOW_PROFILE": (
        "It is slim and low profile, not bulky at all.",
        "The material is thick.",
    ),
    "APP.COLOR_AESTHETIC": (
        "The beige color is cute and matches my outfits.",
        "It works well under clothes.",
    ),
    "MAT.FABRIC": (
        "The fabric is a soft cotton blend.",
        "It is comfortable.",
    ),
    "MAT.DURABILITY": (
        "It is still durable after a few washes.",
        "I washed it once before wearing it.",
    ),
    "MAT.ELASTICITY_RETENTION": (
        "It has not stretched out or lost its elasticity.",
        "The elastic is snug when new.",
    ),
    "MAT.THICKNESS": (
        "The band is thick and well padded.",
        "It is low profile under clothes.",
    ),
    "MAT.CARE": (
        "It is easy to wash and dries quickly.",
        "It fell apart after a few washes.",
    ),
    "VAL.PRICE_VALUE": (
        "For the price, it is worth every penny.",
        "It arrived in a nice box.",
    ),
    "CX.RETURN_EXCHANGE": (
        "The return was easy and the refund came quickly.",
        "I am still deciding whether to buy it.",
    ),
    "FUL.PRODUCT_CONDITION": (
        "It arrived in perfect condition, not damaged.",
        "Shipping took a week.",
    ),
    "GEN.OVERALL_EVALUATION": (
        "Overall I love it and would recommend it.",
        "The straps are adjustable.",
    ),
    "USE.LAYERING": (
        "I wear it over my clothes when I am at home.",
        "It is invisible under a shirt.",
    ),
    "ACT.COMPATIBILITY": (
        "I can walk and chase my toddler while wearing it.",
        "It fits true to size.",
    ),
    "SAF.PRESSURE_PLACEMENT": (
        "It puts no pressure on my belly, so I feel safe wearing it.",
        "It feels a bit tight.",
    ),
}


def load_taxonomy_module():
    spec = importlib.util.spec_from_file_location("_frozen_taxonomy", TAXONOMY_PY)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load %s" % TAXONOMY_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    tax = load_taxonomy_module()
    codes = [c.code for c in tax.ASPECTS]
    missing = [c for c in codes if c not in EXAMPLES]
    extra = [c for c in EXAMPLES if c not in codes]
    if missing or extra:
        raise SystemExit("example map mismatch: missing=%s extra=%s" % (missing, extra))

    aspects = []
    for code in tax.ASPECTS:
        family = code.code.split(".", 1)[0]
        positive, negative = EXAMPLES[code.code]
        aspects.append(
            {
                "code": code.code,
                "label": code.label,
                "family": family,
                "definition": code.definition,
                "positive_example": "[derived] " + positive,
                "negative_example": "[derived] " + negative,
                "include": code.include,
                "exclude": code.exclude,
            }
        )

    contexts = [
        {"code": c.code, "label": c.label, "definition": c.definition}
        for c in tax.CONTEXTS
    ]

    doc = {
        "taxonomy_id": tax.TAXONOMY_VERSION,
        "supersedes": getattr(tax, "TAXONOMY_SUPERSEDES", None),
        "frozen_at": tax.TAXONOMY_FROZEN_AT,
        "revision_note": getattr(tax, "TAXONOMY_REVISION_NOTE", ""),
        "resolution_rules": [
            {
                "step": rule["step"],
                "code": rule["code"],
                "condition": rule["condition"],
                "lexicon": list(rule["lexicon"]),
            }
            for rule in getattr(tax, "SUP_RESOLUTION_ORDER", [])
        ],
        "resolution_note": (
            "SUP 族按 step 升序判断；第一个命中的 code 是该 evidence span 的唯一 "
            "SUP code。step 2（weight/load）优先于 step 3（BACK），因此 "
            "'the weight off my pelvis and lower back' 归 SUP.PRESSURE_OFFLOAD。"
        ),
        "source_file": "voc/taxonomy.py",
        "source_sha256": hashlib.sha256(TAXONOMY_PY.read_bytes()).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aspect_count": len(aspects),
        "family_labels": FAMILY_LABELS,
        "derived_fields": ["positive_example", "negative_example"],
        "example_note": (
            "positive_example = an utterance that should receive this code with "
            "positive polarity. negative_example = a near-miss that must NOT "
            "receive this code because it falls under the taxonomy exclude rule. "
            "Both are [derived] from the frozen lexicon; the frozen module has no "
            "examples of its own. Definitions are verbatim from the frozen module."
        ),
        "aspects": aspects,
        "contexts": contexts,
        "output_note": (
            "Aspect codes come only from aspects[]. Context codes come only from "
            "contexts[]. Journey and outcome outputs use the plain enums defined "
            "in CODING-CONTRACT.md, not the JNY.*/OUT.* codes in the frozen module."
        ),
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT)
    print("aspects", len(aspects), "contexts", len(contexts))


if __name__ == "__main__":
    main()
