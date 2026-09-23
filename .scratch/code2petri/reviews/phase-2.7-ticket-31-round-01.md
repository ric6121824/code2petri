# Code Review: Ticket 31 (Viewer: Input Remapping) — Round 01

**Branch:** `feature/live-fold-reduction-js-prototype`  
**Diff:** `git diff HEAD` (4 files changed)  
**Spec:** [`.scratch/code2petri/issues/31-viewer-input-remapping.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/31-viewer-input-remapping.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** 391 tests — **all pass**

---

## Standards

### (a) Documented Standards Violations
**None detected (Hard standard).**
- **Domain Vocabulary ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md))**: Conforms strictly to domain terminology (`Transition`, `Place`, `Compound Node`, $\tau$ execution weight).
- **Petri Net Semantics**: Preserves separation between bipartite graph structure and UI interaction layer. Place nodes remain purely structural without spurious interaction triggers.

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Test Runner & Template Reading Helpers Addressed** ([`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py))
   - Extracted shared `_read_template_html()` and `_run_node_script()` helpers, reducing boilerplate across headless Node.js tests.
2. **Feature Envy / Incomplete Data Adapter** ([`code2petri/viewer/template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1067-L1100))
   - Node metadata extraction was encapsulated cleanly into `getInspectorData(node)` rather than directly manipulating DOM elements inside the event listener.

---

## Spec

### (a) Missing or Partial Requirements
**None.** All 5 acceptance criteria are fully met:
1. **Right Mouse Drag Pan**: Holding and dragging button 2 (mask 2) updates `cy.pan()` based on delta coordinates.
2. **Middle Mouse Drag Pan**: Holding and dragging button 1 (mask 4) updates `cy.pan()` based on delta coordinates.
3. **Place Tap Invariance**: Left-clicking place nodes returns immediately without modifying canvas pan or zoom, and does not open the inspector.
4. **Transition / Component Node Inspection**: Left-clicking opens the `#inspector-panel` displaying `label`, `tau` weight, `component_type`, and `line_number`.
5. **Scroll Wheel Zoom**: Cytoscape wheel zoom handler scales the canvas centered at cursor coordinates.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Inspector Dismissal Mechanisms:**
   - Added an explicit close button (`#inspector-close`) and background canvas click handler (`evt.target === cy`) to hide the inspector panel when clicking outside nodes.
   - *Assessment:* Approved standard UI usability enhancement; prevents inspector card from permanently occluding the graph.

### (c) Implementation Looks Wrong

1. **Compound Node $\tau$ Representation:**
   - Compound function containers represent nested scopes rather than unit execution steps. Setting `tau: '—'` for compound nodes cleanly distinguishes them from atomic or opaque transitions that carry numeric execution weights.

---

## Summary

- **Standards:** 0 hard violations, 0 blocking smells. Reusable test harness helpers and metadata adapter cleanly separated.
- **Spec:** All 5 acceptance criteria satisfied and verified via both template assertion and headless Cytoscape execution. 391/391 tests passing.
