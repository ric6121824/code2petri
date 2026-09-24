# Code Review: Ticket 36 (JS Fold Engine: Marked Graph + State Machine) — Round 02

**Commit:** `b7a32d6` (`refactor(viewer): resolve round 1 review findings for ticket 36`)  
**Diff:** `git diff fbcf3e7...HEAD` (4 files changed, 466 insertions(+), 465 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/36-js-fold-engine-marked-graph-state-machine.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/36-js-fold-engine-marked-graph-state-machine.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 55 tests in `test_html_viewer.py` and 413 repository tests pass.

---

## Standards

### (a) Round 1 Verification & Documented Standards
**Status: PASS (0 Hard Violations).**
All documented standard violations and smells flagged in Round 1 were addressed:
1. **Domain Vocabulary ([`CONTEXT.md:38-40`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L38-L40)) → ✅ RESOLVED**
   Method renamed from `_detectMacroCandidates` to `_detectSESESubnetCandidates(isMarkedGraph)`, removing avoided "macro" terminology from the engine API.
2. **Duplicated Code (Reduction Routine) → ✅ RESOLVED**
   Common reduction mechanics (~110 lines) across marked graphs and state machines extracted into a clean `_executeSESEReduction(candidate, boundaryConfigFn)` helper.
3. **Duplicated Code (Test Fixtures) → ✅ RESOLVED**
   Extracted shared class-level constants `MARKED_GRAPH_NET_JSON` and `STATE_MACHINE_NET_JSON` in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py), eliminating 6 duplicate inline JSON literals.
4. **Repeated Switches / Cascades → ✅ RESOLVED**
   Unified all fold types into a declarative registry `LiveFoldReductionEngine.FOLD_TYPE_REGISTRY`. `updateFoldableHighlights` and tap handlers now dispatch uniformly without nested `if/else if` cascades.
5. **Data Clump / Parameter Bloat → ✅ RESOLVED**
   `_createOpaqueComponentNode` now accepts an options object (`{ opaqueId, label, rawLabel, tau, omega, componentType, parentId, consumedSubnet, position }`) while retaining backwards compatibility for older call sites.

### (b) Newly Introduced Smells (Judgement Calls)
- **None blocking.** `_createOpaqueComponentNode` retains a dual-mode argument parsing wrapper to preserve compatibility with existing elementary fold call sites.

---

## Spec

### (a) Round 1 Verification
1. **Prioritization Gating Behind Elementary Reductions → ✅ RESOLVED**
   Documented in both spec ([`36-js-fold-engine-marked-graph-state-machine.md:17`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/36-js-fold-engine-marked-graph-state-machine.md#L17)) and code comments ([`code2petri/viewer/template.html:1850-1854`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1850-L1854)), citing Lassen & van der Aalst (2008) Definition 21 (Order of Reductions). Elementary reductions (Sequence $\to$ Choice $\to$ Loop) must be exhausted before structural SESE folds to prevent premature structural folding.
2. **Marking Discrepancy on Subnet Detection → ✅ RESOLVED**
   Documented in spec ([`36-js-fold-engine-marked-graph-state-machine.md:18`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/36-js-fold-engine-marked-graph-state-machine.md#L18)) and code comments as an intentional token conservation invariant: in workflow nets, marked internal places represent active concurrent state, so live folding over them is safely prohibited.
3. **Acceptance Criteria Coverage → ✅ ALL SATISFIED (6/6)**
   - **AC1 & AC3 (Detection & Highlighting):** Boundary nodes correctly highlighted via registry classes (`contractible-marked-graph`, `contractible-state-machine`).
   - **AC2 & AC4 (Reduction):** Subnets collapse into opaque components with correct $\tau$ and $\omega$ values.
   - **AC5 (Parity with Python):** Verified matching Python engine outputs and symmetry multipliers.
   - **AC6 (Reconstitution Data):** `consumedSubnet` retains full node, edge, and boundary mappings.

### (b) New Scope Creep or Defects
**None detected.** All 55 tests in `test_html_viewer.py` pass cleanly.

---

## Summary

- **Standards:** 0 hard violations, all 5 Round 1 findings resolved (method renaming, helper extraction, test fixture deduplication, `FOLD_TYPE_REGISTRY` dispatch table, options object).
- **Spec:** All 6 acceptance criteria verified and satisfied; prioritization gating and token conservation invariants formally documented.
