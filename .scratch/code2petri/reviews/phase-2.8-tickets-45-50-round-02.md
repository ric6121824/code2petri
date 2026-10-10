# Code Review — Phase 2.8 (Tickets 45–50), Round 02

**Commits:**
- `f128678` (`fix(viewer): address phase 2.8 review findings`)
- `429d3c0` (`docs: resolve phase 2.8 viewer tickets`)
- `e73dd36` (`feat(viewer): fold functions and reopen sessions`)
- `9581548` (`feat(viewer): fold selected places in one pass`)
- `48bd5a6` (`Merge branch 'phase-2.8-tickets-45-50' into phase-2.8-ticket-50`)
- `e4a6992` (`feat(viewer): show root function identity`)
- `8c45e17` (`merge integration branch into ticket 48`)
- `7427acd` (`feat(viewer): save fold state snapshots`)
- `dd82ba7` (`feat(viewer): dock node inspector sidebar`)

**Diff:** `git diff a7f0d7b...HEAD` (13 files changed, 1,942 insertions, 145 deletions). Uncommitted worktree changes were excluded.

**Master Spec:** [Phase 2.8: Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md)  
**Ticket 45 context:** [Docked Sidebar Inspector](../issues/45-viewer-docked-sidebar.md)  
**Previous Review:** [Phase 2.8, Round 01](./phase-2.8-tickets-45-50-round-01.md)  
**Standards:** [issue tracker conventions](../../../docs/agents/issue-tracker.md), [triage labels](../../../docs/agents/triage-labels.md), [domain documentation guidance](../../../docs/agents/domain.md), [GLOSSARY.md](../../../GLOSSARY.md), [ADR 0004](../../../docs/adr/0004-docked-sidebar-instead-of-floating-popover.md), and Fowler's 12-smell baseline.
**Tests:** Not run during this review.

---

## Standards

### (a) Documented Standards

**S1 — Status values don't match the documented triage roles (hard documented mismatch)**

The [issue tracker convention](../../../docs/agents/issue-tracker.md#L10) defines the `Status:` line as the issue's triage state and directs readers to the [five-role mapping](../../../docs/agents/triage-labels.md#L5). None of those roles is `resolved`. All six implementation tickets—[45](../issues/45-viewer-docked-sidebar.md#L7), [46](../issues/46-batch-place-fold-selection.md#L7), [47](../issues/47-fold-entire-function-compound.md#L7), [48](../issues/48-save-session.md#L7), [49](../issues/49-smart-open-session-pnml.md#L7), and [50](../issues/50-info-panel-function-name.md#L7)—use `Status: resolved`. The tracker separately permits `claimed`/`resolved` for Wayfinding child tickets; these implementation issues do not use that ticket format.

> **Suggestion:** Separate triage from completion (for example, keep `Status:` for a canonical triage role and add a `Resolution:` field), or update the tracker convention to explicitly allow a terminal `resolved` value for implementation issues.

The docked sidebar continues to follow ADR 0004. No other documented-standard breach was found.

### (b) Baseline Code Smells (Judgement Calls)

**S2 — Carry-forward possible Duplicated Code: Fold action post-processing**

[`handleFoldEntireFunction`](../../../code2petri/viewer/template.html#L1655) and [`handleBatchPlaceFold`](../../../code2petri/viewer/template.html#L2051) still repeat the layout, viewport restoration, and fold-highlight refresh sequence:

```javascript
if (cy.elements().length > 0 && typeof cy.layout === 'function') {
  cy.layout(Object.assign({}, DAGRE_LAYOUT_OPTIONS, { fit: false, animate: false })).run();
}
restoreViewport(cy, viewportBefore.zoom, viewportBefore.pan);
updateFoldableHighlights();
```

They also duplicate skipped-result formatting. The round 1 fix commit did not change these handlers. **Suggestion:** Extract shared post-fold refresh and result-summary helpers if the paths should remain aligned. This is a judgement-call smell, not a hard violation.

---

## Spec

### (a) Reassessment of Round 01 Findings

**P1 — Batch and full-function folding: RESOLVED**

The spec requires folding places “contractible at the moment of evaluation” ([line 27](../specs/phase-2.8-viewer-interactive-enhancements.md#L27)) and repeating full-function folding until “a fixed point is reached” ([line 28](../specs/phase-2.8-viewer-interactive-enhancements.md#L28)). `executeBatchFold` now dispatches registered place-targeted fold types, and full-function folding repeats batch passes ([`reduction_engine.js:1241`](../../../code2petri/viewer/engine/reduction_engine.js#L1241), [`reduction_engine.js:1306`](../../../code2petri/viewer/engine/reduction_engine.js#L1306)).

**P2 — Rejected snapshots can still partially replace the active session: PARTIALLY RESOLVED**

The spec requires validation before replacing the active session and says a rejected snapshot must leave it intact ([line 36](../specs/phase-2.8-viewer-interactive-enhancements.md#L36)). The prior `[null]` `foldSteps` case is now rejected. However, `validateNet` checks only that `places`, `transitions`, and `arcs` are arrays ([`session_snapshot.js:165`](../../../code2petri/viewer/engine/session_snapshot.js#L165)); it does not validate their entries. For example, `document.originalNet.transitions: [null]` passes validation, then restore replaces the graph before `transition.metadata` throws ([`template.html:2166`](../../../code2petri/viewer/template.html#L2166)).

> **Suggestion:** Validate each place, transition, and arc record, plus nested fields used by restore, before replacing the active graph. Add a regression case confirming that an invalid net entry is rejected without changing the current session.

**P3 — Saved root function identity: RESOLVED**

The spec requires the snapshot to retain “source/function identity” ([line 34](../specs/phase-2.8-viewer-interactive-enhancements.md#L34)). Snapshot context now reads the active document identity ([`template.html:2097`](../../../code2petri/viewer/template.html#L2097)).

### (b) Scope Creep

None found.

---

**Summary:** Standards: 2 findings (1 hard status mismatch; 1 carry-forward judgement-call smell), with the status mismatch the most significant. Spec: 1 remaining partial finding; the batch-fold and function-identity findings from Round 01 are resolved.
