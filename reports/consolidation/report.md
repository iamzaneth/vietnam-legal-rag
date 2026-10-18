# Repository consolidation

Completed and independently reviewed: PASS after one fix cycle. Two parallel Explorers, a Planner, one implementation Coder, project quality checks, an independent Reviewer and the Orchestrator final gate ran. Pre-existing parser work remains preserved; no commit or crawl was performed.

Before:
```text
data/extracted/{vbpl,vbpl-validation-100,vbpl-validation-500}/
reports/extract-validation-{50,100,500}/
docs/ (21 files)
```
After:
```text
data/extracted/vbpl/<source-id>/
reports/validation/{report.json,report.md,history.zip,history-index.json,evidence/}
reports/consolidation/{migration.json,implementation.diff,report.md,verification logs}
docs/ (7 operational documents)
```

| Area | Files before → after | Logical MB before → after |
|---|---:|---:|
| reports | 1,047 → 25 | 738.90 → 102.03 |
| data/extracted | 3,708 → 2,564 | 287.91 → 244.17 |
| docs | 21 → 7 | 0.70 → 0.07 |
| scripts | 5 → 5 | 0.00 → 0.00 |

Counts include `.gitkeep`; logical bytes exclude Python caches. Report/ledger self-writes slightly affect byte totals. Full initial inventory, per-file dispositions and final inventory are in migration.json.

All 500 unique identities remain from 726 bundle copies. The accepted final uniform output supplied the canonical bundles; 161 superseded copies differed. Selection verified frozen output hashes, immutable RAW provenance, identity and schema, never recency. All 2,563 extracted JSON artifacts passed compatibility checks. Every canonical bundle remains byte-identical to the accepted proof. No extracted legal JSON was manually repaired.

Removed 226 duplicate document copies and both task-specific Extract roots. Removed 852 superseded report snapshots, repeated audits, test/debug logs and stale checkpoints. Retained 195 exact historical proof members in the indexed archive: source/fixture decisions, accepted gates, final hash proof, historical baseline reporting inputs and reproduction evidence. Active archive locators resolve. Archived historical commands may mention intentionally removed intermediate outputs.

Retained documentation: architecture.md, data-conventions.md, EXTRACTION_FINALIZATION_SPEC.md, extract-validation-workflow.md, extracted-schema.md, python-layout.md and vbpl-crawl.md. Removed 14 superseded generated audit/comparison documents; their complete filenames and original inventory appear in migration.json. Current guidance and links were consolidated into the retained documents.

Ordinary extraction defaults use the unified collection. Validation defaults use reports/validation; default audit/report resolve the saved corpus configuration and archived baselines. Explicit CLI options retain priority. Progress recovery uses configured targets. A separate mapping preserves the frozen original target hash and proves the migrated manifest differs only in declared locator substitutions. Tests permit future canonical collection growth while protecting accepted bundles. Four thin script wrappers and the packaged schema symlink remain.

Verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -t . -q`: 649 passed, zero skips, 133.997 seconds. Evidence: review-full-tests.txt.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m unittest tests.unit.cli.test_commands tests.unit.evaluation.test_consolidation tests.unit.evaluation.test_runner tests.unit.evaluation.test_wave_sampling tests.unit.evaluation.test_report tests.unit.evaluation.test_progress -q`: 54 passed, zero skips, 1.273 seconds after the synthetic fixture was expanded to the full 349 + 150 + golden = 500 scope. Evidence: review-focused-tests.txt.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.cli validate report --output-dir reports/validation/runtime/default-rebuilt`: exit 0; same acceptance metrics and ordered 500 identities. Temporary output removed. Evidence: review-default-report.txt.
- Reviewer independently ran the evaluation/consolidation/report/runner/progress/CLI subset: 47 passed, zero skips, 1.250 seconds. Both initial findings resolved; no blocking findings remain.
- `.venv/bin/python -m vietnam_legal_rag.cli --help`, `extract --help`, and `validate --help`: exit 0. Evidence: cli-help.txt.
- Orchestrator independently verified all 2,585 protected SHA-256 values, every accepted bundle hash, all 195 archive member hashes, unchanged parser fingerprint and final identity count. `git diff --check` passed. Active path search found only the deliberate historical archive prefix in its reporting test; documentation link checks passed.

Historical reporting tests compare immutable metric/source/review decisions with real archived inputs. Current artifact file lists and serialized validation fields are checked against the accepted canonical bundles, whose final parser output supersedes the old copies.

Hygiene: temporary scripts, reconstructed baselines, rebuilt output and superseded cleanup test logs removed. No reusable implementation was added to scripts. Final tree/status/diff inspected. RAW, schemas, fixtures, secrets and all 17 original .gitkeep files remain unchanged. Pre-existing uncommitted/untracked work was accounted for.

Limitations: no full-corpus regeneration or live collection was needed. Parser acceptance relies on preserved prior uniform proof, supplemented by migration integrity checks. Automated semantic completeness remains 312/500; reviewed completeness remains 300/500 with 200 retained source ambiguities. Deleted superseded intermediates are represented by inventory/hash/disposition, not recoverable content.
