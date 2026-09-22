# 38 — JS Fold Engine: Unstructured Knot Isolation

**What to build:**
Client-side fallback reduction that isolates and collapses minimal irreducible SESE knots when no structured reduction rule applies.

**Blocked by:** 37 — JS Fold Engine: Well-Structured SESE Reduction

**Status:** ready-for-agent

- [ ] When structured rules cannot reduce a region, finds the minimal internal SESE pair containing >1 transition
- [ ] Collapses only the minimal knot into an opaque transition using ProM unstructured penalty formula
- [ ] If no internal SESE pair exists, falls back to reducing the remaining outer net if transitions > 1
- [ ] Surrounding workflow structure remains intact and reducible by earlier rules
