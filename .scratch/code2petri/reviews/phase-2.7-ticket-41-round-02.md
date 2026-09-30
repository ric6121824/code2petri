# Code Review: Ticket 41 (Viewer: Component Node Renaming via HUD) — Round 02

**Commit:** [`08d898a`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) (`refactor(viewer): resolve round 1 review findings for ticket 41`)  
**Diff:** `git diff 361c694...HEAD` (2 files changed, 233 insertions(+), 127 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/41-viewer-component-node-renaming-hud.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/41-viewer-component-node-renaming-hud.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 91 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Round 1 Verification & Documented Standards
**Status: PASS (0 Hard Violations).**
All documented standards violations and smells flagged in Round 1 were addressed:

1. **Vocabulary (CONTEXT.md, Component Node Renaming) → ✅ RESOLVED**
   - HUD title updated to `"Component Node Renaming"`, label field to `"Name:"`, and event handler renamed to [`applyComponentNodeRename`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1418).

2. **Duplicated Code (DOM Resolution) → ✅ RESOLVED**
   - Extracted [`_resolveHudElements()`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1404-L1416) in `template.html`, eliminating repetitive defensive DOM element queries across `openInspector`, `closeInspector`, and `applyComponentNodeRename`.

3. **Data Clumps (`rememberedCustomNames` Key Waterfall) → ✅ RESOLVED**
   - Replaced six-representation probe waterfall with canonical key factory [`_consumedSubnetKey(consumedSubnet)`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1740-L1761), applied consistently during opaque transition creation and name restoration.

4. **Speculative Generality (Lazy Map Initialization) → ✅ RESOLVED**
   - Initialized `this.rememberedCustomNames = new Map()` in the constructor body ([`template.html:1737`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1737)) and removed redundant lazy-initialization guards.

5. **Mysterious Name (`tKey` / `pKey`) → ✅ RESOLVED**
   - Replaced obscure keys with descriptive identifiers `consumedTransKey` and `consumedPlaceKey` within [`_consumedSubnetKey`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1751-L1756).

### (b) Baseline Code Smells in New Diff (Judgement Calls)

1. **Middle Man / Dead Code ([`template.html:1434`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1434))**:
   ```javascript
   const saveInspectorName = applyComponentNodeRename;
   ```
   - *Analysis*: `saveInspectorName` was retained as an alias for backwards compatibility during refactoring. No internal callers or test scripts reference this identifier. It preserves the deprecated "inspector" naming.
   - *Recommendation (Non-blocking)*: Remove the unused alias definition.

---

## Spec

### (a) Round 1 Verification & Acceptance Criteria
**Status: PASS (All Acceptance Criteria Satisfied).**

1. **P1 — Line Number Calculation on Folded Components → ✅ RESOLVED**
   - Opaque component creation now calculates `source_line` across consumed nodes ([`template.html:1822-1845`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1822-L1845)) as scalar or range (`min–max`), properly displaying in the HUD stat pill. Verified in [`test_hud_stat_pills_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4346-L4351).

2. **P2 — Auto-Save on Blur Reverted → ✅ RESOLVED**
   - Removed `change` listener. Commits only occur via explicit Save button click or Enter key. Dismissing the HUD by clicking the canvas background restores the input value and discards uncommitted drafts ([`template.html:1488-1490`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1488-L1490)). Verified in [`test_hud_closes_when_clicking_canvas_background_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4459-L4478).

3. **P3 — Engine Method Overloading Reverted → ✅ RESOLVED**
   - Removed string ID overloading from [`canSinglePlaceContract`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2288) and [`executeSinglePlaceContraction`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2370). Call sites pass node element references.

4. **P4 — Canvas Background Dismissal Scoped → ✅ RESOLVED**
   - Guarded HUD dismissal in `tap` handler with `evt.target === cy` ([`template.html:4043`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L4043)). Tapping uncontractible place nodes no longer closes the HUD. Verified in [`test_hud_closes_when_clicking_canvas_background_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4462-L4466).

5. **P5 — False-Positive Key Collision Across Adjacent Folds → ✅ RESOLVED**
   - Canonical [`_consumedSubnetKey`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1740) scopes identities with fold-type prefixes and boundary IDs (`place::${consumedPlaceId}`, `choice::...`). Verified by new test [`test_renaming_one_component_does_not_affect_adjacent_fold_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4559).

6. **Acceptance Criteria Coverage (6/6 Satisfied)**:
   - **AC1 (Open HUD on Click):** Left-clicking a transition or component opens the floating HUD popover near the node.
   - **AC2 (Stat Pills):** Displays tau weight, component type, and source line number as compact pills.
   - **AC3 (Pre-filled Editable Field):** Pre-fills input with node's current label.
   - **AC4 (Immediate Update):** Saving immediately renames node on canvas.
   - **AC5 (Click-Away Dismissal):** Closes when clicking canvas background and discards draft edits.
   - **AC6 (Persistence Across Unfold/Re-fold):** Custom label persists through unfold and subsequent re-fold cycles.

### (b) Requirements Implemented but Look Wrong (Edge Case)

1. **Nested Component Line Range Propagation ([`template.html:1831-1836`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1831-L1836))**:
   ```javascript
   const line = Number(rawLine);
   if (!isNaN(line) && line > 0) { ... }
   ```
   - When folding a region containing an already-folded component with a range string (e.g. `'42–50'`), `Number('42–50')` evaluates to `NaN`. As a result, line numbers from nested components are skipped when calculating the outer component's line range.
   - **Recommendation (Non-blocking)**: Split `rawLine` on `/[–-]/` and parse individual numeric bounds so nested ranges propagate upward to parent folds.

### (c) Behaviour in Diff Not Asked For (Scope Creep)
- **None.** Commit `08d898a` exclusively addresses Round 1 findings and tightens scope.

---

## Summary

- **Standards:** 0 hard violations; all 5 Round 1 findings resolved (`Component Node Renaming` vocabulary, `_resolveHudElements` helper, canonical `_consumedSubnetKey` factory, constructor map initialization, descriptive key names). Only 1 non-blocking judgement call noted (`saveInspectorName` dead alias).
- **Spec:** All 6 acceptance criteria verified and satisfied; all 5 Round 1 defects/scope creep resolved (computed line numbers, explicit save semantics, API signature restored, background-only dismissal, adjacent fold isolation test passing).
