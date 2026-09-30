# Code Review: Ticket 38 (JS Fold Engine: Unstructured Knot Isolation) — Round 01

**Commit:** [`a7cf6d2`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/38-js-fold-engine-unstructured-knot-isolation.md) (`feat(viewer): implement live unstructured knot reduction engine (ticket 38)`)  
**Diff:** `git diff fc2112b...HEAD` (3 files changed, 623 insertions(+), 10 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/38-js-fold-engine-unstructured-knot-isolation.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/38-js-fold-engine-unstructured-knot-isolation.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 69 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

1. **Domain Vocabulary Drift — Node Clicking ([`CONTEXT.md:79-82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L79-L82))**:
   - **Rule:** `Place-Centric Fold Trigger` (*Avoid: Node clicking, manual reduction*).
   - **Violation:** In [`tests/test_html_viewer.py:3314`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3314):
     ```python
     """Validates that left-clicking boundary place triggers unstructured reduction and opens inspector."""
     ```
     Uses "left-clicking [boundary place]" (Node clicking).
   - **Actionable Fix:** Rephrase docstring to use domain term `Place-Centric Fold Trigger`.

2. **Domain Vocabulary Drift — Weight Options ([`CONTEXT.md:63-66`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L63-L66))**:
   - **Rule:** `Fold Config` (*Avoid: Weight options, reduction settings*).
   - **Violation:** In [`tests/test_html_viewer.py:3280`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L3280):
     ```python
     """Validates that LiveFoldReductionEngine respects custom unstructured multiplier option matching Python."""
     ```
     Uses "multiplier option" rather than config / penalty weight.
   - **Actionable Fix:** Replace "multiplier option" with `Fold Config` or penalty weight.

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Unstructured Penalty & Accumulation ([`code2petri/viewer/template.html:2638-2661`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2638-L2661) & [`lines 2701-2726`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2701-L2726))**:
   - The identical logic shape (subgraph arc counting, ProM formula weight calculation, config scaling, symmetry multiplier, and $\tau_{new}/\omega$ accumulation) is duplicated between minimal knot isolation and the global fallback branch.
   - **Actionable Fix:** Extract a shared helper `_calculateUnstructuredOmega(nodeIds, compTrans)` mirroring Python's `_calculate_unstructured_omega`.

2. **Repeated Switches — SESE Precedence Cascades ([`code2petri/viewer/template.html:1934-1940`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1934-L1940) & [`lines 3214-3233`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L3214-L3233))**:
   - Definition 21 SESE reduction precedence is hardcoded via deep nested `if` cascades and ad-hoc flags (`hasPriorToUnstructured`) in both `getFoldType` and `updateFoldableHighlights`.
   - **Actionable Fix:** Drive SESE fold detection sequentially through an ordered array of detector strategies.

---

## Spec

### (a) Missing or Partial Requirements
- **None.** All checklist items from ticket 38 are implemented:
  - Minimal SESE knot isolation and global fallback are fully implemented in `detectUnstructured()`.
  - Priority gating in `getFoldType()` and `updateFoldableHighlights()` strictly gates unstructured reduction behind elementary (Sequence, Choice, Loop), Marked Graph, State Machine, and Well-Structured reductions, matching Lassen Def. 21.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Configurable Weight Scaling:**
   - In `template.html`: `cfg.unstructured` option defaults to `7.0`, and dynamically rescales penalty weight:
     `weight = (self.cfg.unstructured / 7.0) * weight;`
   - *Spec Line 11:* `"- [x] The unstructured component's tau is calculated using the ProM penalty formula ($5 \times (||F_C| - (|P_C| + |T_C|)| + 1)$)"`
   - *Assessment:* Approved benign scope creep to preserve parity with Python `FoldConfig(unstructured=...)`.

2. **Visual Styling & Inspector HUD Wiring:**
   - In `template.html`: Added CSS rules for `node.place.contractible-unstructured` (`#e06c75`) and inspector popover support.
   - *Assessment:* Necessary visual affordance aligning with Phase 2.7 live fold UX conventions.

### (c) Requirements Implemented but Look Wrong
- **None.** The implementation accurately reflects the spec and matches Python reference behavior:
  - **Penalty Calculation:** Correctly computed via `5 * (Math.abs(arcCount - nodeCount) + 1)` and scaled by `diffP * diffT` symmetry multipliers, matching Python `_calculate_unstructured_omega()`.
  - **Minimal Knot Selection:** Implemented via `sortMinimal: true` (`a.nodes.size - b.nodes.size` with deterministic source/sink tie-breaking), matching Python `(len(sese_nodes), p_src_id, p_snk_id)`.
  - **Global Fallback:** Correctly gates on `transNodes.length > 1`, extracts entry/exit places, and collapses remaining topology while rejecting trivial nets ($\le 1$ transition).
  - Parity validated across all 8 new test cases.

---

## Summary

- **Standards (4 findings):** 2 test docstring domain vocabulary drifts ("left-clicking", "multiplier option"), 2 baseline smells (duplicated penalty/accumulation calculation in minimal vs global fallback, hardcoded nested SESE precedence cascades). Worst issue: Duplicated penalty calculation logic across `detectUnstructured` branches.
- **Spec (2 findings):** 0 missing requirements, 2 benign scope additions (configurable `cfg.unstructured` weight scaling and HUD styling/inspector wiring), 0 incorrect implementations. Worst issue: None (all acceptance criteria fully satisfied with Python parity).
