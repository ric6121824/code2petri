# Code Review: Ticket 39 (Viewer: Collapsed Compound State) — Round 01

**Commit:** [`6a29124`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/39-viewer-collapsed-compound-state.md) (`feat(viewer): implement collapsed compound container state (ticket 39)`)  
**Diff:** `git diff f053f82...HEAD` (3 files changed, 482 insertions(+), 14 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/39-viewer-collapsed-compound-state.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/39-viewer-collapsed-compound-state.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 75 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)
- **None.** The diff adheres strictly to [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md):
  - Consistently uses the ubiquitous domain term `Collapsed Compound State` ([`CONTEXT.md:83-86`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L83-L86)) across implementation and tests, avoiding prohibited terms ("folder node", "closed sub-graph").

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code — Function Name Sanitization ([`code2petri/viewer/template.html:1633-1640`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1633-L1640) & [`lines 1709-1714`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1709-L1714))**:
   - The logic stripping `()` suffixes, prefixing fallback labels, and sanitizing `compound_` prefixes (`String(fnName).replace(/\(\)$/, '').trim().replace(/^compound_/, '')`) is duplicated between `_updateCollapsedCompoundStates` and `renameNode`.
   - **Actionable Fix:** Extract a shared helper `_getCompoundFunctionName(compoundNode)` on `LiveFoldReductionEngine`.

2. **Duplicated Code — Collapsed Status Payload Injection ([`code2petri/viewer/template.html:1977, 2426, 2556, 3098`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1977))**:
   - The 4-line block computing `isCompoundCollapsed` and injecting it into both `consumedSubnet` and the return payload is copy-pasted across `executeSequenceFold`, `executeWhileFold`, `executeChoiceFold`, and `executeStructuralCandidate`.
   - **Actionable Fix:** Extract a helper method that decorates the fold return payload and step record.

3. **Feature Envy / Message Chains — Cytoscape Traversal in Inspector Formatting ([`code2petri/viewer/template.html:1269-1277`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1269-L1277))**:
   - `getInspectorData(node)` reaches directly into `node.cy().getElementById(...)` to retrieve the child node's `tau` when inspecting a collapsed compound.
   - **Actionable Fix:** Cache or store `tau` directly on `compoundNode.data('tau')` during `_updateCollapsedCompoundStates` so inspector reads remain local.

4. **Speculative Generality — Dead State & Unused Parameters ([`code2petri/viewer/template.html:1521, 1614`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1521))**:
   - `this.history = [];` is initialized in the constructor but never referenced. Additionally, `_updateCollapsedCompoundStates(specificParentId = null)` declares a parameter never supplied by any caller.
   - **Actionable Fix:** Remove `this.history` (which also contradicts the non-linear undo architecture) and remove unused parameters.

---

## Spec

### (a) Missing or Partial Requirements

1. **Focus and Inspector Transition to Collapsed Container**:
   - *Spec Line 9:* `"- [x] When all internal nodes of an inlined function compound node are reduced to a single component, the container transitions to the Collapsed Compound State automatically"`
   - *Finding:* In [`code2petri/viewer/template.html:3326-3335`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L3326-L3335), when the final internal fold reduces a compound into a collapsed state, selection focus and inspector opening target `res.node` (the child component with `opacity: 0`, `pointer-events: none`, and label `""`), rather than the parent compound container that now represents the function.
   - **Actionable Fix:** In `handleFoldReduction`, if `res.isCompoundCollapsed`, re-target selection and inspector trigger to `cy.getElementById(parentId)`.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Global State Array Initialization**:
   - `this.history = [];` added in [`code2petri/viewer/template.html:1521`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1521).
   - *Spec Finding:* Explicitly contradicts [`specs/phase-2.7-live-fold-reduction.md:42`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md#L42): *"Graph mutations in JS will not use a global state array."*
   - **Actionable Fix:** Delete `this.history = [];`.

2. **Forward Implementation of Renaming API**:
   - `renameNode(nodeOrId, newName)` added to `LiveFoldReductionEngine`.
   - *Spec Finding:* Component node renaming belongs to Ticket 41. While benign, ensure it does not conflict with incoming Ticket 40 (Component-Local Unfold).

### (c) Requirements Implemented but Look Wrong

1. **Label Mutation Cascade on Missing `function_name`**:
   - *Spec Line 10:* `"- [x] The collapsed container displays the label function_name (c_XX) where c_XX is the component identifier"`
   - *Finding:* In `_updateCollapsedCompoundStates` ([`code2petri/viewer/template.html:1634`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1634)), if `function_name` is missing, `fnName` falls back to `compoundNode.data('label')`. Because `data('label')` is mutated to `${fnName} (${opaqueId})`, subsequent periodic calls from `updateFoldableHighlights()` re-read the already-collapsed label, appending `(c_XX)` repeatedly on each call (e.g. `func (c_01) (c_01)`).
   - **Actionable Fix:** Fall back to `compoundNode.data('original_label')` before `data('label')`.

2. **Highlight Updates Clobber Renamed Labels**:
   - *Spec Line 10:* `"- [x] The collapsed container displays the label function_name (c_XX) where c_XX is the component identifier"`
   - *Finding:* `_updateCollapsedCompoundStates()` unconditionally recalculates `${fnName} (${opaqueId})` using `onlyChild.id()`. If a user or test renamed `c_01` (stored in `onlyChild.data('custom_name')`), the next canvas highlight update or fold event overwrites the container label back to `c_01`.
   - **Actionable Fix:** Read `onlyChild.data('custom_name') || onlyChild.data('label') || onlyChild.id()` when constructing the collapsed label.

3. **Child Un-Hiding Guarded Strictly by `children.length > 1`**:
   - *Spec Line 11:* `"- [x] The internal nodes are hidden, leaving only the closed container visible on the canvas"`
   - *Finding:* In [`code2petri/viewer/template.html:1675-1688`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1675-L1688), removing `.collapsed-child` and restoring `label` is guarded by `if (children.length > 1)`. If an uncollapse or net mutation leaves exactly 1 non-opaque child, the child remains hidden with `opacity: 0` and empty label.
   - **Actionable Fix:** Restore any child with `collapsed-child` whenever `isCollapsed` is false, regardless of child count.

---

## Summary

- **Standards (4 findings):** 0 hard standard violations; 4 baseline smells (duplicated function name sanitization, duplicated collapsed status injection, feature envy in inspector tau retrieval, speculative generality in dead `this.history` state). Worst issue: Duplicated collapsed status payload injection across fold methods.
- **Spec (6 findings):** 1 partial requirement (selection/inspector focus remains on hidden child instead of collapsed container), 2 scope creep issues (`this.history` global array, forward-implemented `renameNode`), 3 incorrect implementations (label mutation recursion on missing `function_name`, clobbering renamed labels during highlight refreshes, un-hiding guarded strictly by `children.length > 1`). Worst issue: Highlight updates clobbering custom component names and mutating labels recursively.
