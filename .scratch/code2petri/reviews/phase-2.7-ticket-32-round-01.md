# Code Review: Ticket 32 (JS Fold Engine: Sequence) — Round 01

**Branch:** `feature/live-fold-reduction-js-prototype`  
**Diff:** `git diff HEAD` (3 files changed)  
**Spec:** [`.scratch/code2petri/issues/32-js-fold-engine-sequence.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/32-js-fold-engine-sequence.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** 400 tests — **all pass**

---

## Standards

### (a) Documented Standards Violations
**None detected (Hard standard: 0 violations).**
- **Domain Vocabulary ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md))**: Conforms strictly to domain terminology (`Transition`, `Place`, `Opaque Transition`, `Single-Place Contraction`, `Transition Weight (tau)`, and `Component Penalty (omega)`). Avoids prohibited aliases (*black box*, *leaf transition*, *firing cost*, *folder node*, *merged graph*).
- **Petri Net Semantics**: Preserves bipartite invariants (place consumed between two transitions; boundary arcs re-anchored to the newly spawned opaque component).

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Test Harness & DOM Mocking** ([`tests/test_html_viewer.py:970-1015`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L970-L1015), [`tests/test_html_viewer.py:1082-1130`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L1082-L1130))
   - Node.js Cytoscape harness initialization and DOM element mocking (`inspectorPanel`, `inspectorLabel`, etc.) are repeated across headless tests in `test_html_viewer.py`.
   - *Assessment:* Acceptable for unit test isolation; shared test fixture can be extracted in a future test refactoring pass.

2. **Primitive Obsession / Repeated Switches — Node Type Checks** ([`code2petri/viewer/template.html:1504-1520`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1504-L1520))
   - Node classification checks (`targetNode.hasClass('place') || targetNode.data('type') === 'Place'`) repeat across handlers.
   - *Assessment:* Consider standardizing node predicate functions (`isPlace`, `isTransition`) in `template.html`.

3. **Speculative Generality — Cross-boundary Pruning & State Callback** ([`code2petri/viewer/template.html:1396-1418`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1396-L1418), [`1480-1483`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1480-L1483))
   - Cross-compound parent container pruning (`consumedCompounds`) and `this.onStateChange` callback hook prepare for Ticket 38/40 (cross-boundary folding & local unfold).
   - *Assessment:* Benign forward compatibility.

---

## Spec

### (a) Missing or Partial Requirements
**None.** All 5 acceptance criteria are fully met and verified by automated unit and headless tests:
1. **Visual Highlight**: Place nodes eligible for Single-Place Contraction are visually styled green (`.contractible`, `.contractible-sequence`, `#3fb950`).
2. **Left-Click Contraction**: Left-clicking an eligible place removes $p, t_{src}, t_{snk}$ and replaces them with an opaque component `c_XX`.
3. **Tau Badge Display**: The resulting component displays its updated $\tau$ weight ($1.0 + \tau_1 + \tau_2$) via SVG badge and opens the inspector panel.
4. **Subgraph Snapshot Storage**: `c_XX.data('consumedSubgraph')` stores original node snapshots, positions, classes, internal edges, boundary arcs, and compound containment for future local unfold.
5. **Python Engine Alignment**: Headless Node test validates that JS $\tau$ (5.25), $\omega$ (1.0), and running SM score match Python `fold_single_place_contraction` on custom-weighted nets.

### (b) Scope Creep (Behaviour in Diff Not Asked For)
1. **Compound Container Pruning:**
   - Prunes parent compound nodes if sequence contraction consumes all remaining elements within them, preserving compound data in `consumedSubgraph`.
   - *Assessment:* Approved; prevents orphaned empty compound bounding boxes in multi-function nets.
2. **`onStateChange` Hook:**
   - Dispatches state change events if registered.
   - *Assessment:* Approved lightweight notification hook.

### (c) Implementation Looks Wrong
**None found.**
- Strict ProM $1 \to 1 \to 1$ linearity checks, zero-token guard, and self-loop guards are enforced.
- Boundary arcs are correctly rewired to the new opaque transition.

---

## Summary

- **Standards:** 0 hard violations, 3 baseline smells (test harness duplication, redundant node type checks, anticipatory compound pruning).
- **Spec:** All 5 acceptance criteria satisfied and verified across 400/400 passing tests. 0 defects.
