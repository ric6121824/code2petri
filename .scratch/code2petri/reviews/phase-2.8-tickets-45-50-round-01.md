# Code Review — Phase 2.8 (Tickets 45–50), Round 01

**Commits:**
- `429d3c0` (`docs: resolve phase 2.8 viewer tickets`)
- `e73dd36` (`feat(viewer): fold functions and reopen sessions`)
- `9581548` (`feat(viewer): fold selected places in one pass`)
- `48bd5a6` (`Merge branch 'phase-2.8-tickets-45-50' into phase-2.8-ticket-50`)
- `e4a6992` (`feat(viewer): show root function identity`)
- `8c45e17` (`merge integration branch into ticket 48`)
- `7427acd` (`feat(viewer): save fold state snapshots`)
- `dd82ba7` (`feat(viewer): dock node inspector sidebar`)

**Diff:** `git diff a7f0d7b...HEAD` (13 files changed, 1,805 insertions, 145 deletions). Uncommitted worktree changes were excluded.

**Master Spec:** [Phase 2.8: Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md)  
**Ticket 45 context:** [Docked Sidebar Inspector](../issues/45-viewer-docked-sidebar.md)  
**Standards:** [AGENTS.md](../../../AGENTS.md), [domain documentation guidance](../../../docs/agents/domain.md), [GLOSSARY.md](../../../GLOSSARY.md), [ADR 0004](../../../docs/adr/0004-docked-sidebar-instead-of-floating-popover.md), and Fowler's 12-smell baseline. No dedicated coding-standards or contributing guide was found.
**Tests:** Not run during this review.

---

## Standards

### (a) Documented Standards

**Status: PASS — 0 hard violations.** The docked sidebar in [template.html](../../../code2petri/viewer/template.html) follows ADR 0004 by using a fixed right sidebar that pushes the canvas. The implementation uses glossary terms including *Batch Place Fold*, *Fold State Snapshot*, *Component-Local Unfold*, and *Live Fold Reduction*.

### (b) Baseline Code Smells (Judgement Calls)

**S1 — Possible Duplicated Code: Fold action post-processing**

[`handleFoldEntireFunction`](../../../code2petri/viewer/template.html#L1655) and [`handleBatchPlaceFold`](../../../code2petri/viewer/template.html#L2051) repeat the layout, viewport restoration, and fold-highlight refresh sequence:

```javascript
if (cy.elements().length > 0 && typeof cy.layout === 'function') {
  cy.layout(Object.assign({}, DAGRE_LAYOUT_OPTIONS, { fit: false, animate: false })).run();
}
restoreViewport(cy, viewportBefore.zoom, viewportBefore.pan);
updateFoldableHighlights();
```

Both handlers also format the skipped-result summary. **Suggestion:** Extract shared post-fold refresh and result-summary helpers if the two paths are expected to remain aligned. This is a heuristic, not a hard violation.

---

## Spec

### (a) Missing or Partial Requirements / Incorrect Behavior

**P1 — Batch and full-function folding skip eligible structural reductions**

The spec says batch folding should execute “the appropriate fold on any place that is contractible at the moment of evaluation” ([line 27](../specs/phase-2.8-viewer-interactive-enhancements.md#L27)); full-function folding should repeat until “a fixed point is reached” ([line 28](../specs/phase-2.8-viewer-interactive-enhancements.md#L28)). [`getFoldType`](../../../code2petri/viewer/engine/reduction_engine.js#L1190) can return structural reductions for place nodes, but [`executeBatchFold`](../../../code2petri/viewer/engine/reduction_engine.js#L1241) only executes `sequence`, `choice`, and `while`. It skips eligible `state_machine`, `well_structured`, and `unstructured` place candidates. Since full-function folding delegates to batch folding, it can stop before reaching the requested state.

> **Suggestion:** Execute every registered place-targeted fold type returned by `getFoldType`, and add coverage for structural reductions in both batch and full-function folding.

**P2 — Rejected snapshots can partially replace the active session before failing**

The spec requires validating the snapshot before replacing the active session and says a rejected snapshot must leave that session intact ([line 36](../specs/phase-2.8-viewer-interactive-enhancements.md#L36)). [`_validateDocumentContext`](../../../code2petri/viewer/engine/session_snapshot.js#L173) only checks that `foldSteps` is an array, so an entry such as `[null]` passes validation. [`restoreFoldStateSnapshot`](../../../code2petri/viewer/template.html#L2135) replaces the graph and document state before dereferencing `step.net`, which then throws ([line 2163](../../../code2petri/viewer/template.html#L2163)); the previous session is no longer intact.

> **Suggestion:** Validate each fold-step record and all nested document fields used during restore before mutating the graph. Add a regression case that opens a snapshot with an invalid fold step and confirms the current session remains unchanged.

**P3 — Saving can lose the explicit root function name**

The spec requires the saved document to retain “source/function identity” ([line 34](../specs/phase-2.8-viewer-interactive-enhancements.md#L34)). The viewer generator stores the root name in `payload.document.function_name` ([`viewer/__init__.py`](../../../code2petri/viewer/__init__.py#L148)), but [`getFoldStateDocumentContext`](../../../code2petri/viewer/template.html#L2088) checks `payload.function_name`, net/compound fields, and not `payload.document.function_name`. For a net without a root compound, the snapshot can store an empty function name and reopening shows “Unavailable.”

> **Suggestion:** Read the explicit function name from `payload.document.function_name` (or the canonical active document metadata), then test save/open for a net without a root compound.

### (b) Scope Creep

None found.

---

**Summary:** Standards: 1 judgement-call finding and 0 hard violations; worst is duplicated fold post-processing. Spec: 3 findings; worst is a rejected snapshot partially replacing the active session.
