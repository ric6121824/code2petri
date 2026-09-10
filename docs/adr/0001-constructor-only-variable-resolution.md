# Constructor-Only Variable Resolution for Cross-File Calls

We decided to implement lightweight, file-wide constructor-assignment tracking (`const x = new Foo(...)` and `x = Foo(...)`) directly within language walkers rather than performing full static type analysis or coupling code2petri to code2flow's internal variable model. This decision provides sufficient class resolution for instance method calls (such as `gpuEngine.step()` resolving to `WebGLEngine.step` in the GameOfLife simulator) while maintaining clean separation between the two sibling tools and avoiding the overhead of multi-pass semantic type inference.

## Status

Accepted

## Considered Options

- **Full variable analysis / reuse code2flow model**: Coupled code2petri walkers to code2flow's internal `Node` and `Variable` structures, increasing architectural entanglement and requiring dual-pass parsing.
- **Pure method name matching (no variable tracking)**: Matching on callee method name alone without instance owner resolution, which causes false-positive links when different classes define identical method names.
- **Lightweight constructor tracking in walkers**: Scanning top-level and function-level constructor instantiations via a dedicated `collect_variable_bindings` walker method, providing deterministic resolution for canonical instantiation patterns.

## Consequences

Direct constructor instantiations will cleanly resolve cross-file method invocations across both JavaScript and Python. However, dynamic dependency injection, factory methods, reassignments, or complex aliasing across module boundaries will remain unresolvable and will degrade gracefully to annotated opaque transitions marked `[unresolved]`.
