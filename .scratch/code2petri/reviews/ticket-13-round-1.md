# Code Review: Ticket 13 (Round 1)

Reviewing full diff against `5230f85` (`feat(code2petri): implement variable bindings and call site extraction (ticket 12)`):
- Ticket: `.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md`
- Architecture Reference: `docs/adr/0001-constructor-only-variable-resolution.md`, `CONTEXT.md`

---

## Standards

### (a) Documented Repo Standards (`CONTEXT.md`, ADR 0001)
- **Hard Violations: 0.**
  - **Resolution Context & Symbol Table**: `SymbolTable` indexes callable definitions across files partitioned by language (`python` vs `javascript`), without coupling to analysis targets or mutating ASTs.
  - **Constructor-Only Variable Resolution (ADR 0001)**: `resolve_call` uses caller variable bindings (`{"gpuEngine": "WebGLEngine"}`) to map instance receivers (`obj.method`) to qualified class methods (`Class.method`).
  - **Call Site & Resolution Domain Models**: Operates directly on typed [`CallSite`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/walker_protocol.py#L9-L16) and decorates [`Transition`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L61) with both `metadata` and typed [`CallResolution`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L42-L58).

---

### (b) Baseline Smells (Judgement Calls)
1. **Fallback Matching on Bare Names in Context Symbols (Minor)**:
   - In `resolve_call`, if no exact qualified match `s.name == callee_name` exists, it checks `s.bare_name == callee_name`.
   - *Assessment*: Desirable fallback that allows bare calls to match standalone functions without requiring module qualification while preserving ambiguous match detection if multiple symbols share the bare name.

---

## Spec

### (a) Missing or Partial Requirements
**None (0 Missing).**
All Ticket 13 requirements are fully satisfied:
- `SymbolTable` indexes discoverable functions, methods, and callbacks across multiple files, partitioned by language ([`13-symbol-table-and-call-resolution.md:9`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L9)).
- Call resolution resolves callee calls with owners (`obj.method`) using caller variable bindings to match against `Class.method` ([`13-symbol-table-and-call-resolution.md:10`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L10)).
- Call resolution resolves bare function calls (`func()`) against local file definitions first, then against unique context symbols of the same language ([`13-symbol-table-and-call-resolution.md:11`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L11)).
- Cross-language call matching is strictly prohibited ([`13-symbol-table-and-call-resolution.md:12`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L12)).
- Matching transitions are decorated with `metadata={"resolved": True, "resolved_to": qualified_name, "target_file": filepath}` and `resolution=CallResolution(...)` ([`13-symbol-table-and-call-resolution.md:13`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L13)).
- Ambiguous matches (>1) or missing matches (0) are decorated with `metadata={"resolved": False}` and logged at `DEBUG` level ([`13-symbol-table-and-call-resolution.md:14`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L14)).
- Unit tests verify symbol table indexing, successful same-language resolution, variable-binding resolution, ambiguous match handling, and unresolvable fallback ([`13-symbol-table-and-call-resolution.md:15`](file:///.scratch/code2petri/issues/13-symbol-table-and-call-resolution.md#L15)).
- All 218 unit/integration tests pass without regression.

---

### (b) Behaviour Not Asked For (Scope Creep)
**None (0 Scope Creep).**
Implementation is tightly scoped to `SymbolTable` and resolution engine as specified.

---

### (c) Implemented But Wrong
**None (0 Defects).**
Verified across synthetic and real-world multi-file packages (`tests/test_code/game_of_life/app.js` and `webgl-engine.js`).

---

## One-Line Summary

- **Standards**: 0 hard violations, 1 judgement call (clean bare-name context fallback).
- **Spec**: 0 missing requirements, 0 scope creeps, 0 logic defects.
