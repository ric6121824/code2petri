# Code Review: Ticket 29 (Prefactor: Backend Composite Assembly)

**Commit:** `9e72890` (`feat(composite): assemble composite net with parent hierarchy and viewer seam (ticket 29)`)  
**Diff:** `git diff 90e49bb...HEAD` (10 files changed, 699 insertions(+), 31 deletions(-))  
**Spec:** [`.scratch/code2petri/issues/29-prefactor-backend-composite-assembly.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/29-prefactor-backend-composite-assembly.md)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  

---

## Standards

### (a) Documented Standards Violations
**None detected (Hard standard).**
- **Domain Vocabulary ([`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md))**: Fully adheres to repo terms (`Composite Net`, `Inline Expansion`, `Opaque Transition`, `Call Site`). No prohibited vocabulary (`merged graph`, `unrolling`, `leaf transition`, etc.) was introduced.
- **Architectural Rules ([`docs/adr/0002-boundary-place-unification.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0002-boundary-place-unification.md))**: Boundary place fusion and bipartite net invariants are strictly preserved during callee splicing in [`code2petri/inline.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py).

### (b) Baseline Code Smells (Judgement Calls)

1. **Duplicated Code**
   - **Hierarchy Metadata Decoration:** In [`code2petri/inline.py:182-210`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L182-L210), identical hierarchy metadata decoration is copy-pasted across transitions and places in `_splice_callee_net`:
     ```python
     new_meta["inline_expansion"] = True
     if "parent" not in new_meta or new_meta["parent"] is None:
         new_meta["parent"] = compound_id
     elif prefix and new_meta.get("parent"):
         new_meta["parent"] = f"{prefix}{new_meta['parent']}"
     if "enclosing_function" not in new_meta or new_meta["enclosing_function"] is None:
         new_meta["enclosing_function"] = fn_name
     ```
     A dedicated helper updating node hierarchy metadata would eliminate this duplication as well as the duplicate loops in `_inline_expand_recursive` (lines 292–302).
   - **Actionable Fix:** Extract a `_decorate_node_hierarchy(meta: dict, compound_id: str, fn_name: str, prefix: str) -> None` helper in `inline.py` that applies all three mutations atomically. Replace both the `Place` and `Transition` decoration blocks in `_splice_callee_net` with a single call to this helper.
   - **Model Property Delegation:** In [`code2petri/model.py:42-68, 182-208`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L42-L68), the `parent` and `enclosing_function` property accessors, setter delegations to `self.metadata`, and serialization logic in `to_dict` are duplicated across `Place` and `Transition`.
   - **Actionable Fix:** Extract a `NodeBase` mixin (or abstract base class) in `model.py` carrying the shared `parent`, `enclosing_function` properties, their setters, and the corresponding `to_dict` serialization entries. Let `Place` and `Transition` inherit from `NodeBase` so the property and serialization logic lives in exactly one place.

2. **Primitive Obsession & Data Clumps**
   - In [`code2petri/model.py:442-464`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L442-L464), compound containers are stored as raw `Dict[str, Any]` inside `PetriNet.compounds` rather than a first-class domain type (e.g. `CompoundContainer`), unlike `Place`, `Transition`, and `Arc`.
   - `parent` and `enclosing_function` continually travel together as loosely typed arguments across `add_place`, `add_transition`, and `metadata`.
   - **Actionable Fix:** Introduce a `@dataclass(frozen=True) class CompoundContainer` with fields `id: str`, `label: str`, `enclosing_function: str`, `node_ids: Set[str]` (the IDs of nodes belonging to this compound). Store `PetriNet.compounds` as `Dict[str, CompoundContainer]` instead of `Dict[str, Any]`. This removes the raw-dict primitive obsession, makes the hierarchy queryable by type-safe attributes, and eliminates the scattered `parent`/`enclosing_function` kwarg pair — callers pass a `CompoundContainer` reference instead.

3. **Speculative Generality**
   - In [`code2petri/viewer/__init__.py:45-95`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L45-L95), `generate_html` introduces redundant parameters `composite_net: Optional[Union[PetriNet, Dict[str, Any]]]` and `mode: Optional[str]`, forcing multiple overlapping resolution branches:
     ```python
     is_composite = (
         mode == "composite"
         or composite_net is not None
         or (isinstance(net_or_fold, PetriNet) and bool(getattr(net_or_fold, "compounds", None)) and mode is None)
     )
     ```
     Passing `composite_net` via `net_or_fold` directly would simplify the signature and eliminate mode ambiguities.
   - **Actionable Fix:** Drop `composite_net` and `mode` from the `generate_html` signature entirely. Detection becomes `is_composite = isinstance(net_or_fold, PetriNet) and bool(net_or_fold.compounds)` — a single truth-y check on the model itself. The caller (`engine.py`) already has the `PetriNet` with `compounds` populated; it just needs to pass it as `net_or_fold`. Delete both parameters and all dead branches they gate.

---

## Spec

### (a) Missing or Partial Requirements

1. **Expansion to Maximum Depth by Default:**
   - *Spec Line 3:* `"...the viewer receives a single pre-assembled composite net that already contains every callee's subnet at maximum depth."`
   - *Finding:* In [`code2petri/engine.py:82`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L82), `inline_depth` defaults to `1`. Multi-level call hierarchies (e.g., A $\to$ B $\to$ C) are only expanded to depth 1 by default; deeper subnets remain collapsed behind opaque transitions unless the user explicitly passes a higher `--inline-depth`.
   - **Actionable Fix:** When `ext == "html"` and composite mode is active, override `inline_depth` to a sentinel value (e.g., `sys.maxsize` or a dedicated constant `UNLIMITED_DEPTH = 999`) before calling `precompute_callee_nets`. This makes the default HTML export faithfully assemble the full transitive closure, matching the spec's intent, while `--inline-depth` can still cap it explicitly for large codebases.

2. **Explicit `--inline` Flag Required for HTML Composite Assembly:**
   - *Spec Line 9:* `"- [x] Running code2petri on a file with inlined function calls produces an HTML file whose viewer opens showing all callee subnets already present in the graph, not collapsed behind opaque transitions"`
   - *Finding:* In [`code2petri/engine.py:228`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L228), `is_composite_html` is only activated when `inline=True`. Running `code2petri` on a file with function calls without `--inline` still outputs the legacy fold viewer with opaque transitions.
   - **Actionable Fix:** When `ext == "html"` and `context` (Resolution Context) is provided, implicitly activate composite assembly without requiring `--inline`. Reserve `--inline` exclusively for the PNML/JSON flat expansion path. This aligns with the spec's statement that the viewer should show expanded callees whenever the HTML is generated with a Resolution Context available.

### (b) Scope Creep (Behaviour in Diff Not Asked For)

1. **Hardcoded Viewer Header Overrides:**
   - In [`code2petri/viewer/template.html:937-938`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L937-L938), `#info-step-title` and `#info-step-desc` are mutated to hardcoded strings (`"Composite Petri Net View"`). This was not requested in Ticket 29.
   - **Actionable Fix:** Replace the hardcoded strings with a `{{MODE_LABEL}}` template variable injected from `generate_html`. This removes the hardcoded mutation and opens the door for Ticket 26 (Display Current File) to populate the same slot dynamically with the filename.
2. **Silent Suppression of `--fold` Flag:**
   - In [`code2petri/engine.py:229`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L229), `is_composite_html` unconditionally forces `fold_active = False`. Passing `--fold` alongside `--inline` for HTML output is silently discarded without user notification or warning.
   - **Actionable Fix:** Add an explicit `logger.warning("--fold is not compatible with composite HTML output and will be ignored.")` immediately before the `fold_active = False` override. This satisfies the principle of faithful feedback without breaking behaviour.

### (c) Implementation Looks Wrong

1. **Compound Node Tap Handler Triggers Broken Relayout:**
   - *Spec Line 9:* `"- [x] Running code2petri on a file with inlined function calls produces an HTML file whose viewer opens showing all callee subnets already present in the graph, not collapsed behind opaque transitions"`
   - *Finding:* In [`code2petri/viewer/template.html:842-880`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L842-L880), compound containers are added with `classes: 'compound'`. The legacy tap handler (`if (expandedNodes.has(targetId) || targetNode.hasClass('compound'))`) catches clicks on pre-assembled containers, attempts to delete them from `expandedNodes` (where they do not reside), and calls `renderStep()`. The compound does not collapse, but the entire graph undergoes an unintended Cytoscape/Dagre re-layout and animation on click.
   - **Actionable Fix:** Guard the tap handler against pre-assembled compounds by checking for a distinguishing data attribute, e.g. `targetNode.data('composite_preassembled') === true`. Add `composite_preassembled: true` to all compound node data at injection time in `template.html`. Inside the tap handler, short-circuit immediately (`return;`) when this flag is present, preventing the erroneous `renderStep()` call and layout re-run.

---

## Summary

- **Standards:** 3 baseline smells (Duplicated Code across metadata decoration and property accessors, Primitive Obsession in compounds storage, Speculative Generality in `generate_html` parameters), 0 hard violations. Worst issue: Duplicated Code in hierarchy metadata decoration.
- **Spec:** 2 partial requirements (default depth limited to 1 vs maximum depth; `--inline` required to activate composite mode), 2 scope creep items, 1 implementation defect (clicking pre-assembled compound nodes triggers unintentional Cytoscape relayout). Worst issue: Default `inline_depth=1` failing to expand to maximum depth by default.
