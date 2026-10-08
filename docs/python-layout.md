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
- `cli/`: thin crawl/extract/validate/audit/compare commands.

Domain implementations stay separate; none exceeded 640 lines after organization.
Only identical helpers were consolidated: ancestor-aware `walk` in validation,
`sha` in the extract audit, and `semantic_nodes` in schema refinement. Existing
callers import those shared functions. No blanket compatibility modules were added.

## Module move/rename map

All listed modules were moved with import updates. Other source modules and
placeholder `__init__.py` files were retained.

| Previous package-relative module | Current module |
|---|---|
| `ingestion.html_source` | `ingestion.html.source` |
| `ingestion.html_tables` | `ingestion.html.tables` |
| `ingestion.structured_html` | `ingestion.html.structure` |
| `ingestion.legal_hierarchy` | `ingestion.semantics.hierarchy` |
| `ingestion.quoted_content` | `ingestion.semantics.quotations` |
| `ingestion.table_semantics` | `ingestion.semantics.tables` |
| `ingestion.vbpl_tabs` | `ingestion.semantics.vbpl` |
| `ingestion.form_refinement` | `ingestion.refinement.forms` |
| `ingestion.semantic_refinement` | `ingestion.refinement.semantic` |
| `ingestion.schema_cleanup` | `ingestion.refinement.schema` |
| `ingestion.extract_quality` | `ingestion.validation.quality` |
| `ingestion.extract_validation` | `ingestion.validation.extract` |
| `ingestion.form_validation` | `ingestion.validation.forms` |
| `ingestion.hierarchy_validation` | `ingestion.validation.hierarchy` |
| `evaluation.extract_audit` | `evaluation.audit.extract` |
| `evaluation.hierarchy_audit` | `evaluation.audit.hierarchy` |
| `evaluation.schema_audit` | `evaluation.audit.schema` |

The schema resource stays anchored to `vietnam_legal_rag.ingestion`; packaged
golden invariants stay in `evaluation/golden_invariants.json`. Versions remain
2.3.2. Old module imports in active source/tests are replaced; historical audit
documents retain the names used when those runs happened.

## Test organization

Unit tests mirror ingestion subpackages, with separate evaluation and CLI tests.
`tests/regression/` contains the 25-capture regression, portable source patterns
and the five primary captures/golden regression. Fixture JSON remains unchanged.
Package `__init__.py` files allow standard unittest discovery to recurse.

| Previous test filename(s) under `tests/unit/` | Current path(s) under `tests/` |
|---|---|
| `test_crawl_legal_documents.py` | `unit/ingestion/test_crawl.py` |
| `test_legal_hierarchy.py` | `unit/ingestion/semantics/test_hierarchy.py` |
| `test_structured_html.py` | `unit/ingestion/html/test_structure.py` |
| `test_semantic_refinement.py` | `unit/ingestion/refinement/test_semantic.py` |
| `test_tooling_cli.py` | `unit/cli/test_commands.py` |
| `test_validation_report.py` | `unit/evaluation/test_report.py` |
| `test_validation_runner.py` | `unit/evaluation/test_runner.py` |
| `test_validation_sampler.py` | `unit/evaluation/test_sampler.py` |
| `test_batch_capture_regressions.py` | `regression/test_batch_capture.py` |
| `test_batch_source_patterns.py` | `regression/test_source_patterns.py` |
| `test_form_refinement.py`, `test_form_node_invariant.py` | `unit/ingestion/refinement/test_forms.py` (merged) |
| `test_schema_cleanup.py`, `test_consistency_cleanup.py` | `unit/ingestion/refinement/test_schema.py` (merged) |
| `test_symbol_list_finalization.py` | `unit/ingestion/refinement/test_lists.py`, `regression/test_golden.py` (split) |
| `test_extract_legal_documents.py` | `unit/ingestion/test_extract.py`, `unit/ingestion/semantics/test_vbpl.py`, `unit/ingestion/validation/test_extract.py` (split) |

The original classes and all 264 test methods/assertions remain. Small, identical
synthetic parser helpers and the RAW builder are shared in `tests/support.py`;
tests no longer import other test-case classes for fixture creation.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t . -v
```

`vlr validate report --tests-dir` now takes the test root, containing both
`unit/` and `regression/`; its default is `tests`.

## Scripts and placeholders

Retain `audit_extract_schema.py`, `audit_vbpl_hierarchy.py`,
`compare_vbpl_extract.py` and `run_extract_validation.py` as six-line wrappers
to preserve historical audit/comparison commands and the existing validation interface. Delete only the redundant
`write_extract_validation_50_report.py` wrapper after verifying the generic
`vlr validate report` reproduces batch-50 evidence. There is no batch-specific
report implementation and no new batch-numbered script.

Existing directories, including empty pipeline placeholders and `scripts/`,
remain. All 17 `.gitkeep` files remain unchanged. No RAW, current Extract, fixture,
schema, canonical report or historical evidence file was removed or modified.

## File counts and final size review

Counts include `__init__.py` and are recursive; rows overlap. New package markers
increase counts while duplicate implementations decrease. There are 17 test files
with cases, plus ten package markers and one shared helper module.

| Directory | Before | After |
|---|---:|---:|
| `src` | 40 | 45 |
| `src/vietnam_legal_rag/ingestion` | 17 | 21 |
| `src/vietnam_legal_rag/evaluation` | 9 | 10 |
| `src/vietnam_legal_rag/cli` | 7 | 7 |
| `tests` | 16 | 28 |
| `tests/unit` | 16 | 22 |
| `scripts` | 5 | 4 |

Every remaining Python file is classified as a retained implementation/test,
a relocated implementation/test, a merged test, a necessary package marker,
a shared fixture helper, or a compatibility wrapper. Empty future packages
remain intentionally; the tiny CLI adapters avoid duplicating argument parsing.
No identical top-level production function/class implementations remain.

| Python file | Lines |
|---|---:|
| `src/vietnam_legal_rag/__init__.py` | 1 |
| `src/vietnam_legal_rag/api/__init__.py` | 1 |
| `src/vietnam_legal_rag/cli/__init__.py` | 1 |
| `src/vietnam_legal_rag/cli/__main__.py` | 20 |
| `src/vietnam_legal_rag/cli/audit.py` | 48 |
| `src/vietnam_legal_rag/cli/compare.py` | 22 |
| `src/vietnam_legal_rag/cli/crawl.py` | 30 |
| `src/vietnam_legal_rag/cli/extract.py` | 20 |
| `src/vietnam_legal_rag/cli/validate.py` | 68 |
| `src/vietnam_legal_rag/core/__init__.py` | 1 |
| `src/vietnam_legal_rag/evaluation/__init__.py` | 1 |
| `src/vietnam_legal_rag/evaluation/audit/__init__.py` | 1 |
| `src/vietnam_legal_rag/evaluation/audit/extract.py` | 170 |
| `src/vietnam_legal_rag/evaluation/audit/hierarchy.py` | 310 |
| `src/vietnam_legal_rag/evaluation/audit/schema.py` | 330 |
| `src/vietnam_legal_rag/evaluation/config.py` | 55 |
| `src/vietnam_legal_rag/evaluation/extract_comparison.py` | 62 |
| `src/vietnam_legal_rag/evaluation/report_writer.py` | 199 |
| `src/vietnam_legal_rag/evaluation/validation_runner.py` | 217 |
| `src/vietnam_legal_rag/evaluation/validation_sampler.py` | 53 |
| `src/vietnam_legal_rag/generation/__init__.py` | 1 |
| `src/vietnam_legal_rag/indexing/__init__.py` | 1 |
| `src/vietnam_legal_rag/ingestion/__init__.py` | 1 |
| `src/vietnam_legal_rag/ingestion/crawl_legal_documents.py` | 510 |
| `src/vietnam_legal_rag/ingestion/extract_legal_documents.py` | 213 |
| `src/vietnam_legal_rag/ingestion/html/__init__.py` | 1 |
| `src/vietnam_legal_rag/ingestion/html/source.py` | 191 |
| `src/vietnam_legal_rag/ingestion/html/structure.py` | 451 |
| `src/vietnam_legal_rag/ingestion/html/tables.py` | 353 |
| `src/vietnam_legal_rag/ingestion/refinement/__init__.py` | 1 |
| `src/vietnam_legal_rag/ingestion/refinement/forms.py` | 593 |
| `src/vietnam_legal_rag/ingestion/refinement/schema.py` | 363 |
| `src/vietnam_legal_rag/ingestion/refinement/semantic.py` | 483 |
| `src/vietnam_legal_rag/ingestion/semantics/__init__.py` | 1 |
| `src/vietnam_legal_rag/ingestion/semantics/hierarchy.py` | 640 |
| `src/vietnam_legal_rag/ingestion/semantics/quotations.py` | 318 |
| `src/vietnam_legal_rag/ingestion/semantics/tables.py` | 175 |
| `src/vietnam_legal_rag/ingestion/semantics/vbpl.py` | 281 |
| `src/vietnam_legal_rag/ingestion/validation/__init__.py` | 1 |
| `src/vietnam_legal_rag/ingestion/validation/extract.py` | 165 |
| `src/vietnam_legal_rag/ingestion/validation/forms.py` | 237 |
| `src/vietnam_legal_rag/ingestion/validation/hierarchy.py` | 192 |
| `src/vietnam_legal_rag/ingestion/validation/quality.py` | 157 |
| `src/vietnam_legal_rag/preprocessing/__init__.py` | 1 |
| `src/vietnam_legal_rag/retrieval/__init__.py` | 1 |
| `tests/__init__.py` | 1 |
| `tests/regression/__init__.py` | 1 |
| `tests/regression/test_batch_capture.py` | 46 |
| `tests/regression/test_golden.py` | 71 |
| `tests/regression/test_source_patterns.py` | 419 |
| `tests/support.py` | 44 |
| `tests/unit/__init__.py` | 1 |
| `tests/unit/cli/__init__.py` | 1 |
| `tests/unit/cli/test_commands.py` | 65 |
| `tests/unit/evaluation/__init__.py` | 1 |
| `tests/unit/evaluation/test_report.py` | 63 |
| `tests/unit/evaluation/test_runner.py` | 64 |
| `tests/unit/evaluation/test_sampler.py` | 20 |
| `tests/unit/ingestion/__init__.py` | 1 |
| `tests/unit/ingestion/html/__init__.py` | 1 |
| `tests/unit/ingestion/html/test_structure.py` | 239 |
| `tests/unit/ingestion/refinement/__init__.py` | 1 |
| `tests/unit/ingestion/refinement/test_forms.py` | 324 |
| `tests/unit/ingestion/refinement/test_lists.py` | 198 |
| `tests/unit/ingestion/refinement/test_schema.py` | 377 |
| `tests/unit/ingestion/refinement/test_semantic.py` | 294 |
| `tests/unit/ingestion/semantics/__init__.py` | 1 |
| `tests/unit/ingestion/semantics/test_hierarchy.py` | 274 |
| `tests/unit/ingestion/semantics/test_vbpl.py` | 124 |
| `tests/unit/ingestion/test_crawl.py` | 397 |
| `tests/unit/ingestion/test_extract.py` | 113 |
| `tests/unit/ingestion/validation/__init__.py` | 1 |
| `tests/unit/ingestion/validation/test_extract.py` | 34 |
| `scripts/audit_extract_schema.py` | 6 |
| `scripts/audit_vbpl_hierarchy.py` | 6 |
| `scripts/compare_vbpl_extract.py` | 6 |
| `scripts/run_extract_validation.py` | 6 |

## Verification (2026-10-08)

- All 264 tests passed with no skips, including ingestion, evaluation, CLI, batch capture, source patterns and golden fixtures.
- All 214 pre-existing source functions/classes remain structurally equivalent after import and test-path/help updates. Five removed duplicate helper definitions match their shared replacements. All test identities and assertion/subtest/skip expressions were preserved.
- Offline auditing of a copied batch-50 state reparsed 209 published tab JSON artifacts across the 50 captures and golden, with exact byte equality and zero audit errors. All prior document and golden validations match. The audit exits 1 for the nine pre-existing source-warning documents; warnings were not changed.
- Generic reporting reproduces canonical metrics, all document evidence, repairs, golden validation, wave history and unsuccessful candidates exactly. Generated timestamps, command paths and generic wording may differ; canonical reports were untouched.
- All source modules import; console/module/alias/wrapper help and package discovery were checked.
- Hashes verified all 1,113 protected corpus/schema/fixture/report files and 17 placeholders unchanged. All 351 pre-existing directories remain, including the installed virtual environment.
- No crawl or sample selection was run. No parser/schema versions or Extract rules changed.

See [validation workflow](extract-validation-workflow.md) for baseline reproduction
and the separately authorized next validation phase.
