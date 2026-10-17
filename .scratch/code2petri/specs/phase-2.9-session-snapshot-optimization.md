# Phase 2.9: Compact and Reliable Fold State Snapshots

Status: ready-for-human

Implementation: complete (Tickets 51–52; updated 2026-10-16).

Ticket 51 is resolved. Ticket 52's download lifecycle is implemented and remains ready for human verification of completed downloads in Safari, Chrome, and Firefox. The problem statements below record the pre-implementation behavior, not a claim that the old serialization path is still active.

## Problem Statement

Users cannot reliably save larger folding sessions. Safari and Firefox reportedly abandon the download silently, while Chrome repeatedly presents a wait prompt. Small saves succeed. Users need to preserve their work without losing nested folds or waiting through unexpectedly large serialization workloads.

The visible graph size is a poor predictor of snapshot size. Each opaque transition currently stores its consumed subnet under two synonymous fields, `consumedSubnet` and `consumedSubgraph`. Those fields share an object in memory, but JSON writes both copies. When a fold consumes another folded component, serialization repeats the duplication recursively. A graph with only a few visible nodes can therefore produce a very large file. JSON-based cloning expands these aliases before the final download serialization, and indentation further increases the output.

There is also a separate download-lifecycle concern: Save Session revokes its Blob URL 100 ms after initiating the download. Premature cleanup is a plausible contributor to browser failures, but it has not been established as the cause of the reported Safari or Firefox behavior. The exact Chrome prompt has not been confirmed either. Phase 2.9 must address the demonstrated serialization problem and validate download reliability independently.

## Solution

Keep the existing self-contained, offline HTML viewer and its Save Session / Open Session workflow. Save a compact, lossless JSON Fold State Snapshot containing each restoration record once per component, without the redundant legacy alias. Reduce temporary copies during saving and manage download resources so the browser can consume the file before cleanup.

Opening existing snapshots remains supported. Users can reopen, unfold, rename, refold, and save again without reintroducing duplicate restoration records. Preserve the Phase 2.8 session contract, including engine and document context, layout, and viewport.

Deliver three improvements in this phase, in this order: canonical restoration records, compact serialization with fewer allocations, and a verified Save Session download lifecycle. Measure the result before considering workers or compression.

## User Stories

1. As a viewer user, I want to save a large session, so that I can preserve my folding work reliably.
2. As a viewer user, I want deeply nested folds to produce reasonably sized files, so that simplifying the visible graph does not unexpectedly make saving impractical.
3. As a viewer user, I want Save Session to avoid redundant processing, so that saving does not unnecessarily freeze the viewer.
4. As a viewer user, I want a complete JSON download in Safari, Chrome, and Firefox, so that I can use my preferred browser.
5. As a viewer user, I want small sessions to continue saving normally, so that the optimization does not disrupt everyday use.
6. As a viewer user, I want to open snapshots saved before this phase, so that my existing work remains usable.
7. As a viewer user, I want to save an opened legacy session in the compact format, so that subsequent saves benefit from the optimization.
8. As a viewer user, I want to unfold every saved nested component, so that reducing file size does not discard restoration history.
9. As a viewer user, I want Component-Local Unfold to preserve unrelated folds after reopening, so that I can continue exploring one part of the net at a time.
10. As a viewer user, I want Component Node Renaming to survive saving, reopening, unfolding, and refolding, so that my annotations remain useful.
11. As a viewer user, I want Transition Weight, Component Penalty, Fold Config, and Structuredness Metric behavior preserved, so that reopening does not change my analysis.
12. As a viewer user, I want compound structure and Collapsed Compound State preserved, so that folded called functions reopen correctly.
13. As a viewer user, I want node positions, zoom, and pan preserved, so that I resume at the same view.
14. As a viewer user, I want document identity, original-net context, and playback/reset behavior preserved, so that a reopened session remains a complete working session.
15. As a viewer user, I want saving to leave my active graph, selection, and view unchanged, so that I can keep working immediately afterward.
16. As a viewer user, I want repeated saves to produce independent, complete files, so that a later save does not interrupt an earlier download.
17. As a viewer user, I want a detectable save failure to be reported without losing my session, so that I can retry while my work remains available.
18. As a viewer user, I want to keep saving and opening sessions offline from generated HTML, so that I do not need a server, installation, or network connection.
19. As a viewer user, I want the existing recognizable session filename and JSON format retained, so that I can find and reopen my files normally.
20. As a viewer user, I want to continue Live Fold Reduction after reopening, so that new components do not collide with existing or restorable component IDs.

## Implementation Decisions

1. **Preserve the current architecture and format.** The generated HTML remains self-contained and embeds the viewer implementation. Session files contain data, without another copy of the viewer code. Retain `snapshotType: code2petri-fold-state`, schema version 1, the JSON extension, and existing filename rules. The current reader already accepts the canonical restoration field, so removing its redundant alias does not require a new container or schema version.

2. **Use one restoration field on disk.** Write `consumedSubnet` as the canonical field throughout nested component restoration records. Accept legacy records containing only `consumedSubgraph`, canonical records, and records containing both. When both exist, retain the existing reader's canonical-field precedence; when only the legacy field supplies the restoration record, normalize it to the canonical field. Keep current validation behavior for malformed snapshots. Do not merge conflicting histories or use global node-ID deduplication: the same identity may legitimately occur in different saved contexts.

3. **Canonicalize before expansion can occur.** Build the snapshot through a schema-aware capture/copy that omits the redundant restoration branch before any JSON-based clone or recursive traversal could expand it. Applying a filter only to the final serialization is insufficient if an earlier clone has already duplicated the history. Apply this rule to restoration records wherever the existing snapshot contract stores them, including retained document context. Scope alias normalization to restoration data, rather than deleting similarly named user metadata indiscriminately.

4. **Preserve ownership and history.** Capturing a snapshot must not delete aliases or otherwise mutate the live Cytoscape graph, engine, or document context. Preserve the existing detached-snapshot behavior: subsequent live edits must not change a previously captured snapshot. Keep all distinct consumed nodes and edges, nested component records, compound boundaries, names, weights, configuration, counters, original-net data, callee data, playback context, layout, and viewport required by the existing session contract. Size reduction must not come from truncating history or preventing Component-Local Unfold.

5. **Encode the download once, without indentation.** Use compact JSON and remove full-snapshot stringify/parse cloning from the save path. A direct detached capture followed by one final JSON encoding is the intended shape. Avoid retaining unnecessary intermediate strings or parsed copies after download initiation. Preserve existing public capture, parse, and download behavior for their callers; internal factoring may change to achieve this without forcing a broader reduction-engine rewrite.

6. **Keep reopening and resaving canonical.** Both imported legacy records and newly created folds must pass through canonical capture when saved. Save → Open → fold/unfold → Save must not restore the redundant alias on disk. Retain validation before replacing active state, component-counter recovery, and the existing no-relayout restoration behavior. Compatibility normalization must not bypass malformed-input checks.

7. **Give each download a safe, bounded resource lifetime.** Replace the unconditional 100 ms revocation with an explicit lifecycle suitable for the target browsers. Keep the Blob URL available during asynchronous download consumption, then release it and any temporary DOM resources. Repeated saves must not revoke a preceding pending download, and error paths must not leak resources. Choose and document the retention/cleanup policy using browser evidence. An anchor download does not provide an application-level confirmation that the file has finished writing; a timer or click alone must not be reported as proof of completion.

8. **Preserve the save interaction and failure handling.** Continue initiating the download from the user's Save Session action. Surface errors the application can detect without changing the active session. Do not silently report success when download initiation is unavailable or throws. Do not claim to detect browser cancellations or silent browser failures that are outside the application's observable lifecycle.

9. **Measure before adding another mechanism.** Profile the optimized capture, encoding, Blob creation, and download initiation separately enough to distinguish serialization stalls from download failures. Record output bytes and elapsed time for fresh, folded, and deeply nested fixtures. Heap measurements are useful where supported, but are not a prerequisite for the format correction. Workers, compression, and streaming require separate follow-up decisions if representative workloads remain problematic.

## Testing Decisions

- **Primary behavioral seam:** extend the existing Save Session → downloaded JSON → Open Session → continued folding/unfolding flow. Reuse the generated-viewer integration tests and Node/headless Cytoscape snapshot tests. Assert file contents and resumed behavior rather than private helper names, source-text patterns, or an exact cleanup delay. This keeps capture, validation, engine restoration, and UI wiring covered through the existing public workflow.

- **Nested-history size regression:** construct a deterministic sequence net with 14 places and 13 transitions, then perform 12 successive nested sequence contractions through the real reduction engine. Save the resulting three-node graph through the production save path. With a minimal valid document context, require the UTF-8 JSON output to stay below 100 KiB and retain all restoration records. Save smaller nested depths as well to demonstrate that adding levels does not recursively duplicate aliases. The observed compact result is about 24 KB; the bound leaves room for ordinary metadata changes. Do not use machine-dependent duration limits as unit-test assertions.

- **Lossless nested round trip:** open that downloaded file through the actual snapshot parser/restoration flow and unfold all 12 levels. Verify original node and edge identities, endpoints, relevant metadata, and weights. Include a separate folded region to verify Component-Local Unfold leaves unrelated folds intact. A size test without successful restoration is insufficient.

- **Compatibility matrix:** cover canonical-only, legacy-only, both-field, and mixed nested version-1 records, including the existing precedence when both fields are present. Open, continue working, and resave each supported form; verify the resulting restoration records contain the canonical field only. Verify a newly compact snapshot remains accepted by the previous version-1 reader contract. Continue rejecting malformed/unsupported snapshots before active-state replacement.

- **Session fidelity and capture independence:** extend existing round-trip fixtures for custom and remembered names, unfolded/refolded components, compound boundaries, Collapsed Compound State, Transition Weight, Component Penalty, Fold Config, component IDs/counter, document identity, original-net/callee/playback context, node positions, zoom, and pan. Compare pre-save and post-save active state, including selection and metric display. Change the live session after capture and confirm the captured snapshot remains unchanged. Use representative existing fixtures rather than duplicating every reduction-rule test.

- **Actual download-helper coverage:** existing tests that inject a replacement download callback remain useful for snapshot assertions but do not establish the real helper's lifecycle. Exercise the production helper with controlled DOM, Blob, object-URL, and clock boundaries. Verify a usable URL at download initiation, complete intended bytes, independent repeated downloads, eventual resource cleanup, and cleanup/error reporting after detectable failures. Automated lifecycle tests do not substitute for browser download verification.

- **Browser acceptance:** use freshly generated HTML containing the implementation and test small, representative large, and deeply nested sessions in Safari 18.6 (the reported version), Chrome, and Firefox where available. Record actual browser versions. For each, inspect the completed downloaded file, parse it, reopen it, and continue unfolding. Confirm the correct filename, complete bytes, and unchanged active session; repeat saves. Record responsiveness and whether the reported prompts or silent failures recur. Chromium success or headless WebKit success alone does not establish a Safari fix. If a browser cannot be exercised, record that validation gap instead of marking its acceptance check passed.

- **Representative performance evidence:** repeat the Aeroblasters fresh-net and folded-net measurements described below, or use an equivalent documented fixture if the local source is unavailable. Compare the same graph state and context before and after the change. Keep the deterministic regression fixture self-contained in the test suite; automated tests must not depend on a user's Drive path. Timing and memory observations support the recommendation but are not universal performance guarantees.

Phase acceptance requires compact lossless snapshots, legacy compatibility, unchanged active state, and verified download cleanup. Browser-specific reliability claims additionally require completed-file evidence from those browsers. No acceptance criterion permits discarding session capabilities to meet a size target.

## Out of Scope

- A standalone viewer application, shared external viewer bundle, server, or change to the generated offline HTML architecture.
- PNML import, general JSON net import, or changes to PNML export and its download helper.
- Compressed session formats, ZIP/gzip containers, binary formats, reference-table schemas, or a new snapshot version.
- Web Workers, streaming/file-system save APIs, progress/cancellation UI, and asynchronous save orchestration unless separately specified after profiling the initial optimization.
- Removing original-net context, playback data, custom names, or nested unfold history to reduce file size.
- Changes to reduction rules, Structuredness Metric calculations, Batch Place Fold, Fold-Entire-Function, or the inspector layout.
- Automatically rewriting users' previously generated HTML or saved sessions. Existing HTML embeds the old implementation and must be regenerated to receive the fix; opening and resaving a compatible old snapshot is the supported way to produce a compact snapshot with the updated viewer.

## Further Notes

### Profiling evidence supporting the scope

Read-only local profiling compared the production save path with a compact serialization that omitted the redundant restoration alias before encoding. The alternative output was also passed through the existing snapshot parser. Sizes below use decimal MB/KB and are rounded.

| Fixture | Current pretty-printed snapshot | Compact canonical snapshot |
|---|---:|---:|
| Aeroblasters, fresh net: 849 nodes / 904 edges | 1.37 MB | 0.84 MB |
| Same net after 12 eligible sequence folds: 825 nodes / 880 edges | 3.52 MB | 0.86 MB |
| Synthetic sequence after 12 nested folds: 3 visible nodes / 2 edges | 89.40 MB | 24 KB |

For the synthetic fixture, removing indentation alone still produced approximately 11.53 MB. Removing the recursive alias duplication produced the much larger improvement. The compact snapshot reopened and unfolded all 12 components back to the original 27 nodes and 26 edges, with original identities and topology verified.

The synthetic production save took approximately 720 ms in the local Node measurement; compact canonical encoding took less than 1 ms. These measurements compare the existing production path with an exploratory alternative, not two released implementations or complete browser download times. They demonstrate avoidable serialization work; they do not establish browser responsiveness limits or prove the cause of the user's failures. The measured fold sequences are reproducible examples, not a reconstruction of the user's unsaved session.

### Relationship to existing work

- [Phase 2.8](./phase-2.8-viewer-interactive-enhancements.md) delivered the session workflow. Phase 2.9 optimizes and hardens that contract.
- [Ticket 51: Compact, lossless Fold State Snapshot saves](../issues/51-safari-large-session-download.md) is resolved and delivers canonical, compact, lossless session data. [Ticket 52: Reliable large Save Session downloads across browsers](../issues/52-reliable-save-session-downloads.md) implements independent download lifetimes and remains `ready-for-human` for browser acceptance. Ticket 51's prerequisite is satisfied.
- Reuse the snapshot and generated-viewer testing prior art in [the viewer tests](../../../tests/test_html_viewer.py). The current capture/download implementation is in [the session snapshot module](../../../code2petri/viewer/engine/session_snapshot.js), with restoration records created by [the reduction engine](../../../code2petri/viewer/engine/reduction_engine.js).
- Preserve [the domain glossary](../../../GLOSSARY.md), [boundary place unification](../../../docs/adr/0002-boundary-place-unification.md), and [the adopted reduction algorithm](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md). This phase changes persistence representation and resource handling, not the Petri net semantics.

## Delivery Record

- Canonical detached capture writes each nested restoration record once, accepts legacy aliases, and produces compact version-1 snapshots without discarding unfold history.
- The download helper keeps each Blob URL independently for a bounded 30-second grace period, removes temporary anchors, and cleans up detectable initiation failures. This timer does not prove file completion. Ticket 52 records 11 focused tests and 134 viewer tests passing at implementation time; those historical results were not rerun here.
- 2026-10-16: The user confirmed implementation completion. Completed-file checks in Safari 18.6, Chrome, and Firefox, including browser versions and small/large/deep sessions, remain unperformed in the recorded evidence. The original Safari/Firefox failure cause remains provisional. No browser-specific reliability claim is added by this documentation update.
