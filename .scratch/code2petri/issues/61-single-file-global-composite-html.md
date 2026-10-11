# 61: Inline same-file callees in global composite HTML

**What to build:** A global HTML export opens with its resolved function subnets already inlined as nested function compounds, whether callees are defined in other files or in the entry file itself. Expansion follows the configured depth and retains recursion protection, so users can inspect the full composite without expanding call sites manually.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] A single-file source fixture with global calls to same-file functions generates an initially expanded composite net containing those callee subnets.
- [x] Reachable nested callees are expanded to the configured depth, while recursive call chains terminate safely.
- [x] The initial HTML graph represents inlined functions as nested compounds with valid boundary wiring and a valid bipartite net.
- [x] Multi-file global HTML exports retain their current initial composite behavior.
- [x] Automated coverage verifies the generated HTML's initial graph, not only its embedded callee lookup data.

## Comments

### 2026-10-11 — Implementation complete

Global HTML output now implicitly inlines same-file callees using the HTML-local symbol table, following `--inline-depth` and the existing recursion guard. Multi-file global composite output remains covered. Focused single-file and multi-file tests pass. Full-suite verification was attempted, but this runner lacks Node.js, causing unrelated JavaScript parsing and headless-viewer test failures.
