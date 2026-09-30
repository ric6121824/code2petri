# Code Review — Ticket 42, Round 01

**Commit:** [`90f7f35`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) (`feat(viewer): implement client-side PNML export (ticket 42)`) + [`688a913`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/42-viewer-client-side-pnml-export.md)  
**Diff:** `git diff 08d898a...HEAD` (4 files changed, 680 insertions(+), 51 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/42-viewer-client-side-pnml-export.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/42-viewer-client-side-pnml-export.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Tests:** All 97 tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass.

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

**S1 — Domain Vocabulary: `downloadPnmlFile` vs Client-Side Export ([`CONTEXT.md:27-30`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L27-L30))**
`CONTEXT.md` explicitly specifies **Client-Side Export** and lists *Avoid: Browser download, frontend save*.
The implementation inverts this domain model: `downloadPnmlFile` is the primary function name in [`template.html:1693`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1693) and [`prototype/pnml_exporter.js:151`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/pnml_exporter.js#L151), while `exportPnml` is relegated to a secondary alias. The test method [`test_client_side_pnml_export_download_triggers_file_download_headless`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4872) also uses the avoided phrase.

> **Fix:** Invert the relationship: name the primary function `exportClientSidePnml` or `exportPnml`. Relegate the browser trigger logic to an internal helper such as `_triggerBlobDownload(blob, filename)`. Align test method names to use "Client-Side Export" rather than "file download".

### (b) Baseline Code Smells (Judgement Calls)

**S2 — Duplicated Code: XML Serialization between `template.html` and `prototype/pnml_exporter.js`**
Over 100 lines of XML generation logic (`escapeXml`, `serializeToPnml`, and blob/anchor download logic) are duplicated almost verbatim between [`template.html:1545-1725`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1545-L1725) and [`code2petri/viewer/prototype/pnml_exporter.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/pnml_exporter.js).

> **Fix:** Treat `template.html` as the single production deliverable. If `prototype/pnml_exporter.js` is an obsolete prototype scratch file, remove or archive it rather than maintaining two diverging copies of the serializer.

**S3 — Duplicated Code: Test harness XML extraction in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py)**
The regex extraction and XML parsing sequence (`re.search(r'___XML_START___(.*?)___XML_END___', proc.stdout, re.DOTALL)` followed by `ET.fromstring`) is duplicated across 4 test methods (`test_client_side_pnml_export_*`).

> **Fix:** Extract a shared test helper `_run_pnml_export_test(self, net_literal, test_logic)` in `tests/test_html_viewer.py` returning `(root, xml_content, proc)`.

**S4 — Middle Man: `const exportPnml = downloadPnmlFile;`**
[`template.html:1724`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1724) and [`pnml_exporter.js:173`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/pnml_exporter.js#L173) define `exportPnml` solely as a delegate pointing to `downloadPnmlFile`.

> **Fix:** Make `exportPnml` the direct implementation and remove the alias delegate.

**S5 — Primitive Obsession: Ad-hoc property fallback cascades**
[`template.html:1592-1615`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1592-L1615) and [`pnml_exporter.js:62-90`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/pnml_exporter.js#L62-L90) cascade across multiple loosely-typed property fallbacks (`custom_name`, `raw_label`, `label`, `original_label`, `source_line`, `line_number`, `parent`, `enclosing_function`).

> **Fix:** Encapsulate node property resolution into a helper `_resolveNodeExportData(node)` to cleanly isolate export data mappings.

---

## Spec

### (a) Missing or Partial Requirements

**P1 — Collapsed Compound Container label not reflected on export**
> Spec: *"The exported file reflects the graph exactly as it appears on screen — including any folds the user has applied and any component nodes they have renamed"*

When an inlined function is fully folded into a Collapsed Compound State, the canvas displays `function_name (c_XX)` on the closed container tile. In `serializeToPnml` ([`template.html:1588`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1588)), compound containers are filtered out (`!t.hasClass('compound')`). As a result, the exported transition represents only the internal child node with sub-step labels rather than reflecting the collapsed function folder label visible on screen.

> **Fix:** When exporting a transition belonging to a collapsed compound container (`isCollapsedChild(t)`), resolve its exported label to match the container's visible label (`compound.data('label')` or `compound.data('custom_name')`).

### (b) Scope Creep

**P2 — Proprietary `<toolspecific tool="code2petri">` XML metadata**
> Spec: *"The exported PNML contains the places, transitions, arcs, and initial token markings of the graph as currently displayed"*

[`template.html:1622–1642`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1622-L1642) generates proprietary `<toolspecific tool="code2petri" version="1.0">` blocks for transitions (`tau`, `omega`, `component_type`, `line_number`, `enclosing_function`, `<resolved>`, `<unresolved/>`). While mirroring the Python backend, this was not requested in ticket 42 or the master spec.

> **Fix:** Keep `<toolspecific>` metadata minimal or optional so external tools (such as ProM) receive standard PNML elements without unrequested vendor extensions.

**P3 — Unused `prototype/pnml_exporter.js` modified in ticket scope**
Redundant modifications to `code2petri/viewer/prototype/pnml_exporter.js` were included in the commit, but this file is unused by the production viewer runtime.

> **Fix:** Remove prototype changes from the ticket diff so modifications remain strictly focused on `code2petri/viewer/template.html`.

### (c) Requirements Implemented but Look Wrong

**P4 — `raw_label` evaluated before `label` causes unrenamed components to export internal expression instead of visible `c_XX`**
> Spec: *"Component nodes that have been renamed export with the user-assigned label, not the auto-generated c_XX ID"* and *"The exported file reflects the graph exactly as it appears on screen"*

In `serializeToPnml` ([`template.html:1592-1596`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1592-L1596)):
```javascript
let label = t.data('custom_name') || t.data('raw_label');
if (!label) {
  const rawDataLabel = t.data('label');
```
For an **unrenamed** component node, `t.data('raw_label')` contains the composite sequence/choice expression (e.g., `"StepAlpha ; StepBeta"`), whereas `t.data('label')` holds the auto-generated ID (e.g., `"c_01"`) visible on screen. Because `raw_label` is evaluated before `label`, unrenamed components export as their internal synthetic expression rather than the auto-generated `c_XX` ID shown on screen.

> **Fix:** Check `custom_name` first, then the on-screen `label`, only falling back to `raw_label` or `id`:
```javascript
let label = t.data('custom_name') || t.data('label') || t.data('raw_label') || tId;
```

---

## Summary

**Standards:** 5 findings — 1 hard violation (vocabulary drift: `downloadPnmlFile` vs CONTEXT.md `Client-Side Export`); 4 judgement calls (code duplicated between `template.html` and prototype exporter, test XML extraction duplication, middle man delegate alias, primitive property cascade). Worst: S1 (vocabulary inversion of canonical domain concept).

**Spec:** 4 findings — 1 partial requirement (collapsed compound folder label not exported); 2 scope creep (proprietary `<toolspecific>` metadata, prototype file edits); 1 requirement implemented wrong (unrenamed components export internal composite expression instead of on-screen `c_XX` ID). Worst: P4 (unrenamed components deviate from on-screen representation).
