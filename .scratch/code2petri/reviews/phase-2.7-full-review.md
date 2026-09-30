# Code Review: Phase 2.7 (Live Fold Reduction) — Comprehensive Review

**Branch:** `feature/live-fold-reduction-js-prototype`  
**Base Commit:** `82165ea` (`master`)  
**Diff:** `git diff master...HEAD` (46 files changed, 13,986 insertions(+), 123 deletions(-), 26 commits covering Tickets 29–42)  
**Master Spec:** [`.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md)  
**Ticket Specs:** Tickets 29 through 42 in [`.scratch/code2petri/issues/`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/issues/)  
**Standards:** [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) and Fowler 12-smell baseline  
**Test Suite:** All 98 unit tests in [`tests/test_html_viewer.py`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py) pass; full suite (`discover tests`) passes.

---

## Standards

### (a) Documented Standards Violations (Hard Violations)

**S1 — Domain Vocabulary: "Browser Download" / "File Download" ([`CONTEXT.md:27-30`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L27-L30))**
`CONTEXT.md` defines the domain term as **Client-Side Export** and explicitly lists *Avoid: Browser download, frontend save*.
- [`code2petri/viewer/prototype/pnml_exporter.js:109-113`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/pnml_exporter.js#L109-L113): JSDoc reads `"Triggers a browser file download..."` and function is named `downloadPnmlFile`.
- [`code2petri/viewer/template.html:1740`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1740): Retains `const downloadPnmlFile = exportClientSidePnml;`.
- [`tests/test_html_viewer.py:4529`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/tests/test_html_viewer.py#L4529): `def test_export_pnml_button_triggers_browser_download_headless(self):`.

> **Fix:** Rename `downloadPnmlFile` to `triggerClientSideExport` (or remove the alias). Update JSDoc and test method names to use `client_side_export` rather than `browser_download`.

**S2 — Prohibited Vocabulary in Master Spec / Documentation ([`CONTEXT.md:7-26`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md#L7-L26))**
[`.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/specs/phase-2.7-live-fold-reduction.md) contains terms explicitly listed in `CONTEXT.md` avoid lists:
- Line 31: `"- JS Reduction Engine:"` (Avoid: *JS reduction*)
- Line 35: `"Right-Click ...: Trigger Component-Local Unfold (non-linear local undo)."` (Avoid: *Local undo*)
- Line 47: `"...prevent premature macro collapsing."` (Avoid: *macro collapsing*)

> **Fix:** Align spec text with canonical domain terminology (**Live Fold Reduction**, **Component-Local Unfold**, **Structural Fold**).

---

### (b) Baseline Code Smells (Judgement Calls)

**S3 — Duplicated Code & Divergent Change: Dual JS Engines ([`prototype/reduction_engine.js`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/prototype/reduction_engine.js) vs [`template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L1933))**
The prototype directory maintains 1,171 lines of `LiveFoldReductionEngine` in `reduction_engine.js` (frozen at Ticket 33), while [`template.html`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html) grew to 4,456 lines containing the active engine through Ticket 42. Furthermore, `template.html` suffers from **Divergent Change**: CSS styles, Cytoscape event mapping, floating HUD UI, SESE reachability math, and PNML serialization are all maintained in a single HTML file.

> **Fix:** Extract the reduction engine and PNML serializer into dedicated JS modules in `code2petri/viewer/engine/` that are bundled or injected into `template.html` and reused by prototype runners and tests. Retire the orphaned `prototype/reduction_engine.js`.

**S4 — Refused Bequest / Middle Man: Dict Protocol on Domain Dataclass ([`code2petri/model.py:49-63`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/model.py#L49-L63))**
`CompoundContainer` is a domain dataclass, yet it implements `__getitem__`, `get`, `__contains__`, `keys`, and `items` purely because a single caller in [`code2petri/inline.py:150`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/inline.py#L150) accessed `{c["id"] for c in caller_net.compounds}`.

> **Fix:** Change `inline.py:150` to `c.id` and remove dictionary protocol methods from `CompoundContainer`.

**S5 — Primitive Obsession & Repeated Switches: Untyped Dicts in Viewer Assembly ([`code2petri/viewer/__init__.py:76-118`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/__init__.py#L76-L118))**
`generate_html` accepts `Union[PetriNet, FoldResult, dict]`, forcing repetitive `isinstance(net_or_fold, dict)` vs `PetriNet` branching and defensive `getattr(..., None)` lookups throughout the viewer entry point.

> **Fix:** Require typed `PetriNet` or `FoldResult` models at the viewer seam and eliminate raw dict support.

**S6 — Mysterious Name / Magic Number: `UNLIMITED_DEPTH = 999` ([`code2petri/engine.py:53, 217`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/engine.py#L53))**
`UNLIMITED_DEPTH: int = 999` uses an arbitrary integer to represent recursive inline expansion.

> **Fix:** Use `math.inf` or `max_depth: Optional[int] = None` where `None` explicitly signifies expansion until fixpoint.

---

## Spec

### (a) Missing or Partial Requirements

**P1 — Running SM Score Display Missing in Composite Viewer**
> Master Spec User Story 4: *"As an analyst, I want the browser to calculate the component penalty ($\omega$) and new transition weight ($\tau$) in real-time when I perform a Live Fold Reduction, so the cognitive complexity score remains mathematically rigorous."*  
> User Story 8: *"As a developer, I want to left-click a transition/component node to open a sidebar or modal, so I can view its metadata ($\tau$ weight, SM score, line number)."*

In [`template.html:4354-4360`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L4354-L4360), `#fold-controls` (which hosts `#val-sm`) is removed from the DOM in composite mode (`foldControls.remove()`). While `engine.calculateSMScore()` is calculated internally, the running SM score is never rendered or updated in the composite UI after live folds or unfolds. Furthermore, the HUD popover stat pills only display Tau, Type, and Line — omitting the SM score.

> **Fix:** Preserve `#badge-sm` in the viewer header during composite mode. In `handleFoldReduction` and `handleRightClickUnfold`, update `valSm.textContent = engine.calculateSMScore().toFixed(1)`. Add an SM score stat pill to the HUD popover.

---

### (b) Scope Creep (Unasked Behaviour in Diff)

**P2 — Macro SESE & Non-Place Reductions (Tickets 35–38)**
> Master Spec: *"- JS Reduction Engine: The core reduction algorithms from fold.py (specifically fold_single_place_contraction, fold_choice, and fold_while) will be rewritten in JavaScript..."*  
> Out of Scope: *"- Component-Centric Folding (Lasso / Shift-Click): ... the initial prototype will strictly implement Place-Centric Folding (Single-Place Contraction)."*

Tickets 35–38 implemented bidirectional SESE reachability, Marked Graph, State Machine, Well-Structured SESE, and Unstructured Knot isolation. Crucially, Marked Graph reduction attaches to *transitions* (`contractible-marked-graph`), directly exceeding the master spec's strict boundary of Place-Centric Folding.

> **Fix:** Formally update the Phase 2.7 Master Spec to incorporate Tickets 35–38 and transition triggers, aligning documented scope with the delivered prototype.

---

### (c) Requirements Implemented Incorrectly

**P3 — Left-Click Interaction Conflict on Transitions**
> Master Spec Interaction Mapping: *"- Left-Click (Transition/Component): Open sidebar for metadata inspection and node renaming."*

In [`template.html:4262-4266`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L4262-L4266):
```javascript
if (target.hasClass('transition') && target.hasClass('contractible-marked-graph')) {
  handleFoldReduction(target);
  return;
}
```
Left-clicking a transition with `contractible-marked-graph` immediately folds the subnet instead of opening the HUD popover, preventing the user from inspecting or renaming that transition.

> **Fix:** Left-clicking any transition should strictly open the HUD popover (`openInspector(node)`). Provide an explicit "Contract Marked Graph" action button inside the HUD rather than overloading left-click.

**P4 — Cross-Boundary Parent Hierarchy Loss on Nested Folds**
> Master Spec Decision: *"- Initial Assembly: Python's inline.py engine ... will inject hierarchy metadata (enclosing_function or explicit parent pointers) into the nodes..."*

In [`template.html:2605-2610`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/code2petri/viewer/template.html#L2605-L2610):
```javascript
if (parentSrc && parentSnk && parentSrc === parentSnk) {
  parentId = parentSrc;
} else {
  parentId = null;
}
```
When folding across boundaries between nested callee functions (e.g., function C nested inside function B), `parentId` defaults to `null`. This ejects the contracted component `c_XX` out to the canvas root rather than retaining it inside the enclosing parent compound container.

> **Fix:** Compute the lowest common ancestor (LCA) compound container of `parentSrc` and `parentSnk` instead of falling back to `null`.

---

## Summary

- **Standards:** 2 hard violations (lingering "browser download" vocabulary in prototype/tests, unaligned terms in master spec); 4 judgement calls (dual-engine duplication across `prototype/` and `template.html`, dict protocol emulation on `CompoundContainer`, untyped dict branching in `viewer/__init__.py`, `999` magic number). Worst: **S3** (3,600+ lines inlined in single `template.html` causing Divergent Change and prototype desync).
- **Spec:** 1 missing requirement (running SM score not visible in composite mode); 1 scope creep (macro SESE and transition fold triggers not reconciled with master spec); 2 incorrect implementations (left-click collision on Marked Graph transitions, nested compound parent ejection). Worst: **P3** (left-click collision preventing node inspection).
