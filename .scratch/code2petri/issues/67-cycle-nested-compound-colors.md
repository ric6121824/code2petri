# 67: Cycle Nested Compound Colors

**What to build:** Make expanded called-function compounds repeat green, blue, and purple by nesting depth, keeping parent and child visually distinct at any depth. Reserve orange for unresolved call transitions and retain the existing brown/gold collapsed-compound appearance, including when opening older sessions.

**Blocked by:** None (can start immediately).

**Status:** ready-for-human

- [x] Use the existing green, blue, and purple palette cyclically: depth zero green, one blue, two purple, three green, four blue, five purple, and repeat at arbitrary depth. Siblings at the same depth share a color.
- [x] Derive presentation from the active compound parent hierarchy and use depth modulo three only for palette selection. Do not clamp or overwrite semantic depth, change ownership, or restart depth-dependent padding.
- [ ] Apply coherent expanded background, border, and label/text-background styling in the existing light theme. Parent and child differ visually; deeper expanded compounds never use the orange palette slot.
- [ ] Preserve ordinary unresolved-call transitions' orange styling and all type-specific reduction affordances. Fully collapsed compounds retain the existing brown/gold override independent of their depth.
- [ ] Apply the same convention at fresh generated-viewer boot, runtime expansion, Component-Local Unfold, Reset, playback, and Open Session.
- [ ] On opening older compatible sessions, recompute active presentation from hierarchy rather than trusting legacy clamped color classes. Local unfolding must likewise normalize restored compounds. No source access or session schema migration is required.
- [ ] Styling does not mutate unopened snapshot input, detached captures, or stored restoration history, and does not change graph topology, parent/depth metadata, nested padding, tokens, names, fold eligibility/actions, component weights/SM, or viewport.
- [ ] Verify actual rendered colors and readable labels in the generated browser viewer at depths zero through at least eight, including equal-depth siblings, distinct parent/child pairs, collapsed overrides, and unresolved orange transitions. CSS string matching alone is insufficient.
- [ ] Cover the Dots & Boxes shape where depth-four GameState._coerce_direction() and depth-three GameState._edge_for_move() formerly shared orange, using a self-contained fixture rather than the user's export path.
- [ ] Cover an older snapshot with a legacy depth-three class on a deeper compound, local unfold restoring old classes, runtime expansion, Reset/playback, and save/open continuation; assert canonical active colors and preserved analysis/session state.

## Context and decisions

The current palette clamps depths three and above to the same orange class. The reported _coerce_direction() compounds have true depth four but carry that legacy depth-three class. This follow-up changes presentation only, independently of structural function-fold eligibility.

This belongs to Phase 2.7's Nested Compound Nodes presentation, extending delivered Ticket 30 without reopening it. [Ticket 66](./66-function-scoped-structural-folding.md) separately handles structural function folding in Phase 2.8; neither ticket blocks the other.

See the [Phase 2.7 specification](../specs/phase-2.7-live-fold-reduction.md).

### 2026-10-13 — Implementation

Implemented cyclic expanded compound classes and separate depth-padding classes. Initial element generation is covered headlessly for depths zero through eight, sibling consistency, hierarchy, and exact semantic depth. CSS keeps the collapsed brown/gold override and removes the expanded orange depth class. Actual browser colors, labels, legacy-session restoration, runtime expansion/reset/playback, and session-history preservation remain pending; keep this ticket ready for human verification.

The final full suite ran 576 tests with 1 failure and 4 errors: the prototype runner could not bind its test port; optional `pygraphviz` and `pytest` dependencies are unavailable; and two pre-existing integration expectations disagree with current return shapes (`PetriNet.initial_net` and two-value `WalkerProtocol` unpacking). Focused regression suites and `compileall` passed.

## Comments

- 2026-10-13: User approved green/blue/purple cycling by depth, equal colors for siblings, no orange expanded compound slot, and retention of brown/gold collapsed compounds. Published locally with to-spec and to-tickets.
