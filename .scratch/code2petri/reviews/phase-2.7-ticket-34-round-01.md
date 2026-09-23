# Code Review: Ticket 34 (JS Fold Engine: While Loop Reduction) — Round 01

**Commit:** `ed83412` (`feat(viewer): implement live while loop reduction engine (ticket 34)`)  
**Diff:** `git diff 6e7f845...HEAD` (4 files changed, 645 insertions(+), 10 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/34-js-fold-engine-while-loop.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/34-js-fold-engine-while-loop.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 45 tests in `test_html_viewer.py` and 399 repository tests pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

1. **Domain Vocabulary Drifts ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md))**:
   - **`Component-Local Unfold` & `Consumed Subnet`** (*Avoid: local undo, closed sub-graph*):
     - In [`tests/test_html_viewer.py:1792-1793`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L1792-L1793):
       ```javascript
       // Verify consumed subnet storage for local unfold
       const sub = c01.data('consumedSubnet') || c01.data('consumedSubgraph');
       ```
     - **Actionable Fix:** Replace `"local unfold"` in comments with the canonical domain term **`Component-Local Unfold`**. Remove the fallback reference to `consumedSubgraph` to prevent resurrecting the prohibited term `"sub-graph"`.
   - **`Single-Place Contraction` vs `Structural Fold`**:
     - In [`code2petri/viewer/template.html:1667`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1667) and tests: method named `executeWhileContraction(placeNode)`.
     - *Observation:* Contraction specifically denotes Single-Place Contraction in `CONTEXT.md`. A while-loop reduction is a multi-node **Structural Fold**.
     - **Actionable Fix:** Rename `executeWhileContraction` to `executeWhileFold` or `executeWhileReduction`.

### (b) Baseline Code Smells (Judgement Calls)

1. **Data Clumps in Helper Signature** ([`code2petri/viewer/template.html:1211`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1211)):
   - `_createOpaqueComponentNode(opaqueId, label, rawLabel, tau, omega, componentType, parentId, consumedSubnet, position = null)` now takes 9 positional arguments.
   - **Actionable Fix:** Refactor parameters into a single options object: `_createOpaqueComponentNode({ opaqueId, label, rawLabel, tau, omega, componentType, parentId, consumedSubnet, position })`.

2. **Duplicated Code — Boundary Arc Relinking & Compound Pruning** ([`code2petri/viewer/template.html:1774-1798, 1845-1870`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1774-L1798)):
   - Re-linking incoming/outgoing boundary arcs to the new component (`boundaryInArcs.forEach` / `boundaryOutArcs.forEach`) and pruning empty compound containers (`consumedCompounds`) is copy-pasted almost verbatim across `executeSinglePlaceContraction`, `executeChoiceContraction`, and `executeWhileContraction`.
   - **Actionable Fix:** Extract `_relinkBoundaryArcs(boundaryInArcs, boundaryOutArcs, targetNodeId)` and `_pruneEmptyCompounds(consumedCompounds)` helpers inside `LiveFoldReductionEngine`.

3. **Duplicated Code — Test Topology Fixture** ([`tests/test_html_viewer.py:1682-1701, 1737-1756`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L1682-L1701)):
   - The 20-line JSON string defining the while-loop topology is duplicated verbatim across `test_place_nodes_eligible_for_while_loop_reduction_highlighted_purple` and `test_left_click_eligible_while_loop_head_folds_loop_headless`.
   - **Actionable Fix:** Extract a shared `WHILE_LOOP_NET_JSON` string constant in `test_html_viewer.py`.

4. **Repeated Switches / Cascades** ([`code2petri/viewer/template.html:2008-2030, 2058-2068`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2008-L2030)):
   - Cascading `if (foldType === 'choice') ... else if (foldType === 'sequence') ... else if (foldType === 'while')` is repeated across `updateFoldableHighlights` (handling 4 CSS classes) and Cytoscape `tap` event dispatch.
   - **Actionable Fix:** Define a fold type descriptor map (e.g. `{ while: { cssClass: 'contractible-while', execute: (p) => engine.executeWhileContraction(p) }, ... }`) to dispatch uniformly without cascading switch statements.

---

## Spec

### (a) Missing or Partial Requirements
**None.** All 5 acceptance criteria are fully met and verified:
1. **Purple Highlight**: While-loop head places (2-in/2-out with self-loop transition) are highlighted purple (`.contractible-while`).
2. **Fold Execution**: Left-clicking an eligible place folds the loop into an opaque component at the entry transition.
3. **Tau Multiplier**: Component receives updated $\tau$ with $2.0\times$ loop multiplier applied ($\tau_{\text{new}} = \tau_{\text{src}} + \tau_{\text{snk}} + 2.0 \times \tau_{\text{loop}}$).
4. **Python Match**: $\tau$ and $\omega$ values strictly match Python `fold_while` for identical topologies.
5. **Reconstitution Storage**: `consumedSubnet` retains all deleted nodes and arcs for future Component-Local Unfold.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Commit Artifact**:
   - `ed83412` includes `.scratch/code2petri/reviews/phase-2.7-tickets-32-33-round-02.md`, which reviews prior tickets rather than Ticket 34.
2. **Compound Boundary Pruning**:
   - Implemented `isFunctionFoldedIntoSingleComponent` and `consumedCompounds` pruning to clean up empty function boxes. Approved forward-compatible seam for Ticket 38.

### (c) Implementation Nuances / Questionable Areas

1. **Immediate Dagre Relayout Overrides Entry Position Seeding:**
   - *Spec Line 10:* `"- [x] Left-clicking an eligible loop head place folds the loop into an opaque component at the entry transition"`
   - *Observation:* `c_01` is seeded with `t_src.position()`, but the click handler immediately triggers `cy.layout(DAGRE_LAYOUT_OPTIONS).run()`, smoothly animating the component to its DAG layout position. This is the intended Cytoscape UI flow.
2. **Formula Alignment:**
   - The $2.0\times$ multiplier applies strictly to the loop body transition ($\tau_{\text{new}} = \tau_{\text{src}} + \tau_{\text{snk}} + 2.0 \times \tau_{\text{loop}}$) rather than scaling the overall composite sum. This aligns with ProM / Python `fold_while` per spec line 12.

---

## Summary

- **Standards:** 1 minor vocabulary drift ("local unfold" / fallback `consumedSubgraph`), 4 baseline smells (9-arg data clump in `_createOpaqueComponentNode`, copy-pasted boundary arc re-linking, duplicated test fixture, repeated `foldType` cascades). Worst issue: 9-parameter data clump in `_createOpaqueComponentNode`.
- **Spec:** 0 missing requirements, all 5 acceptance criteria satisfied and verified. 1 unrelated review artifact committed, 1 approved forward-compatible scope seam.
