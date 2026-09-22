# 39 — Viewer: Collapsed Compound State

**What to build:** When the user folds all internal nodes of an inlined function down to a single component, the function's compound container automatically switches to a "closed folder" visual state. The container shrinks to a compact tile labelled with the function name and a component ID (`function_name (c_XX)`), clearly distinguishing it from a generic opaque transition created by folding individual places.

**Blocked by:** 38 — JS Fold Engine: Unstructured Knot Isolation

**Status:** ready-for-agent

- [ ] When all internal nodes of an inlined function compound node are reduced to a single component, the container transitions to the Collapsed Compound State automatically
- [ ] The collapsed container displays the label `function_name (c_XX)` where `c_XX` is the component identifier
- [ ] The internal nodes are hidden, leaving only the closed container visible on the canvas
- [ ] A Collapsed Compound State is visually distinct from a plain opaque transition
