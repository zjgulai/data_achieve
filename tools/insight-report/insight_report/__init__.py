"""insight-report: local VOC analysis pipeline (stdlib only).

Modules:
  ingest.py       raw response readers and ledger lineage
  identity.py     Amazon PDP identity freeze
  counting.py     six-level count separation and reconciliation
  coding.py       rule-based aspect/polarity/severity/context coder
  evidence.py     six-level evidence grading and counterevidence
  metrics.py      coverage, co-occurrence, need states, NumberRefs
  render.py       single-file inline-CSS HTML renderer
  validate.py     schema, invariants, anti-patterns, HTML checks
  build_report.py orchestrator

The package never reads ref/ at runtime and never calls the network.
"""

__version__ = "1.0.0"
