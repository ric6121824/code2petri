# 20 — CLI Integration & Headless Fold/Inline Output

**What to build:** Wire the fold engine (Tickets 17–18) and inline expansion engine (Ticket 19) into the `code2petri` CLI and serialization pipeline, adding new flags and output behaviors.

A user can run `code2petri app.js -t stepCpu --fold -o net.json` and receive a JSON file with the `FoldResult` schema (initial net, fold steps, final SM score). A user can run `code2petri app.js -t stepCpu --fold -o net.dot` and receive the penultimate fold state rendered in DOT (well-structured components folded into dummy transitions, irreducible nodes fully exposed, SM score embedded in the graph title). A user can run `code2petri app.js -t loop --inline --context . -o composite.json` and receive a Composite Net with resolved callees spliced in. The SM score is printed to stderr whenever `--fold` is active. Commands without new flags produce identical output to Phase 2 (backward compatibility).

New CLI flags:
- `--fold`: Opt-in fold analysis. Implicitly activated by `.html` output (Ticket 21).
- `--no-fold`: Explicitly disables fold analysis (overrides `.html` implicit activation).
- `--weights <path_or_json>`: Overrides default `FoldConfig` penalty weights.
- `--inline`: Activates inline expansion (requires `--context`).
- `--inline-depth <N>`: Controls inline expansion depth (default 1).

Pipeline ordering: inline expansion runs first (if active), then fold analysis runs on the resulting net (if active).

**Blocked by:** 18 — Fold Reduction Engine & SM Computation, 19 — Inline Expansion Engine.

**Status:** complete

- [x] `--fold` flag added to `argparse` in the CLI; activates the fold engine on the generated `PetriNet` before serialization.
- [x] `--no-fold` flag added; overrides implicit `--fold` activation.
- [x] `--weights` flag added; accepts a file path or inline JSON string and constructs a `FoldConfig` with overridden $\rho$ values.
- [x] `--inline` flag added; activates inline expansion (raises an error if `--context` is not also provided).
- [x] `--inline-depth` flag added with default 1.
- [x] JSON output with `--fold` serializes the full `FoldResult` schema (not the raw `PetriNet` dict).
- [x] DOT/PNG/SVG output with `--fold` renders the penultimate fold state: dummy transitions visible with tau labels, irreducible nodes exposed, SM score in the graph title label.
- [x] PNML output with `--fold` serializes the penultimate fold state with dummy transitions carrying `<toolspecific>` metadata for component type and $\tau$.
- [x] SM score is printed to stderr (e.g., `Code2Petri: SM score = 42.0`) when `--fold` is active.
- [x] `--inline` combined with `--fold` runs inline expansion first, then fold analysis on the composite net.
- [x] Commands without `--fold` or `--inline` produce identical output to Phase 2 (backward compatibility).
- [x] `"opaque"` (superseding `"dummy"`) is added to `Transition.RESERVED_METADATA_KEYS` for canonical domain terminology consistency.
- [x] Integration tests verify: `--fold` JSON schema, `--fold` DOT penultimate state, `--no-fold` passthrough, `--weights` override changes SM score, `--inline` without `--context` raises error, backward-compatible output unchanged.
- [x] Existing tests continue to pass.
