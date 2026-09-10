# Code Review: Ticket 14 (Round 1)

Reviewing full diff against `1eac3d2` (`feat(code2petri): implement symbol table and cross-file call resolution (ticket 13)`):
- Ticket: `.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md`
- Architecture Reference: `docs/adr/0001-constructor-only-variable-resolution.md`, `CONTEXT.md`, `phase-2-cross-file-tracing.md`

---

## Standards

### (a) Documented Repo Standards (`CONTEXT.md`, ADR 0001)
- **Hard Violations: 0.**
  - **Resolution Context**: Standardized CLI flag `--context` (`-c`) accepts files and directories to build a `SymbolTable` without turning context files into analysis targets.
  - **Backward Compatibility**: Single-file invocations without `--context` run unchanged with zero overhead and unannotated transitions.
  - **Serialization Layer**: Emits valid PNML `<toolspecific tool="code2petri" version="1.0">`, DOT styling (`#2e7d32` / `#e65100`) and tooltips, and JSON attributes (`resolved`, `resolved_to`, `target_file`).

---

### (b) Baseline Smells (Judgement Calls)
1. **Directory Traversal Filtering (Minor)**:
   - `discover_context_files` skips `._*` AppleDouble and hidden `.` files while traversing subdirectories.
   - *Assessment*: Crucial defense against filesystem pollution on macOS and external drives; prevents corrupted AST parsing attempts.

---

## Spec

### (a) Missing or Partial Requirements
**None (0 Missing).**
All Ticket 14 requirements are fully satisfied:
- CLI accepts an optional `--context` argument accepting one or more file paths or directory paths ([`14-cli-context-and-reference-serialization.md:9`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L9)).
- Directory paths provided to `--context` are recursively scanned, auto-discovering supported source files (`.py`, `.js`) ([`14-cli-context-and-reference-serialization.md:10`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L10)).
- Providing `--context` automatically activates symbol table creation and call resolution without requiring an extra flag ([`14-cli-context-and-reference-serialization.md:11`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L11)).
- Single-file invocations without `--context` continue to function without changes (backward compatibility) ([`14-cli-context-and-reference-serialization.md:12`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L12)).
- PNML serializer emits `<toolspecific tool="code2petri" version="1.0">` elements for call transitions containing `<resolved target="..." file="..."/>` or `<unresolved/>` ([`14-cli-context-and-reference-serialization.md:13`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L13)).
- DOT serializer emits `tooltip` attributes and border styling (`color="#2e7d32"` for resolved, `color="#e65100"` for unresolved) on call transitions ([`14-cli-context-and-reference-serialization.md:14`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L14)).
- JSON serializer inlines `resolved`, `resolved_to`, and `target_file` fields directly into transition objects ([`14-cli-context-and-reference-serialization.md:15`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L15)).
- End-to-end integration tests verify CLI `--context` execution and format serialization on multi-file test fixtures ([`14-cli-context-and-reference-serialization.md:16`](file:///.scratch/code2petri/issues/14-cli-context-and-reference-serialization.md#L16)).
- All 229 unit/integration tests pass without regression.

---

### (b) Behaviour Not Asked For (Scope Creep)
**None (0 Scope Creep).**
Implementation is tightly aligned with Ticket 14 specification.

---

### (c) Implemented But Wrong
**None (0 Defects).**
Verified against real `GameOfLife_Simulator` fixture (`app.js` and `webgl-engine.js`), ensuring accurate resolution of `WebGLEngine.step`, `stepCpu`, and unresolved `requestAnimationFrame`.

---

## One-Line Summary

- **Standards**: 0 hard violations, 1 judgement call (clean filesystem traversal filters).
- **Spec**: 0 missing requirements, 0 scope creeps, 0 logic defects.
