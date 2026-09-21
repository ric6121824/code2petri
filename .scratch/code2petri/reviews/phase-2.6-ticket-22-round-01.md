# Ticket 22: Code Review (Round 1)

**Diff:** `a2f9919...HEAD`  
**Commits:** `9d46ae6`  
**Spec:** `.scratch/code2petri/issues/22-nested-call-resolution.md`  

## Standards
**STATUS: PASS**

### (a) Documented Repo Standards (`CONTEXT.md`)
* **None (0 hard violations).** The diff adheres strictly to [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md):
  - **Call Site & Resolution Context**: Nested call resolution operates directly on `CallSite` records via `SymbolTable.resolve_call_sites(callee_net, callee_call_sites)` without introducing deprecated terminology (*call point*, *secondary file*).
  - **Opaque Transition**: Unexpanded calls inside inlined callees remain faithfully represented as opaque transitions, preserving the canonical term throughout docstrings and test assertions without forbidden aliases (*black box*, *leaf transition*).
  - **Composite Net & Inline Expansion**: Inlining mechanics cleanly integrate into `inline_expand` / `_inline_expand_recursive` without deprecated concepts (*unrolling*, *flattening*, *merged graph*).

### (b) Baseline Code Smells (Fowler Refactoring ch. 3 — Judgement Calls)
1. **Duplicated Code** (Judgement Call)
   - **Location**: [`tests/test_inline_expansion.py:450-456, 485-491, 521-527, 563-569`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_inline_expansion.py#L450-L569)
   - **Hunk**:
     ```python
     fp = self._write_temp_file("...", code)
     symbol_table = SymbolTable()
     symbol_table.index_file(fp)

     tree = self.py_walker.parse_file(fp)
     main_node = self.py_walker.find_function(tree, "main_func")
     main_res = self.py_walker.walk_function(main_node, "main_func", filepath=fp)
     ```
   - **Analysis**: The 6-line test fixture setup (writing a temp file, indexing the symbol table, parsing the AST, and walking the target function) recurs across all 4 newly added test methods. A small helper method (e.g. `_setup_inline_test(...)`) would eliminate boilerplate.

2. **Possible Speculative Generality** (Minor Judgement Call)
   - **Location**: [`code2petri/inline.py:47-50`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L47-L50)
   - **Hunk**:
     ```python
     def _get_callee_net(
         symbol: Symbol,
         symbol_table: Optional[SymbolTable] = None,
     ) -> Tuple[Optional[PetriNet], List[CallSite]]:
     ```
   - **Analysis**: `_get_callee_net` is a private module helper with a single call site in `_inline_expand_recursive`, where `symbol_table` is already non-optional. The default `symbol_table: Optional[SymbolTable] = None` is harmless defensive programming, but strictly unneeded by existing callers.

---

## Spec
**STATUS: PASS**

### (a) Requirements Missing or Partial
* **None (0 missing requirements).** All requirements from `.scratch/code2petri/issues/22-nested-call-resolution.md` are fully satisfied:
  - Spec: `"- [x] The _get_callee_net function (or equivalent inlining logic) accepts the SymbolTable."`
    - **Implemented**: `_get_callee_net` in [`code2petri/inline.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L46-L51) accepts `symbol_table: Optional[SymbolTable] = None`, threaded through from `_inline_expand_recursive`.
  - Spec: `"- [x] CallSite records internal to the callee are explicitly resolved against the SymbolTable before the callee subnet is spliced into the caller net."`
    - **Implemented**: `_get_callee_net` calls `symbol_table.resolve_call_sites(callee_net, callee_call_sites)` prior to returning the net and call sites for splicing.
  - Spec: `"- [x] Visualizer integration test or manual verification proves that nested call transitions receive the resolved = true metadata and are styled green in DOT/HTML outputs."`
    - **Implemented**: `test_nested_call_visualizer_rendering` in [`tests/test_inline_expansion.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_inline_expansion.py#L552-L617) verifies `resolved = True` metadata, DOT fillcolor (`#2e7d32`), and HTML viewer styling/classes.

### (b) Behaviour in the Diff Not Asked For (Scope Creep)
* **None.**
  - The changes to `code2petri/inline.py` are minimal (9 lines) and strictly confined to threading `symbol_table` and resolving callee call sites.
  - Supporting tests in `tests/test_inline_expansion.py` (`test_nested_call_resolution_unresolved` and `test_nested_call_resolution_multi_depth`) validate negative status handling and multi-depth recursion without introducing unrequested behaviors.
  - Issue tracker artifact `.scratch/code2petri/issues/22-nested-call-resolution.md` documents closure notes and verification.

### (c) Requirements Implemented Incorrectly
* **None.**
  - Resolution state (`resolution` and `metadata`) populated on the callee net transitions is faithfully cloned into the caller net during `_splice_callee_net` (`resolution=ct.resolution`, `new_meta = dict(ct.metadata)`). Edge cases where `symbol_table` is `None` or callee call sites are empty are properly guarded.

---

## Summary
- **Standards:** 2 findings (0 hard violations, 2 baseline smells: worst is **Duplicated Code** in test fixtures).
- **Spec:** 0 findings (all requirements satisfied, 0 scope creep, 0 incorrect implementations).
