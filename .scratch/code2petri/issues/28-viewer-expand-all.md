# 28 — Multi-Level Deep Expand All Resolved Calls Control

**What to build:** An "Expand All" / "Collapse All" control in the HTML viewer that expands resolved calls to arbitrary depth — expanding callees inside callees down to every level of the call tree without limit (up to cycle/recursion guards) — providing an immediate, fully unrolled total project overview without manual point-and-click.

**Blocked by:** None — can start immediately

**Status:** resolved

- [ ] Backend Precomputation: When generating HTML output, `precompute_callee_nets` recursively discovers and embeds callee nets to the full transitive closure across all nesting levels (or respects an unlimited/high depth default when HTML is requested), guarded against recursive call cycles.
- [ ] Dedicated UI Control: An "Expand All" / "Collapse All" button is placed in the viewer header next to the existing navigation controls.
- [ ] Deep Transitive Expansion: Clicking "Expand All" runs a fixed-point expansion loop: it repeatedly finds all unexpanded resolved call transitions across all currently visible subnets, expands them using their embedded callee nets, and repeats until no expandable transitions remain (or recursion guards prevent further expansion).
- [ ] Cytoscape Layout Re-run: After the full multi-level expansion reaches a fixed point, the `dagre` layout re-runs once so the entire multi-level nested compound graph is laid out cleanly.
- [ ] Collapse All: Clicking "Collapse All" collapses all compound nodes back to the root level model.
- [ ] Automated Tests: Headless viewer tests verify that clicking "Expand All" on a multi-level nested call graph (e.g. A -> B -> C -> D) unrolls all 3 levels of compound subnets into the DOM.

## Answer

Superseded by Phase 2.7 Tickets 29–30: the viewer now boots directly into the fully expanded composite hierarchy, so a separate Expand All / Collapse All control is not needed. See the [grand roadmap](../grand_plan.md).
