# Ticket 21: Code Review (Round 2)

**Diff:** `e9ed5cf...HEAD`  
**Commits:** `a47a0da`, `80d39bd`, `e49c009`  
**Spec:** `.scratch/code2petri/issues/21-html-viewer-and-validation.md`

## Standards
**STATUS: PASS**

### Documented Standards Violations (Hard Violations)
* **None (0 violations).** The diff adheres strictly to [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md):
  - Strictly adheres to domain vocabulary (**Composite Net**, **Opaque Transition**, **Inline Expansion**, **Walker Protocol**, **Resolution Context**).
  - No occurrences of forbidden terms (*"merged graph"*, *"global net"*, *"black box"*, *"leaf transition"*, *"unrolling"*) in project source or test files.

### Baseline Code Smells (Judgement Calls)
1. **Round 1 Smells Successfully Addressed:**
   * **Middle Man:** `to_html()` methods were removed from [`code2petri/model.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py) and [`code2petri/fold.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py). [`code2petri/engine.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py) dispatches directly to `generate_html`.
   * **Feature Envy:** [`code2petri/viewer/__init__.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L67-L77) now calls `net_or_fold.to_dict()` and unpacks `**fold_dict` rather than re-extracting internal attributes.
   * **Mysterious Name:** `target: Any` was renamed to `net_or_fold: Union[PetriNet, FoldResult, Any]` in [`code2petri/viewer/__init__.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L54).
   * **Duplicated Code:** Extracted `_extract_embedded_data()` helper in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L13-L22).

2. **Remaining Minor Code Smell:**
   * **Duplicated Code (Minor Test Duplication):**
     * **Location:** [`tests/test_game_of_life_validation.py:250-254, 278-282`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_game_of_life_validation.py#L250-L282)
     * **Hunk:**
       ```python
       match = re.search(r'<script id="code2petri-data" type="application/json">\s*(\{.*?\})\s*</script>', content, re.DOTALL)
       self.assertIsNotNone(match)
       data = json.loads(match.group(1))
       ```
     * **Analysis:** Regex extraction and parsing of embedded JSON is repeated in `test_game_of_life_validation.py` instead of importing `_extract_embedded_data` from `test_html_viewer.py` or `tests/petri_assertions.py`. (Judgement call / advisory only).

---

## Spec
**STATUS: PASS**

### Verification of Round 1 Findings:
1. **Critical Blocker (Vendor JS Missing in Git): RESOLVED**
   * `.gitignore` was updated with `!code2petri/viewer/vendor/` and `!code2petri/viewer/vendor/**`.
   * All vendor libraries (`cytoscape.min.js`, `dagre.min.js`, `cytoscape-dagre.js`) are tracked in git. The generator succeeds offline without internet access on fresh clones.
2. **Initial Step SM Score Display: RESOLVED**
   * [`code2petri/viewer/template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L552-L572) computes `initialSm` by summing the $\tau$ weights of transitions in `initialNet`. At Step 0, `valSm` reflects `initialSm.toFixed(1)` rather than abruptly jumping from `0.0`.
3. **Visual Tau Badge: RESOLVED**
   * Rendered as an SVG data-URI badge assigned to `badge_svg` and styled via Cytoscape `background-image` on `.opaque[badge_svg]`. Text string concatenation `(τ=...)` was removed.
4. **GameOfLife CLI Validation: RESOLVED**
   * [`tests/test_game_of_life_validation.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_game_of_life_validation.py#L232-L288) invokes `main([...])` directly, verifying CLI flags (`--context`, `--fold`, `--inline`, `-o`) and HTML file emission end-to-end.
5. **Scope Creep Pruned: RESOLVED**
   * Unrequested `#node-details` panel, zoom/fit toolbar buttons, and global keyboard event listeners were removed.

### (a) Requirements Missing or Partial
* **None.** All 16 checklist requirements from `.scratch/code2petri/issues/21-html-viewer-and-validation.md` are fully satisfied.

### (b) Behaviour in Diff Not Asked For (Scope Creep)
* **None.** All previously identified unrequested UI elements and model shims have been pruned.

### (c) Implemented but Implementation Looks Wrong (Advisories)
* **None.** Live SM score, fold/unfold/reset playback, Dagre layouts, and CLI pipelines function as specified.

---

## Summary
- **Standards Axis:** 0 hard violations, 1 minor baseline smell (duplicated test helper across test files). **STATUS: PASS**
- **Spec Axis:** 0 missing requirements, 0 scope creep, 0 incorrect implementations. **STATUS: PASS**
