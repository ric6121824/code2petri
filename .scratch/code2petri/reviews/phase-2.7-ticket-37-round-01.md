# Code Review: Ticket 37 (JS Fold Engine: Well-Structured SESE Reduction) — Round 01

**Commit:** [`4ffb8e9`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/37-js-fold-engine-well-structured-sese.md) (`feat(viewer): implement live well-structured sese reduction engine (ticket 37)`)  
**Diff:** `git diff b7a32d6...HEAD` (4 files changed, 554 insertions(+), 28 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/37-js-fold-engine-well-structured-sese.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/37-js-fold-engine-well-structured-sese.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 60 tests in `test_html_viewer.py` pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

1. **Domain Vocabulary Drift ([`CONTEXT.md:47-50`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L47-L50))**:
   - **Rule:** `Structural Fold` (*Avoid: Graph compression, subnet deletion, macro collapsing*).
   - **Violation:** In [`.scratch/code2petri/reviews/phase-2.7-ticket-36-round-02.md:36`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.7-ticket-36-round-02.md#L36):
     `...exhausted before structural SESE folds to prevent premature macro collapsing.`
     Uses the explicitly prohibited domain term "macro collapsing".
   - **Actionable Fix:** Replace with "premature structural folding" or "premature SESE reduction".

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Candidate Discovery Pipeline ([`code2petri/viewer/template.html:2509-2622`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2509-L2622))**:
   - `detectWellStructured()` re-implements boundary place querying, candidate traversal, token validation, function boundary checking, transition $\tau$ aggregation, symmetry calculation, sorting, and maximal candidate filtering almost identically to `_detectSESESubnetCandidates()` ([`code2petri/viewer/template.html:2398-2499`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2398-L2499)).
   - **Actionable Fix:** Extract the common candidate discovery and validation pipeline into a shared helper parameterized by candidate acceptance predicate and multiplier type.

2. **Repeated Switches — Fallback and Class Cascades ([`code2petri/viewer/template.html:3142-3147`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L3142-L3147) & [`lines 3061-3067`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L3061-L3067))**:
   - The place tap handler and `updateFoldableHighlights` add new `if/else if` cascades branching directly on specific CSS classes (`contractible-state-machine`, `contractible-well-structured`).
   - **Actionable Fix:** Query `LiveFoldReductionEngine.FOLD_TYPE_REGISTRY` entries polymorphically by matching the node's classes against registered `className` values.

3. **Primitive Obsession — Prefix Formatting ([`code2petri/viewer/template.html:2874`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2874))**:
   - `_executePlaceSESEReduction(candidate, prefix)` passes raw strings (`'sm'`, `'ws'`) solely to format boundary edge IDs (`arc_${prefix}_in_${newId}`).
   - **Actionable Fix:** Derive the edge prefix or ID format from `candidate.componentType` or `FOLD_TYPE_REGISTRY` rather than passing a separate string parameter.

4. **Duplicated Code — Test Assertions ([`tests/test_html_viewer.py:2845-2880`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L2845-L2880))**:
   - Identical JS test script logic and Node harness assertions are duplicated sequentially within `test_well_structured_rejects_pt_handle_and_internal_cycle_headless`.
   - **Actionable Fix:** Parameterize the negative topology test cases over `(net_json, description)`.

---

## Spec

### (a) Missing or Partial Requirements

1. **Configurable `well_structured` Penalty Option Missing in Constructor**:
   - *Spec Line 11:* `"- [x] JS tau and omega values match the Python fold engine for the same topology"`
   - *Finding:* In [`code2petri/viewer/template.html:1449-1455`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1449-L1455), `LiveFoldReductionEngine.constructor` initializes `this.cfg` with defaults for `sequence`, `choice`, `loop`, `marked_graph`, and `state_machine`, but omits `well_structured`. Passing custom `{ well_structured: X }` options (matching Python's `FoldConfig(well_structured=X)`) is ignored, defaulting to 2.0.
   - **Actionable Fix:** Add `well_structured: (options && options.well_structured !== undefined) ? options.well_structured : 2.0` to `this.cfg` in the engine constructor.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Altered Marked Graph / State Machine Candidate Filtering**:
   - *Spec Header:* `"What to build: The user can trigger a Well-Structured reduction that collapses a SESE subnet which is free from PT/TP handles and internal cycles..."`
   - *Finding:* In [`code2petri/viewer/template.html:2498`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2498), `_detectSESESubnetCandidates(isMarkedGraph)` was updated to return `this._filterMaximalCandidates(candidates)` instead of `candidates`. While maximal candidate filtering aligns with Lassen Def. 18, altering Ticket 36's detection return behavior was not requested in Ticket 37.
   - **Actionable Fix:** Confirm intentional retrofitting or keep ticket changes scoped to Well-Structured components.

2. **Commit Scope Leak**:
   - Commit `4ffb8e9` tracks [`.scratch/code2petri/reviews/phase-2.7-ticket-36-round-02.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.7-ticket-36-round-02.md), an unrelated review artifact from Ticket 36.
   - **Actionable Fix:** Exclude prior review markdown files from feature commits.

### (c) Requirements Implemented but Look Wrong

1. **Inoperative Multiplier Fallback in `detectWellStructured`**:
   - *Spec Line 11:* `"- [x] JS tau and omega values match the Python fold engine for the same topology"`
   - *Finding:* In [`code2petri/viewer/template.html:2588`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2588), `const multiplier = (self.cfg.well_structured !== undefined ? self.cfg.well_structured : 2.0);` attempts to read `self.cfg.well_structured`. Because the constructor never assigned `well_structured` onto `this.cfg`, `self.cfg.well_structured` is always undefined and unconditionally falls back to 2.0. Parity tests passed only because `FoldConfig(well_structured=2.0)` matched this fallback.
   - **Actionable Fix:** Wire `well_structured` properly into `this.cfg` in the constructor so custom configs are obeyed.

---

## Summary

- **Standards (5 findings):** 1 domain vocabulary drift ("macro collapsing"), 1 commit hygiene issue (bundled prior review), 3 baseline smells (duplicated candidate pipeline across `detectWellStructured` and `_detectSESESubnetCandidates`, repeated `if/else if` fallback cascades, primitive prefix string). Worst issue: Duplicated SESE discovery and validation pipeline.
- **Spec (3 findings):** 1 partial requirement (`well_structured` omitted in engine constructor options), 1 scope alteration (retrofitting maximal candidate filtering onto Ticket 36 marked graph / state machine detection), 1 inoperative multiplier read (`self.cfg.well_structured` always undefined). Worst issue: Inoperative `self.cfg.well_structured` in constructor breaking custom configuration parity.
