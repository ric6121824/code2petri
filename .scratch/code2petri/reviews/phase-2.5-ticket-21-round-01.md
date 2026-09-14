# Ticket 21: Code Review (Round 1)

**Diff:** `e9ed5cf...HEAD`  
**Commits:** `a47a0da`, `80d39bd`  
**Spec:** `.scratch/code2petri/issues/21-html-viewer-and-validation.md`

## Standards
**STATUS: PASS**

### Documented Standards Violations (Hard Violations)
* **None (0 violations).** The diff adheres strictly to [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md):
  - Properly uses **Composite Net** in [`test_game_of_life_validation.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_game_of_life_validation.py#L258) without using avoided terms ("merged graph", "global net").
  - Explicitly labels collapsed transitions as **Opaque Transition** in [`template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L397) (avoiding "black box", "leaf transition").
  - Conforms to Walker Protocol and Resolution Context guidelines.

### Baseline Code Smells (Judgement Calls)
1. **Middle Man**
   * **Location:** [`code2petri/model.py:456-460`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L456-L460) and [`code2petri/fold.py:176-180`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/fold.py#L176-L180)
   * **Finding:** Both `PetriNet.to_html` and `FoldResult.to_html` merely lazy-import and delegate onward to `generate_html`.
   * **Suggestion:** While this provides a uniform interface for `TEXT_SERIALIZERS["html"](target)`, `TEXT_SERIALIZERS["html"]` could directly call `generate_html(target)` without needing the delegating middleman methods.
2. **Feature Envy & Duplicated Code**
   * **Location:** [`code2petri/viewer/__init__.py:67-79`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L67-L79)
   * **Finding:** `generate_html` manually re-extracts properties already serialized by `FoldResult.to_dict()` (`fold.py:L157-163`), reaching into `target`'s internal properties rather than utilizing `target.to_dict()`.
   * **Suggestion:** Use `target.to_dict()` or reuse existing serialization methods.
3. **Duplicated Code**
   * **Location:** [`tests/test_html_viewer.py:63-65, 75-77`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L63-L77)
   * **Finding:** Identical regex extraction and JSON parsing logic (`re.search(r'<script id="code2petri-data"...')`) recurs across test methods.
   * **Suggestion:** Extract a helper method `_extract_embedded_data(html_content)`.
4. **Mysterious Name**
   * **Location:** [`code2petri/viewer/__init__.py:53`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L53) and [`code2petri/engine.py:241`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L241)
   * **Finding:** Parameter named `target: Any`. In `code2petri`, "target" typically designates `target_function`.
   * **Suggestion:** Type as `target: Union[PetriNet, FoldResult]` to clarify domain semantics.

---

## Spec
**STATUS: FAIL**

### (a) Missing or Partial Requirements
1. **Vendor Libraries Omitted by Git (CRITICAL BLOCKER):**
   * **Spec Line 20:** `"- [x] An HTML template exists that inlines minified Cytoscape.js and Dagre layout plugin source."`
   * **Spec Line 24:** `"- [x] The generated HTML file contains zero external resource references (no CDN links, no external CSS/JS files)."`
   * **Finding:** While `code2petri/viewer/vendor/` exists in your working directory, line 11 of `.gitignore` (`vendor`) ignores that directory. As a result, `cytoscape.min.js`, `dagre.min.js`, and `cytoscape-dagre.js` were **not committed** to git in commit `a47a0da`. On any clean clone or CI checkout, running HTML output will immediately crash with `FileNotFoundError: Missing required vendor library: .../dagre.min.js`.
   * **Fix:** Add an exception to `.gitignore` (e.g. `!code2petri/viewer/vendor/` or `!code2petri/viewer/vendor/*.js`) and `git add code2petri/viewer/vendor/`.
2. **Visual Tau Badge Rendered as Label Text:**
   * **Spec Line 26:** `"- [x] Dummy transitions are visually distinct (different border style or shape) and display their accumulated $\tau$ weight as a badge."`
   * **Finding:** The $\tau$ weight is concatenated onto the node's label string (`" (τ=" + tauStr + ")"`), rather than rendered as a visual badge element.

### (b) Behaviour in the Diff Not Asked For (Scope Creep)
1. **Interactive Node Inspector, Fit/Zoom Buttons & Keyboard Shortcuts:**
   * **Spec Line 10:** `"- **--no-fold mode**: Produces a static interactive HTML view (pan/zoom, no fold controls)."`
   * **Finding:** The viewer adds an unrequested metadata inspector panel (`#node-details`), Fit/Zoom toolbar buttons (`#btn-fit`, `#btn-zoom-in`, `#btn-zoom-out`), and keyboard listeners (`ArrowLeft`, `ArrowRight`, `Escape`). (Note: These are helpful visual enhancements, but technically scope creep).
2. **Direct `.to_html()` Methods on Model Classes:**
   * **Spec Line 21:** `"- [x] A Python generator function accepts a FoldResult (or raw PetriNet for --no-fold) and produces a complete HTML string with the data blocks and library source embedded."`
   * **Finding:** Beyond `generate_html()`, `.to_html()` serialization methods were added directly to `PetriNet` and `FoldResult`.

### (c) Implemented but Implementation Looks Wrong (Advisories)
1. **Initial Step SM Score Display:**
   * **Spec Line 8:** `"- **Live SM score**: Displays the current accumulated SM score, updating with each fold/unfold."`
   * **Finding:** In [`template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L588), the viewer hardcodes `valSm.textContent = '0.0'` when `currentStep === 0`. However, the initial net contains non-zero transition weights ($\tau \ge 1.0$), so jumping to Step 1 abruptly changes the score from `0.0` to the actual initial sum.
2. **GameOfLife CLI Requirements Tested via Python API:**
   * **Spec Line 33:** `"- [x] GameOfLife validation: code2petri app.js -t stepCpu --fold -o net.html with --context <game_of_life_dir> produces a valid HTML file..."`
   * **Finding:** In [`tests/test_game_of_life_validation.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_game_of_life_validation.py#L236), the tests invoke the Python function `code2petri(...)` directly rather than invoking CLI `main()`, leaving the CLI argument parsing with `--context` and `-o .html` unverified for this test case.

---

## Summary
- **Standards Axis:** 0 hard violations, 4 baseline smells (worst: Feature Envy & duplication in [`code2petri/viewer/__init__.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L67-L79)). **STATUS: PASS**
- **Spec Axis:** 2 partial requirements (CRITICAL: vendor JS ignored by `.gitignore`), 2 scope creep, 2 advisories. **STATUS: FAIL**
