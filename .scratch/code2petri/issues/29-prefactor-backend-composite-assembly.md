# 29 — Prefactor: Backend Composite Assembly

**What to build:** When `code2petri` generates an HTML output file for a program with inlined callees, the viewer receives a single pre-assembled composite net that already contains every callee's subnet at maximum depth. The viewer opens in the fully-expanded state immediately without requiring the user to click anything.

**Blocked by:** None — can start immediately.

**Status:** complete

- [x] Running `code2petri` on a file with inlined function calls produces an HTML file whose viewer opens showing all callee subnets already present in the graph, not collapsed behind opaque transitions
- [x] Node hierarchy information (which nodes belong to which inlined function boundary) is present in the data payload and readable by JavaScript at load time
- [x] The pre-computed fold step playback slider is absent when composite mode is active
- [x] A composite net with at least two levels of nesting (A calls B calls C) is supported and verified
