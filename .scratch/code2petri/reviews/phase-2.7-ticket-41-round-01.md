# Code Review — Ticket 41, Round 01

**Commit:** `361c694 feat(viewer): implement component node renaming via floating HUD (ticket 41)`
**Diff:** `git diff 58d55b9...HEAD`
**Spec:** `.scratch/code2petri/issues/41-viewer-component-node-renaming-hud.md`
**Standards:** `CONTEXT.md` + Fowler 12-smell baseline
**Tests:** 90 pass

---

## Standards

### (a) Documented Standards Violations (Hard Standards)

**S1 — Vocabulary: `saveInspectorName` / HUD labels don't use domain term (CONTEXT.md, Component Node Renaming)**
`saveInspectorName` names the event handler after UI plumbing ("inspector") rather than the domain operation. The HUD title ("Node Inspector") and label field ("Name / Label:") also avoid the CONTEXT.md term.

> **Fix:** Rename the local function to `applyComponentNodeRename` (or `commitNodeRenaming`). Update the HUD `<h3>` title to "Component Node Renaming" and the label field to "Name:".

### (b) Baseline Code Smells (Judgement Calls)

**S2 — Duplicated Code: DOM element resolution duplicated across `openInspector` and `saveInspectorName`**
The same four-element defensive-lookup pattern (`inputEl`, `labelEl`, `tauEl`, `typeEl`) is copy-pasted into both functions:
```js
const inputEl = typeof inspectorInput !== 'undefined' && inspectorInput
  ? inspectorInput
  : (typeof document !== 'undefined' ? document.getElementById('hud-input-label') : null);
```

> **Fix:** Extract a single `_resolveHudElements(refs)` helper that accepts the closure-captured element refs and returns `{ inputEl, labelEl, tauEl, typeEl, lineEl }`. Call it from both sites.

**S3 — Data Clumps: `_rememberCustomName` / `executeSinglePlaceContraction` cascade over six field shapes for one concept**
The key-lookup waterfall probes `consumedSubnet.consumedPlaceId`, `.placeId`, `.headPlaceId`, `.splitPlaceId`, `sourcePlaceId__targetPlaceId`, sorted `consumedTransIds`, then walks `consumedSubnet.nodes` — six representations of "what consumed-subnet is this?". This cluster wants a canonical identity.

> **Fix:** Introduce a private `_consumedSubnetKey(consumedSubnet)` factory that encodes a single deterministic key from the subnet record (e.g. `consumedTransIds` sorted + joined). All lookup and registration sites call it. Delete the waterfall.

**S4 — Speculative Generality: lazy `|| new Map()` guard appears twice**
```js
this.rememberedCustomNames = this.rememberedCustomNames || new Map();
```
The guard fires on every call because the map is never initialised at construction time.

> **Fix:** Add `this.rememberedCustomNames = new Map();` to the constructor body alongside other instance fields. Remove both lazy guards.

**S5 — Mysterious Name: `tKey` / `pKey`**
Single-letter-prefixed composite IDs give no signal about what they key.

> **Fix:** Rename to `consumedTransKey` and `consumedPlaceKey` respectively.

---

## Spec

### (a) Missing or Partial Requirements

**P1 — Source line number pill always shows `—` for folded components**
> Spec: "The HUD displays tau weight, component type, and source line number as compact stat pills"

`getInspectorData` reads `node.data('source_line') || node.data('line_number') || '—'`. Opaque/component nodes from the JS fold engine carry neither attribute — those fields live on raw transition nodes from the Python backend. The pill will always show `—` for any folded component.

> **Fix:** During fold execution, record `sourceLineNumber` on the component node's data — either (a) inherit the earliest `source_line` from among the consumed transitions, or (b) store the range as `"L{min}–L{max}"`. Write it with `cy.add({ data: { ..., source_line: ... } })` when the opaque node is created, and update the read path in `getInspectorData` accordingly. Add a test asserting that a folded node's HUD shows a non-`—` line number.

### (b) Scope Creep

**P2 — Auto-save fires on `input change` (blur transition) — no explicit save action required**
> Spec: "Saving a new name updates the node's displayed label" (implies deliberate save); AC 5: "The HUD closes when the user clicks elsewhere"

The `change` event commits the rename on every focus-blur cycle, even when the user meant to cancel by clicking away.

> **Fix:** Remove the `change` listener. Keep only the explicit Save button click and Enter-key handler. Clicking elsewhere should close the HUD and discard any uncommitted text (restore the input to `node.data('label')` before hiding).

**P3 — `canSinglePlaceContract` / `executeSinglePlaceContraction` refactored to accept string IDs**
Both engine methods were extended to accept either a node object or a string ID. This is a non-trivial engine API change with no basis in the T41 spec.

> **Fix:** Revert the overloading. If the HUD's save path needs to look up a node by ID, do the lookup at the call site (`cy.getElementById(id)`) before calling the method, keeping the method's contract unchanged.

**P4 — HUD closes on tap of a non-contractable place node**
> Spec: "The HUD closes when the user clicks elsewhere on the canvas"

The new `tap` handler also dismisses the HUD when the user taps a place node that fails `canSinglePlaceContract`. A place node is a graph element, not "elsewhere on the canvas."

> **Fix:** Scope the close trigger to the canvas background only by checking `e.target === cy` before closing, rather than firing on any node-tap that happens to fall through.

### (c) Requirements Implemented but Look Wrong

**P5 — `_rememberCustomName` composite keys will produce false-positive matches across adjacent folds**
> Spec: "A renamed component retains its custom label after being unfolded and re-folded"

Keys are built from `consumedTransIds.slice().sort().join('__')` and `sourcePlaceId__targetPlaceId`. When two folds in a chain share overlapping transition sets or boundary places (e.g. sequential sequence contractions), a rename on one component silently bleeds onto a re-fold of an adjacent component. The test harness only exercises disjoint nets, so the collision is invisible.

> **Fix:** Use the opaque node's **own stable ID** (`c_XX`, assigned by the fold-time counter) as the canonical rename key. Store as `this.rememberedCustomNames.set(opaqueNodeId, name)`. At re-fold time, look up `rememberedCustomNames.get(newOpaqueNodeId)` only if the new node was produced from the same original fold record. Add a test with two adjacent folds sharing a boundary place, asserting that renaming one does not affect the other.

---

## Summary

**Standards:** 5 findings — 1 hard (vocabulary: `saveInspectorName` / HUD labels vs CONTEXT.md domain term); 4 judgement calls (Duplicated DOM resolution, Data Clumps key cascade, Speculative lazy guard, Mysterious `tKey`/`pKey`). Worst: S3 (Data Clumps — six-shape key waterfall in `_rememberCustomName`).

**Spec:** 5 findings — 1 missing (source line number never populated for folded nodes); 3 scope creep (auto-save on blur, engine API change, extended HUD close trigger); 1 wrong (key collision in `_rememberCustomName` — silent label bleed across adjacent folds, undetected by tests). Worst: P5 (composite key collision — correctness bug with no test coverage).
