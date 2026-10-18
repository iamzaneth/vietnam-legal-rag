# Extract validation workflow

Run from the repository root using `.venv`. Collection is explicit and uses the
network; extraction, audits, and report rebuilding operate offline on stored RAW.
Reusable implementation belongs in `ingestion/` and `evaluation/`; command parsing
belongs in `cli/`. The four scripts remain thin compatibility entrypoints.

## Canonical locations

- `data/raw/vbpl/<document_scope>/<source-id>/`: immutable capture evidence.
- `data/extracted/vbpl/<source-id>/`: one accepted JSON bundle per source identity.
- `reports/validation/report.json` and `report.md`: current total-corpus results.
- `reports/validation/evidence/`: live state, target, cumulative reviews, parser
  freeze, uniform verification, tests, and completion context.
- `reports/validation/history.zip` and `history-index.json`: unique earlier
  acceptance/source-review evidence, exact original commands, and member hashes.
- `reports/consolidation/migration.json`: migration inventory and disposition ledger.

History members retain original paths and bytes. `history.zip!/reports/...`
locators are read directly by the baseline-manifest loader. Extract members before
rerunning historical commands. Historical batch-report tests extract the
50-document evidence to a temporary directory and run the real report assertions.
Older generated documentation and superseded intermediate diagnostics are removed;
current operational guidance and unique acceptance proof remain.

## Commands and configuration

```bash
.venv/bin/python -m vietnam_legal_rag.cli validate --help
.venv/bin/python -m vietnam_legal_rag.cli extract --help
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python -m vietnam_legal_rag.cli validate report \
  --report-dir reports/validation \
  --sample-manifest reports/validation/evidence/corpus_validation_state.json \
  --target-manifest reports/validation/evidence/target_manifest.json \
  --output-dir reports/validation/runtime/rebuilt
```

Default report root is `reports/validation`; default Extract root is
`data/extracted/vbpl`. A new independent validation run must explicitly select a
separate report/state root; changing batch size does not create a new data store.
The selected state declares its target; mismatched configuration is rejected.
`--batch-size`, `--wave-size`, scope quotas and `--wave-offset` configure sampling.
Scope targets must sum to the sample target; selection alternates until a quota
fills. `--sample-manifest` is full state JSON, not a bare URL list.

With no explicit selected state, `validate audit` and `validate report` resolve
`evidence/corpus_validation_state.json` and its saved quotas, scope order, wave
size and baseline manifests. The default audit includes baseline documents and
the golden, covering the whole accepted target; it writes audit results to that
selected state. The default report also resolves `evidence/target_manifest.json`.
Explicit state/configuration arguments retain their meaning. Use `--output-dir`
to rebuild reports without replacing the accepted report.

`inventory-local` verifies complete RAW, provenance, identity and duplicates.
`select-local` reuses verified unused captures without network requests. Crawl,
discover and inspect are separate network operations. Never recrawl complete RAW
merely to refresh derived output. Never alter extracted legal JSON manually.

## Gates, recovery and evidence

`--require-wave-gates` requires current-parser audits, explicit source reviews,
repair evidence and passing tests before acquiring the next wave. Repeat
`--baseline-manifest` to include earlier samples without editing their historical
state. Archived baseline locators are read directly without extraction.
`complete-wave --wave N` records each gate; partial final waves are allowed only
when the configured overall target is assembled.

`audit --regenerate` rebuilds from preserved RAW; audits check schema, source text,
provenance, order, hierarchy, tables and determinism against independent evidence.
Warnings may produce exit 1; classify actual diagnostics rather than treating an
exit status as proof of parser failure. Golden invariants remain unchanged.
After the last parser change, uniformly regenerate and audit the complete target.
A passing sample is never proof of corpus-wide correctness.

`--progress-dir` records atomic state/checkpoint/resume evidence. Before expensive
operations persist the command, parser/schema state, scope, output and recovery
step; immediately record the actual exit/result afterward. On interruption read
AGENTS.md, state, target manifest, checkpoint, and actual artifacts, then continue
from the first unfinished operation. Do not restart completed work.

The total-report action reads cumulative validations from the selected state,
`cumulative_reviews.json`, and `report-context.json`. Source reviews must match
the current implementation fingerprint. Explicit successful uniform validation,
wave gates, tests and repository hygiene are also required for final acceptance.
Automated semantic completeness (312/500 in the accepted milestone) is distinct
from reviewed semantic completeness (300/500); 200 documents retain source
ambiguity. Preserve missing/ambiguous source information rather than inventing it.

The accepted 500-document collection includes earlier samples and unused local
captures, counting each source identity once. Its final frozen output hashes and
RAW hashes are retained. The migration validates those bytes without expensive
regeneration. Later parser work must establish new uniform acceptance evidence.
Keep regression fixtures, schemas, RAW, secrets and all `.gitkeep` files intact.

The frozen parser proof retains the SHA-256 of the original target manifest in
`history.zip`. `reports/consolidation/migration.json#/target_manifest_migration`
records both original and live hashes and the exact role-manifest locator mapping.
The migration verifies full JSON equality after applying only those locator
substitutions; document membership, order and RAW/validation provenance remain
unchanged. The historical frozen hash is never rewritten to match migrated bytes.
