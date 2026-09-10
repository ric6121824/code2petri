# 13 — Symbol Table & Cross-File Call Resolution Engine

**What to build:** Build the cross-file symbol indexing and call matching engine. This component takes a primary file and a collection of context files, builds an indexed symbol table of all callable functions and class methods by language and qualified name, and resolves caller `CallSite` records against targets. Resolved calls attach target metadata to the caller net's transitions, while unresolvable calls are marked as unresolved.

**Blocked by:** 12 — Constructor Variable Binding & Call Site Extraction

**Status:** ready-for-agent

- [ ] `SymbolTable` class indexes all discoverable functions, methods, and callbacks across multiple files, partitioned by language.
- [ ] Call resolution resolves callee calls with owners (`obj.method`) using the caller's variable bindings to match against `Class.method` in the symbol table.
- [ ] Call resolution resolves bare function calls (`func()`) against local file definitions first, then against unique matching symbols across context files of the same language.
- [ ] Cross-language call matching is strictly prohibited (Python calls only match Python symbols; JavaScript calls only match JavaScript symbols).
- [ ] Matching transitions are decorated with `metadata={"resolved": True, "resolved_to": qualified_name, "target_file": filepath}`.
- [ ] Ambiguous matches (>1) or missing matches (0) are decorated with `metadata={"resolved": False}` and logged at `DEBUG` level.
- [ ] Unit tests verify symbol table indexing, successful same-language resolution, variable-binding resolution, ambiguous match handling, and unresolvable fallback.
