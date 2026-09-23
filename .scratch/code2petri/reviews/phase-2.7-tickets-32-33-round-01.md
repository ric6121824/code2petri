# Code Review: Tickets 32 & 33 (JS Fold Engine: Sequence & Choice) — Round 01

**Scope:** Ticket 32 (Live Sequence Reduction) & Ticket 33 (Live Choice Reduction)  
**Commits:** `f05fee2` and `2606ff1`  
**Diff:** `git diff 8f08db6...HEAD` (6 files changed, 1,391 insertions(+), 38 deletions(-))  
**Specs:**
- [`.scratch/code2petri/issues/32-js-fold-engine-sequence.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/32-js-fold-engine-sequence.md)
- [`.scratch/code2petri/issues/33-js-fold-engine-choice.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/33-js-fold-engine-choice.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 391 unit and viewer tests pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

1. **Domain Vocabulary Drifts ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md))**:
   - **`Live Fold Reduction`** (*Avoid: JS reduction, client-side folding*):
     - In [`tests/test_html_viewer.py:1394, 1460, 1715, 1786`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L1394-L1460): docstrings and error messages refer to `"JS sequence fold"`, `"JS contraction failed"`, `"JS choice fold"`, and `"JS choice contraction failed"`.
     - **Actionable Fix:** Replace `"JS sequence fold"` / `"JS contraction"` with `"Live Fold Reduction (Single-Place Contraction)"` and `"Live Fold Reduction (Choice)"`.
   - **`Single-Place Contraction`** (*Avoid: Sequence collapsing, chain reduction*):
     - In [`code2petri/viewer/template.html:1224`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1224): Method named `canContractPlace(placeNode)` rather than `canSinglePlaceContract(placeNode)` or `detectSequenceCandidates(placeNode)`.
     - **Actionable Fix:** Rename `canContractPlace` to `canSinglePlaceContract` or `detectSequenceCandidate` to align with domain vocabulary and avoid confusion with choice contractions.
   - **`Collapsed Compound State / Fold Step`** (*Avoid: closed sub-graph, reduction snapshot*):
     - In [`code2petri/viewer/template.html:1388-1402`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1388-L1402) and [`tests/test_html_viewer.py:1359-1365`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L1359-L1365): reduction data is stored under property `consumedSubgraph` and commented as `"consumed subgraph storage"`.
     - **Actionable Fix:** Rename property `consumedSubgraph` to `consumedSubnet` or `reductionData`.

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Test Regex Extraction & Engine Setup** ([`tests/test_html_viewer.py:1177-1183`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L1177-L1183)):
   - Exact regex slicing for extracting `LiveFoldReductionEngine`, `updateFoldableHighlights`, and mock DOM inspector setup is copy-pasted across 6 test methods.
   - **Actionable Fix:** Extract a shared helper fixture `_setup_live_fold_test_harness(node_script: str) -> str` in `test_html_viewer.py`.

2. **Duplicated Code — Contraction Execution Routine** ([`code2petri/viewer/template.html:1315-1375`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1315-L1375)):
   - `executeSinglePlaceContraction` and `executeChoiceContraction` duplicate opaque component ID generation (`'c_' + String(stepNum).padStart(2, '0')`), element serialization, graph deletion, and opaque transition creation.
   - **Actionable Fix:** Extract a common `_createOpaqueComponentNode(id, label, tau, omega, type, consumedData)` helper in `LiveFoldReductionEngine`.

3. **Speculative Generality** ([`code2petri/viewer/template.html:1169-1175`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1169-L1175)):
   - `this.history = []`: Linearly appended on every fold, but never popped or read. (Component-Local Unfold in Ticket 39 is explicitly non-linear).
   - `this.cfg = { sequence: 1.0, choice: 1.0, loop: 3.0 }`: Configures `loop` before Ticket 34.
   - `this.onStateChange`: Unused callback parameter.
   - `executeChoiceContraction(placeNode, bundleIndex)` accepts unused `bundleIndex`.
   - **Actionable Fix:** Remove unused callbacks and parameters until the corresponding tickets require them.

4. **Repeated Switches / Cascades** ([`code2petri/viewer/template.html:1723-1770`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1723-L1770)):
   - Place eligibility cascades distinguishing sequence vs choice are repeated across `updateFoldableHighlights` and `cy.on('tap')`.
   - **Actionable Fix:** Add a helper `engine.getFoldType(placeNode) -> 'sequence' | 'choice' | null` to evaluate priority and type in one place.

---

## Spec

### (a) Missing or Partial Requirements

1. **Multi-Bundle Choice Selection (Ticket 33):**
   - *Spec Line 10:* `"- [x] Left-clicking an eligible place fuses its parallel outgoing transitions into a single opaque component"`
   - *Finding:* When an eligible place branches toward multiple distinct join places (e.g. multi-way branching to two separate merge targets), `detectChoiceCandidates()` groups all valid bundles, but `executeChoiceContraction(placeNode)` defaults to `check.bundles[bundleIndex || 0]`. Because the canvas tap handler passes no bundle index, it silently folds only the first bundle in arbitrary map iteration order.
   - **Actionable Fix:** When multiple bundles originate from the same place, either fold all valid parallel bundles or provide bundle selection so the reduction does not depend on arbitrary iteration order.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Auto-Inspector & Canvas Relayout (Ticket 32):**
   - *Spec Line 11:* `"- [x] The resulting component displays its updated tau weight"`
   - *Finding:* Left-clicking an eligible place not only creates the component with its $\tau$ badge, but forcibly triggers full Dagre canvas relayout (`cy.layout(DAGRE_LAYOUT_OPTIONS).run()`) and automatically opens the sidebar inspector (`openInspector(res.node)`).
   - *Assessment:* Canvas relayout is helpful for clean visualization; auto-opening inspector is acceptable UX feedback, though unrequested.

2. **Compound Pruning & Function Boundary Encapsulation (Tickets 32 & 33):**
   - *Finding:* `isFunctionFoldedIntoSingleComponent()` checks and `consumedCompounds` pruning to delete empty compound boxes were added, anticipating Ticket 38.
   - *Assessment:* Approved forward-compatible seam for Collapsed Compound State.

### (c) Implementation Looks Wrong

1. **Default $\omega$ and $\tau$ Value Mismatch on Sequence Contraction (Ticket 32):**
   - *Spec Line 13:* `"- [x] The JS tau and omega values for a sequence contraction match the output of the Python fold engine for the same topology"`
   - *Finding:* In JS, `LiveFoldReductionEngine` hardcodes default `this.cfg.sequence = 1.0`, computing $\omega = 1.0$ and $\tau = 1.0 + \tau_1 + \tau_2$. However, in Python, default `FoldConfig.sequence` is `0.0` (per Lassen 2008 Def. 21 and `FoldConfig`), computing $\omega = 0.0$ and $\tau = \tau_1 + \tau_2$.
   - The unit test in `tests/test_html_viewer.py` masked this divergence by passing `FoldConfig(sequence=1.0)` to Python rather than comparing against the default Python configuration!
   - **Actionable Fix:** Set `this.cfg.sequence = 0.0` by default in `LiveFoldReductionEngine` to match Python's default `FoldConfig.sequence = 0.0`. Single-Place Contractions have zero penalty ($\omega = 0$) and simply sum $\tau = \tau_1 + \tau_2$. Update the test assertion to use default `FoldConfig()`.

---

## Summary

- **Standards:** 4 documented vocabulary drifts under `CONTEXT.md` (drifts to "JS contraction" and "consumed subgraph"), 4 baseline smells (test harness duplication, duplicate opaque node construction, speculative `history`/callbacks). Worst issue: Vocabulary drift to non-domain terms in docstrings and property names.
- **Spec:** 1 semantic discrepancy (JS sequence $\omega$ default of 1.0 vs Python default of 0.0), 1 partial multi-bundle handling item, 2 approved scope additions. Worst issue: Sequence contraction default penalty mismatch ($\omega=1.0$ vs $\omega=0.0$).
