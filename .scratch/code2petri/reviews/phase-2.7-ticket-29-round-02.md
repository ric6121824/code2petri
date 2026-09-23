# Code Review: Ticket 29 — Round 2 (Composite Assembly Refactor)

**Commit:** `ded547d` (`refactor(composite): address Round 01 code review for Ticket 29`)  
**Diff:** `git diff 9e72890...HEAD` (11 files changed, 515 insertions(+), 189 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/29-prefactor-backend-composite-assembly.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/29-prefactor-backend-composite-assembly.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test suite:** 383 tests — **all pass**

---

## Standards

### (a) Round 1 Verification

1. **Duplicated Code – Hierarchy Metadata Decoration (`inline.py`) → ✅ RESOLVED**
   `_decorate_node_hierarchy(meta, compound_id, fn_name, prefix)` extracted and called at both former duplicate sites. Unit test in `test_inline_expansion.py` covers the helper directly.

2. **Duplicated Code – Model Property Delegation (`model.py`) → ✅ RESOLVED**
   `NodeBase` mixin introduced. Both `Place` and `Transition` now inherit from it, sharing `parent`/`enclosing_function` property accessors and the `_serialize_base_dict()` serialization helper. The 20-line duplicate property block in `Transition` is gone.

3. **Primitive Obsession & Data Clumps (`model.py`) → ⚠️ PARTIAL**
   `CompoundContainer` dataclass introduced — good. Two sub-issues remain:
   - The class is `@dataclass` (mutable), not `@dataclass(frozen=True)` as suggested. This is a reasonable design choice because `compound.node_ids.update(…)` is called in `inline.py` post-construction, but the intentional mutability is not documented in the docstring.
   - **Actionable Fix:** Add a docstring note: `"node_ids is intentionally mutable — the splicer adds members after construction."` Consider using `field(default_factory=set)` (see #5 below).
   - `CompoundContainer` implements `.keys()` and `.items()` as a `dict`-compatibility shim without `__iter__`. `dict(comp)` works via Python's informal mapping protocol (`keys()` + `__getitem__`) but this is fragile and undocumented.
   - **Actionable Fix:** Either register `CompoundContainer` as a `collections.abc.Mapping` (implementing `__iter__` and `__len__`) or replace the shim with an explicit `.to_dict()` method and update all `dict(comp)` call sites.

4. **Speculative Generality – `generate_html` params (`viewer/__init__.py`) → ✅ RESOLVED**
   Both `composite_net` and `mode` parameters removed. Detection is now:
   ```python
   is_composite = (
       isinstance(net_or_fold, PetriNet) and bool(getattr(net_or_fold, "compounds", None))
   ) or (
       isinstance(net_or_fold, dict) and bool(net_or_fold.get("compounds"))
   )
   ```

### (b) Newly Introduced Smells

5. **`__post_init__` anti-pattern for mutable default (Judgement call)** ([`code2petri/model.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py)):
   ```python
   # current
   node_ids: Optional[Set[str]] = None
   def __post_init__(self): if self.node_ids is None: self.node_ids = set()
   ```
   - **Actionable Fix:** Use `field(default_factory=set)` — the idiomatic dataclass form that is self-documenting and avoids the `None` sentinel:
     ```python
     node_ids: Set[str] = field(default_factory=set)
     ```

6. **`id` shadows the Python built-in in `NodeBase` (Judgement call)** ([`code2petri/model.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py)):
   `NodeBase.__init__` uses `id` as a parameter name, shadowing the built-in. `Place` already uses the `id_`/`id` dual-parameter idiom for backwards compatibility and passes `node_id` to `super().__init__(id=node_id, …)`, which is fine. But `NodeBase` advertising `id` as a public keyword arg is a hazard.
   - **Actionable Fix:** Rename the `NodeBase.__init__` parameter to `id_` or `node_id` and update `Transition`'s `super()` call to match.

7. **`list + list` materialisation (Style note)** ([`code2petri/inline.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py)):
   ```python
   for node in list(composite_net.places) + list(composite_net.transitions):
   ```
   Materialises both sequences. `itertools.chain(composite_net.places, composite_net.transitions)` is zero-copy and more idiomatic.

---

## Spec

### (a) Round 1 Verification

1. **Expansion to Maximum Depth by Default → ✅ RESOLVED**
   `engine.py` defines `UNLIMITED_DEPTH: int = 999` and sets `actual_inline_depth = UNLIMITED_DEPTH if is_composite_html else 1`. `--inline-depth` can still cap it explicitly.

2. **`--inline` Flag Required for HTML Composite Assembly → ✅ RESOLVED**
   `engine.py` now computes:
   ```python
   effective_inline = inline or (is_html and bool(context) and not fold)
   ```
   Composite assembly activates implicitly when `ext == "html"` and `--context` is provided.

3. **Hardcoded Viewer Header Overrides → ✅ RESOLVED**
   `{{MODE_LABEL}}` and `{{MODE_DESC}}` template variables substituted from `viewer/__init__.py`. The hardcoded `textContent` JS overrides are also removed.

4. **Silent Suppression of `--fold` Flag → ✅ RESOLVED**
   ```python
   if is_composite_html and fold:
       logger.warning("--fold is not compatible with composite HTML output and will be ignored.")
   ```

5. **Compound Node Tap Handler Triggers Broken Relayout → ✅ RESOLVED**
   `composite_preassembled: true` data flag injected at compound creation; tap handler early-returns when the flag is present.

### (b) New Issues

6. **`generate_html` parameters removed (`composite_net`, `mode`) → ✅ RESOLVED (Option B)** ([`code2petri/viewer/__init__.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py)):
   - **Resolution Note:** *Notice that `composite_net` and `mode` were introduced in commit `9e72890` (Ticket 29 Round 1) and never shipped in any release or merged to master. Reverting them in Round 2 restores `generate_html` to its exact master signature. Because there are zero external consumers or releases with these parameters, no deprecation shim is required.*

7. **🟡 Logically Misleading Mouseover Cursor Guard (Low priority)** ([`code2petri/viewer/template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html)):
   The `composite_preassembled !== true` guard is appended as a global AND on the entire `resolved || expandedNodes || compound` condition, meaning it also suppresses pointer cursor for resolved transitions and expanded nodes that happen to coincide — though in practice they never carry the flag. Functionally harmless.
   - **Actionable Fix:** Tighten the guard to only the `.hasClass('compound')` branch: `(n.data('resolved') === true || expandedNodes.has(n.id())) || (n.hasClass('compound') && n.data('composite_preassembled') !== true)`.

---

## Summary

| # | Finding | Status | Class |
|---|---------|--------|-------|
| S1 | `_decorate_node_hierarchy` extracted | ✅ Resolved | — |
| S2 | `NodeBase` mixin introduced | ✅ Resolved | — |
| S3 | `CompoundContainer` not frozen; informal `dict` mapping | ⚠️ Partial | Judgement call |
| S4 | `composite_net`/`mode` params removed | ✅ Resolved | — |
| S5 | `field(default_factory=set)` vs `__post_init__` | 🆕 New | Judgement call |
| S6 | `id` shadows built-in in `NodeBase` | 🆕 New | Judgement call |
| S7 | `list + list` vs `itertools.chain` | 🆕 New | Style |
| P1–P5 | All 5 Round 1 spec findings | ✅ Resolved | — |
| P6 | Removal of unmerged `generate_html` params | ✅ Resolved | Option B documented |
| P7 | Logically misleading mouseover cursor guard | 🆕 New | Low priority |

- **Standards:** 3 resolved, 1 partial (CompoundContainer mutability), 3 new minor smells. Worst remaining: `id` shadowing built-in in `NodeBase`.
- **Spec:** 6 resolved, 1 low-priority clarity issue (mouseover cursor guard). No breaking changes on shipped APIs.
