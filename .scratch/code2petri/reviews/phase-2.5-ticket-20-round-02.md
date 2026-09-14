# Ticket 20: Code Review (Round 2)

**Diff:** `43e6e87...HEAD`  
**Commit:** `db9fe9a`  
**Spec:** `.scratch/code2petri/issues/20-cli-integration-fold-inline.md`

## Standards Axis Findings & Suggestions
**STATUS: FAIL**

### Round 1 Findings Check

- **Duplicated ext parsing:** **Fixed.** `ext` is now properly reused in `code2petri/engine.py`.
- **Feature Envy in engine.py:** **Fixed.** `FoldResult` now exposes its own `to_dot()` and `to_pnml()` methods, encapsulating the underlying `penultimate_net` and `final_sm`. 
- **Primitive Obsession in test string matching:** **Fixed.** The code now properly leverages `is_inlined` and `inline_expansion` metadata.
- **The "dummy" terminology hard violation:** **FAILED.** 

### Documented Standards Violations (Hard Violations)

**1. `CONTEXT.md` (Opaque Transition)**
* **Location:** `code2petri/model.py` and `tests/test_petri_model.py`
* **Violation:** While `fold.py` was correctly updated to only emit `"opaque": True`, `model.py` retains `is_dummy` as a "deprecated alias" and keeps `"dummy"` in `Transition.RESERVED_METADATA_KEYS`. 
* **Suggestion:** `CONTEXT.md` explicitly overrides the spec. You must purge the word "dummy" from the codebase entirely. Delete the `is_dummy` property outright, remove `"dummy"` from `RESERVED_METADATA_KEYS`, and delete the `test_dummy_and_opaque_in_reserved_metadata_keys` assertion for it.

### Baseline Smells (Judgement Calls)

**1. Duplicated Code / Feature Envy**
* **Location:** `code2petri/fold.py` (`collapse_sequence` and `collapse_choice`)
* **Finding:** Both functions manually unpack `t1.metadata.get("tau", 0.0) if hasattr(t1, "metadata") else 0.0`.
* **Suggestion:** These functions envy the internal representation of the Transition object. This extraction logic already exists! Use the existing `t1.get_tau()` method instead of re-implementing the dictionary unpack.

---

## Spec Axis Findings & Suggestions
**STATUS: FAIL**

### Round 1 Findings Check
- **Dummy transition DOT styling:** **FAILED.**

### (a) Missing or Partial Requirements
- **None.** The implementation accurately fulfills the pipeline.

### (b) Scope Creep (Unasked Behaviour)
- **Dummy transition DOT styling (CRITICAL PNG BUG):**
  - **Finding:** In Round 1, you were explicitly warned that `penwidth="2"` breaks the `pymupdf` SVG-to-PNG renderer for `<polygon>` elements. In `db9fe9a`, you updated the conditional to check `if self.is_opaque:`, but you **kept** the `penwidth="2"` attribute!
  ```python
  penwidth_attr = ', penwidth="2"' if self.is_opaque else ""
  ```
  - **Suggestion:** Delete the `penwidth_attr` entirely. Do not try to add borders or stroke-width to these nodes, or you will break the PNG exports.

### (c) Implemented but Looks Wrong (Advisories)
- **Unreachable implicit `.html` activation:**
  - **Finding:** As noted in Round 1, `.html` is not in `SUPPORTED_EXTENSIONS` yet, making the implicit `--fold` activation dead code. This is fine and expected until Ticket 21.
