# Code Review: Ticket 31 (Viewer: Input Remapping) — Round 01

**Commit:** `ec34ee5` (`feat(viewer): remap input and add inspector panel (ticket 31)`)  
**Diff:** `git diff 562f81e...HEAD` (6 files changed, 806 insertions(+), 30 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/31-viewer-input-remapping.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/31-viewer-input-remapping.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** 391 tests — **all pass**

---

## Standards

### (a) Documented Standards Violations
**None detected (Hard standard: 0 violations).**
- **Domain Vocabulary ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md))**: Conforms strictly to domain terminology (`Transition`, `Place`, `Opaque Transition`, and `Transition Weight (tau)`). Avoids prohibited aliases (*black box*, *leaf transition*, *firing cost*, *folder node*, *merged graph*).
- **Graph Invariants**: Place nodes remain purely structural; left-clicking does not trigger viewport panning or false inspector activations.

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Test Harness & DOM Mocking** ([`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L834-L938))
   - Identical regex extraction for inspector/tap handlers, DOM element mocking (`inspectorPanel`, `inspectorLabel`, etc.), and Node.js Cytoscape harness initialization is copy-pasted verbatim between `test_place_left_click_does_not_pan_or_inspect_headless` and `test_transition_and_component_left_click_opens_inspector_headless`.
   - **Actionable Fix:** Extract a shared helper method `_setup_inspector_node_harness(node_script_body: str) -> str` in `test_html_viewer.py` to encapsulate DOM mocking and Cytoscape instance creation.

2. **Repeated Switches / Inconsistent Type Cascades** ([`code2petri/viewer/template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1067-L1085, L1148-L1158))
   - Node classification (Place vs Transition vs Compound) is checked across `mouseover`, `tap`, and `getInspectorData` using slightly differing fallback combinations:
     - `getInspectorData`: `node.hasClass('compound') || node.data('is_compound') === true`
     - `tap`: `targetNode.hasClass('transition') || targetNode.data('type') === 'Transition' || targetNode.data('type') === 'Opaque Transition'`
   - **Actionable Fix:** Standardize element classification via small helper predicates (e.g. `function isPlace(n)`, `function isTransition(n)`, `function isCompound(n)`) in `template.html` to eliminate redundant cascading checks.

---

## Spec

### (a) Missing or Partial Requirements
**None.** All 5 acceptance criteria are fully met and verified by automated unit and headless tests:
1. **Right Mouse Drag Pan**: Dragging with button 2 updates `cy.pan()` by delta coordinates.
2. **Middle Mouse Drag Pan**: Dragging with button 1 updates `cy.pan()` by delta coordinates.
3. **Place Tap Invariance**: Left-clicking place nodes returns immediately without panning, zooming, or opening the inspector.
4. **Transition / Component Node Inspection**: Left-clicking opens the `#inspector-panel` displaying `label`, `tau` weight, `component_type`, and `line_number`.
5. **Scroll Wheel Zoom**: Zooming continues to scale centered at cursor coordinates.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Inspector Dismissal Mechanics:**
   - In [`code2petri/viewer/template.html:1120-1132`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1120-L1132), an explicit close button (`#inspector-close`) and background canvas click listener (`evt.target === cy`) were added to hide the panel.
   - *Assessment:* Approved standard UI usability enhancement; prevents the inspector card from permanently occluding graph elements.

2. **Hover Cursor Pointer on Transitions & Compounds:**
   - `cy.on('mouseover', 'node', ...)` sets `cursor = 'pointer'` on all inspectable transition and compound nodes.
   - *Assessment:* Approved usability feedback indicating interactive nodes.

### (c) Implementation Looks Wrong

1. **Coupled Expand/Collapse and Inspector Trigger in Single-Function Mode:**
   - *Spec Line 3:* `"Left-clicking a transition or component node opens an inspector panel showing that node's static metadata."`
   - *Finding:* In legacy single-function mode (where `composite_preassembled` is false), left-clicking a resolved call transition triggers both `openInspector(targetNode)` and in-place expansion/collapse (`renderStep()`). In composite mode (Ticket 29+), `composite_preassembled === true` guards against topology mutation, so only inspection occurs.
   - *Assessment:* Minor legacy artifact; does not affect composite mode.

---

## Summary

- **Standards:** 0 hard violations, 2 baseline smells (duplicated test harness fixture in `test_html_viewer.py`, inconsistent node type check cascades in `template.html`). Worst issue: Duplicated DOM mocking harness in headless tests.
- **Spec:** All 5 acceptance criteria satisfied and verified. 2 approved UI usability additions (inspector dismissal and hover cursor pointer). 0 defects.
