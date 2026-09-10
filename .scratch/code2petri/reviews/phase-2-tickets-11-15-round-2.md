# Code Review: Phase 2 (Tickets 11–15 — Round 2 Re-Review)

Re-evaluating the Phase 2 cross-cutting changes following the implementation of findings from [phase-2-tickets-11-15.md](phase-2-tickets-11-15.md).

---

## Status of Previous Findings

| Finding from Round 1 | Category | Status | Resolution Note |
|---|---|---|---|
| **Logic Defect**: Bare calls fallback matching class methods via `bare_name` | Spec (Incorrect) | **Resolved** | Added `Symbol.is_method` and `_find_unique_bare_symbol_match` in `code2petri/symbol_table.py` filtering out methods (`not s.is_method`) for both local and context files. Added regression tests in `tests/test_symbol_table.py`. |
| **Smell 1a**: Registry duplication between `engine.py` and `symbol_table.py` | Standards (Duplication) | **Resolved** | Centralized `SUPPORTED_WALKERS` in `code2petri/symbol_table.py` and imported as `WALKERS = SUPPORTED_WALKERS` in `code2petri/engine.py`. |
| **Smell 1b**: Symbol disambiguation repetition in `symbol_table.py` | Standards (Duplication) | **Resolved** | Extracted helper `_find_unique_bare_symbol_match` reused across local and context search paths. |
| **Smell 1c**: Metadata key blacklist repeated across PNML & DOT formatters | Standards (Duplication) | **Resolved** | Defined `Transition.RESERVED_METADATA_KEYS = {"resolved", "resolved_to", "target_file", "status"}` in `code2petri/model.py`. |
| **Smell 2**: Primitive obsession in `resolve_call_sites` dict assembly | Standards (Design) | **Resolved** | Directly instantiated `CallResolution(resolved=True, ...)` and `CallResolution(resolved=False)` on `t.resolution`. Explicitly added `status: "[unresolved]"` to metadata. |
| **Spec Clarification**: Ticket 15 checklist item 10 AST fidelity | Spec (Checklist) | **Resolved** | Updated item 10 in `.scratch/code2petri/issues/15-game-of-life-cross-file-validation.md` to accurately reflect `init` and `randomizeBoth` in `app.js`. |

---

## Standards

- **Hard Violations: 0.**
  Clean implementation adheres strictly to `CONTEXT.md` and ADR 0001.
- **Baseline Smells: 0.**
  All identified code smells (registry duplication, symbol disambiguation repetition, metadata reserved keys, and dictionary-based resolution instantiation) have been eliminated.

---

## Spec

- **Missing Requirements: 0.**
- **Scope Creeps: 0.**
- **Logic Defects: 0.**
  The bare-call method fallback bug has been resolved; bare calls now resolve strictly to top-level/standalone functions.

---

## Verification Results

- All 234 unit, integration, and validation tests across all 11 test modules pass cleanly with 0 errors and 0 failures:
  - `tests/test_petri_model.py`
  - `tests/test_walker_protocol.py`
  - `tests/test_python_walker.py`
  - `tests/test_javascript_walker.py`
  - `tests/test_petri_if_branching.py`
  - `tests/test_petri_loops.py`
  - `tests/test_petri_try.py`
  - `tests/test_petri_pipeline.py`
  - `tests/test_symbol_table.py` (including `test_bare_call_does_not_match_class_method`)
  - `tests/test_context_pipeline.py`
  - `tests/test_game_of_life_validation.py`
