# Called-function boundary folding: diagnostic replay

Related issue: [Ticket 53](../../issues/53-called-function-fold-boundary-trigger.md).

Original reported input: [aeroblasters_global_foldable.html](</Users/pingchungtsai/My Drive (ric6121824@gmail.com)/Digital Media MSc/Semester 4/Graph Data/output_code2petri/Aeroblasters-261010/aeroblasters_global_foldable.html>). The affected occurrences are one `BlinkingText.update()` and three `Message.update()` function compounds. "Opposite side" refers to graph connection direction.

This is a diagnostic fixture, not an implemented fix or a replacement for the generated-viewer regression suite. It uses the repository's actual reduction engine and highlight function with two stripped post-fold graph shapes captured from the reported Aeroblasters viewer. Each case has seven nodes (including the function container) and six arcs. No original source path, generated HTML, or temporary files are required.

From the repository root:

```sh
node .scratch/code2petri/debug/called-function-boundary-folding/repro.cjs
```

On 2026-10-10 both cases returned `internalFoldType: null`, `internalGreen: false`, `complete: false`, and `collapsed: false`; the command exited 1. A successful implementation must expose an eligible internal place and complete each function while retaining the two caller-owned boundary places.

The fixtures retain opaque-node flags but intentionally omit earlier fold history. Full history, nested unfolding, weights/SM, and the sidebar/viewport must be tested through the existing generated-viewer seam before closing the issue.

## Controlled probe results

The probes changed only an in-memory copy of the reported HTML's engine, which matched the repository engine. They did not modify the HTML or runtime source.

1. Bypassing the two Choice function-boundary checks made the exit-side split eligible. Choice followed by Sequence completed the `BlinkingText.update()` remainder.
2. With that same bypass, the entrance-side merge still had no eligible internal place. Directly applying Choice at the exterior entrance and then calling Fold-Entire-Function completed the `Message.update()` remainder and preserved both caller boundary places.
3. Bypassing only elementary-reduction priority did not expose a reduction at either internal place. The baseline had no elementary reductions, so priority did not cause the observed stall.

These bypasses identify the obstruction; they are not a safe patch. An implementation must validate ownership of every consumed transition, retain boundary places as anchors, and reject caller/sibling consumption or mixing unresolved functions.
