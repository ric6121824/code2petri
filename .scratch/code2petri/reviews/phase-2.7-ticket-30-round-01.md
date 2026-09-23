# Code Review: Ticket 30 — Viewer: Nested Compound Nodes on Load (Round 01)

## Standards
* **Documented Standards Violations:** None detected (0 hard violations). Evaluated against `CONTEXT.md`.
* **Baseline Smells Addressed:**
  1. *Duplicated Code:* Extracted shared `_extract_template_net_to_elements()` helper in `tests/test_html_viewer.py` and consolidated `DAGRE_LAYOUT_OPTIONS` in `template.html`.
  2. *Mysterious Name:* Renamed `cId`, `c`, `d`, `x` in `computeCompoundDepth` to descriptive names (`compoundId`, `compound`, `depth`, `candidate`).
  3. *Primitive Obsession / Inverted Padding:* Replaced modulo arithmetic `depth % 4` with clamped `Math.min(depth, 3)` to ensure monotonic decreasing padding and prevent depth 4+ wrapping back to the root padding.
  4. *Speculative Generality:* Replaced empty `try { cy.fit(null, 30); } catch(e) {}` with clean check `if (cy.elements().length > 0) cy.fit(null, 30);`.

## Spec
* **Requirements Coverage:**
  - Distinct named containers for each inlined function on first load: Verified.
  - Visually distinguishable nested compound nodes without overlap: Verified via Cytoscape Dagre bounding box containment (`c_leaf` $\subset$ `c_middle` $\subset$ `c_outer`) and leaf node Euclidean distance checks.
  - Automatic layout without requiring user interaction: Verified.
  - Readable compound node headers displaying function name (`fn()`): Verified.
* **Review Adjustments:**
  - Cycle recursion safety in `computeCompoundDepth(compoundId, visited)` prevents infinite call stack errors on cyclic parent references.
  - Maintained compound cursor pointer selector (`node.transition.resolved, node.compound`) per existing interactive mode behavior.

## Summary
- **Standards:** 0 hard violations, 4 smells identified and resolved.
- **Spec:** All acceptance criteria satisfied and verified.
