# 39 — Viewer: Collapsed Compound State

**What to build:**
When all internal nodes of an inlined function compound node are reduced to a single transition, transition the container into a Collapsed Compound State styled like a closed folder showing the function name and component number.

**Blocked by:** 38 — JS Fold Engine: Unstructured Knot Isolation

**Status:** ready-for-agent

- [ ] Detects when an inlined function compound node's internal elements have fully collapsed into a single component
- [ ] Mutates the compound node visual state into a closed-container / folder presentation
- [ ] Displays label formatted as `function_name (c_XX)` on the collapsed container
- [ ] Internal elements are hidden while preserving parent-child association
