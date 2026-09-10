# 14 — CLI Context Ingestion & Reference Serialization

**What to build:** Expose cross-file reference tracing through the CLI and render resolution metadata in all supported output formats. Users can specify context files and directories via `--context`. Graph serializers render resolution metadata visually and structurally, giving users clear insight into cross-file connections.

**Blocked by:** 13 — Symbol Table & Cross-File Call Resolution Engine

**Status:** complete

- [x] CLI accepts an optional `--context` argument accepting one or more file paths or directory paths.
- [x] Directory paths provided to `--context` are recursively scanned, auto-discovering supported source files (`.py`, `.js`).
- [x] Providing `--context` automatically activates symbol table creation and call resolution without requiring an extra flag.
- [x] Single-file invocations without `--context` continue to function without changes (backward compatibility).
- [x] PNML serializer emits `<toolspecific tool="code2petri" version="1.0">` elements for call transitions containing `<resolved target="..." file="..."/>` or `<unresolved/>` (delivered ahead of time in Ticket 11).
- [x] DOT serializer emits `tooltip` attributes and border styling (`color="#2e7d32"` for resolved, `color="#e65100"` for unresolved) on call transitions (delivered ahead of time in Ticket 11).
- [x] JSON serializer inlines `resolved`, `resolved_to`, and `target_file` fields directly into transition objects (delivered ahead of time in Ticket 11).
- [x] End-to-end integration tests verify CLI `--context` execution and format serialization on multi-file test fixtures.
