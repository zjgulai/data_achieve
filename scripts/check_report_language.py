#!/usr/bin/env python3
"""Dispatcher for the shared business-report language and number gate.

The gate implementation lives in
``apps/api/src/data_intelligence_hub/report_quality``. This file only makes it
runnable from the repository root without installing the API package.

Usage:
    python3 scripts/check_report_language.py --html report.html \\
      --manifest manifest.json --strict
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from data_intelligence_hub.report_quality.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())