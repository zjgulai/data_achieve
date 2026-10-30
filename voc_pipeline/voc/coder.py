"""Rule-based single coder.

This is deliberately not an LLM.  Every annotation can be replayed from the
frozen lexicon, so the corpus is reproducible and the failure modes are
obvious.  It is still single-coded: G7 is not passed, and no output of this
module may be used as a prevalence metric.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .canonical import CanonicalRecord
from .taxonomy import ASPECTS, CONTEXTS, GAPS, JOURNEYS, MEDICAL, OUTCOMES, TAXONOMY_VERSION

NEGATIVE_CUES = (
    "uncomfortable",
    "hurt",
    "hurts",
    "hurting",
    "pain",
    "painful",
    "ache",
    "aches",
    "slipped",
    "slips",
    "slip",
    "slides",
    "slid",
    "rolled down",
    "rolls down",
    "roll down",
    "bunch",
    "bunches",
    "dig",
    "digs",
    "digging",
    "cut into",
    "cuts into",
    "chafe",
    "chafed",
    "chafing",
    "rash",
    "itchy",
    "itch",
    "sweaty",
    "too hot",
    "too tight",
    "too loose",
    "too small",
    "too big",
    "too large",
    "too short",
    "too long",
    "useless",
    "waste",
    "waste of money",
    "disappointed",
    "disappointing",
    "not worth",
    "overpriced",
    "expensive",
    "cheap",
    "returned",
    "returning",
    "refund",
    "didn't work",
    "doesn't work",
    "didn't help",
    "doesn't help",
    "no difference",
    "no support",
    "not supportive",
    "lack of support",
    "fell apart",
    "wore out",
    "stretched out",
    "lost elasticity",
    "regret",
    "hate",
    "bad",
    "poor",
    "annoying",
)

POSITIVE_CUES = (
    "comfortable",
    "comfy",
    "soft",
    "cozy",
    "supportive",
    "support",
    "supports",
    "helped",
    "helps",
    "relief",
    "relieved",
    "relieves",
    "great",
    "love",
    "loved",
    "perfect",
    "amazing",
    "works",
    "worked",
    "worth",
    "recommend",
    "recommended",
    "stays in place",
    "stayed in place",
    "doesn't slip",
    "didn't slip",
    "breathable",
    "invisible",
    "discreet",
    "durable",
    "cute",
    "favorite",
    "saved",
)

QUALIFIERS = ("sometimes", "a bit", "a little", "kind of", "mostly", "somewhat", "occasionally")
NEGATORS = ("not", "n't", "no", "never", "hardly", "without", "isn't", "wasn't", "doesn't", "didn't", "don't", "can't", "cannot", "zero", "lacks", "lacked", "lacking")

# "helps with back pain" names the condition, not a product fault.  Only a
# pain noun next to a relief verb flips this; "it hurts my back" stays
# negative because "hurt" is a verb and not in PAIN_NOUN_RE.
PAIN_NOUN_RE = re.compile(r"\b(?:lower back pain|back pain|pelvic pain|hip pain|pain|aches?)\b")
RELIEF_CUE_RE = re.compile(
    r"\b(?:relief|relieve[sd]?|relieving|help(?:s|ed|ing)?|eas(?:e|es|ed|ing)|"
    r"sav(?:e|es|ed|ing)|less pain|no pain)\b"
)

CLAUSE_SPLIT = re.compile(r"[.!?;\n]|,\s*(?:but|however|although|though)\s+", re.I)
# Within one clause, a sentiment cue is only evidence about the product when
# the product (or a product attribute) is named in the same comma/dash
# segment.  This is what stops "I wore comfortable sneakers ... I wore a belly
# band ... I'm STILL in pain" from becoming a product evaluation.
SEGMENT_SPLIT = re.compile(r"[,;—–]|(?<=\s)[-–](?=\s)|[()]")

# Product nouns that identify the reviewed item.  Brand names alone are not
# enough: "Momcozy nursing bra" is a different product and must not anchor a
# belly-band evaluation.
PRODUCT_NOUN_RE = re.compile(
    r"\b(?:belly bands?|bands?|belts?|straps?|velcro|wraps?|momcozy|"
    r"ergonest|cozysupport|cozy support|garments?|waistbands?|back support|"
    r"belly support|support belts?|product|item)\b",
    re.I,
)
# Attribute nouns can anchor only when a product noun is already established
# in this clause or the immediately preceding clause ("The fabric is soft").
ATTRIBUTE_NOUN_RE = re.compile(
    r"\b(?:fabric|material|design|sizing|size|fits?|padding|closure|seams?|"
    r"stitching|elastic|thickness)\b",
    re.I,
)
# A segment that talks about a different product ("Momcozy nursing bra",
# "pregnancy pillows") is not a belly-band evaluation, even if it names the
# brand or a generic attribute.
BAND_NOUN_RE = re.compile(
    r"\b(?:belly bands?|bands?|belts?|straps?|velcro|wraps?|waistbands?|"
    r"back support|belly support|support belts?|garments?)\b",
    re.I,
)
OTHER_PRODUCT_RE = re.compile(
    r"\b(?:bras?|nursing bra|leggings?|underwear|pillows?|kinesiology tape|"
    r"sneakers?|shoes?|socks?|shirts?|dress(?:es)?)\b",
    re.I,
)
# Any pronoun that can refer back to the product inside a clause.
GENERAL_REFERENCE_RE = re.compile(r"\b(?:it|its|it's|it’s|this|that|these|those|they|them)\b", re.I)
# A pronoun that is the subject of the segment.  "of it", "so that" and
# "one person" are deliberately not references to the product.
REFERENCE_PRONOUN_RE = re.compile(
    r"^(?:(?:and|but|so|yet|also|then|now|plus)\s+)*(?:it|its|it's|it’s|this|that|"
    r"these|those|they|them|the (?:band|belt|strap|product|item|fabric|material|design|support))\b",
    re.I,
)
# A segment that introduces a new subject cannot inherit the previous
# segment's product anchor.  This is the "句子主语不是第三方事件" check.
NEW_SUBJECT_RE = re.compile(
    r"^(?:(?:and|but|so|yet|also|then|now|plus)\s+)*(?:i|i'm|i’m|i've|i’ve|i'd|i’d|"
    r"i'll|we|we're|we’re|we've|he|she|you|my|our|his|her|their|amazon|walmart|"
    r"target|pharmacy|union|strike|picketing|colleagues|organizers?|doctors?|midwife|nurse)\b",
    re.I,
)
# Third-party actors and events are not the evaluated object, even when the
# clause also happens to mention the product.
THIRD_PARTY_RE = re.compile(
    r"\b(?:union|strike|striking|picketing|picket|colleagues|organizers?|husband|"
    r"family|midwife|doctors?|nurse|amazon|walmart|target|pharmacy|retailers?|"
    r"stores?|sellers?|vendor|delivery|shipping|shipped|labor rights|government)\b",
    re.I,
)
# Purchase-help / recommendation request.  A record that asks which product to
# buy is not automatically an experience record (FC-10).  Since decision A
# (experience gate), a request only changes the *scope*: a record with a real
# first-hand evaluation stays ``true`` and is marked ``partial``; a record
# whose only evaluation is a past, unnamed product stays ``false``.
HELP_SEEK_RE = re.compile(
    r"(?:\b(?:recs?|recommendations?|suggestions?|advice|tips?)\b|"
    r"\bhelp me (?:find|choose|pick)\b|"
    r"\blooking for (?:a |an |the )?(?:good |better |new )?(?:breathable )?(?:belly |support )?(?:band|belt)\b|"
    r"\bany (?:advice|suggestions?|recommendations?|recs|tips|ideas)\b|"
    r"\bis there anything i can do\b|\bwhat can i do\b|"
    r"\bhow (?:are we|did you all|did you|do you)\b|"
    r"\bwhat\b[^?]{0,80}\b(?:do|did) you\b|"
    r"\bhas anyone\b|\banyone (?:tried|been able|running|using|have)\b|"
    r"\bwhich\b[^?]{0,60}\bbest\b|\bwhat(?:'s| is) the best\b|"
    r"\bshould i (?:buy|get|try|be using)\b|\bdo i need\b|\bdo leggings work\b|"
    r"\bis this (?:normal|abnormal)\b|\bthanks for your takes\b|\bwondering if\b)",
    re.I,
)
# A title question is a request unless it is a social question that does not
# seek a product decision ("Any goals for race day?").
SOCIAL_TITLE_QUESTION_RE = re.compile(
    r"\b(?:any goals|any christmas babies|in the trenches)\b", re.I
)
# A past-use marker makes an evaluation background in a help-seeking record.
# "she is my first" (first child) is not a past-product marker, so the bare
# "my first" phrase is deliberately not matched.
PAST_MARKER_RE = re.compile(
    r"\b(?:my|with my|during my|in my|after my|from my|for my)\s+"
    r"(?:first|last|previous|prior|second|third)\s+(?:pregnancy|baby|child|kid|birth)\b"
    r"|\b(?:for|with|during|in|after|from) my first\b"
    r"|\bmy first (?:pregnancy|baby|child|kid|birth)\b"
    r"|\b(?:last|previous|prior)\s+(?:pregnancy|time)\b"
    r"|\bused to\b|\byears ago\b",
    re.I,
)
# A named brand or model is attributable even when the use happened in the
# past, so it is never treated as an unnamed background mention.
BRAND_MODEL_RE = re.compile(
    r"\b(?:momcozy|ergonest|cozysupport|cozy support|yb001|azband|fitsplint|"
    r"fitsplit|babybellyband|frida(?:\s+mom)?|keababies)\b",
    re.I,
)
# A direct purchaser relaying a family member's use is not a third-party
# external event; it is a first-hand purchase with a relayed evaluation.
RELAYED_RE = re.compile(
    r"\bbought (?:it |this |one |a |the )?(?:for|as a gift for)\s+(?:my|our|a)\s+"
    r"(?:daughter|son|wife|husband|mom|mother|sister|brother|friend|niece|nephew|"
    r"sister-in-law|brother-in-law)\b",
    re.I,
)
EXPERIENCE_SCOPES = ("full", "partial", "none")
EXPERIENCE_SOURCES = ("first_person", "relayed")
# E-merge §2.2: the only aspect gate.  ``product_match`` and
# ``experience_scope`` are orthogonal; a record must be on-topic and carry a
# full/partial evaluation before it can emit an aspect.  There is no second
# boolean and no per-claim exception.
ON_TOPIC_PRODUCT_MATCH = frozenset({"exact_current_family", "category_adjacent"})
EVALUATION_SCOPES = frozenset({"full", "partial"})


def is_on_topic(product_match: str) -> bool:
    """Whether the record is about the support-band product family."""
    return product_match in ON_TOPIC_PRODUCT_MATCH


def has_evaluation(experience_scope: str) -> bool:
    """Whether the scope assessment found an attributable evaluation."""
    return experience_scope in EVALUATION_SCOPES


def in_experience_cohort(product_match: str, experience_scope: str) -> bool:
    """The cohort predicate from E-merge §2.2."""
    return is_on_topic(product_match) and has_evaluation(experience_scope)


def emits_aspects(product_match: str, experience_scope: str, text: str) -> bool:
    """The only aspect-emission predicate (E-merge §2.4)."""
    return in_experience_cohort(product_match, experience_scope) and bool(
        (text or "").strip()
    )
# A pain/uncomfortable cue whose grammatical subject is the reviewer's body is
# a symptom, not a product fault.  "it hurts my back" is product evidence and
# stays; "I'm so uncomfortable walking" is not.
SELF_STATE_CUES = ("pain", "painful", "ache", "aches", "sore", "soreness", "hurt", "hurts", "hurting", "uncomfortable")
SELF_SUBJECT_RE = re.compile(
    r"\b(?:i|i'm|i’m|i am|i was|i feel|i felt|i started|i've|i’ve|we|we're|we’re|our|my)\b",
    re.I,
)
PRODUCT_SUBJECT_RE = re.compile(
    r"\b(?:it|its|this|that|these|those|they|the (?:band|belt|strap|product|item)|"
    r"momcozy|ergonest|(?:a |the |my )?belly band)\b",
    re.I,
)
# "I've heard ... can help" is not an observed experience.
HEARSAY_RE = re.compile(
    r"\b(?:i've heard|i’ve heard|i heard|people say|they say|everyone says|apparently|it is said|"
    r"someone\b[^.]{0,40}\brecommend(?:s|ed|ing)?)\b",
    re.I,
)
# These lexicons are stems, not whole words; the boundary wrapper would break
# them ("ventilat" must still match "ventilation").
STEM_LEXICONS = {"ventilat"}


@dataclass(frozen=True)
class ClauseSpan:
    clause: str
    start: int
    end: int
    has_anchor: bool = False
    ref_available: bool = False


def _trim_span(text: str, start: int, end: int) -> ClauseSpan:
    raw = text[start:end]
    left = len(raw) - len(raw.lstrip())
    right = len(raw.rstrip())
    return ClauseSpan(text[start + left : start + right], start + left, start + right)


def clause_spans(text: str) -> list[ClauseSpan]:
    """Split text into clauses while keeping offsets into the original text."""
    spans: list[ClauseSpan] = []
    pos = 0
    for match in CLAUSE_SPLIT.finditer(text):
        end = match.start()
        # A question mark is part of the clause: polarity_of must see it.
        if match.group(0) in {"?", "！", "？"}:
            end = match.end()
        spans.append(_trim_span(text, pos, end))
        pos = match.end()
    spans.append(_trim_span(text, pos, len(text)))
    return [span for span in spans if span.clause]


def clauses(text: str) -> list[str]:
    parts = [span.clause for span in clause_spans(text)]
    return parts or [text]


def _clause_pool(text: str, anchored_only: bool) -> list[ClauseSpan]:
    """Clauses that can plausibly describe the product.

    Reddit posts mix pregnancy symptoms with product experience.  A clause is
    codeable if it names the product, or if it uses a pronoun within one
    clause of the last product mention.  TikTok Shop reviews are different:
    a verified purchase is about the item by construction, so ``anchored_only``
    is False for them.
    """
    pool: list[ClauseSpan] = []
    last_anchor = -99
    for i, span in enumerate(clause_spans(text)):
        has_anchor = bool(PRODUCT_NOUN_RE.search(span.clause))
        if has_anchor:
            last_anchor = i
        near_reference = last_anchor >= 0 and i - last_anchor <= 1
        updated = ClauseSpan(span.clause, span.start, span.end, has_anchor, has_anchor or near_reference)
        if (
            not anchored_only
            or has_anchor
            or (
                near_reference
                and (GENERAL_REFERENCE_RE.search(span.clause) or ATTRIBUTE_NOUN_RE.search(span.clause))
            )
        ):
            pool.append(updated)
    return pool


def anchored_clauses(text: str) -> list[str]:
    """Backwards-compatible string-only view of :func:`_clause_pool`."""
    return [span.clause for span in _clause_pool(text, anchored_only=True)]


def _cue_pattern(cue: str) -> str:
    """Wrap a cue so it cannot match inside a longer word.

    Without this, the positive cue ``comfortable`` matches inside
    ``uncomfortable`` and the clause gains a phantom positive.  The same
    wrapper is applied to taxonomy lexicons, so ``thin`` no longer matches
    inside ``things``.
    """
    return f"(?<![a-z]){cue}(?![a-z])"


def _lexicon_pattern(pattern: str) -> str:
    if pattern in STEM_LEXICONS:
        return f"(?<![a-z]){pattern}\\w*(?![a-z])"
    if re.fullmatch(r"[a-z]+", pattern):
        # Preserve inflected forms ("supports", "helped", "smaller") without
        # letting short stems match unrelated words ("thin" inside "things").
        suffixes = ["s", "ed", "ing", "er", "est", "ly", "r", "st"]
        if pattern.endswith(("s", "x", "ch", "sh")):
            suffixes.insert(0, "es")
        if pattern.endswith("e"):
            suffixes.insert(0, "d")
        return f"(?<![a-z]){pattern}(?:{'|'.join(suffixes)})?(?![a-z])"
    return _cue_pattern(pattern)


def _is_question_clause(clause: str) -> bool:
    stripped = clause.strip()
    if stripped.endswith(("?", "？")):
        return True
    low = stripped.lower()
    return any(
        key in low
        for key in ("any suggestions", "recommendations", "which one", "looking for", "should i", "any advice")
    )


def has_negation(clause: str, start: int) -> bool:
    """Whether the cue at ``start`` is the negator's target.

    A negator applies to the next polarity cue in its comma-free segment, not
    to every cue within N characters.  This keeps "not a lot of support very
    soft" from marking ``soft`` as negated, while "did not find that it
    provided optimal relief" still negates ``relief``.  ``not only`` is
    additive, not negative.
    """
    prefix = clause[:start]
    boundary = max(
        prefix.rfind(","),
        prefix.rfind(" but "),
        prefix.rfind(" and "),
        prefix.rfind(";"),
    )
    offset = boundary + 1 if boundary >= 0 else 0
    # Hyphens and dashes act as word separators: "Pain-NO relief" must see "no".
    segment = prefix[offset:].lower().replace("-", " ").replace("—", " ")
    padded = " " + segment + " "
    negator = ""
    neg_end = -1
    for candidate in NEGATORS:
        idx = padded.rfind(f" {candidate} ")
        if idx >= 0:
            end = idx + len(candidate)  # segment offset of the word end
            if end > neg_end:
                neg_end, negator = end, candidate
    if neg_end < 0 or len(segment) - neg_end > 60:
        return False
    remainder = segment[neg_end:]
    if negator == "not" and re.match(r"\s+only\b", remainder):
        return False
    # Emphatic idioms: "never felt so comfortable" / "can't believe how
    # comfortable" are praise, not negation of the positive cue.
    if negator == "never" and re.match(
        r"\s+(?:felt|been|had|experienced|seen|used)\s+(?:so|this|such|more|better|as)\b", remainder
    ):
        return False
    if negator in {"can't", "cannot"} and re.match(r"\s+believe\s+(?:how|it|this|that)\b", remainder):
        return False
    # "I didn't think it would support my belly but it does" / "I never
    # thought it would make such a difference" negates the reviewer's doubt,
    # not the product's support.
    if negator in {"not", "never", "didn't", "don't", "wasn't", "isn't", "can't", "cannot"} and re.match(
        r"\s+(?:think|thought|sure|expect|expected|believe|realize|realise|imagine|imagined)\b", remainder
    ):
        return False
    # "I cannot stand anything tight" describes an intolerance; the negator
    # does not turn "tight" into praise.
    if negator in {"can't", "cannot", "couldn't"} and re.match(
        r"\s+(?:stand|handle|tolerate|deal with|bear)\b", remainder
    ):
        return False
    # Another polarity cue between the negator and this cue means the negator
    # already bound to that cue.
    for cue in POSITIVE_CUES + NEGATIVE_CUES:
        if re.search(_cue_pattern(cue), remainder):
            return False
    return True


def polarity_of(clause: str) -> str:
    """Cue-level polarity for one clause.

    Every positive cue contributes positive evidence unless a negator binds to
    it; every negative cue contributes negative evidence unless a negator
    binds to it.  The clause is ``mixed`` only when both kinds of evidence
    survive, so "not a lot of support but very soft" does not become a single
    verdict for every aspect in the clause.
    """
    low = clause.lower()
    if _is_question_clause(clause):
        return "unknown"
    pos_hit = False
    neg_hit = False
    for cue in POSITIVE_CUES:
        for match in re.finditer(_cue_pattern(cue), low):
            # "support belt" / "support band" name the product; the word
            # "support" there is a noun, not praise for the product.
            if cue == "cozy" and re.search(r"\bmom\s+$", low[: match.start()]):
                # "Mom Cozy" is the brand, not a softness claim.
                continue
            if cue in {"support", "supports"}:
                after = low[match.end() :]
                # "support belt" / "support band" / "support panels" name a
                # product or one of its parts, not praise for the product.
                if re.match(r"\s*(?:belts?|bands?|panels?|layers?|straps?)\b", after):
                    continue
                # "to support my back" states a purpose, not an evaluation.
                if re.search(r"\bto\s+$", low[: match.start()]) and re.match(
                    r"\s+(?:my|the)\s+(?:back|belly|pelvic|hips?|abdomen)\b", after
                ):
                    continue
                # "for additional support" states a purpose, not praise.
                if re.search(r"\bfor\s+(?:additional\s+|extra\s+|more\s+)?$", low[: match.start()]) and re.match(
                    r"\s*(?:$|[.,;!?])", after
                ):
                    continue
            if has_negation(low, match.start()):
                neg_hit = True
            else:
                pos_hit = True
    for cue in NEGATIVE_CUES:
        for match in re.finditer(_cue_pattern(cue), low):
            if has_negation(low, match.start()):
                pos_hit = True
            else:
                neg_hit = True

    if pos_hit and neg_hit:
        # "helps with back pain": the pain is the condition being relieved,
        # not a product fault.  "relief for a short time then pain again" is
        # not relief; it is a mixed outcome and must abstain.
        if PAIN_NOUN_RE.search(low) and RELIEF_CUE_RE.search(low):
            if re.search(r"\b(?:then|but)\b[^.]{0,60}\b(?:pain|ache|sore)\b", low) or re.search(
                r"\bpain again\b", low
            ):
                return "mixed"
            return "qualified_positive" if any(q in low for q in QUALIFIERS) else "positive"
        return "mixed"
    if neg_hit:
        return "qualified_negative" if any(q in low for q in QUALIFIERS) else "negative"
    if pos_hit:
        return "qualified_positive" if any(q in low for q in QUALIFIERS) else "positive"
    return "unknown"


@dataclass(frozen=True)
class CodeHit:
    """One lexicon match with enough offsets to quote the exact source text."""

    code: Any
    clause: str
    clause_start: int
    clause_end: int
    segment: str
    segment_start: int
    segment_end: int
    match_start: int
    match_end: int
    anchored: bool


def _segment_spans(text: str, clause_start: int, clause_end: int) -> list[tuple[str, int, int]]:
    segments: list[tuple[str, int, int]] = []
    pos = clause_start
    for match in SEGMENT_SPLIT.finditer(text, clause_start, clause_end):
        span = _trim_span(text, pos, match.start())
        if span.clause:
            segments.append((span.clause, span.start, span.end))
        pos = match.end()
    span = _trim_span(text, pos, clause_end)
    if span.clause:
        segments.append((span.clause, span.start, span.end))
    return segments or [(text[clause_start:clause_end], clause_start, clause_end)]


def _segment_anchor_flags(
    segments: list[tuple[str, int, int]], ref_available: bool
) -> list[bool]:
    """Which segments have a product subject, in reading order.

    A segment is product-anchored when it names the product/attribute, when it
    starts with a pronoun that refers to the product, or when it is a bare
    continuation ("soft, comfortable, supportive") of an anchored segment.
    A new subject ("I wore ...", "my back ...", "the union ...") breaks the
    inheritance, and third-party actors/events are never product evidence.
    """
    flags: list[bool] = []
    previous = False
    for segment, _start, _end in segments:
        anchored = bool(PRODUCT_NOUN_RE.search(segment)) or (
            ref_available and bool(ATTRIBUTE_NOUN_RE.search(segment))
        )
        if not anchored and ref_available and REFERENCE_PRONOUN_RE.match(segment):
            anchored = True
        if not anchored and previous and not NEW_SUBJECT_RE.match(segment):
            anchored = True
        if OTHER_PRODUCT_RE.search(segment) and not BAND_NOUN_RE.search(segment):
            anchored = False
        if THIRD_PARTY_RE.search(segment):
            anchored = False
        flags.append(anchored)
        previous = anchored
    return flags


def _segment_index(segments: list[tuple[str, int, int]], offset: int) -> int:
    for i, (_segment, start, end) in enumerate(segments):
        if start <= offset < end:
            return i
    # The match can end exactly on a segment boundary; pick the nearest
    # preceding segment rather than dropping the hit.
    for i in range(len(segments) - 1, -1, -1):
        if segments[i][1] <= offset:
            return i
    return 0


def _self_state_dominates(segment: str, local_offset: int) -> bool:
    """Whether the nearest pain/uncomfortable cue is about the reviewer.

    Only used to gate aspect coding.  Medical annotations still see the text.
    """
    low = segment.lower()
    matches = []
    for cue in SELF_STATE_CUES:
        matches.extend(re.finditer(_cue_pattern(cue), low))
    if not matches:
        return False
    cue = min(matches, key=lambda match: abs(match.start() - local_offset))
    prefix = low[: cue.start()]
    # "helps with lower back pain" / "back pain ... helped a ton" is relief;
    # the pain noun is the condition, not the product fault.
    for relief in RELIEF_CUE_RE.finditer(low):
        if not has_negation(low, relief.start()):
            return False
    self_matches = list(SELF_SUBJECT_RE.finditer(prefix))
    product_matches = list(PRODUCT_SUBJECT_RE.finditer(prefix))
    last_self = self_matches[-1].start() if self_matches else -1
    last_product = product_matches[-1].start() if product_matches else -1
    if last_product > last_self:
        return False
    return last_self >= 0


def _match_codes(
    text: str, codes, anchored_only: bool = False, product_bound: bool = False
) -> list[CodeHit]:
    """Match every taxonomy lexicon, keeping offsets and segment context.

    ``product_bound`` is True for verified-purchase reviews: the record is
    about the item by construction, so the product-noun requirement is waived.
    The segment/third-party checks still run for non-shop sources.
    """
    pool = _clause_pool(text, anchored_only=anchored_only)
    raw_hits: list[CodeHit] = []
    for code in codes:
        patterns = [_lexicon_pattern(pattern) for pattern in code.lexicon]
        for span in pool:
            clause_text = text[span.start : span.end]
            segments = _segment_spans(text, span.start, span.end)
            flags = [True] * len(segments) if product_bound else _segment_anchor_flags(segments, span.ref_available)
            for pattern in patterns:
                for match in re.finditer(pattern, clause_text, re.I):
                    match_start = span.start + match.start()
                    match_end = span.start + match.end()
                    index = _segment_index(segments, match_start)
                    segment, seg_start, seg_end = segments[index]
                    raw_hits.append(
                        CodeHit(
                            code=code,
                            clause=span.clause,
                            clause_start=span.start,
                            clause_end=span.end,
                            segment=segment,
                            segment_start=seg_start,
                            segment_end=seg_end,
                            match_start=match_start,
                            match_end=match_end,
                            anchored=flags[index],
                        )
                    )
    # One hit per code per clause is enough; prefer a hit whose segment is
    # product-anchored over one that merely shares the clause.
    best: dict[tuple[str, int], CodeHit] = {}
    for hit in raw_hits:
        key = (hit.code.code, hit.clause_start)
        current = best.get(key)
        if current is None or (hit.anchored and not current.anchored):
            best[key] = hit
    return list(best.values())


def _evidence_span(
    text: str, segment_start: int, segment_end: int, match_start: int, match_end: int, limit: int = 120
) -> tuple[int, int, str]:
    """Return a source-aligned quote of at most ``limit`` characters."""
    segment_start = max(0, segment_start)
    segment_end = min(len(text), segment_end)
    if segment_end - segment_start <= limit:
        return segment_start, segment_end, text[segment_start:segment_end]
    core = max(1, match_end - match_start)
    start = max(segment_start, match_start - max(0, limit - core) // 2)
    end = min(segment_end, start + limit)
    if end - start < limit:
        start = max(segment_start, end - limit)
    return start, end, text[start:end]


@dataclass
class Annotation:
    """One coded label with a source-aligned quote.

    ``span_start``/``span_end`` are 0-based, end-exclusive offsets into
    ``f"{record.title}. {record.text}"`` (into ``record.text`` when the title
    is empty).  ``span_text`` is always ``source_text[span_start:span_end]``
    and is capped at 120 characters.
    """

    canonical_id: str
    axis: str
    code: str
    polarity: str
    evidence_span: str
    taxonomy_version: str = TAXONOMY_VERSION
    coder_id: str = "rule-v1"
    span_start: int = -1
    span_end: int = -1
    span_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class CodedRecord:
    canonical_id: str
    annotations: list[Annotation] = field(default_factory=list)
    unknown_aspects: list[dict[str, Any]] = field(default_factory=list)
    medical_flags: list[str] = field(default_factory=list)
    journey_stage: str = "unknown"
    outcome: str = "OUT.UNKNOWN"
    gap: str = "unknown"
    claim_relation: str = "not_assessed_at_G7"
    codes_hit: list[str] = field(default_factory=list)
    # E-merge §2: ``product_match`` says whether the record is about the
    # product family; ``experience_scope`` says how substantive the first-hand
    # evaluation is.  They are orthogonal and neither one can override the
    # other.  ``product_match`` is copied from the canonical record so the
    # gate can be evaluated on a coded record alone.
    product_match: str = ""
    experience_reason: str = ""
    # ``full`` = substantive attributable evaluation; ``partial`` =
    # attributable first-hand evaluation that is incidental or undetermined;
    # ``none`` = no attributable evaluation.  This field is the single
    # authority for the experience layer.
    experience_scope: str = ""
    # ``relayed`` = direct purchaser relaying a family member's or friend's use.
    experience_source: str = "first_person"
    # E-merge §2.4 also requires a non-empty body, not just a title.
    text_present: bool = True
    product_match_source: str = "auto"
    product_match_override_reason: str = ""
    contract_version: str = "E-merge/1"

    def __post_init__(self) -> None:
        if self.experience_scope not in EXPERIENCE_SCOPES:
            self.experience_scope = "none"
        if self.experience_source not in EXPERIENCE_SOURCES:
            self.experience_source = "first_person"
        if self.experience_scope == "none":
            # Forbidden combination E-merge §2.3(2): no evaluation to relay.
            self.experience_source = "first_person"

    @property
    def has_evaluation(self) -> bool:
        """Whether the scope assessment found an attributable evaluation."""
        return has_evaluation(self.experience_scope)

    @property
    def in_cohort(self) -> bool:
        """E-merge §2.2 ``in_cohort`` predicate."""
        return in_experience_cohort(self.product_match, self.experience_scope)

    @property
    def emit_aspects(self) -> bool:
        """E-merge §2.4 ``emit_aspects`` predicate."""
        return self.in_cohort and self.text_present

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "annotations": [a.to_dict() for a in self.annotations],
            "unknown_aspects": self.unknown_aspects,
            "medical_flags": self.medical_flags,
            "journey_stage": self.journey_stage,
            "outcome": self.outcome,
            "gap": self.gap,
            "claim_relation": self.claim_relation,
            "codes_hit": self.codes_hit,
            "product_match": self.product_match,
            "product_match_source": self.product_match_source,
            "product_match_override_reason": self.product_match_override_reason,
            # Deprecated derived view (E-merge §3.2).  It equals ``in_cohort``
            # and is never read as a gate by this pipeline.  Keep it for one
            # release so old consumers do not silently treat it as false.
            "experience": self.in_cohort,
            "experience_reason": self.experience_reason,
            "experience_scope": self.experience_scope,
            "experience_source": self.experience_source,
            "contract_version": self.contract_version,
        }


def _is_reddit_comment(rec: CanonicalRecord) -> bool:
    """Whether a Reddit record is a comment rather than a top-level post.

    Comment URLs are ``/comments/<thread>/<slug>/<comment_id>/``; posts have
    only ``/comments/<thread>/<slug>/``.  A question inside a comment is
    normally a reply to another person ("Have you tried them?"), not the
    author collecting opinions for their own decision.
    """
    if rec.source != "reddit":
        return False
    parts = [part for part in (rec.url or "").split("/comments/")[-1].split("/") if part]
    return len(parts) >= 3


def help_seeking(rec: CanonicalRecord) -> bool:
    """Whether the author is asking for help/recommendations for their own case.

    A2: this is no longer a scope trigger.  A question title or request body
    does not downgrade a substantive evaluation and does not upgrade a
    symptom-only post.  The function is retained as a reason label and for
    diagnostics; :func:`assess_experience_scope` decides the scope from the
    body's evaluation content.  Current corpus examples: B06 ``c-1vztlvl``,
    B13 ``c-1tue1fz`` and B18 ``c-1q2ir63`` remain ``partial`` because their
    evaluation is incidental, not because their titles are questions.
    """
    if rec.source == "tiktok_shop":
        return False
    if _is_reddit_comment(rec):
        return False
    title = (rec.title or "").strip()
    body = rec.text or ""
    if HELP_SEEK_RE.search(f"{title}\n{body}"):
        return True
    # "?!" and "?" both close a request title.  Strip whitespace and
    # exclamation marks but keep the question mark, so "instore?!" still ends
    # with "?".  Social questions that do not ask for a product decision are
    # not requests.
    if title.rstrip(" !.。！").endswith(("?", "？")) and not SOCIAL_TITLE_QUESTION_RE.search(title):
        return True
    return False


# Backwards-compatible internal name used by the rule coder.
_is_help_seeking = help_seeking


def _sentence_containing(text: str, span: str) -> str:
    """The sentence around ``span``, using the same source text as the coder."""
    index = text.find(span)
    if index < 0:
        return ""
    start = index
    while start > 0 and text[start - 1] not in ".!?\n":
        start -= 1
    end = index + len(span)
    while end < len(text) and text[end] not in ".!?\n":
        end += 1
    if end < len(text):
        end += 1
    return text[start:end]


def _has_polarity_cue(low: str) -> bool:
    """A polarity cue that is an evaluation, not a product noun or purpose."""
    for cue in POSITIVE_CUES + NEGATIVE_CUES:
        for match in re.finditer(_cue_pattern(cue), low):
            if cue in {"support", "supports"}:
                after = low[match.end() :]
                if re.match(r"\s*(?:belts?|bands?|panels?|layers?|straps?)\b", after):
                    continue
                if re.search(r"\bto\s+$", low[: match.start()]) and re.match(
                    r"\s+(?:my|the)\s+(?:back|belly|pelvic|hips?|abdomen)\b", after
                ):
                    continue
                if re.search(
                    r"\bfor\s+(?:additional\s+|extra\s+|more\s+)?$", low[: match.start()]
                ) and re.match(r"\s*(?:$|[.,;!?])", after):
                    continue
            return True
    return False


def _has_current_evaluation(text: str) -> bool:
    """Whether a non-past segment evaluates the product (side effects count).

    The product noun and the polarity cue must sit in the same comma/dash
    segment.  "My back is in pain, it will take days to get a belly band"
    mentions both, but the pain is a symptom and the band is a logistics
    complaint, not an evaluation.
    """
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if not sentence.strip() or PAST_MARKER_RE.search(sentence):
            continue
        for segment in SEGMENT_SPLIT.split(sentence):
            if not PRODUCT_NOUN_RE.search(segment):
                continue
            if _has_polarity_cue(segment.lower()):
                return True
    return False


def is_past_unspecified_evaluation(rec: CanonicalRecord, spans: list[str]) -> bool:
    """Whether every quoted evaluation is a past, unnamed-product mention.

    Retained for artifact comparisons and tests.  A2's scope evaluator now
    applies the same past/named-product rule clause by clause; this helper is
    no longer the scope trigger.  A named brand/model is attributable even in
    the past, and any current product evaluation keeps the record ``true``.
    Current corpus: B01 ``c-1sn8eo1`` and B17 ``c-1x65j91`` are the two
    background-only cases.  ``c-1ofb8c1`` contains "she is my first" (first
    child), which must not count as a past-product marker.
    """
    source_text = f"{rec.title}. {rec.text}" if rec.title else rec.text
    if BRAND_MODEL_RE.search(source_text):
        return False
    real_spans = [span for span in spans if span]
    if not real_spans:
        # No codeable aspect: a current side-effect evaluation still counts
        # (the leg-pain case has no taxonomy aspect), so only a record with no
        # current evaluation at all is background.
        return not _has_current_evaluation(source_text)
    for span in real_spans:
        sentence = _sentence_containing(source_text, span)
        if not PAST_MARKER_RE.search(sentence):
            return False
    return True


def experience_source(rec: CanonicalRecord, notes: str = "") -> str:
    """``relayed`` when a direct purchaser relays a family member's use.

    Current corpus: ``c-7659258409535112974`` (B16, "Bought for my daughter
    and she said ..."), ``c-7695606260216399630`` ("My wife loves the belt
    ...") and ``c-7698978357326268173`` ("Definitely has helped my wife with
    her back ...") are the relayed records.
    """
    text = f"{rec.title} {rec.text}"
    if RELAYED_RE.search(text) or "relayed" in (notes or "").lower():
        return "relayed"
    return "first_person"


# --- A2 experience scope ---------------------------------------------------
# A2 redefinition: ``partial`` is an attributable first-hand product
# evaluation that is incidental or undetermined.  It is not a title-shape
# proxy.  The title never enters this calculation, and the unit is the clause
# rather than the bare polarity phrase, so the subject and context of an
# evaluation count toward ``C``.
#
# Decision table (A2, revised against the blind three-judge consensus):
#   R0 no attributable evaluation                         -> none
#   R1 undetermined current use only                      -> partial
#   R2 one decisive clause (>= 2 families, >= 1 specific) -> full
#   R3 A >= 2, >= 1 specific, S >= 0.15 or P >= 0.20      -> full
#   R4 C >= 500, A >= 2, >= 1 specific                    -> full
#   R5 N >= 2, S >= 0.35, >= 1 specific                   -> full
#   R6 N >= 3, S >= 0.25, >= 1 specific                   -> full
#   R7 N >= 2, P >= 0.40, >= 1 specific                   -> full
#   R8 otherwise                                          -> partial
#
# A = attribute families, C = evaluation characters, N = evaluations,
# S = evaluation share of the body, P = evaluation share of the densest
# paragraph.  "Specific" excludes the generic overall/support families, so a
# short "love it / very supportive" endorsement stays partial.
#
# These thresholds come from the blind majority over 54 records (see the
# 2026-10-30 scope review), not from any single record.  R2 and R3's P branch
# are what restore decisive results that are a small share of a long narrative.
#
# Tightening set T1-T8 (2026-10-30).  Every rule below comes from the blind
# three-judge majority, not from one sample.  Each line states the false
# conflicts it removes and the true positives it must keep:
#   T1 anchor tightening (question/request mentions do not anchor; bare
#      plurals and generic advice need a first-person, definite, brand, or use
#      anchor): removes X30, X16(a), X37, X31, X48, X45; keeps all 17
#      judge-full records and drops no experience=true record to none.
#   T2 efficacy summary only at clause start: removes X52 and X16(b); X35
#      ("Nothing helps!") becomes the known none miss, kept on purpose.
#   T3 purpose phrase / noun guard: removes X14, X38, X42(help); keeps
#      past-tense helped (X03/X22/X44) and "the support doesn't last" (X10).
#   T4 request and passive-recommend guard: removes X42, X39, X32(request);
#      active "I recommend it" still evaluates.
#   T5 hearsay extension ("she used", "my friend said", "some say"): removes
#      X02, X32; first-person "I used/felt" is unaffected.
#   T6 apostrophe normalisation before every guard: removes X51; no semantic
#      loss, the curly quote only stopped the guard from matching.
#   T7 negated-intolerance guard ("can't stand/handle/tolerate"): removes
#      X33 and the X18 root cause; "it doesn't hurt anymore" still counts.
#   T8 cue table cleanup (drop "fine" and one-off phrases, bound "way
#      better"): removes X21; X10 stays full without "fine".

# Cue -> (direction, attribute family).  Standard coder cues are included so
# the scope layer does not depend on the aspect taxonomy (A2 §6.5: v2 aspect
# coverage is incomplete; evaluation-sentence extraction must stand alone).
_SCOPE_CUE_FAMILY: dict[str, tuple[str, str]] = {
    # support / relief
    "support": ("pos", "support"),
    "supports": ("pos", "support"),
    "supportive": ("pos", "support"),
    "helped": ("pos", "support"),
    "helps": ("pos", "support"),
    "help": ("pos", "support"),
    "helping": ("pos", "support"),
    "relief": ("pos", "support"),
    "relieved": ("pos", "support"),
    "relieves": ("pos", "support"),
    "works": ("pos", "support"),
    "worked": ("pos", "support"),
    "saved": ("pos", "support"),
    "remedied": ("pos", "support"),
    "fixes": ("pos", "support"),
    "fix": ("pos", "support"),
    "functional": ("pos", "activity"),
    "solid": ("pos", "support"),
    # comfort
    "comfortable": ("pos", "comfort"),
    "comfy": ("pos", "comfort"),
    "soft": ("pos", "comfort"),
    "cozy": ("pos", "comfort"),
    "nice": ("pos", "comfort"),
    # breathability / appearance / durability / value / overall
    "breathable": ("pos", "breathability"),
    "invisible": ("pos", "appearance"),
    "discreet": ("pos", "appearance"),
    "cute": ("pos", "appearance"),
    "no one could tell": ("pos", "appearance"),
    "nobody could tell": ("pos", "appearance"),
    "durable": ("pos", "durability"),
    "worth": ("pos", "value"),
    "favorite": ("pos", "overall"),
    "love": ("pos", "overall"),
    "loved": ("pos", "overall"),
    "perfect": ("pos", "overall"),
    "amazing": ("pos", "overall"),
    "great": ("pos", "overall"),
    "recommend": ("pos", "overall"),
    "recommended": ("pos", "overall"),
    "good": ("pos", "overall"),
    "trusty": ("pos", "overall"),
    "incredible": ("pos", "overall"),
    "convenient": ("pos", "function"),
    "benefit": ("pos", "support"),
    "feels better": ("pos", "overall"),
    "felt better": ("pos", "overall"),
    "feel better": ("pos", "overall"),
    "huge difference": ("pos", "overall"),
    "difference": ("pos", "overall"),
    # stability
    "stays in place": ("pos", "stability"),
    "stayed in place": ("pos", "stability"),
    "stays put": ("pos", "stability"),
    "stay put": ("pos", "stability"),
    "doesn't slip": ("pos", "stability"),
    "didn't slip": ("pos", "stability"),
    # comfort / skin / fit negatives
    "uncomfortable": ("neg", "comfort"),
    "hurt": ("neg", "comfort"),
    "hurts": ("neg", "comfort"),
    "hurting": ("neg", "comfort"),
    "pain": ("neg", "comfort"),
    "painful": ("neg", "comfort"),
    "ache": ("neg", "comfort"),
    "aches": ("neg", "comfort"),
    "uncomfy": ("neg", "comfort"),
    "stiff": ("neg", "comfort"),
    "worse": ("neg", "comfort"),
    "make things worse": ("neg", "comfort"),
    "didn't stop": ("neg", "comfort"),
    "didn’t stop": ("neg", "comfort"),
    "too long": ("neg", "comfort"),
    "break out": ("neg", "skin"),
    "breakout": ("neg", "skin"),
    "bacne": ("neg", "skin"),
    "chafe": ("neg", "skin"),
    "chafed": ("neg", "skin"),
    "chafing": ("neg", "skin"),
    "rash": ("neg", "skin"),
    "itchy": ("neg", "skin"),
    "itch": ("neg", "skin"),
    "dig": ("neg", "comfort"),
    "digs": ("neg", "comfort"),
    "digging": ("neg", "comfort"),
    "cut into": ("neg", "comfort"),
    "cuts into": ("neg", "comfort"),
    # stability negatives
    "slipped": ("neg", "stability"),
    "slips": ("neg", "stability"),
    "slip": ("neg", "stability"),
    "slides": ("neg", "stability"),
    "slide": ("neg", "stability"),
    "slid": ("neg", "stability"),
    "rolled down": ("neg", "stability"),
    "rolls down": ("neg", "stability"),
    "roll down": ("neg", "stability"),
    "bunch": ("neg", "stability"),
    "bunches": ("neg", "stability"),
    # fit / breathability / value / overall negatives
    "too tight": ("neg", "fit"),
    "too loose": ("neg", "fit"),
    "tight": ("neg", "fit"),
    "too small": ("neg", "fit"),
    "too big": ("neg", "fit"),
    "too large": ("neg", "fit"),
    "too short": ("neg", "fit"),
    "sweaty": ("neg", "breathability"),
    "too hot": ("neg", "breathability"),
    "hot": ("neg", "breathability"),
    "warmer": ("neg", "breathability"),
    "useless": ("neg", "overall"),
    "waste": ("neg", "value"),
    "waste of money": ("neg", "value"),
    "disappointed": ("neg", "overall"),
    "disappointing": ("neg", "overall"),
    "not worth": ("neg", "value"),
    "overpriced": ("neg", "value"),
    "expensive": ("neg", "value"),
    "cheap": ("neg", "value"),
    "returned": ("neg", "return"),
    "returning": ("neg", "return"),
    "refund": ("neg", "return"),
    "didn't work": ("neg", "support"),
    "doesn't work": ("neg", "support"),
    "didn't help": ("neg", "support"),
    "doesn't help": ("neg", "support"),
    "no difference": ("neg", "support"),
    "no support": ("neg", "support"),
    "not supportive": ("neg", "support"),
    "lack of support": ("neg", "support"),
    "fell apart": ("neg", "durability"),
    "wore out": ("neg", "durability"),
    "stretched out": ("neg", "durability"),
    "lost elasticity": ("neg", "durability"),
    "regret": ("neg", "overall"),
    "hate": ("neg", "overall"),
    "bad": ("neg", "overall"),
    "poor": ("neg", "overall"),
    "annoying": ("neg", "overall"),
    # support negatives that read as an evaluation
    "doesn't fix": ("neg", "support"),
    "didn't fix": ("neg", "support"),
    "doesn’t fix": ("neg", "support"),
}

_SCOPE_CUE_PATTERNS: dict[str, re.Pattern[str]] = {
    cue: re.compile(_lexicon_pattern(cue) if re.fullmatch(r"[a-z]+", cue) else _cue_pattern(cue))
    for cue in _SCOPE_CUE_FAMILY
}

# Multi-word expressions that are general English, not one record's wording.
# They live as patterns because their component words ("better", "through",
# "gone") are too broad to be cues on their own.  Each entry is
# ``(direction, attribute family, pattern)``.
_SCOPE_CUE_REGEX: dict[str, tuple[str, str, re.Pattern[str]]] = {
    "degree better": (
        "pos",
        "overall",
        re.compile(r"\b(?:way|much|far|a lot|so much|significantly|vastly)\s+better\b", re.I),
    ),
    "night and day": (
        "pos",
        "overall",
        re.compile(r"\b(?:night and day|day and night)\b", re.I),
    ),
    "enabled activity": (
        "pos",
        "activity",
        re.compile(
            r"\b(?:got|get|gets|getting|helped|helps)\s+me\s+through\b"
            r"|\b(?:back to|able to|can (?:now )?|could)\s+"
            r"(?:walk|run|sprint|jog|play|work|sleep|move|exercise|lift|stand|sit|"
            r"breathe|bend|kneel)\w*\b",
            re.I,
        ),
    ),
    "symptom relief": (
        "pos",
        "relief",
        re.compile(
            r"\b(?:pain|ache|discomfort|soreness)\s+(?:is|are|was|were)?\s*"
            r"(?:finally |completely |totally |all |now )*(?:gone|away)\b",
            re.I,
        ),
    ),
    "weight off": (
        "pos",
        "relief",
        re.compile(r"\b(?:weight|pressure)\s+(?:off|is off|off of|lifted|is lifted)\b", re.I),
    ),
    "needs more": (
        "neg",
        "support",
        re.compile(
            r"\b(?:need|needs|needed|want|wants|wanted|wish)\s+(?:something |a bit )?more\b",
            re.I,
        ),
    ),
    "body problem": (
        "neg",
        "safety",
        re.compile(
            r"\b(?:leg|legs|thigh|thighs|hip|hips|back|pelvis|pelvic|groin)\s+"
            r"(?:issues?|problems?|pain|numbness|tingling|spasms?|cramps?)\b",
            re.I,
        ),
    ),
    "body simile": (
        "neg",
        "comfort",
        re.compile(r"\b(?:felt|feel|feels)\s+like\s+(?:jello|jelly|rubber|noodles|lead)\b", re.I),
    ),
}

# General English idioms for "not decided yet".  These are deliberately
# generic: any one of them signals an undetermined evaluation in any corpus.
_SCOPE_UNDETERMINED_RE = re.compile(
    r"jury is still out|not sure if|not sure whether|not sure which|hard to (?:say|tell)|"
    r"can't tell|cannot tell|no idea if|time will tell|too early to tell|"
    r"remains? to be seen|don't know if|do not know if",
    re.I,
)
_SCOPE_EXPLETIVE_RE = re.compile(
    r"^\s*(?:it seems|it feels|it looks|it appears|it turns out|it's|it’s)\b", re.I
)
_SCOPE_HYPOTHETICAL_RE = re.compile(
    r"\b(?:i'm worried|im worried|worried|afraid|concerned)\b[^.]{0,100}\b(?:will|would|'ll|’ll|might|may|could)\b"
    r"|\b(?:might|may|could|would)\s+(?:feel|be|get|end up)\b",
    re.I,
)
_SCOPE_REQUEST_RE = re.compile(
    r"\b(?:any advice|any suggestions?|recommendations?|recs?\b|would love|would appreciate|"
    r"i'd (?:really )?appreciate|i would (?:really )?appreciate|"
    r"thanks in advance|thank you in advance|appreciate any|looking for|pls drop|please drop|"
    r"if something was|honest opinions|any tips|any ideas|drop the brand|would honestly save|"
    r"any one have|anyone have|has anyone|does anyone|anyone else|what ended up|what was totally|"
    r"anything you|please tell me|tell me which|what should i|how should i)\b",
    re.I,
)
_SCOPE_COURTESY_RE = re.compile(
    r"\b(?:i hope (?:this|it) helps|hope this helps|just wanted to share|"
    r"thanks for (?:listening|reading)|wish me luck)\b",
    re.I,
)
# The prefix of a symptom cue that is about the author's body ("when it's
# particularly …", "I still …", "my …"), not about the product ("the support
# is bad").
_SCOPE_SELF_STATE_PREFIX_RE = re.compile(
    r"\b(?:i|i'm|i am|i feel|i felt|it|it's|it is|it was|feels?|felt|my|our)\s+"
    r"(?:(?:still|particularly|really|so|pretty|very|now|just|a bit|getting)\s+)*$",
    re.I,
)
_SCOPE_HEARSAY_RE = re.compile(
    HEARSAY_RE.pattern
    + r"|\breviews?\s+(?:look|looks|say|says|are|mention|mentions|note|notes|state|states)\b"
    r"|\bi keep hearing\b"
    # "she said/felt", "my friend used it and swears by it": a relayed
    # evaluation is not first-hand.  The pronoun must be the subject of an
    # evaluation verb, so "she is my first" (first child) is not matched.
    r"|\b(?:she|he)\s+(?:said|says|felt|feels|thinks|thought|loves|loved|likes|liked|"
    r"recommended|recommends|swears?|swore|used|uses|tried|tries|had|has|got|gets)\b"
    r"|\b(?:my|a|her|his|their|our)\s+(?:best\s+)?(?:friend|sister|mother|mom|wife|husband|"
    r"daughter|son|coworker|colleague|neighbour|neighbor)\b[^.]{0,60}"
    r"\b(?:said|says|used|uses|loves|loved|liked|recommended|recommends|swears?|swore|"
    r"told me|got|had|helped)\b"
    r"|\b(?:some|other|many|most)\s+(?:people|moms|women|folks)\s+(?:say|said|think|love|swear|recommend)\b"
    r"|\b(?:some|others?|many|most)\s+(?:say|said|think|swear|love|recommend)\b"
    r"|\b(?:people|moms|women|folks)\s+on\s+\w+\s+(?:love|say|swear|recommend)\b",
    re.I,
)
_SCOPE_THIRD_PARTY_RE = re.compile(
    r"\b(?:union|strike|striking|picketing|picket|colleagues|organizers?|husband|family|"
    r"midwife|doctors?|nurse|government|labor rights)\b",
    re.I,
)
# An infinitive of purpose ("to support my pelvic", "for additional support")
# states what the product is for; it is not an observed evaluation.  "to feel
# the benefit" is not in this list: it describes a result the author felt.
_SCOPE_PURPOSE_RE = re.compile(
    r"\b(?:to|for)\s+(?:additional\s+|extra\s+|more\s+|some\s+|the\s+|my\s+)?"
    r"(?:support|help|relief|comfort|compression|stability)\b",
    re.I,
)
# A passive recommendation is not the author's own evaluation.
_SCOPE_PASSIVE_RECOMMEND_RE = re.compile(
    r"\b(?:was|were|is|are|been|being|got)\s+recommended\b", re.I
)
_SCOPE_CONSIDERATION_RE = re.compile(
    r"\b(?:eyeing|looking into|thinking about|considering|want to (?:buy|get|try)|"
    r"planning to (?:buy|get|try)|thinking of (?:buying|getting|trying)|on the market for|"
    r"trying to find|looking for|shopping for|researching|thinking of getting)\b",
    re.I,
)
# A concrete product noun of any kind: scope asks whether the author gives a
# substantive first-hand product evaluation, not whether the product is the
# belly band.  Product identity is a separate field (``product_match``).
_SCOPE_BELLY_PHRASE_RE = re.compile(
    r"\b(?:belly bands?|maternity bands?|support bands?|belly support|back support|"
    r"waistbands?|momcozy|ergonest|fitsplint|frida(?:\s+mom)?|keababies)\b",
    re.I,
)
_SCOPE_ANY_PRODUCT_RE = re.compile(
    _SCOPE_BELLY_PHRASE_RE.pattern
    # Support tapes are the usual comparator in this corpus, so a multi-product
    # comparison can anchor both sides.
    + r"|\b(?:kt|kinesiology|athletic|sports)\s+tape\b",
    re.I,
)
_SCOPE_BARE_PRODUCT_RE = re.compile(r"\b(?:bands?|belts?|straps?|velcro|wraps?)\b", re.I)
_SCOPE_FIRST_PERSON_RE = re.compile(
    r"\b(?:i|i'm|i’m|i've|i’ve|i'd|i’d|we|we're|we’re|we've|my|our)\b", re.I
)
_SCOPE_USE_VERB_RE = re.compile(
    r"\b(?:used?|using|wore|wear|wearing|tried|trying|have|had|got|put|putting|bought|"
    r"ordered|started|switched|switching|grabbed|picked up|took|take|taken|removed|"
    r"adjust(?:ed|ing)?|loosen(?:ed|ing)?|strap(?:ped|ping)?|gives?|gave|give)\b",
    re.I,
)
_SCOPE_COPULA_AFTER_RE = re.compile(
    r"^\s*(?:just|really|also|still|only|sometimes|now|a bit|a little|basically|definitely|actually)?"
    r"\s*(?:is|was|are|were|feels?|felt|seems?|stays?|stayed|keeps?|kept|works?|worked|"
    r"helps?|helped|does|did|doesn't|didn't|isn't|wasn't|can|could|will|would|has|have)\b",
    re.I,
)
_SCOPE_PRONOUN_EVAL_RE = re.compile(
    r"\b(?:it|its|it's|it’s|they|them|these|those|this)\s+(?:is|was|are|were|feels?|felt|"
    r"stays?|stayed|keeps?|kept|works?|worked|working|helps?|helped|helping|"
    r"does|did|doesn't|didn't|isn't|wasn't|never|also|just|only|really|actually|"
    r"definitely|still)\b",
    re.I,
)
_SCOPE_ATTR_SUBJECT_RE = re.compile(
    r"\b(?:the|my|this|that|its|our)\s+(?:fabric|material|design|sizing|size|padding|"
    r"closure|seams?|stitching|elastic|support|compression|velcro|strap|waistband)\s+"
    r"(?:is|was|feels?|felt|stays?|keeps?|works?|helps?|doesn't|didn't|isn't|can|will|"
    r"would|has)\b",
    re.I,
)
_SCOPE_NARROW_SPECIFIC_RE = re.compile(
    r"\b(?:weight off|weight is lifted|pressure off|fix(?:es|ed)?|help(?:s|ed|ing)?|"
    r"eas(?:e|es|ed|ing)|reliev(?:e|es|ed|ing)|stop|scratch(?:es|ed|ing)?|lift|"
    r"rolled? (?:down|up)|rolls? (?:down|up)|slides?|slips?|stays? put|compression|"
    r"velcro|straps?|fabric|sizing|breathab\w*|chafe|rash|tight|loose|durab\w*|padding)\b",
    re.I,
)
_SCOPE_PREFERENCE_RE = re.compile(
    r"\b(?:love|loved|like|liked|prefer|recommend)\b", re.I
)
_SCOPE_ADJECTIVE_PRAISE_RE = re.compile(
    r"^\s*(?:very|really|super|so|pretty|quite)?\s*(?:supportive|comfortable|comfy|soft|"
    r"great|good|nice|amazing|perfect|invisible|discreet|convenient|incredible)\b",
    re.I,
)
_SCOPE_COMFORT_PRAISE_RE = re.compile(
    r"\bit(?:'s|’s| is)\s+(?:super|really|very|so|pretty|quite)?\s*"
    r"(?:comfortable|comfy|soft|good|great|nice)\b",
    re.I,
)
_SCOPE_PRODUCT_VERB_RE = re.compile(
    r"(?:belly band|maternity band|support band|band|belt|strap|velcro)\b[^.]{0,40}"
    r"\b(?:is|was|are|were|feels?|felt|gives?|gave|will|can|does|did|helps?|helped|"
    r"works?|worked|stays?|keeps?)\b",
    re.I,
)
_SCOPE_SELF_BODY_RE = re.compile(
    r"\b(?:my (?:belly|body|bump|stomach)|b-belly|weight gain|looks? chunky)\b", re.I
)
_SCOPE_NEGATED_USE_RE = re.compile(
    r"\b(?:don't|do not|didn't|no longer|stopped)\s+(?:even\s+)?(?:wear|wearing|use|using)\b",
    re.I,
)
_SCOPE_SUMMARY_RE = re.compile(
    r"^\s*(?:nothing|none of (?:it|them|these|those)|no amount of)\b", re.I
)
# Only an efficacy summary ("nothing helps", "no amount of … works") may
# stand in for a product evaluation.  "Nothing brings me more joy" is not one.
_SCOPE_EFFICACY_SUMMARY_RE = re.compile(
    r"^\s*(?:nothing\s+(?:helps?|works?|has helped)|"
    r"none of\s+(?:it|them|these|those)\s+(?:helps?|works?)|no amount of)\b",
    re.I,
)
_SCOPE_CURRENT_USE_RE = re.compile(
    r"\b(?:i(?:'m| am)? (?:now )?(?:using|wearing)|i just started using|i started using|"
    r"i have (?:the|a|my)|i got (?:the|a|my)|i just got|currently using|"
    r"wearing (?:it|the|a|my)|put (?:it|one|a band|the band) on)\b",
    re.I,
)
_SCOPE_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_SCOPE_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class ExperienceScopeAssessment:
    """A2 signals for one record.  ``scope`` is the published value."""

    scope: str
    evaluations: int
    evaluation_chars: int
    evidence_share: float
    attributes: int
    undetermined_use: bool
    reason: str
    evidence: tuple[str, ...] = ()


def _normalise_apostrophes(text: str) -> str:
    # Length-preserving, so clause offsets stay valid.
    return text.replace("’", "'").replace("‘", "'")


def _scope_strip_question_tail(clause: str) -> str:
    """Drop a request tail from an evaluation clause.

    ``which does help sometimes but I'm just wondering ...?`` still carries an
    evaluation; the question tail must not erase it.
    """
    low = clause.lower()
    match = re.search(r"\bbut\s+i(?:'m|’m| am)\s+just\s+wondering\b", low)
    if match and match.start() > 0:
        return clause[: match.start()]
    for marker in (" but i'm just wondering", " but i am just wondering",
                   ", but i'm just wondering", ", but i am just wondering"):
        index = low.find(marker)
        if index > 0:
            return clause[:index]
    if clause.strip().endswith("?"):
        match = re.search(r"\bbut\b", low)
        if match and match.start() > 0:
            return clause[: match.start()]
    return clause


def _scope_cue_hits(text: str) -> list[tuple[int, str, str]]:
    low = _normalise_apostrophes(text.lower())
    hits: list[tuple[int, str, str]] = []
    for cue, (direction, _family) in _SCOPE_CUE_FAMILY.items():
        for match in _SCOPE_CUE_PATTERNS[cue].finditer(low):
            if cue == "cozy" and re.search(r"\bmom\s+$", low[: match.start()]):
                # "Mom Cozy" is the brand, not a softness claim.
                continue
            hits.append((match.start(), cue, direction))
    for cue, (direction, _family, pattern) in _SCOPE_CUE_REGEX.items():
        for match in pattern.finditer(low):
            hits.append((match.start(), cue, direction))
    return sorted(hits)


def _scope_drop_modifier_cue(low: str, cue: str, start: int) -> bool:
    """``a cheap belly band`` / ``cheaper bands I tried`` modifies another item."""
    if cue not in {"cheap", "cheaper", "expensive"}:
        return False
    after = low[start : start + 34]
    before = low[max(0, start - 24) : start]
    if re.search(r"\b(?:belly )?bands?\b", after) and re.search(
        r"(?:a |the |some |those |these |other |than .{0,18})$", before
    ):
        return True
    return False


def _scope_support_is_noun(low: str, start: int) -> bool:
    """Whether "support" is a noun (a product attribute), not praise.

    "The support is weak", "belly band support" and "support belt" describe
    the item, so the word alone must not count as a positive evaluation.
    """
    after = low[start + len("support") : start + len("support") + 34]
    if re.match(r"\s*(?:belt|band|panel|layer|strap)s?\b", after):
        return True
    if re.match(r"\s*(?:doesn't|does not|is|was|lasts?|isn't)\b", after):
        return True
    before = low[max(0, start - 24) : start]
    return bool(
        re.search(
            r"\b(?:the|of|on|for|provide|gives?|decent|strong|great|belly band|back)\s+$",
            before,
        )
    )


def _scope_cue_is_purpose(low: str, start: int) -> bool:
    """Whether the cue at ``start`` is inside ``to support`` / ``for relief``."""
    for match in _SCOPE_PURPOSE_RE.finditer(low):
        if match.start() <= start < match.end():
            return True
    return False


def _scope_self_state_prefix(low: str, start: int) -> bool:
    """Whether a symptom cue's grammatical subject is the author's body.

    The self pronoun may be separated from the cue by the body part
    ("my pelvic and groin pain"), so the check uses a short window and stops
    at a product mention: "my band's support is bad" is about the product.
    """
    window = low[max(0, start - 50) : start]
    if not re.search(
        r"\b(?:i|i'm|i am|i feel|i felt|it|it's|it is|it was|feels?|felt|my|our)\b",
        window,
    ):
        return False
    return not _scope_mentions_product(window)


def _scope_effective_hits(clause: str) -> list[tuple[int, str, str]]:
    low = _normalise_apostrophes(clause.lower())
    relief_spans = [
        (match.start(), match.end())
        for match in _SCOPE_CUE_REGEX["symptom relief"][2].finditer(low)
    ]
    passive_recommend = _SCOPE_PASSIVE_RECOMMEND_RE.search(low)
    hits: list[tuple[int, str, str]] = []
    for start, cue, direction in _scope_cue_hits(clause):
        if _scope_drop_modifier_cue(low, cue, start):
            continue
        if cue in {"support", "supports"} and _scope_support_is_noun(low, start):
            continue
        if cue in {"pain", "painful", "ache", "aches"} and any(
            span_start <= start < span_end for span_start, span_end in relief_spans
        ):
            # "my pain is GONE" is relief, not a negative self-state.
            continue
        if _scope_cue_is_purpose(low, start):
            continue
        if (
            cue in {"recommend", "recommended"}
            and passive_recommend is not None
            and passive_recommend.start() <= start < passive_recommend.end()
        ):
            continue
        effective = direction
        if has_negation(low, start):
            effective = "pos" if direction == "neg" else "neg"
        hits.append((start, cue, effective))
    return hits


_SCOPE_SYMPTOM_CUES = {
    "pain",
    "painful",
    "ache",
    "aches",
    "hurt",
    "hurts",
    "hurting",
    "uncomfortable",
    "bad",
    "worse",
}
_SCOPE_ADVERSE_CUES = _SCOPE_SYMPTOM_CUES | {"body problem", "body simile"}


def _scope_polarity(clause: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Decisive polarity for one evaluation clause.

    Unlike :func:`polarity_of`, this runs on apostrophe-normalised text and
    includes the A2 cue extensions ("helping", "worse", "relief", ...).
    """
    clause = _scope_strip_question_tail(clause)
    # A parenthetical aside that does not name the product ("downhills
    # outside are a little uncomfy") is not evidence about the product.  Keep
    # the span length so cue offsets stay valid.
    clause = re.sub(
        r"\([^)]*\)",
        lambda match: match.group(0)
        if _scope_mentions_product(match.group(0).lower())
        else " " * len(match.group(0)),
        clause,
    )
    low = _normalise_apostrophes(clause.lower())
    if _is_question_clause(clause):
        return "unknown", []
    effective = _scope_effective_hits(clause)
    if re.search(
        r"\b(?:doesn't|didn't|does not|did not|no longer)\s+(?:fix|help|ease|relieve|stop|work)\b",
        low,
    ):
        hits = [
            (start, cue, "neg")
            for start, cue, _ in effective
            if cue in {"fix", "fixes", "help", "helps", "helping", "didn't fix", "doesn't fix"}
        ]
        # "the leg issues didn't stop until I took the band off" is still a
        # negative product outcome; do not lose its cue family.
        return "negative", hits or effective
    if re.search(r"\b(?:doesn't|didn't|does not|did not)\s+(?:feel|feels|felt)\s+better\b", low):
        return "negative", [(start, cue, "neg") for start, cue, _ in effective]
    if re.search(r"\bno amount of\b[^.]{0,140}\bhelp(?:ing|s|ed)?\b", low) or re.search(
        r"\bnothing helps?\b", low
    ):
        hits = [
            (start, cue, "neg")
            for start, cue, _ in effective
            if cue in {"help", "helps", "helping"}
        ]
        return "negative", hits
    if re.search(r"\b(?:lower back pain|back pain|pelvic pain|hip pain|pain|aches?)\b", low) and re.search(
        r"\b(?:relief|relieve[sd]?|help(?:s|ed|ing)?|eas(?:e|es|ed|ing)|"
        r"functional|manageable)\b",
        low,
    ):
        return "positive", [
            hit for hit in effective if hit[1] not in {"pain", "painful", "ache", "aches"}
        ]
    positive = [hit for hit in effective if hit[2] == "pos"]
    negative = [hit for hit in effective if hit[2] == "neg"]
    if positive and negative:
        # "When it's particularly bad I use a belly band ... which also helps":
        # the negative half describes the symptom, not a product fault.  Split
        # the clause instead of discarding the product-directed half.
        body_negative = [
            hit
            for hit in negative
            if hit[1] in _SCOPE_SYMPTOM_CUES and _scope_self_state_prefix(low, hit[0])
        ]
        if len(body_negative) == len(negative):
            return "positive", positive
        return "mixed", effective
    if negative:
        return "negative", effective
    if positive:
        return "positive", effective
    return "unknown", effective


_SCOPE_GENERIC_FAMILIES = {"overall", "support"}


def _scope_families(
    hits: list[tuple[int, str, str]], polarity: str
) -> set[str]:
    families: set[str] = set()
    for _start, cue, effective in hits:
        if polarity.startswith("positive") and effective != "pos":
            continue
        if polarity.startswith("negative") and effective != "neg":
            continue
        if cue in _SCOPE_CUE_FAMILY:
            families.add(_SCOPE_CUE_FAMILY[cue][1])
        elif cue in _SCOPE_CUE_REGEX:
            families.add(_SCOPE_CUE_REGEX[cue][1])
    return families


def _scope_paragraphs(body: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    position = 0
    for match in _SCOPE_PARAGRAPH_SPLIT_RE.finditer(body):
        spans.append((position, match.start()))
        position = match.end()
    spans.append((position, len(body)))
    return spans


def _scope_paragraph_index(spans: list[tuple[int, int]], offset: int) -> int:
    for index, (start, end) in enumerate(spans):
        if start <= offset < end:
            return index
    return len(spans) - 1


_SCOPE_SEGMENT_SPLIT_RE = re.compile(r"[,;—–]|(?<=\s)[-–](?=\s)")
_SCOPE_PRODUCT_PRONOUN_RE = re.compile(
    r"\b(?:it|its|it's|it’s|they|them|these|those|this|mine|ours)\b", re.I
)
_SCOPE_DEFINITE_PRODUCT_RE = re.compile(
    r"\b(?:my|the|this|that|our)\s+(?:belly\s+)?(?:bands?|belts?|straps?|wraps?|product|item)s?\b",
    re.I,
)
_SCOPE_IMPERATIVE_RE = re.compile(
    r"^\s*(?:get|use|try|buy|ask|take|put|wear|choose|pick|go|see|avoid|skip|add|grab)\b",
    re.I,
)
_SCOPE_RESULT_RE = re.compile(
    r"\b(?:i feel|i felt|i'm feeling|i am feeling|i'm back to|i was back to|"
    r"i can (?:now )?(?:walk|run|sprint|jog|play|work|sleep|move|exercise|lift|stand|sit|"
    r"breathe|bend|kneel)|"
    r"i could (?:walk|run|sprint|jog|play|work|sleep|move|exercise|lift|stand|sit|breathe|"
    r"bend|kneel)|"
    r"able to (?:walk|run|sprint|jog|play|work|sleep|move|exercise|lift|stand|sit|breathe|"
    r"bend|kneel)|"
    r"the weight (?:off|is lifted)|my pain is (?:gone|away)|pain (?:is )?gone|"
    r"i have more energy|i sleep better|i'm sleeping)\b",
    re.I,
)
_SCOPE_BODY_REACTION_RE = re.compile(
    r"\b(?:my|our)\s+(?:legs?|thighs?|hips?|back|pelvis|pelvic|body|skin|belly)\b", re.I
)


def _scope_segments(clause: str) -> list[tuple[str, int, int]]:
    """Comma-level segments, keeping parentheses inside their segment."""
    spans: list[tuple[str, int, int]] = []
    position = 0
    for match in _SCOPE_SEGMENT_SPLIT_RE.finditer(clause):
        spans.append((clause[position : match.start()], position, match.start()))
        position = match.end()
    spans.append((clause[position:], position, len(clause)))
    return [(text, start, end) for text, start, end in spans if text.strip()]


def _scope_mentions_product(text: str) -> bool:
    return bool(
        _SCOPE_ANY_PRODUCT_RE.search(text)
        or PRODUCT_NOUN_RE.search(text)
        or BRAND_MODEL_RE.search(text)
        or re.search(r"\bmom\s+cozy\b", text, re.I)
    )


def _scope_anchor(
    evaluation_clause: str,
    product_before: bool,
) -> bool:
    """Whether an evaluation clause can be attributed to a product.

    A clause anchors when an evaluation cue shares a comma segment with the
    product (or with a product pronoun), when a first-person cue segment sits
    in a clause that names the product, when it is a short praise fragment
    following the product, or when it is a first-person result sentence
    ("I feel …", "I'm back to …", "the weight off … is …") after the product
    has been introduced.  Generic advice ("belly bands help too") and purpose
    phrases ("to support my pelvic") do not anchor.
    """
    low = _normalise_apostrophes(evaluation_clause.lower())
    stripped = evaluation_clause.strip()
    if _SCOPE_IMPERATIVE_RE.match(stripped):
        # "Get a good belly band" is advice to the reader, not the author's
        # evaluation.
        return False
    segments = _scope_segments(evaluation_clause)
    clause_mentions_product = _scope_mentions_product(low)
    for index, (segment, _start, _end) in enumerate(segments):
        segment_low = _normalise_apostrophes(segment.lower())
        if not _scope_cue_hits(segment):
            continue
        if _scope_mentions_product(segment_low):
            product_starts = [
                match.start()
                for pattern in (_SCOPE_ANY_PRODUCT_RE, PRODUCT_NOUN_RE, BRAND_MODEL_RE)
                for match in pattern.finditer(segment_low)
            ]
            cue_starts = [hit[0] for hit in _scope_cue_hits(segment)]
            # A long "everything I tried" list can name the product and a
            # different product's praise in one comma segment; only a cue
            # near the product mention is an evaluation of it.
            near_product = any(
                abs(cue_start - product_start) <= 80
                for cue_start in cue_starts
                for product_start in product_starts
            )
            # A bare plural ("belly bands help too") is generic advice; it
            # needs a first-person, definite, brand, or use anchor.
            if near_product and (
                _SCOPE_FIRST_PERSON_RE.search(segment_low)
                or re.search(r"\b(?:me|us)\b", segment_low)
                or _SCOPE_DEFINITE_PRODUCT_RE.search(segment_low)
                or BRAND_MODEL_RE.search(segment_low)
                or _SCOPE_PRODUCT_PRONOUN_RE.search(segment_low)
                or _SCOPE_USE_VERB_RE.search(segment_low)
            ):
                return True
            # Do not stop here: "A belly band seems to make things worse" is
            # a singular product with a predicative verb (the branch below),
            # even though it has no first-person or definite anchor.
        # "A belly band seems to make things worse": a singular product with a
        # predicative verb is the author's item, not generic advice.
        if (
            re.search(
                r"\b(?:a|one)\s+(?:belly\s+)?(?:band|belt|strap)\b[^.]{0,44}"
                r"\b(?:seems?|makes?|made|is|was|feels?|felt|gave|gives)\b",
                segment_low,
            )
        ):
            return True
        if re.search(r"\b(?:mine|ours)\b", segment_low):
            return True
        if (
            (clause_mentions_product or product_before)
            and _SCOPE_PRONOUN_EVAL_RE.search(segment_low)
            and _SCOPE_NARROW_SPECIFIC_RE.search(segment_low)
        ):
            return True
        if (
            clause_mentions_product
            and _SCOPE_FIRST_PERSON_RE.search(segment_low)
            and any(
                _scope_mentions_product(_normalise_apostrophes(earlier.lower()))
                for earlier, _s, _e in segments[:index]
            )
        ):
            # "I have belly band, compression garment, ... and I still hurt":
            # the cue segment refers back to a product named earlier in the
            # same clause.
            return True
    # An attribute is the subject of its own evaluation ("the fabric is
    # soft") after the product has been introduced.
    if product_before and _SCOPE_ATTR_SUBJECT_RE.search(low):
        return True
    # An adverse body reaction after the product was introduced (a weak or
    # painful limb response, not a product attribute).  The evaluation clause
    # itself must name the product, or a product pronoun must precede the
    # reaction ("it made my back hurt").  A symptom sentence whose only
    # pronoun is a later discourse "this" does not become a product
    # evaluation because an earlier paragraph mentioned a band.
    # E-merge §2.6: this is the c-1uuim67 scope false positive (its evidence
    # sentence is "my pelvic and groin pain has not gone away").
    reaction = _SCOPE_BODY_REACTION_RE.search(low)
    if (
        product_before
        and reaction is not None
        and (
            _scope_mentions_product(low)
            or _SCOPE_PRODUCT_PRONOUN_RE.search(low[: reaction.start()])
        )
        and (
            _SCOPE_CUE_REGEX["body problem"][2].search(low)
            or _SCOPE_CUE_REGEX["body simile"][2].search(low)
        )
    ):
        return True
    # Short praise fragment ("So convenient", "Very supportive") directly
    # after the product in the same paragraph.
    if product_before and (
        _SCOPE_ADJECTIVE_PRAISE_RE.match(stripped) or _SCOPE_COMFORT_PRAISE_RE.search(low)
    ):
        return True
    # First-person result sentence after the product has been introduced.
    if product_before and _SCOPE_RESULT_RE.search(low):
        return True
    # "Pros: … / Cons: …" lists inside a product paragraph.
    if product_before and re.match(r"^\s*(?:pros|cons)\b", stripped, re.I):
        return True
    # "No amount of rest, belly band support, … seems to be helping" is a
    # first-hand efficacy statement covering the product.  The product may be
    # named in the same clause but not before the clause start.
    if (
        product_before or _scope_mentions_product(low)
    ) and _SCOPE_EFFICACY_SUMMARY_RE.match(stripped):
        return True
    return False


def _scope_reason_only(clause: str) -> bool:
    """``I got a band because my back hurt`` describes the purchase reason.

    The product is named before ``because`` and every polarity cue sits after
    it, so the clause is not an evaluation of the product.  ``I love it
    because it is comfortable`` keeps its pre-``because`` cue and still counts.
    """
    low = _normalise_apostrophes(clause.lower())
    match = re.search(r"\bbecause\b", low)
    if match is None:
        return False
    products = [item.start() for item in _SCOPE_ANY_PRODUCT_RE.finditer(low)]
    products += [item.start() for item in PRODUCT_NOUN_RE.finditer(low)]
    if not products or min(products) > match.start():
        return False
    cues = [hit[0] for hit in _scope_cue_hits(clause)]
    return bool(cues) and all(position > match.end() for position in cues)


def _scope_sentence_index(bounds: list[tuple[int, int]], offset: int) -> int:
    for index, (start, end) in enumerate(bounds):
        if start <= offset < end:
            return index
    return len(bounds) - 1


def assess_experience_scope(rec: CanonicalRecord) -> ExperienceScopeAssessment:
    """Apply the scope decision table to one record's body.

    The title is deliberately excluded: a question title is not evidence of a
    help-seeking context, and an evaluation title is not evidence of a
    substantive one.  ``rec.text`` is the denominator of ``S``.

    Thresholds are calibrated against the blind three-judge consensus sample
    (54 records, no rubric from this module): a record is ``full`` when it
    carries at least two attribute families, at least one of them specific
    (not just "love"/"supportive"), and either 15% of the whole body or 20%
    of its densest paragraph; ``partial`` otherwise.  The paragraph-local
    share exists because a decisive result can be a small fraction of a long
    narrative.
    """
    body = rec.text or ""
    if not body.strip():
        return ExperienceScopeAssessment("none", 0, 0, 0.0, 0, False, "no_experience_text")
    paragraphs = _scope_paragraphs(body)
    clauses = clause_spans(body)
    # A product named only inside a question ("Does anyone have a band?") is
    # not an experience anchor for later self-state sentences.
    question_spans = [
        (clause.start, clause.end)
        for clause in clauses
        if _is_question_clause(_normalise_apostrophes(clause.clause))
    ]
    product_offsets = [
        match.start()
        for pattern in (_SCOPE_ANY_PRODUCT_RE, PRODUCT_NOUN_RE, BRAND_MODEL_RE)
        for match in pattern.finditer(body)
        if not any(start <= match.start() < end for start, end in question_spans)
    ]
    product_offsets.extend(
        match.start()
        for match in re.finditer(r"\bmom\s+cozy\b", body, re.I)
        if not any(start <= match.start() < end for start, end in question_spans)
    )
    sentence_bounds: list[tuple[int, int]] = []
    position = 0
    for match in _SCOPE_SENTENCE_SPLIT_RE.finditer(body):
        sentence_bounds.append((position, match.start()))
        position = match.end()
    sentence_bounds.append((position, len(body)))
    record_help_seeking = help_seeking(rec)
    evaluations = 0
    evaluation_chars = 0
    families: set[str] = set()
    undetermined_use = False
    decisive_clause = False
    evidence_clauses: list[str] = []
    undetermined_clauses: list[str] = []
    chars_by_paragraph: dict[int, int] = {}
    for clause in clauses:
        evaluation_clause = _scope_strip_question_tail(clause.clause)
        check_text = _normalise_apostrophes(evaluation_clause)
        if _is_question_clause(check_text) or _SCOPE_REQUEST_RE.search(check_text):
            continue
        if _SCOPE_COURTESY_RE.search(check_text):
            continue
        if _SCOPE_HYPOTHETICAL_RE.search(check_text):
            continue
        if _SCOPE_CONSIDERATION_RE.search(check_text):
            continue
        if _SCOPE_HEARSAY_RE.search(check_text) or _SCOPE_THIRD_PARTY_RE.search(check_text):
            continue
        has_product_noun = _scope_mentions_product(check_text)
        if _SCOPE_SELF_BODY_RE.search(check_text) and not has_product_noun:
            continue
        if _SCOPE_NEGATED_USE_RE.search(check_text) and _SCOPE_BELLY_PHRASE_RE.search(
            check_text
        ):
            continue
        if _scope_reason_only(evaluation_clause):
            continue
        paragraph_index = _scope_paragraph_index(paragraphs, clause.start)
        p_start, p_end = paragraphs[paragraph_index]
        product_before = any(p_start <= offset < clause.start for offset in product_offsets)
        if not product_before and paragraph_index > 0:
            prev_start, prev_end = paragraphs[paragraph_index - 1]
            product_before = any(prev_start <= offset < prev_end for offset in product_offsets)
        if not _scope_anchor(evaluation_clause, product_before):
            continue
        polarity, hits = _scope_polarity(evaluation_clause)
        if has_product_noun:
            product_starts = [
                match.start()
                for pattern in (_SCOPE_ANY_PRODUCT_RE, PRODUCT_NOUN_RE, BRAND_MODEL_RE)
                for match in pattern.finditer(check_text.lower())
            ]
            if product_starts and not _SCOPE_EFFICACY_SUMMARY_RE.match(
                check_text.strip()
            ):
                # An efficacy summary binds every listed item to the product
                # ("no amount of rest, belly band support, stretching … seems
                # to be helping"), so its cue may sit far from the noun.
                hits = [
                    hit
                    for hit in hits
                    if min(abs(hit[0] - start) for start in product_starts) <= 80
                ]
                if not hits:
                    continue
        if polarity == "unknown":
            if _SCOPE_UNDETERMINED_RE.search(check_text) and _SCOPE_CURRENT_USE_RE.search(
                _normalise_apostrophes(body)
            ):
                undetermined_use = True
                undetermined_clauses.append(evaluation_clause)
            continue
        if polarity == "mixed":
            continue
        low_evaluation = _normalise_apostrophes(evaluation_clause.lower())
        if hits and all(cue in SELF_STATE_CUES for _start, cue, _direction in hits):
            if all(
                _self_state_dominates(low_evaluation, start)
                for start, _cue, _direction in hits
            ):
                continue
        if PAST_MARKER_RE.search(check_text) and record_help_seeking and not (
            BRAND_MODEL_RE.search(check_text)
            or re.search(
                r"\b(?:this|that|the same)\s+(?:band|belt|one)\b",
                check_text,
                re.I,
            )
        ):
            continue
        clause_families = _scope_families(hits, polarity)
        families |= clause_families
        decisive_hits = [
            hit
            for hit in hits
            if not (
                hit[1] in _SCOPE_ADVERSE_CUES
                and _scope_self_state_prefix(low_evaluation, hit[0])
            )
        ]
        decisive_families = _scope_families(decisive_hits, polarity)
        if (
            len(decisive_families) >= 2
            and decisive_families - _SCOPE_GENERIC_FAMILIES
        ):
            # A single decisive clause that states both a specific attribute
            # or result and a second dimension ("night and day … back to
            # sprinting") is substantive even when it is a small share of a
            # long narrative.  Symptom intensifiers ("hurt so bad") are not a
            # second dimension.
            decisive_clause = True
        evaluations += 1
        evaluation_chars += len(evaluation_clause)
        evidence_clauses.append(evaluation_clause)
        chars_by_paragraph[paragraph_index] = (
            chars_by_paragraph.get(paragraph_index, 0) + len(evaluation_clause)
        )
    share = evaluation_chars / len(body) if body else 0.0
    paragraph_share = 0.0
    for index, chars in chars_by_paragraph.items():
        start, end = paragraphs[index]
        length = max(1, end - start)
        paragraph_share = max(paragraph_share, chars / length)
    attributes = len(families)
    specific_families = families - _SCOPE_GENERIC_FAMILIES
    if evaluations == 0 and not undetermined_use:
        return ExperienceScopeAssessment(
            "none", 0, evaluation_chars, share, attributes, undetermined_use,
            "no_attributable_evaluation",
        )
    if evaluations == 0 and undetermined_use:
        return ExperienceScopeAssessment(
            "partial", 0, evaluation_chars, share, attributes, undetermined_use,
            "undetermined_evaluation", tuple(undetermined_clauses),
        )
    if decisive_clause:
        scope, reason = "full", "substantive_evaluation"
    elif (
        attributes >= 2
        and specific_families
        and (share >= 0.15 or paragraph_share >= 0.20)
    ):
        scope, reason = "full", "substantive_evaluation"
    elif evaluation_chars >= 500 and attributes >= 2 and specific_families:
        scope, reason = "full", "substantive_evaluation"
    elif evaluations >= 2 and share >= 0.35 and specific_families:
        scope, reason = "full", "substantive_evaluation"
    elif evaluations >= 3 and share >= 0.25 and specific_families:
        scope, reason = "full", "substantive_evaluation"
    elif evaluations >= 2 and paragraph_share >= 0.40 and specific_families:
        scope, reason = "full", "substantive_evaluation"
    else:
        scope, reason = "partial", "incidental_evaluation"
    return ExperienceScopeAssessment(
        scope, evaluations, evaluation_chars, share, attributes, undetermined_use,
        reason, tuple(evidence_clauses),
    )


def _note_unknown(out: CodedRecord, code, reason: str, hit: CodeHit, source_text: str) -> None:
    start, end, quote = _evidence_span(
        source_text, hit.segment_start, hit.segment_end, hit.match_start, hit.match_end
    )
    entry = {
        "code": code.code,
        "reason": reason,
        "span_start": start,
        "span_end": end,
        "evidence_span": quote,
    }
    if not any(
        item["code"] == entry["code"]
        and item["reason"] == entry["reason"]
        and item["span_start"] == entry["span_start"]
        for item in out.unknown_aspects
    ):
        out.unknown_aspects.append(entry)


def _annotation(rec: CanonicalRecord, axis: str, code: str, polarity: str, hit: CodeHit, source_text: str) -> Annotation:
    start, end, quote = _evidence_span(
        source_text, hit.segment_start, hit.segment_end, hit.match_start, hit.match_end
    )
    return Annotation(
        rec.canonical_id,
        axis,
        code,
        polarity,
        quote,
        span_start=start,
        span_end=end,
        span_text=quote,
    )


def code_record(rec: CanonicalRecord) -> CodedRecord:
    source_text = f"{rec.title}. {rec.text}" if rec.title else rec.text
    # "customer support was great" is service praise, not product support.
    # The replacement keeps the character count, so offsets still point into
    # the original record text.
    text = re.sub(r"\bcustomer support\b", "customer service", source_text, flags=re.I)
    # A verified-purchase review is about the product by construction, so the
    # Reddit rule (only clauses with a product noun or a nearby pronoun are
    # codeable) would silently drop most of it.  Shop reviews skip anchoring;
    # every clause is attributable to the purchased item.
    product_bound = rec.source == "tiktok_shop"
    anchored = not product_bound
    help_seeking = False if product_bound else _is_help_seeking(rec)
    body_text = (rec.text or "").strip()
    out = CodedRecord(
        canonical_id=rec.canonical_id,
        product_match=rec.product_match,
        text_present=bool(body_text),
        product_match_source=rec.product_match_source,
        product_match_override_reason=rec.product_match_override_reason,
    )
    if not body_text:
        # A title alone is a headline, not an experience report.  E-merge
        # §2.4 also requires a non-empty body for aspects.
        out.experience_scope = "none"
        out.experience_reason = "no_experience_text"
        return out
    if product_bound:
        # A verified-purchase review is product-bound; A2 keeps the TikTok
        # layer at ``full``.
        out.experience_scope = "full"
    else:
        # A2 replaces the title-shaped help-seeking proxy with a
        # content-based decision table.  ``help_seeking`` is now only a
        # reason label, never the scope trigger.
        assessment = assess_experience_scope(rec)
        out.experience_scope = assessment.scope
        if assessment.scope == "none":
            if not is_on_topic(rec.product_match):
                out.experience_reason = "product_mismatch"
            else:
                out.experience_reason = (
                    "help_seeking" if help_seeking else assessment.reason
                )
            return out
    if not is_on_topic(rec.product_match):
        # E-merge §2.3: off-target records may carry a full/partial
        # evaluation, but they never emit aspects and never enter a product
        # claim.  The reason is kept for the audit ledger.
        out.experience_reason = "product_mismatch"
        return out

    aspect_hits: dict[tuple[str, str], CodeHit] = {}
    if out.emit_aspects:
        for hit in _match_codes(text, ASPECTS, anchored_only=anchored, product_bound=product_bound):
            if not hit.anchored:
                continue
            if _self_state_dominates(hit.segment, hit.match_start - hit.segment_start):
                continue
            if HEARSAY_RE.search(hit.segment):
                continue
            clause_pol = polarity_of(hit.clause)
            segment_pol = polarity_of(hit.segment)
            # "soft, comfortable, supportive" is one evaluation written as a
            # list: a short bare continuation inherits the clause polarity.
            if (
                segment_pol == "unknown"
                and not NEW_SUBJECT_RE.match(hit.segment.strip())
                and clause_pol != "unknown"
                and len(hit.segment.split()) <= 4
            ):
                segment_pol = clause_pol
            if segment_pol == "mixed":
                # A clause that is simultaneously positive and negative cannot
                # support a direction claim.  Abstain; do not write two votes.
                _note_unknown(out, hit.code, "mixed_clause", hit, source_text)
                continue
            if segment_pol == "unknown":
                reason = "question_clause" if _is_question_clause(hit.clause) else "unknown_polarity"
                _note_unknown(out, hit.code, reason, hit, source_text)
                continue
            # Keep the first decisive hit per code/polarity.
            aspect_hits.setdefault((hit.code.code, segment_pol), hit)
        for (code, pol), hit in sorted(aspect_hits.items()):
            out.annotations.append(_annotation(rec, "aspect", code, pol, hit, source_text))
    out.experience_source = experience_source(rec)

    for hit in _match_codes(text, CONTEXTS, product_bound=product_bound):
        out.annotations.append(_annotation(rec, "context", hit.code.code, "present", hit, source_text))
    if out.has_evaluation:
        for axis, codes in (("journey", JOURNEYS), ("outcome", OUTCOMES), ("gap", GAPS)):
            for hit in _match_codes(text, codes, anchored_only=anchored, product_bound=product_bound):
                out.annotations.append(_annotation(rec, axis, hit.code.code, "present", hit, source_text))
    for hit in _match_codes(text, MEDICAL, anchored_only=anchored, product_bound=product_bound):
        out.annotations.append(_annotation(rec, "medical", hit.code.code, "present", hit, source_text))
        out.medical_flags.append(hit.code.code)

    # Single-valued rollups: pick the most specific, deterministic first match.
    journey_order = [
        "JNY.RETURN",
        "JNY.CARE",
        "JNY.FIRST_FITTING",
        "JNY.SIZE_SELECTION",
        "JNY.RECOMMEND",
        "JNY.CONSIDERATION",
        "JNY.USE",
    ]
    hit_codes = {a.code for a in out.annotations if a.axis == "journey"}
    out.journey_stage = next((c for c in journey_order if c in hit_codes), "unknown")
    outcome_order = [
        "OUT.RETURN_INTENT",
        "OUT.REGRET",
        "OUT.NO_BENEFIT",
        "OUT.LIMITED_USE",
        "OUT.RELIEF",
        "OUT.ACTIVITY_ENABLED",
        "OUT.RECOMMEND",
        "OUT.CONTINUED_USE",
    ]
    out_codes = {a.code for a in out.annotations if a.axis == "outcome"}
    out.outcome = next((c for c in outcome_order if c in out_codes), "OUT.UNKNOWN")
    gap_codes = {a.code for a in out.annotations if a.axis == "gap"}
    if "GAP.FIT_MISMATCH" in gap_codes:
        out.gap = "fit_mismatch"
    elif "GAP.SUPPORT_MISMATCH" in gap_codes:
        out.gap = "support_mismatch"
    elif "GAP.VALUE_MISMATCH" in gap_codes:
        out.gap = "value_mismatch"
    elif "GAP.MATCHED" in gap_codes:
        out.gap = "matched"
    out.codes_hit = sorted({a.code for a in out.annotations})
    if out.medical_flags:
        out.claim_relation = "review_required"
    return out


def code_corpus(records: list[CanonicalRecord]) -> list[CodedRecord]:
    return [code_record(r) for r in records]


def agreement_report(coded_a: list[CodedRecord], coded_b: list[CodedRecord], field: str = "aspect_code") -> dict[str, Any]:
    """Field-level agreement, used only after two humans code the same sample.

    This function exists so G7 can be executed later without rewriting code.
    It refuses to fabricate a second coder.
    """
    raise RuntimeError(
        "G7 requires two independent human coders; no second coder artifact exists in this run"
    )
