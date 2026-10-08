# Extract validation workflow

Run commands from the repository root with the existing `.venv`. Extraction
and audits are offline; discovery, crawl and source inspection use the network.

## Repository hygiene classification

- **A — keep permanently:** production modules, both extraction schema copies,
  reusable audit/comparison modules, all tests and fixture definitions, existing
  documentation and the canonical batch-50 Markdown/JSON reports. The packaged
  schema serves installed distributions; it is not a redundant scratch copy.
- **B — keep and reorganize:** batch-50 audit/test logs and repairs/reviews/state
  JSON belong in `reports/extract-validation-50/evidence/`. Preserve all five:
  state records candidate attempts and audit history; reviews record explicit
  semantic decisions; repairs include sampling fixes and expectation corrections;
  logs record the original checks. Overlap with the report does not justify
  discarding that evidence.
- **C — regenerable and ignored:** Python bytecode/cache directories and temporary
  verification files under report `runtime/` or `tmp/` directories.
- **D — safe to delete:** the inspected Python caches and cleanup verification
  scratch outputs after their checks complete. No unique source, corpus or
  validation evidence is classified for deletion.

Retain `AGENTS.md`: its package layout, offline extraction, RAW immutability and
regression rules remain applicable. Retain the installed `.venv`, its active
distribution metadata, local configuration,
all versioned historical audits in `docs/`, and the older local
`evaluation/results/vbpl-verification.json`: these are useful history or active
environment files, not proven disposable scratch files.

## Python tooling architecture

Reusable capture/extraction logic stays in `ingestion/`. `evaluation/` owns
`config.py`, `validation_sampler.py`, `validation_runner.py`, `audit/extract.py`,
`audit/hierarchy.py`, `audit/schema.py`, `extract_comparison.py` and
`report_writer.py`. Golden count expectations are declarative packaged data in
`evaluation/golden_invariants.json`, with the original invariants unchanged.
`cli/` owns all argument parsing and user-facing commands. Libraries receive
explicit configuration; the runner no longer mutates module globals.

`pyproject.toml` defines `vlr` and the two retained console aliases.
Install/editably reinstall the package locally to refresh those entrypoints.
The same commands work through `.venv/bin/python -m vietnam_legal_rag.cli`;
individual `cli.crawl`, `cli.extract`, `cli.validate`, `cli.audit` and
`cli.compare` modules are also runnable. The old ingestion `main()` functions
are lazy adapters to preserve existing imports and module invocations.

| Existing script | Decision | Implementation |
|---|---|---|
| `audit_extract_schema.py` | Move logic; retain wrapper | `evaluation/audit/schema.py`, `cli/audit.py` |
| `audit_vbpl_hierarchy.py` | Move logic; retain wrapper | `evaluation/audit/hierarchy.py`, `cli/audit.py` |
| `compare_vbpl_extract.py` | Move logic; retain wrapper | `evaluation/extract_comparison.py`, `cli/compare.py` |
| `run_extract_validation.py` | Move logic; retain wrapper | runner, sampler, per-document audit and `cli/validate.py` |
| `write_extract_validation_50_report.py` | Remove redundant batch-specific wrapper after equivalent report verification | `evaluation/report_writer.py`, `vlr validate report` |

The audit/comparison wrappers retain historical commands; the generic validation
wrapper preserves the existing operational command.
They contain only imports and argument forwarding. The batch-specific report
wrapper was removed after the generic command reproduced the canonical report
metrics and evidence. Use `vlr validate report --report-dir RUN --output-dir DEST`.
New batch sizes need no new source files.

`src/vietnam_legal_rag.egg-info/` is ignored, untracked generated build metadata.
It can be removed after a verified editable install: active distribution
metadata resides under `.venv/.../site-packages/*.dist-info`, and the editable
`.pth` points to `src/`. Building/installing may regenerate egg-info; do not
commit it. Keep the virtual environment's installed metadata.

## Batch-50 regression baseline

Canonical results: [report.md](../reports/extract-validation-50/report.md) and
[report.json](../reports/extract-validation-50/report.json). Original supporting
evidence is in `../reports/extract-validation-50/evidence/`.

`evidence/state.json` is the fixed selected-sample manifest as well as resumable
run state. Preserve its 50 document identities, order, RAW paths, attempts and
wave history. Preserve `data/interim/discovered_urls.jsonl` and its companion
discovery JSON, all RAW captures (including failed/scope-mismatch captures),
the golden RAW, and current Extract results. Large local corpora remain ignored
by Git and need to be retained separately when reproducing on another machine.

`tests/fixtures/vbpl_batch_regressions.json` pins 25 promoted real captures by
source hash and expected structure/diagnostics. `vbpl_primary_captures.json`
pins the five original representative captures. Neither fixture is temporary.
Portable parser-pattern tests and sampler tests run independently of those
local captures; capture-dependent tests can skip when RAW is unavailable.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python -m vietnam_legal_rag.cli validate --help
.venv/bin/python -m vietnam_legal_rag.cli validate audit
```

The audit reads existing Extract files, reparses RAW for deterministic comparison,
and updates its selected state file with the new audit. To preserve historical
state during a check, copy `evidence/state.json` into the ignored `runtime/`
directory and pass that copy with `--sample-manifest` (`--state` remains an alias).
Its exit status is **1** for the retained source warnings (41/50 semantically
complete), even when all integrity checks pass; inspect `audit_errors`, quality
flags and diagnostics. The golden must retain all invariants and zero warnings.
`audit --regenerate` re-extracts from immutable RAW with the current parser;
use it only when regeneration is intended.

Generic reporting requires the selected run state plus `repairs.json`,
`reviews.json` and a passing `tests.txt` in its evidence directory. The fixtures
and test-source paths are configurable; `--tests-dir` is the test root containing
`unit/` and `regression/`. It checks the configured sample count,
distinct identities/URLs, scope quotas/order, completed semantic reviews and all
previous integrity/structure criteria. Warnings keep their existing quality flags.
Markdown describes the actual metrics, waves and golden counts rather than
making batch-specific historical claims. Original canonical batch-50 reports
remain unchanged; rebuild to a separate directory:

```bash
.venv/bin/python -m vietnam_legal_rag.cli validate report \
  --report-dir reports/extract-validation-50 \
  --output-dir reports/extract-validation-50/runtime/rebuilt
```

`vlr audit hierarchy`, `vlr audit schema` and `vlr compare` expose the existing
independent checks. Some freeze-contract checks intentionally refer to the
representative fixtures; their invariants are preserved, not generalized away.

## Next validation phase and final extraction

The sequence is **batch-50 baseline → separately authorized batch-200 validation
→ final re-extraction from retained RAW with the final parser**. Repository
hygiene does not select or crawl the next sample.

`vlr validate` accepts `--batch-size`, `--wave-size`, `--sample-manifest`,
`--report-dir`, `--central-target`, `--local-target`, `--inventory`, `--raw-dir`
and `--extracted-dir`, plus `--regenerate` during audit. `--audit` is an alias
for the audit action. Defaults reproduce batch-50
(50 documents, ten per wave, the existing discovery inventory and Extract root).
A future batch must use a separate state path and explicit batch size; a target
mismatch is rejected. Candidate selection and parser/audit semantics are retained.
Targets default to an even split (Central receives the extra document for an
odd batch). Supplying one scope target derives the other; supplying both must
sum to the batch size. Selection alternates until one quota is filled and then
uses the remaining scope. Resuming checks target and scope membership/order.
`--sample-manifest` points to the full run-state JSON, whose `documents` list
records the fixed selected sample; it is not a bare URL list. New state files
also record `scope_targets`; historical state without that field is supported.
The sampler excludes the golden and already
captured URLs. Existing discovery/crawl/inspect actions remain separate from the
offline audit. Do not rediscover into the original inventory merely to reproduce
an already selected sample.

For the eventual final parser, regenerate the selected corpora from unchanged
RAW, run the complete unit/capture regression suite, and audit actual Extract
artifacts. Keep new run reports/evidence separate from this historical baseline.
Normalized, Chunking, Embeddings and RAG remain outside this workflow.

## Cleanup verification (2026-10-08)

The full unit suite passed: 251 tests, no skips, including golden, parser,
batch-pattern, capture and sampler regressions. The reserved integration
directory contains no tests. An offline audit of a temporary state copy
reproduced every document validation and golden invariant exactly: zero audit
errors, with the nine historical source-warning cases retained. The five evidence
files remained byte-identical. Rebuilt report Markdown matched byte-for-byte;
report JSON matched apart from its regenerated timestamp. The canonical reports
were only edited to update paths/commands.

SHA-256 checks confirmed all 1,139 protected data, source, schema, fixture and
evaluation files stayed unchanged. All 50 selected RAW paths, 25 promoted
regression captures and five primary capture identities resolved. No new sample
was selected, no crawl started, and no parser/schema behavior changed. Temporary
verification outputs and Python caches were removed after verification.

## CLI consolidation verification (2026-10-08)

All 264 unit tests passed, with no skips. Generic-report tests cover smaller and
unequal-scope samples and reject incomplete samples/unreviewed evidence. The
batch-50 machine metrics, document evidence, repairs, golden and wave history
reproduced exactly. Offline auditing of copied state reproduced all existing
document validations and golden invariants. CLI/module/compatibility help,
editable installation and regular wheel contents were verified. Canonical
reports/evidence and RAW/Extract data were not rewritten. No crawl was started.
Independent hierarchy/schema/comparison commands also passed against all five
original representative captures (25 JSON artifacts), preserving their two
existing source warnings. Pre-existing crawler/extractor functions/classes and
all independent audit calculations/checks remained structurally identical.

Source responsibilities, move mappings and test discovery: [Python layout](python-layout.md).
