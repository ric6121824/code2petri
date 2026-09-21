# Phase 2.6 Comprehensive Code Review (Final): Tickets 22–25

**Scope:** Tickets 22 to 25 (Nested Call Resolution, ProM Local Reduction Algorithms, Loops & SESE Macro-Components, Interactive Compound Node Expansion)  
**Diff:** `a2f9919...HEAD` (9 commits, 20 files changed)  
**Commits:**
- `c935d90` refactor(code2petri): resolve tickets 22-25 review findings (Subnet dataclass and NetTopology symmetry multiplier)
- `5c88c33` refactor(viewer): extract addArc helper and refine folded caller notification
- `188c98c` refactor(code2petri): resolve tickets 23-25 round 1 review findings
- `f7fadee` refactor(code2petri): resolve ticket 23 round 2 review findings (reused symmetry multiplier)
- `81c67f6` feat(code2petri): add interactive compound node expansion in html viewer (ticket 25)
- `445c45a` feat(code2petri): port ProM while loop and SESE macro-component reduction (ticket 24)
- `b4d919f` refactor(code2petri): resolve ticket 23 code review findings (round 1)
- `8d2772b` feat(code2petri): port ProM local sequence and choice reduction (ticket 23)
- `9d46ae6` feat(code2petri): resolve nested call sites in inlined callees (ticket 22)

**Standards Baseline:** `CONTEXT.md` (Domain Model Vocabulary) & Fowler 12-smell baseline  
**Spec Baseline:** [`.scratch/code2petri/specs/phase-2.6-interactive-expansion.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.6-interactive-expansion.md) and Issues 22–25

---

## 1. Executive Summary

| Axis | Hard Violations / Blockers | Minor Smells / Deviations | Status | Worst Issue |
| :--- | :---: | :---: | :---: | :--- |
| **Standards** | **0** | **2 smells** | **PASS** | $O(V^2)$ boundary traversal duplication across macro detectors |
| **Spec** | **0** | **3 justified architectural variances, 2 scope notes** | **PASS** | Boundary place unification (ADR-0002) vs direct rewiring (structurally required for bipartite graph validity) |

All 356 unit, reduction, viewer, and integration tests pass cleanly with `BypassSandbox: true` and Node.js in `PATH`.
*Note: The author's most recent commit (`c935d90`) successfully eliminated the previously flagged `Subnet` data clump and `NetTopology` feature envy!*

---

## 2. Standards Review

### (a) Documented Repo Standards (`CONTEXT.md`)
**Status: PASS (0 Hard Violations).**

The recent refactoring commits successfully resolved all prior Phase 2.6 Round 1/2 violations:
- **Prohibited Vocabulary:** `ADR-0003` was scrubbed of "macro-components" in favor of "compound SESE subnets".
- **Single-Place Contraction:** Replaces legacy "sequence collapsing".
- **Opaque Transition & Fold Step:** Used correctly across all refactoring code.
- **CamelCase aliases** (`foldSequence`, `foldChoice`) were purged from the API.

### (b) Verification of Prior Baseline Review Findings
**RESOLVED (in `c935d90`, `188c98c`, `5c88c33`):**
1. **Feature Envy:** `calculate_symmetry_multiplier` was properly relocated into the `NetTopology` class to operate directly on its own graph data.
2. **Data Clumps:** The new `Subnet` dataclass elegantly bundles `places`, `transitions`, and `arcs` together, resolving the parameter clump in `_calculate_unstructured_omega`.
3. **Duplicated Code:** The repetitive single-step wrapper logic was centralized into `_fold_first_candidate`, and shared node formatting was unified in the JS template.

### (c) New Baseline Code Smells (Judgement Calls)
1. **Duplicated Code** ([`code2petri/fold.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py)):
   - **Analysis:** The $O(V^2)$ boundary traversal loop and candidate sorting logic are copy-pasted across the three SESE detection functions (`_detect_macro`, `detect_well_structured`, `detect_unstructured`). They all iterate `for p_src in sorted(topo.place_ids): for p_snk in ...` to find bounded SESE pairs.
   - **Actionable Fix:** Extract a shared `_find_sese_candidates(topo, boundary_ids)` generator that yields bounded SESE pairs. The specific detectors can then filter the yielded pairs by their invariants and grab the optimal candidate.
2. **Middle Man** ([`code2petri/fold.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py)):
   - **Analysis:** While the core logic for `calculate_symmetry_multiplier` was moved to `NetTopology` in `c935d90`, the original module-level function was left behind as a hollow delegate wrapper that just instantiates a topology and forwards the call.
   - **Actionable Fix:** Drop this standalone wrapper entirely. Force external callers and tests to invoke `topo.calculate_symmetry_multiplier()` directly.

---

## 3. Spec Review

### (a) Missing or Partial Requirements
**Status: PASS (0 Missing Requirements, 0 Defects).**
All requirements across tickets 22–25 are fully satisfied. The integration tests prove successful AST collapse and interactive UI compound node toggling.

### (b) Scope Creep (Behaviour Not Asked For)
1. **Architectural Documentation:** The diff introduces `docs/adr/0003-adopt-prom-local-reduction-algorithm.md` and `.scratch/code2petri/prom-analysis-process.md`. While highly valuable, these large architectural artifacts were not explicitly requested by the ticket checklists. *Actionable Suggestion:* Retain the documentation.
2. **Metric Formula Alteration:** The diff replaces Lassen's Definition 22 symmetry difference formula with ProM's 1.5x Choice markup. Although omitted from the Ticket 23 checklist, this fulfills Overarching Spec User Story 1 (*"evaluate if/else branches using the formal Choice multiplier (1.5x)"*). *Actionable Suggestion:* Retain the formula change.

### (c) Implementation Deviations (Justified Architectural Differences)
1. **Boundary Unification vs. Rewiring (ADR-0002):**
   - *Spec Quote (Ticket 25):* `"- [x] Javascript: Dynamically rewire the callee's entrance/exit places to the caller's input/output arcs"`
   - *Finding:* Connecting caller preset places directly to callee entrance places creates illegal Place $\to$ Place arcs in Petri nets ($P \cap T = \emptyset$). The implementation unifies away boundary places entirely to preserve bipartite integrity.
2. **Fold Slider Independence:**
   - *Spec Quote (Ticket 25):* *"The fold slider logic (`apply_fold_step`) will be updated to ignore elements that are children of a compound node."*
   - *Finding:* Instead of complex ignoring logic in `apply_fold_step`, `renderStep` just replaces the entire graph on each slider tick and dynamically re-applies expansions on top of the raw backend state. This is a clean divergence.
3. **Murata Generalization vs. Strict ProM:**
   - *Spec Quote (Ticket 23):* *"Implement `foldChoice` collapsing parallel transitions between a single shared input place and single shared output place."*
   - *Finding:* The implementation intentionally generalizes Murata reduction to group transitions by target place, bypassing strict ProM isolation invariants. This successfully handles complex AST fallthroughs.

---

## 4. Summary

- **Standards Axis:** 2 minor baseline smells ($O(V^2)$ duplication, leftover Middle Man wrapper), 0 hard violations. The author successfully resolved the heavy data clumps and feature envy from prior rounds.
- **Spec Axis:** 0 missing requirements, 3 justified architectural variances.
