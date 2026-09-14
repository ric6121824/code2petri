# Phase 2.5 Code Review & Suggestions (Round 2)

**Scope:** Full Phase 2.5 (Tickets 17 to 21) following commit `6a166fa`  
**Commit Range:** `9c68e0b...HEAD` (23 commits, 38 files changed, 8,917 insertions(+), 47 deletions(-))  
**Standards Baseline:** `CONTEXT.md` (Domain Model Vocabulary) & Fowler 12-smell baseline  
**Spec Baseline:** `.scratch/code2petri/specs/phase-2.5-structural-folding-and-viewer.md` and Issues 17–21  

---

## 1. Executive Summary

| Axis | Hard Violations / Blockers | Minor Smells / Deviations | Status | Worst Issue |
| :--- | :---: | :---: | :---: | :--- |
| **Standards** | **0** | **2 minor smells** | **PASSED** | Vestigial trailing parameter `topology` in `fold.py` |
| **Spec** | **0** | **0** | **PASSED** | None (all functional & mathematical requirements met) |

All 307 `code2petri` unit and integration tests pass cleanly with `BypassSandbox: true`. All critical blockers and design findings identified in Round 1 have been resolved in commit `6a166fa`.

---

## 2. Standards

### (a) Documented Repo Standards (`CONTEXT.md`)
**Status: 0 Hard Violations.**

The canonical domain model vocabulary is strictly honored across all Phase 2.5 code:
- **Opaque Transition**: Transition metadata consistently uses `opaque=True`, `t.is_opaque`, and `t_C{step}`. Forbidden terms ("dummy transition", "black box", "leaf transition") remain completely expunged.
- **Inline Expansion & Composite Net**: Recursive expansion constructs composite nets (`inline_expand`, `composite_net`) without deprecated concepts ("unrolling", "flattening", "merged graph").
- **Call Site & Resolution Context**: Cross-file calls are resolved via structured `CallSite` records and `--context` symbol analysis without referring to "call points" or "secondary files".
- **Faithful Translation**: Control flow structures (including recursive RAF loops) are faithfully modeled.

---

### (b) Verification of Round 1 Recommendations

1. **Middle Man in `code2petri/fold.py`**: **RESOLVED**.
   - Redundant delegators `load_fold_config`, `FoldConfig.from_json`, and `FoldConfig.from_file` were eliminated. Callers now invoke `FoldConfig.load` directly.
2. **Duplicated Code in `code2petri/inline.py`**: **RESOLVED**.
   - Implemented `CallFrame.variants()`. Lines 252 (`active_stack.update(caller_frame.variants())`) and 257 (`callee_frames = callee_frame.variants()`) now reuse this shared logic.
3. **Primitive Obsession in `code2petri/inline.py`**: **RESOLVED**.
   - Raw substring matching on `trans.label` was removed. `JavascriptWalker` now tags callback loops structurally via `CallSite.is_callback_loop = True`, inspected directly by `_is_self_referencing_loop`.
4. **Feature Envy in `code2petri/viewer/__init__.py`**: **RESOLVED**.
   - Reflection `hasattr` checks replaced with explicit type dispatch:
   ```python
   if isinstance(net_or_fold, FoldResult):
       fold_dict = net_or_fold.to_dict()
       display_title = title if title is not None else f"SM Score = {net_or_fold.final_sm}"
   ```
5. **Data Clump in `code2petri/fold.py`**: **RESOLVED**.
   - Detection signatures accept `net_or_topology: Union[PetriNet, NetTopology]`. In `detect_components`, `topo = NetTopology(net)` is instantiated once and passed as the primary argument (`detect_sequences(topo, config)`).

---

### (c) Baseline Smells (Judgement Calls) & Suggestions

1. **Speculative Generality / Vestigial Parameter**
   - **Location:** `code2petri/fold.py:266, 358, 449`
   ```python
   def detect_sequences(
       net_or_topology: Union[PetriNet, NetTopology],
       config: FoldConfig,
       topology: Optional[NetTopology] = None,
   ) -> List[Component]:
   ```
   - **Finding:** Because `net_or_topology` now accepts `NetTopology` directly, the trailing `topology` parameter is vestigial backward-compatibility glue.
   - **Suggestion:** In Phase 3, deprecate the trailing `topology` parameter and standardize signatures cleanly to `(net_or_topology, config)`.

2. **Minor Reflection**
   - **Location:** `code2petri/viewer/__init__.py:77`
   ```python
   net_dict = net_or_fold.to_dict() if hasattr(net_or_fold, "to_dict") else {}
   ```
   - **Finding:** In the fallback branch of `generate_html`, `hasattr` reflection is still used.
   - **Suggestion:** Use explicit type checking: `net_dict = net_or_fold.to_dict() if isinstance(net_or_fold, PetriNet) else {}`.

---

## 3. Spec

### (a) Verification of Round 1 Recommendations

1. **Animated Fold Transitions in HTML Viewer**
   - **Spec Quote:** `phase-2.5-structural-folding-and-viewer.md:26`:
     > *"collapsing the simplest remaining component into a dummy transition with an animation..."*
   - **Status:** **RESOLVED**. In `code2petri/viewer/template.html`, Cytoscape Dagre layout now runs with `animate: true` (350ms duration, ease-in-out). Pre-existing node coordinates are preserved across step transitions and re-seeded into `netToElements`, delivering smooth collapse and expand animations.

2. **Cross-Class Method Collision in Recursion Guard**
   - **Spec Quote:** `phase-2.5-structural-folding-and-viewer.md:78`:
     > *"A recursion guard tracks the active expansion call stack. If a callee appears in the stack (direct or indirect recursion), expansion halts..."*
   - **Status:** **RESOLVED**. `CallFrame.is_qualified` and `variants()` now omit bare names for class methods. Methods like `Game.step` calling `Engine.step` in the same file compare strictly on qualified identifiers, preventing false recursion halts. Verified with dedicated test `test_same_file_cross_class_method_name_collision_no_false_recursion`.

3. **Decoupling Browser Game Loop Logic**
   - **Spec Quote:** `issues/19-inline-expansion-engine.md:11`:
     > *"A recursion guard tracks the active expansion call stack; if a callee appears in the stack (direct or indirect recursion), expansion halts..."*
   - **Status:** **RESOLVED**. Added `CallSite.is_callback_loop` to `code2petri/walker_protocol.py`. `JavascriptWalker` annotates RAF cycles, allowing `code2petri/inline.py` to remain completely runtime- and language-agnostic.

4. **Documentation of Mathematical Deviation & Terminology**
   - **Spec Quotes:**
     - `phase-2.5-structural-folding-and-viewer.md:76`: *"Wire the call transition's preset place → callee's source place, and callee's sink place → call transition's postset place."*
     - `issues/20-cli-integration-fold-inline.md:31`: *"- [x] \"dummy\" is added to Transition.RESERVED_METADATA_KEYS."*
   - **Status:** **RESOLVED**. Formally added **ADR 0002** (Boundary Place Unification for Bipartite Graph Integrity) to `phase-2.5-structural-folding-and-viewer.md:153-161` explaining why place fusion is required for bipartite graph validity ($P \cap T = \emptyset$). Updated Issue 20 to document `"opaque"` canonically superseding `"dummy"`.

---

### (b) Spec Axis Evaluation

- **(a) Missing or Partial Requirements**: **None**. All functional requirements across Tickets 17 through 21 are fully satisfied.
- **(b) Scope Creep (Unasked Behaviour)**: **None unapproved**. The contextual info panel and interactive legend were formally documented and accepted in `issues/21-html-viewer-and-validation.md:9`.
- **(c) Implemented but Looks Wrong**: **None**. Graph transformations, complexity metric calculations, and recursion guard mechanics function accurately.

---

## 4. Next Steps & Recommendations for Phase 3

1. **Clean Deprecations**: Remove the vestigial trailing `topology` parameter in `fold.py` once all external callers have updated.
2. **Phase 3 Extensibility**: `FoldConfig.marked_graph` (AND-splits) is already defined and ready for concurrency modeling when C#/Unity coroutines are introduced.

---

**Summary:** Standards: 0 hard violations, 2 minor baseline smells (worst: vestigial trailing parameter `topology` in `fold.py`). Spec: 0 missing/partial, 0 scope creep, 0 looks wrong (worst: None — all requirements cleanly satisfied).
