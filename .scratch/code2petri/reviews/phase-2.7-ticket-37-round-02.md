# Code Review: Ticket 37 (JS Fold Engine: Well-Structured SESE Reduction) — Round 02

**Commit:** [`fc2112b`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/37-js-fold-engine-well-structured-sese.md) (`refactor(viewer): resolve round 1 review findings for ticket 37`)  
**Diff:** `git diff 4ffb8e9...HEAD` (4 files changed, 299 insertions(+), 191 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/37-js-fold-engine-well-structured-sese.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/37-js-fold-engine-well-structured-sese.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 61 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Round 1 Verification & Documented Standards
**Status: PASS (0 Hard Violations).**
All documented standard violations and smells flagged in Round 1 were addressed:

1. **Domain Vocabulary ([`CONTEXT.md:47-50`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L47-L50)) → ✅ RESOLVED**
   - Prohibited phrase "macro collapsing" in [`.scratch/code2petri/reviews/phase-2.7-ticket-36-round-02.md:36`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/reviews/phase-2.7-ticket-36-round-02.md#L36) was replaced with "premature structural folding".
   - Comments referencing "macro/SESE" and "macro folding" in [`code2petri/viewer/template.html:1874, 1898`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1874) were sanitized to "structural folding".

2. **Duplicated Code (Candidate Discovery Pipeline) → ✅ RESOLVED**
   - Extracted shared helper `_discoverSESESubnets(options)` ([`code2petri/viewer/template.html:2396-2474`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2396-L2474)) parameterizing boundary selectors, node/subnet validation predicates, symmetry multipliers, and maximal candidate filtering. Shared uniformly across Marked Graph, State Machine, and Well-Structured detection.

3. **Repeated Switches (Fallback Cascades) → ✅ RESOLVED**
   - Added static `LiveFoldReductionEngine.getMatchingFoldType(node)` ([`code2petri/viewer/template.html:3000-3009`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L3000-L3009)) to polymorphically query `FOLD_TYPE_REGISTRY.className`, eliminating `if/else if` class-matching cascades across click handlers.

4. **Primitive Obsession (Prefix Formatting) → ✅ RESOLVED**
   - Removed raw string parameter from `_executePlaceSESEReduction(candidate)` ([`code2petri/viewer/template.html:2842-2852`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2842-L2852)), deriving edge prefixes directly from `candidate.componentType`.

5. **Duplicated Code (Test Assertions) → ✅ RESOLVED**
   - Parameterized negative SESE topology test assertions in [`tests/test_html_viewer.py:2822-2882`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L2822-L2882) using `self.subTest(topology=desc)`.

### (b) Baseline Code Smells in New Diff (Judgement Calls)

1. **Divergent Change — Metadata Encapsulation ([`code2petri/viewer/template.html:2848-2852`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2848-L2852))**:
   - `prefixMap` inside `_executePlaceSESEReduction` hardcodes prefix mapping (`StateMachine -> 'sm'`, `WellStructured -> 'ws'`).
   - **Recommendation (Non-blocking):** Move `edgePrefix` into `FOLD_TYPE_REGISTRY` entries to achieve complete metadata encapsulation.

---

## Spec

### (a) Round 1 Verification & Acceptance Criteria
**Status: PASS (All Requirements Satisfied).**

1. **Configurable `well_structured` Penalty Option in Constructor → ✅ RESOLVED**
   - [`code2petri/viewer/template.html:1455`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1455) initializes `well_structured: options.well_structured !== undefined ? options.well_structured : 2.0`.
   - Verified by new headless parity test [`test_well_structured_custom_config_respected_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L2893) against Python [`FoldConfig(well_structured=5.0)`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L51).

2. **Inoperative Multiplier Fallback in `detectWellStructured` → ✅ RESOLVED**
   - [`code2petri/viewer/template.html:2576`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2576) reads `self.cfg.well_structured` directly, which evaluates properly from configured engine options.

3. **Restored Ticket 36 Candidate Filtering → ✅ RESOLVED**
   - `_detectSESESubnetCandidates` sets `filterMaximal: false`, restoring Ticket 36 marked graph and state machine detection behavior. Maximal filtering (`filterMaximal: true`) is properly scoped to `detectWellStructured()` per Lassen Def. 18.

4. **Acceptance Criteria Coverage (4/4 Satisfied)**:
   - **AC1 (Detection & Highlighting):** Subnets free of PT/TP handles and cycles detected and highlighted via `contractible-well-structured`.
   - **AC2 (Reduction):** Collapses into a single opaque component with boundary arcs preserved.
   - **AC3 (Math Parity):** JS $\tau$ and $\omega$ match Python engine across default and custom penalty weights.
   - **AC4 (Reconstitution Data):** Complete subnet details and internal edges preserved in `consumedSubnet`.

### (b) New Scope Creep or Defects
- **None**. Functional changes strictly address Round 1 feedback. All 61 tests in `test_html_viewer.py` pass.

---

## Summary

- **Standards:** 0 hard violations, all 5 Round 1 findings resolved (`_discoverSESESubnets` pipeline extraction, `getMatchingFoldType` registry lookup, options object, test parameterization, domain vocabulary sanitization).
- **Spec:** All 4 acceptance criteria satisfied, constructor penalty configuration wired and tested, Ticket 36 detection behavior preserved.
