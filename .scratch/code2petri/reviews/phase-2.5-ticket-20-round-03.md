# Ticket 20: Code Review (Round 3)

**Diff:** `43e6e87...HEAD`  
**Commits:** `107ceb2`, `db9fe9a`, `e9ed5cf`  
**Spec:** `.scratch/code2petri/issues/20-cli-integration-fold-inline.md`

## Standards
**STATUS: PASS**

### Round 2 Findings Check
1. **"dummy" Terminology Hard Violation (`CONTEXT.md`): FIXED.**  
   The forbidden term "dummy" was completely purged from `code2petri/model.py` and `Transition.RESERVED_METADATA_KEYS`. The property `is_dummy` was deleted. `tests/test_petri_model.py` now explicitly asserts `assertNotIn("dummy", ...)` and `assertFalse(hasattr(t_opaque, "is_dummy"))`. Only canonical domain terms (*Opaque Transition*) remain.
2. **Duplicated Code / Feature Envy in `fold.py` (`t1.metadata.get("tau")` vs `t1.get_tau()`): VERIFIED CLEAN.**  
   The functions `collapse_sequence` / `collapse_choice` cited in Round 2 do not exist in the codebase. All folding operations in `code2petri/fold.py` (`fold_component`, `fold_unstructured`, `fold_net`) already consistently invoke `t.get_tau()`. No direct `metadata.get("tau")` unpacking exists in `code2petri/`.

### (a) Documented Standards Violations (Hard Violations)
* **None.** The full diff strictly conforms to `CONTEXT.md` domain vocabulary:
  - *Opaque Transition*: modeled via `Transition.is_opaque` and `"opaque": True`.
  - *Inline Expansion*: encapsulated via `inline_expand()` and `"inline_expansion": True`.
  - *Composite Net*: correctly formed and referenced.
  - *Resolution Context* & *Call Site*: consistently used across engine and symbol resolution.

### (b) Baseline Smells (Judgement Calls)
1. **Repeated Switches / Type Dispatch (Judgement Call)**
   * **Location:** [`code2petri/engine.py:240-248`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L240-L248)
   * **Hunk:**
     ```python
     if fold_active and fold_result is not None:
         if ext == "json":
             content = fold_result.to_json()
         elif ext in ("dot", "gv"):
             content = fold_result.to_dot()
         elif ext == "pnml":
             content = fold_result.to_pnml()
     else:
         content = TEXT_SERIALIZERS[ext](net)
     ```
   * **Finding:** Both `PetriNet` and `FoldResult` provide identical serialization protocols (`to_dot()`, `to_pnml()`, `to_json()`). Checking `ext` via an `if/elif` cascade duplicates the dispatch mechanism already modeled by `TEXT_SERIALIZERS`.
   * **Suggestion:** Treat `target = fold_result if fold_active else net` polymorphically with a shared serializer map in future cleanup.

---

## Spec
**STATUS: PASS**

### Round 2 Findings Check
- **`penwidth="2"` attribute removal:** **RESOLVED.**  
  In commit `e9ed5cf`, `penwidth_attr` was completely removed from `Transition.to_dot_node()` in `code2petri/model.py`. Opaque transitions now only receive `style="filled,bold"`, eliminating the risk of `pymupdf` SVG-to-PNG polygon rendering crashes. Regression assertions (`self.assertNotIn('penwidth', dot_str)`) were added to tests.

### (a) Missing or Partial Requirements
- **None.** All functional requirements across CLI flags (`--fold`, `--no-fold`, `--weights`, `--inline`, `--inline-depth`), pipeline ordering (inline before fold), output serializations (JSON `FoldResult`, DOT/PNML penultimate nets), stderr reporting, and backward compatibility are completely implemented and tested.
- *Note on Spec line 31 (`"- [x] \"dummy\" is added to Transition.RESERVED_METADATA_KEYS"`):*  
  As mandated by `CONTEXT.md` and enforced in Round 2, `"dummy"` was intentionally replaced by `"opaque"` across metadata and properties to uphold repository architectural terminology.

### (b) Scope Creep (Unasked Behaviour)
- **None.** With the removal of `penwidth="2"`, no unasked behaviors or rendering attributes remain. The visual distinction for opaque nodes adheres directly to Spec line 26.

### (c) Implemented but Looks Wrong (Advisories)
- **Unreachable implicit `.html` activation (harmless scaffolding):**  
  > Spec line 8: *"`--fold`: Opt-in fold analysis. Implicitly activated by `.html` output (Ticket 21)."*  
  The engine activates folding when `is_html = (ext == "html")` (`code2petri/engine.py:215`). However, passing `-o net.html` fails earlier at extension validation with `AssertionError("Unsupported output extension '.html'")` because `"html"` is not yet registered in `SUPPORTED_EXTENSIONS`. This remains expected stubbing pending Ticket 21.

---

## Summary
- **Standards Axis:** 0 hard violations, 1 baseline smell (Repeated Switches in [`engine.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L240-L248)). **STATUS: PASS**
- **Spec Axis:** 0 missing requirements, 0 scope creep, 1 advisory (unreachable `.html` implicit activation pending Ticket 21). **STATUS: PASS**
