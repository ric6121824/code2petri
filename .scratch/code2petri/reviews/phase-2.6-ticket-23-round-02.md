# Ticket 23: Code Review (Round 2 — Current State)

**Diff:** `9d46ae6...HEAD` (including commit `b4d919f` and uncommitted working tree changes)  
**Commits:** `8d2772b`, `b4d919f`, plus uncommitted changes in `code2petri/fold.py` and `code2petri/__init__.py`  
**Spec:** `.scratch/code2petri/issues/23-prom-port-sequence-choice.md`  

## Standards
**STATUS: PASS (0 Hard Violations, 2 Baseline Smells)**

### (a) Verification of Round 1 Standards Findings
1. **Prohibited Aliases for Single-Place Contraction:** **RESOLVED.**
   - Docstrings and comments in [`code2petri/fold.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L284) strictly use **Single-Place Contraction** (and expose `fold_single_place_contraction`). Prohibited terms (*"sequence collapsing"*, *"chain reduction"*) have been eliminated.
2. **Prohibited Terms in ADR 0003:** **RESOLVED.**
   - [`docs/adr/0003-adopt-prom-local-reduction-algorithm.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0003-adopt-prom-local-reduction-algorithm.md#L13-L29) replaced *"bounds for macro-components"* $\to$ *"bounds for compound SESE subnets"*, *"parallel branch collapse"* $\to$ *"atomic parallel transition fold"*, and *"pre-normalization"* $\to$ *"pre-processing AST routing places"*.
3. **Speculative Generality (CamelCase API Aliases):** **RESOLVED.**
   - `foldSequence` and `foldChoice` were removed from [`code2petri/__init__.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/__init__.py) and [`code2petri/fold.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py).
4. **Duplicated Code (Wrapper Boilerplate):** **RESOLVED.**
   - Extracted shared helper `_fold_first_candidate` in [`code2petri/fold.py:327-335`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L327-L335) and reused across reduction functions.
5. **Middle Man (Loop Reduction Bypass):** **RESOLVED.**
   - Added `fold_loop` in [`code2petri/fold.py:585-595`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L585-L595); `fold_net` now dispatches uniformly across the reduction cascade.

### (b) Documented Standards Violations
* **None (0 hard violations).** Production code and ADR 0003 strictly comply with [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md).

### (c) Baseline Code Smells (Judgement Calls)
1. **Duplicated Code** ([`code2petri/fold.py:681-683, 752-754, 832-838`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L681-L683)):
   - **Hunk:**
     ```python
     splits = sum(1 for nid in best_nodes if topo.out_degree(nid) > 1)
     joins = sum(1 for nid in best_nodes if topo.in_degree(nid) > 1)
     diff = abs(joins - splits) + 1
     ```
   - **Analysis:** Symmetry difference calculation (`abs(joins - splits) + 1`) is duplicated inline across `detect_marked_graphs`, `detect_state_machines`, and `detect_well_structured`.
   - **Suggestion:** Parameterize and reuse the existing [`calculate_symmetry_multiplier`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L260-L277) helper.
2. **Redundant Delegation / Dead Execution** ([`code2petri/fold.py:585-595, 1165-1170`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L585-L595)):
   - **Hunk:**
     ```python
     res = fold_while(net, step_number, cfg)
     if res is not None:
         return res
     return _fold_first_candidate(net, detect_loops(net, cfg), step_number)
     ```
   - **Analysis:** `fold_net` cascades `fold_while` then `fold_loop`. However, `fold_loop` internally delegates to `fold_while` first. When reached in `fold_net`, `fold_while` has already evaluated to `None`, making the nested call redundant.
   - **Suggestion:** Restrict `fold_loop` to elementary cycle reduction (`detect_loops`) and allow `fold_net` to govern priority ordering.

---

## Spec
**STATUS: FAIL (0 Missing Requirements, 1 Scope Creep, 2 Critical Implementation Flaws)**

### (a) Status of Round 1 Spec Findings
- **Choice Formula Change:** **RESOLVED.** Documented in Ticket 23 answer referencing Phase 2.6 User Story 1 (ProM 1.5x linear markup).
- **Generalized Murata Parallel Reduction:** **RESOLVED.** Architectural rationale documented in [ADR 0003](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0003-adopt-prom-local-reduction-algorithm.md#L23-L25).
- **ADR / ProM Analysis Docs:** Retained as architectural reference.

### (b) Requirements Missing or Partial
* **None (0 missing requirements).** All 4 spec checklist items from `.scratch/code2petri/issues/23-prom-port-sequence-choice.md` are implemented:
  - `fold_sequence` (1→1→1 intermediate place contraction).
  - `fold_choice` (parallel transition collapse between shared input and output places).
  - Sequence $\to$ Choice greedy loop prioritization.
  - Synthetic AST topology tests (`TestASTTopologyReduction` in [`tests/test_fold_reduction.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_fold_reduction.py)).

### (c) Behaviour Not Asked For (Scope Creep)
1. **Premature Ticket 24 Implementation in Working Tree:**
   - **Finding:** The uncommitted working tree in [`code2petri/fold.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py) and [`code2petri/__init__.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/__init__.py) introduces unrequested Ticket 24 algorithms (`fold_while`, `detect_while`, `fold_marked_graph`, `fold_state_machine`, `fold_well_structured`, and SESE-based `fold_unstructured`).
   - **Impact:** Merging Ticket 24 logic into [`fold_net()`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L1158-L1178) prior to cleanly closing Ticket 23 introduced severe runtime regressions that break the test suite.

### (d) Requirements Implemented But Implementation Looks Wrong (Critical Regressions)
1. **Infinite Loop in `fold_net()` ([`test_unstructured_fold_on_single_place_net`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_fold_reduction.py#L251-L280)):**
   - **Root Cause:** In `fold_net()`, `fold_unstructured` was added inside the `while not _is_trivial_workflow_net(current_net)` loop with `continue`. Because `_is_trivial_workflow_net` requires 2 distinct boundary places ($p_{in} \ne p_{out}$), a single-place self-loop net (`p0 -> t -> p0`) never evaluates to trivial. `detect_unstructured` repeatedly matches the net, infinitely collapsing $t_{Cn}$ into $t_{C(n+1)}$ (ran 37+ CPU minutes, 9.5 GB RAM).
   - **Actionable Fix:** Either revert `fold_unstructured` to run strictly as an irreducible terminal fallback outside the while loop with an immediate `break`, or update the loop termination condition to recognize single-place irreducible terminal nets (`if len(current_net.transitions) <= 1: break`).
2. **Unstructured Penalty Regression ([`test_known_irreducible_net_terminates_with_unstructured_penalty`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_fold_reduction.py#L218-L250)):**
   - **Root Cause:** `detect_unstructured` replaced `omega = float(cfg.unstructured)` (7.0) with an uncalibrated ProM weight calculation $\tau_{new} - \tau_{sum}$, producing $\omega = 156.0$ and failing test assertions expecting 7.0 (`AssertionError: 156.0 != 7.0`).
   - **Actionable Fix:** Reconcile formula changes with `FoldConfig.unstructured` and update tests/spec before modifying unstructured penalty behavior.

---

## Summary
- **Standards Axis:** 2 findings (0 hard violations, 2 baseline smells: worst is duplicated symmetry difference calculation across macro detectors).
- **Spec Axis:** 3 findings (0 missing requirements; 1 scope creep: premature Ticket 24 changes in working tree; 2 critical implementation flaws: infinite loop in `fold_net` and unstructured penalty test regression).
