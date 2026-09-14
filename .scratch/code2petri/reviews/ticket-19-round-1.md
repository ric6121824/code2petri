# Ticket 19: Code Review (Round 1)

**Commit:** `24a7a9b`
**Spec:** `.scratch/code2petri/issues/19-inline-expansion-engine.md`

## Spec Axis Findings

### 1. Self-Referencing Game Loop (`requestAnimationFrame(loop)`) Early Exit
- **Spec Line 23:** `"- [x] Recursion guard: a self-referencing call site (e.g., loop calling requestAnimationFrame(loop)) retains the call transition as an Opaque Transition with {\"recursive_cycle\": True} metadata instead of infinite expansion."`
- **Issue:** Unresolved calls were bypassed early (`if sym is None: continue`). Because `requestAnimationFrame` is a browser built-in not indexed in `SymbolTable`, `requestAnimationFrame(loop)` exited as an untagged unresolved call rather than receiving `{"recursive_cycle": True}` metadata. The subsequent check was unreachable dead code.
- **Fix:** Check for recursive animation loops before skipping unresolved external symbols, annotate `recursive_cycle: True`, and retain as opaque transition.

### 2. Missing Unit Test for `requestAnimationFrame(loop)`
- **Spec Line 26:** `"- [x] Unit tests verify: single callee splicing (...); recursive call guard; depth-1 cap on a multi-level chain; unresolved calls remain opaque."`
- **Issue:** `tests/test_inline_expansion.py` verified direct and mutual recursion in Python, but lacked a test specifically validating `loop` calling `requestAnimationFrame(loop)` retaining the transition with `{"recursive_cycle": True}`.
- **Fix:** Add a dedicated unit test in `tests/test_inline_expansion.py`.

### 3. Scope Creep: Speculative Net Caching
- **Spec Line 6:** `"1. Walk the callee function using the existing walker infrastructure to produce the callee's PetriNet."`
- **Issue:** Checking `hasattr(symbol, "net")` introduced speculative duck-typing and pre-computed net caching on `Symbol` not requested by the spec.
- **Fix:** Remove `hasattr(symbol, "net")` and rely strictly on walker infrastructure.

### 4. Leaking Internal State in Public Signature
- **Spec Line 19:** `"- [x] An inline expansion function accepts a PetriNet, a list of CallSite records, a SymbolTable, and optional max_depth (default 1), and returns a new PetriNet with resolved callees spliced in."`
- **Issue:** `inline_expand` exposed `current_stack` and `caller_function` in its public parameters.
- **Fix:** Restrict public `inline_expand` signature strictly to `(net, call_sites, symbol_table, max_depth=1)` and delegate to internal `_inline_expand_recursive(...)`.

### 5. Redundant Resolution Metadata
- **Spec Line 11:** `"...retained as an annotated Opaque Transition with metadata={\"recursive_cycle\": True}."`
- **Issue:** Manually writing `"resolved"`, `"resolved_to"`, and `"target_file"` into `trans.metadata` is redundant; `trans.resolution: CallResolution` already encapsulates resolution status per Tickets 16/18.
- **Fix:** Only set `trans.resolution` and omit duplicate raw metadata keys.

### 6. Recursion Guard False Positives on Qualified Names
- **Spec Line 11:** `"A recursion guard tracks the active expansion call stack; if a callee appears in the stack..."`
- **Issue:** Splitting on `.` and checking bare names (`rsplit(".", 1)[1]`) causes false-positive recursion when different classes have identical method names (e.g. `ClassA.step()` calling `ClassB.step()`).
- **Fix:** Track exact qualified names `(sym.filepath, sym.name)` or `sym.name` in the recursion stack.

---

## Standards Axis Findings

### 1. Speculative Generality
- `code2petri/inline.py:27-28`: `if hasattr(symbol, "net")...` anticipates unrequested caching.

### 2. Feature Envy
- `code2petri/inline.py:110-118`: Manual field-by-field reconstruction of `CallResolution` (which is a frozen dataclass and can be reused directly).

### 3. Duplicated Code
- `code2petri/inline.py:46-58`: Parsing `symbol.filepath` twice in `_get_callee_net`.

### 4. Primitive Obsession
- `code2petri/inline.py:246`: Substring search in `trans.label` for `requestAnimationFrame` argument instead of structured inspection.

### 5. Repeated Switches
- `code2petri/inline.py:32-38`: If/else fallback cascade for walker selection instead of clean dictionary lookup.
