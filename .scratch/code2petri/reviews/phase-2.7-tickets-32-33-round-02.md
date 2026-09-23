# Code Review: Tickets 32 & 33 (JS Fold Engine: Sequence & Choice) — Round 02

**Scope:** Ticket 32 (Live Sequence Reduction) & Ticket 33 (Live Choice Reduction)  
**Commits:** `6e7f845` (`refactor(viewer): resolve round 1 review findings for tickets 32 and 33`) on top of `f05fee2` and `2606ff1`  
**Diff:** `git diff 8f08db6...HEAD` (focus on `2606ff1...HEAD`)  
**Specs:**
- [`.scratch/code2petri/issues/32-js-fold-engine-sequence.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/32-js-fold-engine-sequence.md)
- [`.scratch/code2petri/issues/33-js-fold-engine-choice.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/33-js-fold-engine-choice.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 399 unit and integration tests pass.

---

## Standards

### (a) Round 1 Verification & Documented Standards
**Status: PASS (0 Hard Violations).**
All documented standard violations flagged in Round 1 were addressed:
1. **`CONTEXT.md` Vocabulary in `tests/test_html_viewer.py` → ✅ RESOLVED**
   All occurrences of `"JS sequence fold"`, `"JS contraction"`, etc., were replaced with `"Live Fold Reduction (Single-Place Contraction)"` and `"Live Fold Reduction (Choice)"`.
2. **`Single-Place Contraction` Method Name → ✅ RESOLVED**
   Renamed to `canSinglePlaceContract(placeNode)` with a backward-compatibility shim `canContractPlace`.
3. **`Consumed Subnet` Vocabulary → ✅ RESOLVED**
   Renamed `consumedSubgraph` to `consumedSubnet` across properties and comments.

### (b) Baseline Code Smells Verification
1. **Duplicated Test Harness in `tests/test_html_viewer.py` → ✅ RESOLVED**
   Extracted `_setup_live_fold_test_harness(net_json_literal, test_logic_js)`, eliminating ~500 lines of duplicated regex scraping.
2. **Duplicated Opaque Node Construction → ✅ RESOLVED**
   Extracted `_createOpaqueComponentNode(...)` in `LiveFoldReductionEngine`, unifying node schema, SVG badge generation, and Cytoscape insertion.
3. **Repeated Type Cascades → ✅ RESOLVED**
   Added `getFoldType(placeNode)` helper; both highlights and click handlers delegate to it.
4. **Speculative Generality → ⚠️ PARTIAL**
   `this.history` and `onStateChange` were removed. However, `loop: 3.0` in `this.cfg` and `bundleIndex = 0` in `executeChoiceContraction` remain ahead of Ticket 34.

### (c) Newly Introduced Smells (Judgement Calls)
1. **Middle Man (Shim):** `canContractPlace` is a 1-line pass-through forwarding to `canSinglePlaceContract`. (Acceptable backward-compatibility shim).
2. **Data Clumps:** `_createOpaqueComponentNode` takes 8 positional arguments; could be bundled into a typed parameters object in a future cleanup.

---

## Spec

### (a) Round 1 Verification
1. **Sequence Contraction Default Penalty Mismatch (Ticket 32) → ✅ RESOLVED**
   `LiveFoldReductionEngine` changed default `this.cfg.sequence` to `0.0`, computing $\omega = 0.0$ and $\tau = \tau_1 + \tau_2$ to match Lassen (2008) Def. 21 and Python's default `FoldConfig()`. Tests now assert against default `FoldConfig()`.
2. **Multi-Bundle Choice Determinism (Ticket 33) → ✅ RESOLVED**
   `detectChoiceCandidates` now sorts bundles deterministically by `targetPlaceId`. Sequential clicks reduce parallel bundles in stable order.
3. **Acceptance Criteria Coverage → ✅ ALL SATISFIED (11/11)**
   - **Ticket 32 (5/5 satisfied):** Green highlight on eligible places; single-place contraction on tap; updated $\tau$ badge; `consumedSubnet` stores restorable data; matches Python default fold engine.
   - **Ticket 33 (6/6 satisfied):** Amber highlight on choice places; parallel transitions fused into opaque component; split/join places preserved; $1.5\times$ choice multiplier applied; matches Python `fold_choice`; restorable data saved.

### (b) New Scope Creep or Defects
**None detected.** All 399 unit and integration tests pass cleanly.

---

## Summary

- **Standards:** 0 hard violations, 6 smells resolved, 1 partial smell (unused `cfg.loop` ahead of Ticket 34).
- **Spec:** All 11 acceptance criteria across Tickets 32 & 33 verified and satisfied; default $\omega=0.0$ semantic alignment resolved.
