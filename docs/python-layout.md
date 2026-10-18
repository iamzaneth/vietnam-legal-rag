# Python source and test layout

Reusable logic is under `src/vietnam_legal_rag/`; argument parsing stays in
`cli/`, and the four `scripts/` files are compatibility entrypoints.
`pyproject.toml` continues to own package discovery and console entrypoints.

## Responsibility boundaries

- `ingestion/crawl_legal_documents.py`: VBPL capture/discovery and publication.
- `ingestion/extract_legal_documents.py`: offline extraction orchestration and public facade.
- `ingestion/html/`: source DOM, HTML structure and physical table geometry.
- `ingestion/semantics/`: legal hierarchy, quotation scope, table meaning and VBPL metadata tabs.
- `ingestion/refinement/`: form/list refinement, semantic second pass and schema cleanup.
- `ingestion/validation/`: output validation, forms, hierarchy and quality diagnostics.
- `evaluation/audit/`: independent serialized-artifact audits; `evaluation/` retains run configuration, sampling, orchestration, reporting and comparison.
- `evaluation/local_inventory.py` and `target_manifest.py`: verify immutable RAW completeness, canonical identity and distinct total-corpus membership.
- `evaluation/progress.py` and `wave_gate.py`: atomic resumable evidence and source-review/test/cumulative-validation gates.
- `cli/`: thin crawl/extract/validate/audit/compare commands.

The packaged schema points to the authoritative repository schema; packaged golden
invariants live in `evaluation/golden_invariants.json`. Schema/parser release 2.3.2
is separate from the implementation fingerprint used by validation gates.

## Test organization

Unit tests mirror ingestion subpackages, with separate evaluation and CLI tests.
`tests/regression/` contains the 25-capture regression, portable source patterns
and the five primary captures/golden regression. Fixtures pin immutable RAW
hashes and reviewed structure/diagnostics. Source-backed expectation corrections
record the old and new values and RAW evidence in the active report; existing
structure, fidelity and provenance assertions remain enforced.
The subsequent hardening work also adds `test_hardening_patterns.py` and selected
source captures in `vbpl_hardening_regressions.json`; it preserves the original
batch and primary fixture contracts. Local inventory, progress, target assembly
and wave-selection tests remain under `tests/unit/evaluation/`.
Package `__init__.py` files allow standard unittest discovery to recurse.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t . -v
```

`vlr validate report --tests-dir` now takes the test root, containing both
`unit/` and `regression/`; its default is `tests`.

## Scripts and placeholders

Retain `audit_extract_schema.py`, `audit_vbpl_hierarchy.py`,
`compare_vbpl_extract.py` and `run_extract_validation.py` as six-line wrappers
to preserve historical audit/comparison commands and the existing validation interface.
No batch-specific reporting implementation is required. Validation defaults to
`reports/validation`; extracted documents use `data/extracted/vbpl/<source-id>/`.
Preserve intentional pipeline placeholder directories and every `.gitkeep`.
