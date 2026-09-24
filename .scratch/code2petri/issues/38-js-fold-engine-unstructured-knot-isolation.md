# 38 — JS Fold Engine: Unstructured Knot Isolation

**What to build:** When no structured reduction rule (Sequence, Choice, Loop, Marked Graph, State Machine, Well-Structured) applies to a region of the graph, the viewer identifies the smallest irreducible SESE knot and collapses only it — leaving the surrounding structured control flow intact and reducible. This matches the ProM reference fallback behaviour.

**Blocked by:** 37 — JS Fold Engine: Well-Structured SESE Reduction

**Status:** complete

- [x] When no structured rule matches, the viewer identifies and collapses only the minimal internal SESE subnet containing the irreducible cycle
- [x] The surrounding structured control flow remains on the canvas, still eligible for subsequent structured reductions
- [x] The unstructured component's tau is calculated using the ProM penalty formula ($5 \times (||F_C| - (|P_C| + |T_C|)| + 1)$)
- [x] If no internal SESE pair exists and more than one transition remains, the entire remaining net is collapsed as a final fallback
- [x] JS tau and omega values match the Python fold engine for the same topologies
