#!/usr/bin/env python3
"""Section registry — the 11 sections are independent pluggable functions.

Each module exposes `render(data) -> SectionResult`. `SectionResult.html` is
None when required data is missing; `reason` then explains the omission in the
visible "本报告省略了什么" appendix. The registry order is frozen.
"""
from __future__ import annotations

import ir_contract as C
from templates.sections import (
    s00_answer,
    s01_experience,
    s02_aspects,
    s03_frames,
    s04_mixed,
    s05_contexts,
    s06_journey,
    s07_social,
    s08_variant,
    s09_agenda,
    s10_evidence,
)

SECTION_MODULES = [
    (C.SECTION_BY_INDEX["00"], s00_answer),
    (C.SECTION_BY_INDEX["01"], s01_experience),
    (C.SECTION_BY_INDEX["02"], s02_aspects),
    (C.SECTION_BY_INDEX["03"], s03_frames),
    (C.SECTION_BY_INDEX["04"], s04_mixed),
    (C.SECTION_BY_INDEX["05"], s05_contexts),
    (C.SECTION_BY_INDEX["06"], s06_journey),
    (C.SECTION_BY_INDEX["07"], s07_social),
    (C.SECTION_BY_INDEX["08"], s08_variant),
    (C.SECTION_BY_INDEX["09"], s09_agenda),
    (C.SECTION_BY_INDEX["10"], s10_evidence),
]
