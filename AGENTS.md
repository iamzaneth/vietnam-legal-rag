# Repository Guidelines

## Project Structure & Module Organization

Python 3.11+ uses a `src/` layout. Implemented code lives in `src/vietnam_legal_rag/ingestion/`: VBPL crawling, HTML parsing, extraction, and validation. Other package modules and `frontend/` are placeholders for future RAG components. Keep reusable logic in the package and task entry points in `scripts/`.

Unit tests live in `tests/unit/`, fixtures in `tests/fixtures/`; `tests/integration/` is reserved. `schemas/extracted.schema.json` defines the extraction contract. Consult `docs/architecture.md` and `docs/data-conventions.md`. Generated data and indexes belong in `data/` and `storage/`.

## Build, Test, and Development Commands

Run from the repository root:

- `python3 -m venv .venv` then `source .venv/bin/activate`: create and activate the environment.
- `python -m pip install -e .`: install the package for development.
- `python -m pip install -e '.[crawl]'`: add Playwright for crawling.
- `python -m playwright install chromium`: install the browser for Chromium mode.
- `vbpl-crawl-one --channel chromium`: capture one VBPL document into `data/raw/vbpl/`.
- `vbpl-extract --debug-tree`: extract local HTML into JSON and print its semantic tree.
- `PYTHONPATH=src python -m unittest discover -s tests/unit -v`: run the unit suite.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for modules/functions, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Follow surrounding code and add type annotations where practical. Preserve Vietnamese text using UTF-8. No formatter or linter is configured in `pyproject.toml`.

## Testing Guidelines

Use standard-library `unittest`, files named `test_*.py`, and methods named `test_*`. Add focused regressions for parser changes, covering schema validity, text preservation, provenance, and determinism. No numeric coverage threshold is configured. Capture-dependent tests may skip when local raw data is unavailable.

## Commit & Pull Request Guidelines

History uses short descriptive subjects, including `remove verification script and related documentation` and `checkpoint: extract v2.3.2 before autonomous freeze`; no fixed prefix scheme is established. Prefer imperative subjects. PRs should explain behavior changes, link relevant issues, record test commands/results, and update documentation for contract changes.

## Data Integrity & Configuration

Follow `docs/EXTRACTION_FINALIZATION_SPEC.md`: preserve raw HTML, fix parser code, and regenerate extracted JSON. Preserve source wording, order, and references; avoid inferred values and document-specific parser hardcoding. Keep extraction offline and deterministic. Store secrets in `.env`; exclude generated corpora, indexes, and caches from commits. Share only small, reviewed fixtures.
