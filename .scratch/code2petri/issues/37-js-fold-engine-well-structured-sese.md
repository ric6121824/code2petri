# 37 — JS Fold Engine: Well-Structured SESE Reduction

**What to build:** The user can trigger a Well-Structured reduction that collapses a SESE subnet which is free from PT/TP handles and internal cycles — representing general structured control flow that doesn't fit the more specific Marked Graph or State Machine patterns.

**Blocked by:** 36 — JS Fold Engine: Marked Graph + State Machine Reductions

**Status:** complete

- [x] Well-Structured SESE subnets (free of PT/TP handles and internal cycles) are detected and their boundary nodes are visually highlighted
- [x] Triggering the reduction collapses the subnet into a single opaque component
- [x] JS tau and omega values match the Python fold engine for the same topology
- [x] The resulting component stores enough information to restore the original subnet on demand
