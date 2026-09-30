# Code Review: Ticket 42 (Viewer: Client-Side PNML Export) — Round 02

**Commit:** [`690c539`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) (`refactor(viewer): resolve round 1 review findings for ticket 42`)  
**Diff:** `git diff 688a913...HEAD` (3 files changed, 207 insertions(+), 208 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/42-viewer-client-side-pnml-export.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/42-viewer-client-side-pnml-export.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** All 98 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Round 1 Verification & Documented Standards
**Status: PASS (0 Hard Violations).**
All documented standards violations and smells flagged in Round 1 were addressed:

1. **Domain Vocabulary (Client-Side Export, [`CONTEXT.md:27-30`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L27-L30)) → ✅ RESOLVED**
   - Canonical implementation and UI handler renamed to [`exportClientSidePnml`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1729).
   - DOM blob/anchor download logic isolated to helper `_triggerBlobDownload` ([`template.html:1707`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1707)).
   - Test renamed from `test_client_side_pnml_export_download_triggers_file_download_headless` to [`test_client_side_pnml_export_triggers_browser_export_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4964).

2. **Duplicated Code (XML Serializer in Prototype) → ✅ RESOLVED**
   - Changes to [`code2petri/viewer/prototype/pnml_exporter.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/pnml_exporter.js) were completely reverted, keeping [`template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) as the single production deliverable.

3. **Duplicated Code (Test XML Extraction Helper) → ✅ RESOLVED**
   - Extracted shared test helper [`_run_pnml_export_test(self, net_literal, test_logic)`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4752) in `tests/test_html_viewer.py`, eliminating duplicated regex search and XML parsing across all export tests.

4. **Middle Man (Alias Delegate) → ✅ RESOLVED**
   - `exportClientSidePnml` is the direct primary function. Legacy aliases (`exportPnml`, `downloadPnmlFile`) are preserved strictly for backward compatibility.

5. **Primitive Obsession (Ad-hoc Property Fallbacks) → ✅ RESOLVED**
   - Encapsulated node property resolution into structured helpers [`_resolvePlaceExportData`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1555) and [`_resolveTransitionExportData`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1566).

### (b) Baseline Code Smells in New Diff (Judgement Calls)

1. **Middle Man ([`template.html:1601-1609`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1601-L1609))**:
   ```javascript
   function _resolveNodeExportData(node, cy) {
     if (!node) return null;
     if (node.hasClass('place')) {
       return _resolvePlaceExportData(node);
     } else if (node.hasClass('transition')) {
       return _resolveTransitionExportData(node, cy);
     }
     return null;
   }
   ```
   - *Analysis*: In `serializeToPnml`, places and transitions are already partitioned into separate collections (`cy.nodes('.place')` and `cy.nodes('.transition')`). Routing both through `_resolveNodeExportData` adds an unnecessary dispatch layer.
   - *Recommendation (Non-blocking)*: Call `_resolvePlaceExportData(p)` and `_resolveTransitionExportData(t, cy)` directly from their respective iteration loops and prune the wrapper.

---

## Spec

### (a) Round 1 Verification & Acceptance Criteria
**Status: PASS (All Acceptance Criteria Satisfied).**

1. **P1 — Collapsed Compound Container Label on Export → ✅ RESOLVED**
   - [`_resolveTransitionExportData`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1566-L1588) checks whether a transition is inside a collapsed compound container (`isInsideCollapsedCompound`) and exports the container's visible label (`custom_name || collapsed_label || label`). Verified by new test [`test_client_side_pnml_export_collapsed_compound_container_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4926).

2. **P2 — Proprietary `<toolspecific>` XML Metadata Removed → ✅ RESOLVED**
   - In [`serializeToPnml`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1611-L1659), `includeTools` defaults to `false`. Export generates clean, standard PNML suitable for immediate import into external tools (e.g. ProM) without vendor extension bloat.

3. **P3 — Prototype File Scope Creep Reverted → ✅ RESOLVED**
   - All changes to `code2petri/viewer/prototype/pnml_exporter.js` were reverted to baseline.

4. **P4 — Unrenamed Component Label Fallback → ✅ RESOLVED**
   - [`_resolveTransitionExportData`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1578-L1585) now checks `custom_name` first, then the on-screen `label` (`c_XX`), before falling back to internal `raw_label`. Unrenamed components correctly export with the `c_XX` identifier shown on screen.

5. **Acceptance Criteria Coverage (6/6 Satisfied)**:
   - **AC1 (Toolbar Button):** Export button is visible in the viewer toolbar.
   - **AC2 (Download Trigger):** Clicking the button triggers a browser download of a `.pnml` file.
   - **AC3 (Faithful Canvas Reflection):** Places, transitions, arcs, and initial markings reflect live folds and current canvas state.
   - **AC4 (Renamed Components):** Renamed component nodes export with their user-assigned label rather than auto-generated IDs.
   - **AC5 (ProM Validity):** Exported XML conforms to standard PNML schema without unrequested vendor metadata.
   - **AC6 (Pure Client-Side):** Zero server roundtrips or Python dependencies required during export.

### (b) Behaviour in Diff Not Asked For (Scope Creep)
- **None.** Vendor metadata was removed from default export, and prototype scratch file modifications were completely eliminated.

### (c) Requirements Implemented Wrong
- **None.**

---

## Summary

- **Standards:** PASS (0 hard violations; domain vocabulary aligned to **Client-Side Export**, test helper extracted, prototype changes reverted, property resolution encapsulated). Only 1 minor non-blocking smell noted (`_resolveNodeExportData` middle man).
- **Spec:** PASS (All 6 acceptance criteria met; collapsed compound container labels exported correctly, standard PNML emitted by default, on-screen `c_XX` IDs preserved for unrenamed components, 98 tests pass).
