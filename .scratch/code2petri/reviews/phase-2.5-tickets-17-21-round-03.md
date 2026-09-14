# Phase 2.5 Code Review Report (Round 3)

**Scope:** Full Phase 2.5 (Tickets 17 to 21) following commits `6a166fa`, `867d1c4`, and `c9c32cf`  
**Commit Range:** `9c68e0b...HEAD` (25 commits across Tickets 17–21)  
**Standards Baseline:** `CONTEXT.md` (Domain Model Vocabulary) & Fowler 12-smell baseline  
**Spec Baseline:** `.scratch/code2petri/specs/phase-2.5-structural-folding-and-viewer.md` and Issues 17–21  

---

## 1. Executive Summary

| Axis | Hard Violations / Blockers | Baseline Smells / Deviations | Status | Worst Issue |
| :--- | :---: | :---: | :---: | :--- |
| **Standards** | **0** | **0** | **PASSED** | None — all standards honored, all prior smells cleanly resolved |
| **Spec** | **0** | **0** | **PASSED** | None — 100% functional, mathematical, and CLI/viewer compliance |

All 318 `code2petri` unit and integration tests pass cleanly (100% OK). All findings from Round 1 and Round 2 have been thoroughly resolved.

---

## 2. Standards

### (a) Documented Repo Standards (`CONTEXT.md`)
**Status: 0 Hard Violations.**

The canonical domain model vocabulary is strictly honored across all new and modified modules:
- **Opaque Transition**: Transition metadata consistently uses `opaque=True`, `t.is_opaque`, and `t_C{step}`. Forbidden aliases (*dummy transition*, *black box*, *leaf transition*) are completely expunged from non-vendor code.
- **Inline Expansion & Composite Net**: Recursive expansion in `code2petri/inline.py` constructs composite nets (`inline_expand`, `composite_net`) without deprecated concepts (*unrolling*, *flattening*, *merged graph*).
- **Call Site & Resolution Context**: Cross-file calls are resolved via structured `CallSite` records and `--context` symbol analysis without references to *call points* or *secondary files*.
- **Faithful Translation**: Control flow structures, boundary conditions, and recursive loop cycle guards accurately model source language semantics.

---

### (b) Verification of Round 2 Recommendations
Both items identified in Round 2 were resolved in commit `c9c32cf`:

1. **Speculative Generality / Vestigial Trailing Parameter in `code2petri/fold.py`**: **RESOLVED**.
   - Trailing `topology: Optional[NetTopology] = None` parameters were removed from `calculate_symmetry_multiplier`, `detect_sequences`, `detect_choices`, and `detect_loops`.
   - Signatures now cleanly standardize on `(net_or_topology: Union[PetriNet, NetTopology], config: FoldConfig)`.
2. **Minor Reflection in `code2petri/viewer/__init__.py:77`**: **RESOLVED**.
   - Replaced reflection `hasattr(net_or_fold, "to_dict")` with explicit type dispatch:
     ```python
     net_dict = net_or_fold.to_dict() if isinstance(net_or_fold, PetriNet) else {}
     ```

---

### (c) Baseline Smells (Judgement Calls)
**Status: 0 Smells Identified.**
- No mysterious names, duplicated code, data clumps, or speculative generality remain in the diff.
- Method responsibilities, data structures, and pipeline wiring adhere cleanly to single-responsibility boundaries.

---

## 3. Spec

### (a) Verification of Refactoring in `c9c32cf`
- **Spec Quote (`issues/17-fold-config-and-component-detection.md:15`)**:
  > *"- [x] A detection function accepts a PetriNet and FoldConfig and returns a list of Component instances sorted by Definition 21 priority..."*
- **Spec Quote (`issues/21-html-viewer-and-validation.md:22`)**:
  > *"- [x] A Python generator function accepts a FoldResult (or raw PetriNet for --no-fold) and produces a complete HTML string with the data blocks and library source embedded."*
- **Status:** **PASSED**. Parameter signatures accept `net_or_topology: Union[PetriNet, NetTopology]`, satisfying the requirement to accept `PetriNet`. Type dispatch in `generate_html` strictly checks `isinstance(net_or_fold, PetriNet)`.

---

### (b) Spec Axis Evaluation
- **(a) Missing or Partial Requirements**: **None (0 findings)**.
  - Component detection order (Sequence → Choice → Loop → Unstructured), $\omega$ penalty calculations with branch symmetry multipliers, and $\tau$ accumulation strictly adhere to Lassen & van der Aalst (2008).
  - Headless CLI exports (`.dot`, `.png`, `.pnml`) faithfully output the penultimate fold state, and JSON outputs serialize full `FoldResult` schemas.
  - Offline HTML viewer operates 100% self-contained with step playback, live SM score, and 350ms smooth collapse/expand animations.
- **(b) Behaviour in Diff Not Asked For (Scope Creep)**: **None unapproved (0 findings)**.
  - Contextual info panel and interactive legend are formally documented and accepted in `issues/21-html-viewer-and-validation.md:9`.
  - Opaque transition vocabulary formally codified in `issues/20-cli-integration-fold-inline.md:31`.
- **(c) Implemented but Looks Wrong**: **None (0 findings)**.
  - Boundary place fusion formally codified in **ADR 0002** (`phase-2.5-structural-folding-and-viewer.md:155-161`) to preserve bipartite graph validity ($P \cap T = \emptyset$).
  - Recursion guard prevents false halts across same-name methods in distinct classes (`CallFrame.is_qualified`) while `CallSite.is_callback_loop` cleanly halts browser RAF loop cycles without language leakage.

---

**Summary:** Standards: 0 hard violations, 0 baseline smells (worst: None). Spec: 0 missing/partial, 0 unasked, 0 looks wrong (worst: None).
