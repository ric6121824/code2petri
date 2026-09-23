# Code Review: Ticket 30 (Viewer: Nested Compound Nodes on Load) — Round 01

**Commit:** `562f81e` (`feat(viewer): render nested compound nodes on load (ticket 30)`)  
**Diff:** `git diff ded547d...HEAD` (4 files changed, 398 insertions(+), 29 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/30-viewer-nested-compound-nodes-on-load.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/30-viewer-nested-compound-nodes-on-load.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** 387 tests — **all pass**

---

## Standards

### (a) Documented Standards Violations
**None detected (Hard standard).**
- **Domain Vocabulary ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md))**: Conforms strictly to domain terminology (`Composite Net`, `Inline Expansion`). Avoids forbidden aliases (*merged graph*, *folder node*, *closed sub-graph*).
- **Compound Structure**: Preserves Dagre-based compound containment semantics in Cytoscape without violating bipartite net structures.

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Incomplete Helper Extraction & Runner Boilerplate** ([`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L37-L47))
   - While `_extract_template_net_to_elements()` was extracted, `test_net_to_elements_preserves_hierarchy_and_enclosing_function` (line 498) retains the duplicate regex extraction logic instead of using the new helper.
   - The Node.js execution harness (`subprocess.run(["node", "-e", ...])` + assert returncode == 0 and 'PASS' in stdout) is copy-pasted across `test_nested_compound_nodes_hierarchy_and_depth_classes` and `test_nested_compound_nodes_cytoscape_dagre_layout_no_overlap`.
   - **Actionable Fix:** Call `_extract_template_net_to_elements()` in line 498, and extract a reusable `_run_node_script(self, script: str) -> subprocess.CompletedProcess` helper method in `test_html_viewer.py`.

2. **Duplicated Code — CSS Style Rule Redundancy** ([`code2petri/viewer/template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L756-L766))
   - `node.compound.depth-0` duplicates `'background-color'`, `'border-color'`, `'color'`, and `'text-background-color'` already declared in the parent `node.compound, node:parent` rule.
   - **Actionable Fix:** Remove redundant declarations from `node.compound.depth-0`, retaining only `'padding': '28px'`.

3. **Duplicated Evaluation — Redundant Depth Calculation** ([`code2petri/viewer/template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L371-L373))
   - In `sortedCompounds.forEach(function(compound) { const depth = computeCompoundDepth(compound.id); ... })`, depths were already memoized in `compoundDepthMap` during topological sort.
   - **Actionable Fix:** Use `compoundDepthMap.get(compound.id) || 0` directly instead of re-entering `computeCompoundDepth`.

---

## Spec

### (a) Missing or Partial Requirements

1. **Visual Distinguishability for Deep Nesting ($\ge 4$ levels):**
   - *Spec Line 10:* `"- [x] Nested compound nodes (A containing B containing C) are visually distinguishable and do not overlap unintentionally"`
   - *Finding:* In [`code2petri/viewer/template.html:372`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L372), depth classes are clamped with `Math.min(depth, 3)`, and CSS only styles `depth-0` through `depth-3`. For hierarchies deeper than 3 levels (e.g. A $\to$ B $\to$ C $\to$ D $\to$ E), depths 3, 4, etc. share identical `#e65100` borders, backgrounds, and `18px` padding, losing visual boundary differentiation between deeply nested containers.
   - **Actionable Fix:** Add palette rotation or define additional depth levels (e.g., `depth-4`, `depth-5`) with distinct border styles/colors so deeper nesting maintains visual distinguishability.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Defensive Cycle Detection in Compound Depth Calculation:**
   - In [`code2petri/viewer/template.html:346-350`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L346-L350), `computeCompoundDepth` introduces visited-set tracking to handle cyclic compound parents.
   - *Assessment:* Approved harmless defensive logic. Backend composite assembly guarantees acyclic containment trees by construction, but client-side guard prevents infinite recursion.

### (c) Implementation Looks Wrong

1. **Fallback Label Degradation:**
   - *Spec Line 12:* `"- [x] Compound node headers display a readable function name"`
   - *Finding:* `const readableLabel = compound.label || (compound.function_name ? compound.function_name + '()' : compound.id);`. If both `label` and `function_name` are missing, it falls back to raw ID (`compound_foo_1`).
   - *Assessment:* Minor edge-case degradation; in standard backend pipelines `function_name` is always populated.

---

## Summary

- **Standards:** 0 hard violations, 3 minor baseline smells (duplicated helper/test runner boilerplate, redundant CSS in `depth-0`, unmemoized depth lookup). Worst issue: Duplicated Node test execution harness in `test_html_viewer.py`.
- **Spec:** All 4 acceptance criteria satisfied on standard 3-tier hierarchies; partial distinguishability for nesting depths $\ge 4$. 1 harmless defensive cycle detection addition. Worst issue: Shared styling for compound depth $\ge 3$.
