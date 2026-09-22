# 29 — Prefactor: Backend Composite Assembly

**What to build:**
Extend composite net generation to build a fully-wired Composite Net with enclosing function and hierarchy parent metadata embedded in each node. Update the HTML generation seam to accept this composite net structure in the data payload, making the fully expanded net available immediately on load.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Composite net generation assembles all inlined function subnets into a single Petri net data model with parent hierarchy metadata attached to nodes
- [ ] HTML generation accepts the composite net data and embeds it into the viewer payload
- [ ] When composite mode is active, the pre-computed step playback slider is disabled or omitted
- [ ] Automated tests verify hierarchy metadata preservation during recursive inlining
