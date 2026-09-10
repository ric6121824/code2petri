# 15 — GameOfLife Simulator Cross-File Validation

**What to build:** Validate cross-file reference tracing against the primary validation target, the multi-file `GameOfLife_Simulator`. This test proves the real-world utility of the feature by analyzing functions in `app.js` with `webgl-engine.js` as resolution context, verifying that WebGL engine method calls cross file boundaries accurately while browser APIs remain cleanly unresolved.

**Blocked by:** 14 — CLI Context Ingestion & Reference Serialization

**Status:** ready-for-agent

- [ ] Integration test analyzes `loop` in `app.js` with `--context webgl-engine.js`, asserting `gpuEngine.step()` resolves to `WebGLEngine.step` in `webgl-engine.js`.
- [ ] Integration test analyzes `init` in `app.js` with directory context `--context ./tests/test_code/game_of_life/`, asserting `gpuEngine.randomize()` and `gpuEngine.drawToScreen()` resolve to `WebGLEngine.randomize` and `WebGLEngine.drawToScreen`.
- [ ] Integration tests verify that calls to browser and WebGL APIs (`document.getElementById`, `gl.bindTexture`, `requestAnimationFrame`) are marked with `resolved: False`.
- [ ] Serialized PNML, DOT, and JSON outputs for `GameOfLife_Simulator` functions reflect correct cross-reference annotations.
- [ ] All unit, integration, and validation tests across the entire test suite pass cleanly.
