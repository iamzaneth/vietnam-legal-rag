# Vietnam Legal RAG — Project Progress Report

**Evidence cut-off:** repository inspection on 18 October 2026, Asia/Ho_Chi_Minh.  
**Coverage:** earliest recoverable Git state through the 500-document acceptance milestone and subsequent repository consolidation.  
**Current software identities:** package `0.1.0`; Extract schema and parser release `2.3.2`; accepted implementation fingerprint `988535905f88162fd6fefc9a9636c2bba7d6fa31a632dcd9f2c233637541bbdb`.

This report distinguishes committed history, uncommitted local implementation, historical execution evidence, and read-only checks performed for this assessment. Dates in Git are shown with their recorded offset; validation timestamps are explicitly UTC. The earliest recoverable commit is not evidence of the project's actual creation date. Sources and archive-member conventions are listed in Section 16.

## 1. Executive Summary

The repository has progressed from an initial Vietnamese legal RAG scaffold and VBPL collection experiment into an implemented, offline, source-faithful HTML extraction and evaluation system. Its strongest demonstrated result is acceptance of **500 distinct VBPL source documents** under one final parser implementation, with preserved RAW evidence, structured JSON, provenance, deterministic regeneration, independent software audits, and recorded source-review decisions. The downstream chatbot is still a planned system: normalization, chunking, embeddings, indexing, retrieval, answer generation, API behavior, and frontend functionality are not implemented by their placeholder directories.

The final 500-document milestone completed on **15 October 2026**, according to its recorded run end. All 500 passed schema, meaningful-text-preservation, and determinism checks. The report records 312 automated semantic-completeness flags, while review-based accounting identifies 300 semantically complete documents and 200 retaining source ambiguity. There were 188 documents with Extract warnings and 873 warning diagnostics. These are different measures, not interchangeable success rates. The accepted scope has no recorded unresolved parser failure or unexplained semantic failure; it is not a claim that all Vietnamese legal material has been extracted correctly or completely. [Current acceptance evidence](validation/report.json)

Subsequent consolidation unified extracted data at `data/extracted/vbpl/<source-id>/`, reduced 726 bundle copies to 500 identities, and replaced three task-size report trees with one canonical report root and an indexed historical proof archive. It retained 195 original archive members and removed 852 superseded report artifacts. Documentation was reduced from 21 files to seven current engineering documents. Cleanup review found and repaired default CLI input resolution and clarified the migrated target-manifest hash. The recorded post-cleanup full suite passed 649 tests with no skips. These later results remain local working-tree evidence rather than committed release history. [Migration and review ledger](consolidation/migration.json)

The practical next step is to make this accepted ingestion baseline durably reproducible, resolve remaining reporting metadata debt, and define the Normalized contract before implementing retrieval. More collection alone would not establish production readiness.

## 2. Project Objectives and Scope

The eventual product objective is a Vietnamese legal-document assistant that retrieves relevant material and generates answers with traceable citations. The implemented work deliberately addresses the prerequisite evidence chain: **VBPL collection → immutable RAW → structured Extract → independent validation and reporting**. Current architecture documents describe the future route from normalization and chunks through indexing, retrieval, generation, and API/UI delivery. Those descriptions are design intent, not evidence of executable downstream behavior. [Architecture](../docs/architecture.md), [README](../README.md)

Within the implemented boundary, success means preserving source wording, source order, document identity, legal hierarchy, physical and logical table relationships, and supported provenance. Unknown dates, unresolved references, incomplete quotations, ambiguous table axes, and incomplete source text must stay visible rather than being completed by inference. A consolidated legal text is not automatically legally effective; source identity is distinct from the legal document number.

The Extract contract preserves separate tab artifacts rather than merging them into a normalized legal document record. Typical bundles contain `content.json`, `properties.json`, `history.json`, `relations.json`, and `manifest.json`; optional captured tabs explain why the current 500 bundles contain more than 2,500 files. Extraction is offline and deterministic. Collection is an explicit network operation; extraction does not call an LLM or fetch missing source content. [Finalization specification](../docs/EXTRACTION_FINALIZATION_SPEC.md), [Extract schema guide](../docs/extracted-schema.md)

This scope excludes OCR reconstruction, attachment-body parsing, authoritative legal-status computation, legal interpretation, production search quality, and answer-quality evaluation. Preserving captured HTML faithfully does not establish that every document's complete legal body was available in that HTML.

## 3. Initial Project State

The earliest recoverable commit, `2248bad`, is dated **30 September 2026, 10:11:55 +07:00** and contains 34 tracked files. It already includes a Python package scaffold, architectural and data-convention documents, a VBPL ingestion module at `ingestion/vbpl.py`, `scripts/verify_vbpl.py`, and a crawler-oriented unit test. The project therefore did not begin in the available history as an empty directory. Earlier work, if any, cannot be reconstructed from the inspected branch history and reflog alone.

At that point, planned API, core, generation, indexing, preprocessing, and retrieval packages were represented by package markers. The tree also reserved frontend, configuration, prompts, notebooks, storage, evaluation, and data directories using placeholders. Its data layout included `data/processed/`; the current explicit Extract/Normalized/Chunks layering emerged later. The initial tree does not demonstrate an operational chatbot, a retrieval index, or a completed extraction-evaluation pipeline. Its README described cleaned full-text HTML/TXT and attachment downloads. Current collection deliberately preserves rendered HTML tabs and separates offline JSON extraction, excluding Download/Original-document tabs and attachments. This is a changed collection policy and responsibility boundary, not evidence that attachment parsing was completed and then retained.

Two subsequent September commits removed the standalone verification script/documentation and added crawler unit tests while removing older VBPL tests. These changes support a transition toward maintained package tests, but commit subjects alone do not prove every operational claim made in later reports.

Reconstruct this baseline with `git ls-tree -r --name-only 2248bad` and inspect specific contents with `git show 2248bad:PATH`. No remote repository URL is assumed. The current initial-state comparison is anchored to that recoverable snapshot, not an invented project-start narrative.

## 4. Chronological Development Timeline

| Recorded time or interval | Evidence-backed development | Evidence status |
|---|---|---|
| 30 Sep, 10:11:55 +07:00 | `2248bad`: first recoverable scaffold, crawler, verification utility, tests and documentation | Git commit; earliest recoverable state |
| 30 Sep, 10:27:26 +07:00 | `2cadff9`: removal of standalone verification script and related documentation | Git commit |
| 30 Sep, 21:08:20 +07:00 | `8971478`: crawler unit-test additions and removal of older VBPL tests | Git commit |
| By 6 Oct, 22:33:27 +07:00 | `b528e31`: Extract 2.3.2 checkpoint before autonomous freeze; schema and semantic extraction already present | Git commit; not a complete history of each earlier schema iteration |
| 6 Oct, 22:43:39–22:51:00 +07:00 | Reflog-only `2027849`: autonomous freeze goal/task, validator and loop script added; reflog then records reset to `b528e31` | Recoverable abandoned checkpoint, outside current branch ancestry; no execution outcome established |
| 6 Oct 17:50 UTC–8 Oct 03:36 UTC | Recorded 50-document validation run and report generation | Archived run timestamps and report |
| 8 Oct, 12:01:32 +07:00 | `4685557`: batch-50 completion checkpoint | Git commit; inspect its tree rather than assuming today's report paths existed then |
| 8 Oct, 13:42:33–14:06:49 +07:00 | `d108b5c`: test refactoring; `81f6bf5`: operating-guide refactoring | Git commits; `81f6bf5` is current HEAD |
| 8 Oct 07:30–20:05 UTC | 100 additional selected documents, five gated waves, cumulative acceptance context of 151 including golden | Archived local run evidence; later than HEAD's recorded work |
| 8 Oct 20:06 UTC–15 Oct 07:47 UTC | Expansion and hardening to 500 total source identities; continuous wave numbering through 23 | Local run state, reviews, audits and final report |
| 15 Oct 07:40 UTC | Final uniform verification records 500 regenerated/audited outputs matching approved bundles and unchanged RAW | Final uniform proof |
| After the 15 Oct acceptance, before the 18 Oct inspection | Report/data/doc consolidation, two review rounds, CLI and target-hash corrections | Local migration ledger; no secure completion timestamp inferred from file modification times |
| 18 Oct inspection | Current structure, archive, accepted bundle hashes and protected-file hashes assessed read-only | Assessment checks; no new full-suite run or collection |

There are seven commits reachable from the current branch, ending at `81f6bf5`, plus one additional unique commit recoverable through the inspected reflog: `20278499f8a7b066c2f1878268437330012784ab`. The 100-document run, 500-document hardening, and consolidation are local evidence, not additional current-branch commits. At inspection, the local branch was `main` at the same reported HEAD as `origin/main`, while substantial tracked and untracked work remained. This is a material reproducibility boundary: checking out HEAD alone would not recreate the current accepted local system.

Historical run timestamps come from the archived 50/100 report JSON and the [current run record](validation/report.json). The date assigned to consolidation is intentionally an interval: filesystem timestamps are insufficient to establish an execution chronology.

The reflog-only automation checkpoint added five files/changes totaling 1,115 inserted lines: `.codex/extract-freeze-goal.md`, `.codex/extract-freeze-task.md`, an `AGENTS.md` addition, `scripts/codex_extract_freeze_loop.sh`, and `scripts/validate_extract_freeze.py`. Its task described generic parser repair followed by tests, actual extraction and a deterministic validator; its loop defined cycle/no-progress controls and validation/status files. These show a recoverable automation design, not proof that the loop ran or achieved acceptance. They are not active files in the current tree. The reflog records the historical reset; no reset, restoration or execution was performed for this report. Inspect with `git show 2027849 --stat` and `git show 2027849:PATH`.

A separate organization milestone is recorded in `git show d108b5c:docs/python-layout.md`: 264 passing tests without skips, a copied-state offline audit of 209 published tab JSON artifacts across the 50 captures and golden, and unchanged protected files. The documented audit retained its source-warning exit status. This bridges the 248-test sample report and later hardening; it is a historical recorded verification, not a test or audit rerun for this assessment.

## 5. Major Technical Milestones

**Collection became a preserved evidence layer.** The crawler captures rendered VBPL HTML tabs and manifests, records source URL, identity, scope classification, capture metadata and hashes, and distinguishes Central/Local using source breadcrumbs. It excludes the Download and Original-document tabs under the current HTML-only collection policy. The evaluation runner adds selection, reuse of verified local captures, failure classification, and gated continuation. Capture success is therefore distinct from successful extraction and from inclusion in the accepted target. [Crawler guidance](../docs/vbpl-crawl.md), [validation runner](../src/vietnam_legal_rag/evaluation/validation_runner.py)

**Extraction acquired a versioned semantic contract.** Schema/parser release 2.3.2 represents a legal document with header, title, preamble, body, closing and annexes; source-backed legal hierarchy and form structures remain within that contract. Hierarchy levels are optional. The parser must distinguish genuine legal provisions from amendment quotations, annex numbering, headers, and form inputs. Metadata tabs remain separate. Public schema release identity is distinct from the implementation fingerprint used to detect code changes during hardening. [Authoritative schema](../schemas/extracted.schema.json)

**Table handling became both more expressive and more scalable.** Physical cells, merged geometry, source order and supported semantic associations are retained. The largest reviewed capture recorded 46,485 physical cells. Source-cell and row/column indexes plus active merged-cell rectangles replaced repeated whole-table scans. This matters because performance was improved without skipping large tables, flattening their relationships, or introducing a document-specific size exemption. The recorded milestone evidence includes actual large-capture audit work; this assessment did not rerun it. [Table-performance record](validation/report.json)

**Evaluation became resumable and evidence-bearing.** Inventories and target manifests count distinct source identities, audit state records parser fingerprints, and wave gates require cumulative validation, source-review decisions and passing tests before continuation. The final accepted corpus was regenerated uniformly under the final parser rather than assembled from outputs accepted at different parser states. Independent software audits inspect serialized artifacts against captured RAW; their independence is an implementation boundary, not legal certification.

**Consolidation separated durable evidence from task scaffolding.** Current data no longer depends on whether a document first appeared in a 50-, 100-, or 500-document task. Historical acceptance inputs remain recoverable through archive members and hashes, while superseded checkpoints and repetitive diagnostics were removed. The repository now has a smaller operational surface without discarding the accepted identities.

## 6. Progress from 50 to 100 to 500 Documents

The milestone labels have different denominators. **100 means a new selected sample after the first 50; 500 means the final total collection.** The golden document is counted separately from those two samples before joining the final target.

| Measure | First 50 selected | Next 100 selected | Final 500 total |
|---|---:|---:|---:|
| Central / Local source category | 25 / 25 | 45 / 55 | 250 / 250 |
| Extract success | 41 | 46 | 312 |
| Success with warnings | 9 | 54 | 188 |
| Failed Extract documents | 0 | 0 | 0 |
| Schema valid | 50/50 | 100/100 | 500/500 |
| Deterministic | 50/50 | 100/100 | 500/500 |
| Meaningful source text preserved | 50/50 | 100/100 | 500/500 |
| Automated semantic-complete flag | 41/50 | 46/100 | 312/500 |
| Recorded warning diagnostics | 28 | 94 | 873 |
| Recorded passing test-run size | 248 | 324 | 640 at final acceptance |

Sources: original archive members `reports/extract-validation-50/report.json` and `reports/extract-validation-100/report.json`, and [final report](validation/report.json). These are historical sample results under their respective parser states. Their semantic-completeness percentages are not a controlled trend experiment: sample composition and parser behavior both changed.

The 50-document milestone recorded 36 repaired parser bug classes, 25 promoted capture regressions, and retained ambiguity rather than forcing all flags true. The next 100 selected documents recorded another 36 new bug classes and reached a cumulative validation context of **50 + 100 + 1 golden = 151**. Its 54 warning documents include 53 documents classified as retaining source ambiguity; warning-document and ambiguity classifications are not identical sets.

The final total is **150 earlier sample documents + 1 golden + 349 additional selected identities = 500**. Collection accounting provides a second, independent partition: **183 initially usable local captures + 317 actually new captures = 500**. Some captures were reused after initial scope-hint mismatches; the 296 “successfully crawled sample” entries in subrun accounting are therefore not the total newly captured RAW count. The accepted target contains no rejected or missing target identities, but collection did experience failed attempts and environment/network failures. “All targets accepted” does not mean every attempted crawl succeeded.

The final hardening report records **187 new bug-class IDs across the next-100 and expansion phases: 36 + 151**. This field excludes the original 50-document milestone's separate 36 classes; it should not be described as the whole project's lifetime defect total. It also records extensions to existing classes separately. Counts of bug classes, promoted captures, test methods and executed tests answer different questions and must remain separate.

## 7. Architecture Evolution

The initial scaffold placed VBPL work in a single ingestion module. The current package separates transformation responsibilities while keeping crawl/extract modules as orchestration layers:

```text
src/vietnam_legal_rag/
├── cli/                    command parsing and dispatch
├── ingestion/
│   ├── html/               source DOM, document structure, physical tables
│   ├── semantics/          hierarchy, quotations, table meaning, VBPL tabs
│   ├── refinement/         forms, lists, semantic second pass, schema cleanup
│   └── validation/         parser-facing quality and structural diagnostics
└── evaluation/
    ├── audit/              independent serialized-artifact audits
    └── configuration, inventory, target selection, progress, gates, reports
```

This division addresses two different kinds of correctness. Parser-facing validation can reject invalid schema or suspicious structures near transformation code. Evaluation audits must independently compare actual output with captured evidence rather than simply reuse the extractor's own answer. Sampling, inventories, report construction and run recovery belong to evaluation, not to document transformation or one-off scripts. [Module responsibilities](../docs/python-layout.md)

`pyproject.toml` owns the `vlr` entrypoint and compatibility aliases `vbpl-crawl-one` and `vbpl-extract`. Four small scripts retain older invocation paths while forwarding to package code. Unit tests mirror the package, regression tests own reviewed capture and pattern cases, and fixtures pin stable source-backed expectations. The schema resource remains linked to the authoritative repository contract and packaged for distribution.

The active storage layout is `data/raw/vbpl/<scope>/<id>/` and `data/extracted/vbpl/<id>/`. Extract identity is the source identity suffix, not a legal document number or validation wave number. Current report inputs live under `reports/validation/evidence/`; historical originals live in an indexed ZIP. The baseline reader supports archive locators directly, avoiding ad hoc extraction directories for normal audits. [Data conventions](../docs/data-conventions.md), [workflow](../docs/extract-validation-workflow.md)

### Development orchestration and multi-agent configuration

The current local `.codex/` configuration adds an explicit development workflow around those package responsibilities. [config.toml](../.codex/config.toml) declares `gpt-6.1-sol` with medium reasoning for the main/default subagent configuration, enables agents, and sets `max_concurrent_threads_per_session = 3`. Four role files provide the following instructions:

| Role | Configured model / reasoning | Assigned responsibility and write boundary |
|---|---|---|
| `vbpl_explorer` | `gpt-6-luna` / high | Read-only code, dependency, fixture and evidence inspection; no crawling, expensive tests or state mutation |
| `vbpl_planner` | `gpt-6.1-sol` / high | Scope, contracts, risks, implementation steps and verifiable acceptance criteria; no application/test edits |
| `vbpl_coder` | `gpt-6.1-sol` / medium | Sole implementation writer for assigned scope; focused fixes and regression tests; preserve RAW and evidence |
| `vbpl_reviewer` | `gpt-6.1-sol` / high | Independent stable-diff review against requirements, plan and actual checks; no source/test edits |

Sources: [explorer.toml](../.codex/agents/explorer.toml), [planner.toml](../.codex/agents/planner.toml), [coder.toml](../.codex/agents/coder.toml), [reviewer.toml](../.codex/agents/reviewer.toml).

[AGENTS.md](../AGENTS.md) makes the main session the orchestrator and routes medium work through Planner → Coder → deterministic Quality Gate → Reviewer → Final Gate. Complex work begins with at most two parallel read-only explorers; edits and state/regeneration writes are serialized through one implementation writer, and review uses a stable diff. At most three fix/review rounds are allowed before replanning or reporting a real blocker. The orchestrator retains final acceptance responsibility; reviewer PASS alone is insufficient.

This is an evolution from the recoverable single-loop freeze attempt toward role separation, explicit handoffs and acceptance gates. The current configuration is untracked local work, and its introduction date is not established by Git. TOML model/reasoning/thread settings and read-only role instructions are configuration intent, not proof that every runtime honored them or that sandbox isolation is enforced. Runtime stages actually evidenced by the consolidation ledger include independent review after corrections; the files alone do not prove execution of every prescribed stage in every earlier task.

The architectural evolution is substantial in ingestion/evaluation, but it has not crossed into implemented retrieval. Package markers in downstream directories reserve ownership; they are not substitute implementations.

## 8. Engineering Problems and Solutions

| Problem | Implemented response and why it matters | Remaining boundary |
|---|---|---|
| Legal hierarchy competes with quotations, decimal annex counters and source headings | Generic hierarchy and quotation rules preserve parentage, order and local amendment boundaries; regression cases guard similar patterns | Missing source punctuation remains explicit ambiguity |
| Blank forms resemble populated facts | Bounded form scopes, prompt/label evidence, blank handling and null values distinguish requested inputs from supplied values | Unknown source semantics stay unknown |
| Bilingual prompts, repeated letterheads and template headers split incorrectly | Generic caption, header and input-run rules retain source text and boundaries; no production UUID/title exceptions | Latest wave still discovered new patterns |
| Layout tables and data tables need different treatment | Physical geometry is retained while semantic roles require supporting evidence; headerless axes are not invented | Source markup may not justify full table semantics |
| Large merged tables cause repeated scans | Shared indexes and merged-cell tracking improve algorithmic behavior without discarding cells | Corpus-wide performance limits remain unmeasured |
| Collection scope hints disagree with captured pages | Breadcrumb classification and explicit mismatch/reuse accounting govern selection | Central/Local source categories are not inferred issuer jurisdiction |
| Interrupted work creates mixed parser states and stale progress | Atomic state, parser fingerprints, cumulative audits and gated waves preserve resumability | Historical aliases and report pointers still need discipline |
| Cleanup breaks default CLI inputs | Audit/report resolve saved accumulated state and configuration; archived baseline manifests remain readable | Explicit new runs still need deliberate state/report roots |
| Migrated target paths change its byte hash | Original and live SHA-256 values are mapped; equality is checked after only role-manifest locator substitutions | Historic hash must never be overwritten merely to match new bytes |

Concrete late-wave repairs included parenthetical colons inside terminal form prompts, referenced blanks followed by completion prose, repeated uncoded template letterheads, grid-pair prompt evidence, and partial template document-number suffixes. These are source-pattern repairs rather than document-specific patches. The final report records 11 new classes in the last wave, which is evidence against assuming parser convergence over the entire source corpus. [Hardening record](validation/report.json)

The broader engineering discipline is to fix transformation rules, add focused regressions, regenerate from preserved RAW, and revalidate affected accumulated documents. Neither legal JSON hand edits nor schema-version inflation is an acceptable way to hide a parser defect. Existing schema 2.3.2 could express the reviewed structures, so the milestone did not require a contract redesign.

## 9. Testing, Validation and Acceptance

The evidence supports several separate verification layers:

1. **Unit and portable regression tests** exercise synthetic DOM, hierarchy, table, form, sampler, state and CLI behavior without uncontrolled collection.
2. **Capture regressions** pin reviewed RAW hashes and structural expectations. Local-capture availability matters; zero skips in the recorded runs means those runs did not omit their then-required captures.
3. **Per-document software audits** compare serialized Extract artifacts with RAW, inspect source text/provenance/structure, and check deterministic regeneration.
4. **Source-review records** classify meaningful ambiguity and parser failure separately. These records establish repository acceptance decisions; they do not establish licensed legal-expert review or independently verified human-review provenance.
5. **Final milestone gates** require uniform current-parser revalidation, completed wave gates, passing tests and repository hygiene.

The final uniform proof records 500 actually regenerated documents, 500 independently audited documents, 500 unchanged RAW hash sets and 500 approved output bundles remaining byte-identical. All 500 passed schema, determinism and meaningful-text preservation. The implementation fingerprint is the full SHA-256 stated at the beginning of this report. [Frozen parser proof](validation/evidence/final-parser-candidate.json), [uniform verification](validation/evidence/final-uniform-verification.json)

Semantic accounting requires special care. The report labels its 300-document measure “Human semantic completeness”; this report uses **review-based completeness** because the artifacts do not independently prove who performed each review. The automated flag is true for 312 documents. Review-based completeness is 300; 200 retain meaningful source ambiguity. Extract warnings affect 188 documents. The 873 warning diagnostics are classified as 852 source ambiguities and 21 expected non-semantic source artifacts. Thus warning count, warning-document count, ambiguity-document count, and semantic-complete count are different denominators. No recorded error/fatal diagnostics, known parser failures or unexplained semantic failures remain within the accepted milestone.

| Recorded verification | Actual observed result in preserved evidence | Assessment treatment |
|---|---|---|
| Final 500 full suite | 640 tests, 0 skips, `OK`, 132.285 seconds | Historical run; log inspected, not rerun now |
| Cleanup correction full suite | 649 tests, 0 skips, `OK`, 133.997 seconds | Historical run; log inspected, not rerun now |
| Cleanup independent review | PASS after two rounds; ledger records a 47-test focused run, 0 skips | Review evidence; not a new full-suite run |
| Current accepted-bundle check | 500 bundles / 2,563 artifact hashes matched frozen maps | Read-only check for this assessment |
| Current preservation/archive check | 2,585 protected hashes and 195 indexed archive members verified | Read-only check for this assessment |

The final report separately records 331 portable hardening test methods and 86 hardening regression captures. Those are coverage inventory counts, not executed-suite totals; the capture collections can overlap the original 25 promoted batch regressions and must not be added as disjoint populations.

The 649 test executions are not a claim of 649 static test methods: parameterization, helpers and suite structure can affect execution counts. The assessment did not repeat full tests, schema validation, extraction, or live collection. It read existing evidence and performed bounded file/hash checks. The distinction matters because a hash match confirms preserved accepted bytes, while a fresh schema audit or a new extraction run would be a different operation. [Final test log](validation/evidence/final-full-tests.txt), [cleanup test log](consolidation/review-full-tests.txt)

## 10. Repository Consolidation and Deep Cleanup

Consolidation replaced task-size-specific storage with a stable source-identity collection. Before migration, 726 bundle copies represented only 500 distinct identities. Of the superseded copies, 161 differed from the final accepted bundle. Selection therefore used approved output hashes, parser/schema compatibility and RAW provenance rather than blindly preferring newer filenames. The migration retained all unique accepted identities and removed 226 redundant bundle copies. It did not manually alter extracted legal content or modify RAW. [Migration ledger](consolidation/migration.json)

Reports were classified by ongoing operational or evidentiary value. Current target, accumulated audit state, source reviews, final frozen proof, uniform verification and final tests remain directly available. The archive retains original bytes of unique acceptance inputs, source/fixture decisions and necessary historical baseline reports. Superseded checkpoint histories, candidate/initial audits and repetitive logs were pruned. Historical prose mentioning a discarded intermediate output does not make that output a permanent dependency; the disposition ledger explains removals.

Documentation retains architecture, data conventions, the finalization specification, workflow, schema guide, Python layout and crawler guidance. Fourteen generated or superseded audit/report documents were removed after consolidating active guidance. The four compatibility script wrappers, schema resource, regression fixtures, configuration and placeholders remain.

| Area | Before cleanup | Current pre-report snapshot | Interpretation |
|---|---:|---:|---|
| Extracted files | 3,708 / 287,905,246 bytes | 2,564 / 244,171,598 bytes | Includes root `.gitkeep`; 500 bundles contain 2,563 JSON files |
| Report files | 1,047 / 738,899,167 bytes | 25 / 102,030,251 bytes | Includes compressed proof and consolidation evidence; excludes this new report |
| Documentation files | 21 / 696,397 bytes | 7 / 66,935 bytes | Current engineering guidance retained |
| Original report artifacts retained in archive | Dispersed | 195 members | ZIP members are not counted as separate live filesystem files |
| Superseded original report artifacts removed | Dispersed | 852 | Their dispositions and original hashes remain recorded |

File sizes are logical bytes, not allocated disk blocks. The ledger's saved post-cleanup report total is 102,031,941 bytes, 1,690 bytes above the fresh pre-report measurement because metadata writes changed its own size. This is a measurement-time difference, not missing validation data. Adding this file makes 26 report files; the comparison intentionally keeps the pre-report baseline fixed.

Independent cleanup review initially found two material problems: default audit/report commands pointed at incompatible progress/sample inputs, and the frozen target hash was unexplained after locator migration. Corrections reused the existing audit path, inferred saved canonical configuration, read archived baseline manifests, and added explicit original/live target-hash equivalence. Synthetic CLI checks cover 349 selected + 150 baseline + golden = 500 without rerunning an expensive audit against accepted state. Final ledger review is PASS. This does not eliminate all metadata debt described in Section 13.

## 11. Initial versus Current Comparison

| Dimension | Earliest recoverable state | Current evidenced state |
|---|---|---|
| Main implementation | Crawler experiment within a package scaffold | Collection, offline semantic Extract, audits and resumable evaluation |
| Data layering | RAW plus a reserved processed layer | Explicit RAW → Extracted; Normalized/Chunks reserved |
| Extraction contract | No current 2.3.2 contract established by that initial tree | Authoritative schema 2.3.2 and packaged resource |
| Validation corpus | No 500-document acceptance evidence | 500 distinct accepted source identities with frozen output/RAW proof |
| Legal structure | Later semantic capability not established by initial tree | Optional hierarchy, quotations, annexes, forms and table relationships |
| Verification | Crawler tests and standalone verification utility | Unit/capture regressions, independent software audits, source-review records and gates |
| Storage organization | Initial collection layout | One canonical Extract root and one canonical report root |
| Product behavior | Planned RAG assistant | Still no implemented retrieval/generation/API/UI pipeline |
| Development orchestration | No current four-role configuration in the initial tree; later reflog-only freeze-loop attempt | Local four-role `.codex/` configuration and AGENTS plan/code/gate/review workflow; configured intent distinguished from evidenced execution |
| Version-control reproducibility | Recoverable initial commit | Seven current-branch commits plus one reflog-only checkpoint; HEAD plus substantial uncommitted implementation and local corpus/evidence |

The largest change is depth and reliability of the ingestion/evaluation layer, not completion of the full product. Maintaining that distinction prevents architectural placeholders from being mistaken for delivered RAG capabilities.

## 12. Subsystem Status

The status vocabulary is **implemented and verified**, **implemented but incomplete/insufficiently verified**, **partial/experimental**, **placeholder/planned**, and **not implemented**. “Verified” below is bounded by the reviewed 500-document extraction milestone and cited historical checks; it does not mean production-wide correctness. A package marker is classified as planned scaffolding even when its directory name describes a sophisticated capability. No delivered downstream component is inferred from configuration intent.

| Subsystem | Status | Concrete evidence and boundary |
|---|---|---|
| VBPL collection | Implemented and verified, bounded to the accepted collection | [Crawler](../src/vietnam_legal_rag/ingestion/crawl_legal_documents.py), [crawler tests](../tests/unit/ingestion/test_crawl.py), RAW manifests and final collection accounting; HTML-only policy, not attachment ingestion |
| RAW storage and preservation | Implemented and verified for the 500 usable captured identities | [Local RAW inventory](validation/evidence/local_raw_inventory.json), [crawler manifest handling](../src/vietnam_legal_rag/ingestion/crawl_legal_documents.py), [protected-hash ledger](consolidation/migration.json) and frozen RAW hash maps; 500 usable manifests are accepted, while the one preserved unusable staging path is excluded from target acceptance |
| HTML parsing | Implemented and verified within captured layouts | [Source DOM parser](../src/vietnam_legal_rag/ingestion/html/source.py), [structure handling](../src/vietnam_legal_rag/ingestion/html/structure.py), [structure tests](../tests/unit/ingestion/html/test_structure.py); source references and physical DOM evidence retained |
| Structured extraction | Implemented and verified for the 500 accepted identities | [Extractor](../src/vietnam_legal_rag/ingestion/extract_legal_documents.py), [extraction tests](../tests/unit/ingestion/test_extract.py), frozen bundle hashes and uniform proof; separate tab JSON rather than normalized cross-tab records |
| Semantic interpretation and form refinement | Implemented and verified for reviewed patterns | [Form refinement](../src/vietnam_legal_rag/ingestion/refinement/forms.py), [semantic pass](../src/vietnam_legal_rag/ingestion/refinement/semantic.py), [form tests](../tests/unit/ingestion/refinement/test_forms.py); source ambiguity remains explicit |
| Legal hierarchy | Implemented and verified for reviewed legal/annex/quotation structures | [Hierarchy](../src/vietnam_legal_rag/ingestion/semantics/hierarchy.py), [quotation handling](../src/vietnam_legal_rag/ingestion/semantics/quotations.py), [hierarchy tests](../tests/unit/ingestion/semantics/test_hierarchy.py); no invented missing levels |
| Table extraction and semantics | Implemented and verified for reviewed captures, including the large-table case | [Physical tables](../src/vietnam_legal_rag/ingestion/html/tables.py), [table semantics](../src/vietnam_legal_rag/ingestion/semantics/tables.py), [hardening regressions](../tests/regression/test_hardening_patterns.py); unknown source axes remain unknown |
| Provenance preservation | Implemented and verified for accepted artifacts | [Extractor manifest logic](../src/vietnam_legal_rag/ingestion/extract_legal_documents.py), [independent Extract audit](../src/vietnam_legal_rag/evaluation/audit/extract.py), RAW/output hash maps; source identity and legal number remain distinct |
| Schema validation | Implemented and verified under schema 2.3.2 | [JSON Schema](../schemas/extracted.schema.json), [parser-facing validator](../src/vietnam_legal_rag/ingestion/validation/extract.py), [validator tests](../tests/unit/ingestion/validation/test_extract.py); fresh schema validation was not repeated for this report |
| Independent software audit | Implemented and verified in recorded milestone runs | [Extract audit](../src/vietnam_legal_rag/evaluation/audit/extract.py), [hierarchy audit](../src/vietnam_legal_rag/evaluation/audit/hierarchy.py), [schema audit](../src/vietnam_legal_rag/evaluation/audit/schema.py), uniform verification; not legal certification |
| Regression testing | Implemented and verified by preserved execution evidence | [Golden tests](../tests/regression/test_golden.py), [batch capture tests](../tests/regression/test_batch_capture.py), [portable source patterns](../tests/regression/test_source_patterns.py), hardening captures; latest preserved full run is 649 tests with zero skips |
| Evaluation and reporting | Implemented but incomplete/insufficiently verified as a fully clean operational surface | [Report writer](../src/vietnam_legal_rag/evaluation/report_writer.py), [runner](../src/vietnam_legal_rag/evaluation/validation_runner.py), [report tests](../tests/unit/evaluation/test_report.py), [CLI tests](../tests/unit/cli/test_commands.py); acceptance metrics are supported, but Section 13 identifies unresolved narrative evidence pointers |
| Data/report consolidation | Implemented and verified for migrated identities and protected bytes | [Migration ledger](consolidation/migration.json), [consolidation tests](../tests/unit/evaluation/test_consolidation.py), target-hash mapping and archive index; retained source documents are not proof of complete VBPL coverage |
| Chunking and indexing | Placeholder/planned | [Preprocessing marker](../src/vietnam_legal_rag/preprocessing/__init__.py), [indexing marker](../src/vietnam_legal_rag/indexing/__init__.py), reserved chunks/index storage; no chunk builder or index lifecycle implemented |
| Embeddings and vector database | Not implemented | Package/dependency and source inspection establish no chosen/integrated embedding model or vector database; requires versioned chunks, model configuration and index persistence |
| Retrieval and reranking | Placeholder/planned | [Retrieval marker](../src/vietnam_legal_rag/retrieval/__init__.py); no executable search/reranking or retrieval benchmark result |
| Generation and citation answers | Placeholder/planned | [Generation marker](../src/vietnam_legal_rag/generation/__init__.py); no model integration, grounded-answer pipeline or answer-quality evidence |
| API | Placeholder/planned | [API marker](../src/vietnam_legal_rag/api/__init__.py); no implemented endpoints or runnable service evidenced |
| Frontend | Placeholder/planned | [Frontend placeholder](../frontend/.gitkeep); no application or frontend framework evidenced |

The **partial/experimental** category does not establish a current downstream prototype: the initial crawler and reflog-only automation attempt were experimental historical work, while current downstream directories remain scaffolding. Application core, prompts and configuration are also reserved; end-to-end product evaluation is not implemented. Current RAW and Extract each contain 2,563 document artifacts plus their layer `.gitkeep`, or 2,564 files. RAW artifacts are HTML/manifests; Extract artifacts are JSON. The 501 capture-path count includes one unusable staging path, which is preserved but excluded from acceptance.

## 13. Limitations and Technical Debt

**Source completeness remains the dominant data limitation.** The crawler excludes Download/Original-document tabs and does not parse their attachments. Formula images and image-only content are retained without OCR. Some captured pages provide summaries, omit referenced attached bodies, contain replacement characters, or lack safe table axes, signer names, dates, or relationship links. Fidelity to those pages is useful evidence, but cannot restore omitted legal material. The system must continue to distinguish unavailable source semantics from a parser failure.

**The sample does not establish universal correctness.** The corpus is balanced by VBPL source category, not proven representative of all issuers, periods, document formats or legal questions. Late discovery of 11 new bug classes in the last wave shows continuing source variation. No representative holdout, corpus-wide recall estimate, production reliability target, or downstream answer evaluation has been established by the cited milestone.

**Version-control and reproducibility debt remain.** The current accepted state includes substantial uncommitted tracked and untracked work beyond HEAD. Local RAW and derived corpora are ignored by Git, so source checkout alone cannot reproduce acceptance. A controlled source/evidence backup and a reviewed release boundary are still needed; this report neither commits files nor claims such a release exists.

**Some active report metadata still points at removed loose files.** In both the current report and `evidence/report-context.json`, `hardening.repair_evidence` includes bare `evidence/repairs.json`, which no longer exists loose; its original 500-run repairs file is retained in the archive. `historical_evidence.first50` and `first100` also retain removed-directory references even though corresponding original archive members exist. These are reporting locator defects, not loss of the archived acceptance evidence. The cleanup ledger's broad stale-path assertion should therefore be read narrowly: it does not prove every narrative pointer is current. They are documented here rather than changed under this report-only task.

**Operational claims have practical boundaries.** TOML dependencies and entrypoints express package configuration, not proof of every deployment environment. Independent audit software and repository review decisions are not independent legal certification. Legal effectiveness must not be inferred from dates, consolidation status or successful parsing. There is no demonstrated production backup policy, hosted service, monitoring, security review, search latency objective or chatbot evaluation in the accepted scope.

## 14. Recommended Roadmap

The sequence below prioritizes dependencies and measurable gates; it does not invent delivery dates, staffing or budgets.

| Priority | Work package | Dependency and completion gate |
|---|---|---|
| 1 | Repair remaining report/context locators | Every active evidence pointer resolves to a live file or indexed archive member; verify archived hash and preserve original historical references separately |
| 2 | Establish a durable accepted baseline | Review current source changes, define source/evidence backup and restoration procedure, and obtain an explicitly authorized commit/release decision; restore the 500 identity/hash set from a clean environment |
| 3 | Define the Normalized contract | Specify cross-tab identity, source-backed metadata, unknown values, legal-status evidence and compatibility rules; review schema and representative fixtures before coding |
| 4 | Implement normalization and legal-aware chunks | Consume stored Extract only; preserve source references and hierarchy; demonstrate lossless traceability from each chunk back to RAW-supported spans |
| 5 | Define retrieval ground truth and evaluation protocol | After chunk semantics are fixed, create reviewed Vietnamese legal queries, expected source/chunk evidence and difficult negative cases; define recall, ranking and citation measures before comparing implementations |
| 6 | Implement embeddings, a versioned index/vector store, and retrieval | Consume the versioned chunks and ground truth; record embedding model/version/configuration and input chunk hashes, persist index membership/version, and implement retrieval/reranking against an evaluated baseline. Gate: repeatable index membership for identical inputs/configuration, no missing or stale chunk-hash mappings, measured retrieval results against the ground-truth set, and documented update/rebuild behavior |
| 7 | Introduce generation and citation verification | Condition answers on retrieved evidence, preserve uncertainty and missing-source limits; evaluate support, citation correctness and abstention independently of fluency |
| 8 | Implement API/frontend and operational controls | Expose evaluated capabilities through tested interfaces; define latency, monitoring, access, secret handling and recovery requirements from actual deployment needs |
| Parallel bounded work | Expand parser coverage and investigate attachments/OCR separately | Use new, explicitly scoped samples/holdouts; freeze existing evidence, maintain offline determinism, and establish a new uniform acceptance run after parser changes |

The indexing/retrieval gate must precede generation: a vector-store connection alone is not a delivered retrieval subsystem. Fix model/version/configuration, make index builds deterministic where the chosen backend permits it, and explicitly account for any numeric/backend nondeterminism. Rebuilding identical chunks must preserve the document/chunk identity and input-hash mapping; retrieval quality must be measured against the same ground truth and an explicit baseline before using retrieved context for answers. No arbitrary accuracy threshold or infrastructure budget is asserted here.

Before broader ingestion, define the purpose of expansion: unseen-format coverage, temporal coverage, issuer diversity, attachment completeness or regression confidence. Each objective needs a selection plan and an acceptance denominator. Repeating a larger convenient sample without such a design would produce more files without a defensible estimate of generalization.

If attachments or OCR become necessary, treat them as a reviewed new source/transformation contract. Preserve original attachments, identify version and provenance, distinguish OCR uncertainty from source text, and avoid silently substituting reconstructed wording for the existing captured HTML evidence.

## 15. Final Assessment

Vietnam Legal RAG currently has a substantial ingestion and evaluation foundation: preserved VBPL captures, an explicit semantic Extract contract, a final uniformly validated 500-document target, reproducible artifact hashes, extensive recorded tests, and a consolidated operational structure. The work demonstrates disciplined handling of legal source evidence rather than a completed legal assistant.

The accepted milestone is credible within its stated boundary. All 500 target identities are accounted for, the final accepted bundles match their frozen maps, and protected evidence remains intact. Source ambiguity is quantified rather than suppressed. Cleanup reduced duplicated storage while preserving original acceptance material, and review corrected substantive operational problems.

The boundary is equally clear: full legal-body completeness, universal parser correctness, legal-effectiveness determination and end-to-end RAG behavior remain unproven or unimplemented. Current development should preserve this source-faithful baseline, close the remaining evidence-pointer and release-reproducibility gaps, and advance downstream stages through explicit contracts and evaluated gates.

## 16. Evidence References

All links below are relative to this report in `reports/`. ZIP members are identified as member names, not presented as nonexistent filesystem links. Dates and quantitative claims should be checked against the corresponding machine-readable source, not only this narrative.

| Evidence | Source and purpose |
|---|---|
| Current-branch Git history | `git log --reverse --format='%h %ad %s' --date=iso-strict`; seven reachable commits from `2248bad` to `81f6bf5` |
| Reflog-only automation checkpoint | `git reflog --all --date=iso-strict`; additional unique commit `20278499f8a7b066c2f1878268437330012784ab`, inspected with `git show 2027849 --stat` and `git show 2027849:PATH`; historical reset recorded, not performed here |
| Historical organization checkpoint | `git show d108b5c:docs/python-layout.md`; recorded 264-test and 209-tab-JSON verification, not newly executed |
| Multi-agent operating configuration | [AGENTS.md](../AGENTS.md), [.codex/config.toml](../.codex/config.toml), and four [explorer](../.codex/agents/explorer.toml), [planner](../.codex/agents/planner.toml), [coder](../.codex/agents/coder.toml), [reviewer](../.codex/agents/reviewer.toml) role files; local configured intent and explicit gates |
| Initial tree | `git ls-tree -r --name-only 2248bad`; inspect with `git show 2248bad:PATH` |
| Contract checkpoint | `git show b528e31:docs/extracted-schema.md`; establishes schema 2.3.2 by that checkpoint |
| Product scope and layout | [README](../README.md), [architecture](../docs/architecture.md), [Python layout](../docs/python-layout.md) |
| Current data and procedures | [Data conventions](../docs/data-conventions.md), [validation workflow](../docs/extract-validation-workflow.md), [crawler guidance](../docs/vbpl-crawl.md) |
| Legal-data correctness contract | [Finalization specification](../docs/EXTRACTION_FINALIZATION_SPEC.md), [schema guide](../docs/extracted-schema.md), [JSON Schema](../schemas/extracted.schema.json) |
| Package configuration | [pyproject.toml](../pyproject.toml); dependencies, version and CLI declarations |
| 50/100 original reports | [Historical archive](validation/history.zip), members `reports/extract-validation-50/report.json` and `reports/extract-validation-100/report.json`; accompanying original state, repairs, reviews and test logs retained where indexed |
| Archive integrity | [History index](validation/history-index.json); original member names, sizes and SHA-256 values |
| Final 500 results | [Report JSON](validation/report.json), [report Markdown](validation/report.md), [report context](validation/evidence/report-context.json) |
| Current source membership | [Target manifest](validation/evidence/target_manifest.json), [local RAW inventory](validation/evidence/local_raw_inventory.json) |
| Accumulated audits and review decisions | [Corpus state](validation/evidence/corpus_validation_state.json), [cumulative reviews](validation/evidence/cumulative_reviews.json) |
| Frozen implementation/output proof | [Final parser candidate](validation/evidence/final-parser-candidate.json), [uniform verification](validation/evidence/final-uniform-verification.json) |
| Historical execution evidence | [640-test log](validation/evidence/final-full-tests.txt), [649-test cleanup log](consolidation/review-full-tests.txt) |
| Consolidation and independent review | [Migration ledger](consolidation/migration.json), [cleanup report](consolidation/report.md), [migration-specific diff](consolidation/implementation.diff) |
| Recorded operational correction | [Default report rebuild output](consolidation/review-default-report.txt); command and result also recorded in ledger |
| Implemented orchestration | [Validation CLI](../src/vietnam_legal_rag/cli/validate.py), [runner](../src/vietnam_legal_rag/evaluation/validation_runner.py), [wave gates/archive manifest reader](../src/vietnam_legal_rag/evaluation/wave_gate.py), [target assembly](../src/vietnam_legal_rag/evaluation/target_manifest.py) |

For this reporting task, read-only inspection included current-branch Git history, reflog-only checkpoint contents, historical organization documentation, tree/status, current multi-agent configuration, source and placeholder inventories, the archived baseline JSON, final acceptance/context/ledger records, and preserved test-log endings. Bounded read-only checks also compared all 500 accepted bundle maps covering 2,563 JSON artifacts, the current parser fingerprint, 2,585 protected-file hashes, and 195 archive members. No full test suite, fresh schema audit, extraction/regeneration, collection, source modification, or acceptance-state update was performed to create this report. Only this Markdown file was authorized for writing.

To reproduce historical analysis, open the indexed archive and parse the named member directly with Python's `zipfile.ZipFile.read`; extract to a deliberate temporary location only when replaying a historical command requires real paths. Do not execute obsolete commands against live canonical evidence without understanding their output and state mutations. Current default audit writes selected audit state, while a report rebuild can use `--output-dir` to keep accepted reports separate. Any new execution should be recorded as new evidence rather than retroactively attributed to the historical logs summarized here.
