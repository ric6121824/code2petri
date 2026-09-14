# Ticket 20: Code Review (Round 1)

**Diff:** `43e6e87...HEAD`  
**Commit:** `107ceb2`  
**Spec:** `.scratch/code2petri/issues/20-cli-integration-fold-inline.md`

## Standards Axis Findings & Suggestions
**STATUS: FAIL**

### Documented Standards Violations (Hard Violations)

**1. `CONTEXT.md` (Opaque Transition)**
* **Location:** `code2petri/model.py` and `code2petri/fold.py` 
* **Violation:** The diff introduces `"dummy": True` and `is_dummy` to represent folded nodes. Even though the spec explicitly asked for "dummy", the documented repo vocabulary (`CONTEXT.md`) overrides the spec text. The domain concept must be an **Opaque Transition**. 
* **Suggestion:** Replace `is_dummy` with `is_opaque`, and stick to `"opaque": True` in metadata.

### Baseline Smells (Judgement Calls)

**1. Duplicated Code**
* **Location:** `code2petri/engine.py`
* **Finding:** The output file extension `ext` is already parsed and validated at the top of the function, but it is parsed a second time further down using `os.path.splitext(output_file)[1]`.
* **Suggestion:** Reuse the `ext` variable defined at the top.

**2. Feature Envy & Duplicated Code**
* **Location:** `code2petri/engine.py`
* **Finding:** The engine reaches deeply into `fold_result` to unpack `penultimate_net` and `final_sm`, manually assembling the DOT title string in two different serialization branches (for text output and file output).
* **Suggestion:** `FoldResult` should encapsulate this by exposing its own serialization method (e.g. `to_dot()` or a `get_display_net()` helper).

**3. Primitive Obsession**
* **Location:** `tests/test_cli_fold_inline.py`
* **Finding:** Using string manipulation (`"inline_" in t.id`) to identify inlined transitions in tests.
* **Suggestion:** This domain concept deserves an explicit metadata property (e.g., `"inline_expansion": True`) rather than inspecting the string identifier.

*(Note: A speculative generality smell regarding HTML output was suppressed because the spec explicitly mandated it).*

---

## Spec Axis Findings & Suggestions
**STATUS: PASS WITH ADVISORY**

### (a) Missing or Partial Requirements
- **None.** The implementation accurately fulfills all specified behaviors, including the correct pipeline ordering and backward compatibility.

### (b) Scope Creep (Unasked Behaviour)
- **Dummy transition DOT styling [WARNING]:**
  - **Finding:** In `code2petri/model.py` (`Transition.to_dot_node`), opaque/dummy transitions are given `style="filled,bold"` and `penwidth="2"`.
  - **Suggestion:** While visually sensible, be extremely careful! Recall the earlier issue where `pymupdf` fails completely to render SVG-to-PNG conversions when `<polygon>` elements possess `stroke-width` attributes. Adding `penwidth="2"` here might break PNG rendering for folded nets just like it did for cross-file transitions!

### (c) Implemented but Looks Wrong (Advisories)
- **Unreachable implicit `.html` activation:**
  - **Finding:** The spec asks for `--fold` to be implicitly activated by `.html` output (Ticket 21). The code correctly sets this up (`is_html = (ext == "html")`). However, because `"html"` is not yet registered in `SUPPORTED_EXTENSIONS` at the top of `engine.py`, attempting to use `-o net.html` crashes early with an `AssertionError("Unsupported output extension '.html'")`.
  - **Suggestion:** This is fine for now as it's just laying groundwork for Ticket 21, but note that the implicit activation is effectively dead code until the extension is officially whitelisted.
