# Code Review: Phase 2 (Round 6 Final Re-Review)

Reviewing full Phase 2 diff between `0de953e` and `HEAD` (`3a241c8`):
- `3a241c8 refactor(code2petri): resolve round 5 review issues for phase 2`
- `bd06fac refactor(code2petri): resolve round 4 review items for phase 2`
- `082a32e refactor(code2petri): resolve round 3 review issues for phase 2`
- `6d0bcec refactor(code2petri): resolve code smells and bare call resolution defect from phase 2 review`
- `de21291 test(code2petri): add GameOfLife simulator cross-file validation suite (ticket 15)`
- `967a084 feat(code2petri): implement CLI context ingestion and reference serialization (ticket 14)`
- `1eac3d2 feat(code2petri): implement symbol table and cross-file call resolution (ticket 13)`
- `5230f85 feat(code2petri): implement variable bindings and call site extraction (ticket 12)`
- `5a5a28d refactor(code2petri): resolve round 2 review issues for ticket 11`
- `44b9154 refactor(code2petri): resolve round 1 review issues for ticket 11`
- `2046f3d feat(code2petri): implement WalkResult protocol return type and transition metadata (ticket 11)`

---

## 1. Round 5 Remediations Verification

All four items identified in Round 5 have been **completely verified as resolved**:
- **Missing `Set` Import:** Added to `from typing import ...` in [`code2petri/model.py:3`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L3); verified with new test `test_transition_type_hints_valid` in [`tests/test_petri_model.py:464`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_petri_model.py#L464).
- **JS NewExpression Extraction:** Deduplicated via [`_extract_new_class_name`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L892-L899) in [`code2petri/javascript_walker.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/javascript_walker.py#L892-L899).
- **Context Engine Deduplication:** Deduplicated seen-set and normalization logic via [`add_file`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L19-L23) in [`code2petri/engine.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L19-L23).
- **JSON Root Promotion for Status:** Promoted `"status": "[unresolved]"` to JSON root on unresolvable calls in [`code2petri/model.py:112-113`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L112-L113) and verified in [`tests/test_petri_model.py:548`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_petri_model.py#L548).

---

## Standards

### (a) Documented Repo Standards (`CONTEXT.md`, ADR 0001)
- **Hard Violations: 0.**
  - **Domain Model Vocabulary** (`CONTEXT.md`): Strict adherence to domain terms (`Walker Protocol`, `Global Scope`, `Synthetic Wrapper`, `Opaque Transition`, `Call Site`, `Resolution Context`, `Variable Binding`). All forbidden terms ("fake node", "secondary files", "type inference", "call point") are avoided.
  - **ADR 0001** (`docs/adr/0001-constructor-only-variable-resolution.md`): Follows lightweight constructor tracking (`collect_variable_bindings`) and graceful fallback to annotated opaque transitions marked `[unresolved]`.

---

### (b) Baseline Smells (Judgement Calls)
1. **Data Clumps / Redundant State** ([`code2petri/symbol_table.py:315-335`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L315-L335)):
   - Synchronizes typed `CallResolution` and dictionary `metadata` for backward-compatibility across legacy formatters and tests.
2. **Feature Envy** ([`code2petri/symbol_table.py:313-335`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L313-L335)):
   - `SymbolTable.resolve_call_sites` directly sets `t.resolution` and `t.metadata`. Moving this decoration onto a `Transition.apply_resolution(sym)` method would encapsulate `Transition` state.
3. **Assertion for Control Flow** ([`code2petri/engine.py:27`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L27)):
   - Raising `AssertionError` for invalid user CLI inputs is an anti-pattern; `FileNotFoundError` or `ValueError` would be more idiomatic.

---

## Spec

### (a) Missing or Partial Requirements
- **None (0 missing or partial).** All functional and serialization requirements specified across Phase 2 master spec, tickets 11–15, and Round 5 suggestions are fully satisfied.

---

### (b) Behaviour in Diff Not Asked For (Scope Creep)
1. **`CallResolution` Domain Object** ([`code2petri/model.py:42-59`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L42-L59)): Strongly typed domain dataclass replacing loose dictionary metadata. *(Benign improvement)*.
2. **Generic Property Serialization** ([`code2petri/model.py:128-132`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L128-L132)): Emits `<property>` tags in PNML and DOT tooltips for arbitrary metadata. *(Benign forward compatibility)*.
3. **Direct Class Receiver Fallback** ([`code2petri/symbol_table.py:248-249`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/symbol_table.py#L248-L249)): Resolves `ClassName.method()` static calls when receiver is un-bound. *(Benign static method support)*.
4. **macOS AppleDouble Filtering** ([`code2petri/engine.py:26`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L26)): Filters `._*` resource-fork files during directory context scans. *(Platform convenience)*.
5. **Optional `filepath` in `walk_function`** ([`code2petri/walker_protocol.py:44`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/walker_protocol.py#L44)): Added optional `filepath: Optional[str] = None` to populate `CallSite.caller_file`. *(Convenience parameter)*.

---

### (c) Requirements Implemented Incorrectly (Logic Defects)
- **None (0 Logic Defects).** Variable binding extraction, symbol matching, same-language boundary enforcement, unresolved diagnostics, and PNML/DOT/JSON serialization logic execute accurately.
- All **235 unit, integration, and cross-file validation tests pass cleanly** (`Ran 235 tests in 8.810s, OK`).

---

## One-Line Summary

- **Standards:** 0 hard violations, 3 minor judgement calls.
- **Spec:** 0 missing functional requirements, 5 benign scope creeps, **0 logic defects**.
