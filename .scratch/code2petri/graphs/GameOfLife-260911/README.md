# Game of Life Simulator — Cross-File Petri Net Analysis (2026-09-11)

This directory contains the updated, **cross-file resolved** Petri net models for the [GameOfLife_Simulator](file:///Users/pingchungtsai/My%20Drive%20%28ric6121824%40gmail.com%29/Digital%20Media%20MSc/Semester%204/GameOfLife_Simulator) project (`app.js` and `webgl-engine.js`).

Compared to the initial baseline in [`GameOfLife-260907`](../GameOfLife-260907/), these nets leverage the new **Phase 2 Cross-File Reference Tracing** capabilities (`--context`):
1. **Cross-File Resolution**: Calls from `app.js` to `gpuEngine.step()` and `gpuEngine.randomize()` are automatically linked to `WebGLEngine.step` and `WebGLEngine.randomize` via constructor variable binding extraction ([ADR 0001](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0001-constructor-only-variable-resolution.md)).
2. **Visual Color-Coding**:
   - **Resolved Calls (Green Border, `#2e7d32`)**: Annotated with interactive SVG/DOT tooltips identifying the target function and target file path.
   - **External / Unresolved Calls (Orange Border, `#e65100`)**: Annotated with `tooltip="Unresolved call"` distinguishing project calls from browser/WebGL APIs (`requestAnimationFrame`, `gl.useProgram`, `gl.bindTexture`).
3. **Multi-Format Parity**: Each target includes `.dot`, `.svg`, `.png`, standardized ISO/IEC 15909 `.pnml` (with `<toolspecific>` metadata), and structured `.json`.

---

## Catalog of Generated Petri Nets

| Component | Target Function | Files | Key Characteristics & Cross-File Resolutions |
|---|---|---|---|
| **`app_loop`** | `loop()` in `app.js` | `app_loop.{dot,svg,png,pnml,json}` | **Recursive Game Loop**: Contains `gpuEngine.step()` (resolved to `WebGLEngine.step` in `webgl-engine.js`), `stepCpu()` (resolved to `stepCpu` in `app.js`), and `requestAnimationFrame(loop)` modeled as a mathematical back-arc cycle to `p0`. |
| **`app_randomizeBoth`** | `randomizeBoth()` in `app.js` | `app_randomizeBoth.{dot,svg,png,pnml,json}` | **Cross-File Seeding**: Sequential pipeline calling `createGrid()`, `drawCpuGrid()`, and `gpuEngine.randomize()` (resolved to `WebGLEngine.randomize` in `webgl-engine.js`). |
| **`app_stepCpu`** | `stepCpu()` in `app.js` | `app_stepCpu.{dot,svg,png,pnml,json}` | **CPU Cellular Automata**: Double-nested loop iterating over grid dimensions with neighbor sampling calling `countNeighbors()` (resolved in `app.js`). |
| **`app_init`** | `init()` in `app.js` | `app_init.{dot,svg,png,pnml,json}` | **Canvas & Engine Bootstrapping**: Calls `createGrid()`, `randomizeBoth()`, and `drawCpuGrid()`. |
| **`app_global`** | `(global)` in `app.js` | `app_global.{dot,svg,png,pnml,json}` | **Top-Level Execution**: Instantiates `gpuEngine = new WebGLEngine(...)`, invokes `init()`, and configures DOM event listeners. |
| **`webgl_step`** | `WebGLEngine.step()` in `webgl-engine.js` | `webgl_step.{dot,svg,png,pnml,json}` | **GPU Compute & Ping-Pong**: Sets up WebGL2 viewport, texture bindings, ping-pong pointer swaps, and calls `this.drawToScreen()` (resolved to `WebGLEngine.drawToScreen`). Browser GL calls marked as external boundaries (`#e65100`). |
| **`webgl_randomize`** | `WebGLEngine.randomize()` in `webgl-engine.js` | `webgl_randomize.{dot,svg,png,pnml,json}` | **Texture Seeding**: Generates random state buffer, calls `gl.texSubImage2D()`, and terminates in `this.drawToScreen()` (resolved). |
| **`webgl_drawToScreen`** | `WebGLEngine.drawToScreen()` in `webgl-engine.js` | `webgl_drawToScreen.{dot,svg,png,pnml,json}` | **Screen Blit**: Fullscreen quad rendering pipeline to default framebuffer. |
| **`webgl_constructor`** | `WebGLEngine.constructor()` in `webgl-engine.js` | `webgl_constructor.{dot,svg,png,pnml,json}` | **Engine Initialization**: Acquires WebGL2 rendering context, compiles shaders, configures vertex buffers, and pre-allocates textures. |

---

## File Summary
- Total Targets Analyzed: **9**
- Formats Per Target: **5** (`.dot`, `.svg`, `.png`, `.pnml`, `.json`)
- Total Artifacts Produced: **45 files**
