# 12 — Constructor Variable Binding & Call Site Extraction

**What to build:** Teach language walkers to harvest constructor instantiations and emit structured call site records during function analysis. In multi-file object-oriented code, instance method calls (e.g. `gpuEngine.step()`) can only be linked if the walker records the instance receiver (`gpuEngine`) and connects it to the class binding (`WebGLEngine`). This ticket implements constructor variable binding harvesting across full file ASTs and extracts detailed `CallSite` records for every call statement.

**Blocked by:** 11 — Prefactor: WalkResult Protocol Return Type and Transition Metadata

**Status:** complete

- [x] `PythonWalker.collect_variable_bindings(tree)` extracts constructor assignments (`x = Foo(...)` and `self.x = Foo(...)`) into a `{variable_name: class_name}` map.
- [x] `JavascriptWalker.collect_variable_bindings(tree)` extracts constructor assignments (`const/let/var x = new Foo(...)` and `this.x = new Foo(...)`) into a `{variable_name: class_name}` map.
- [x] `PythonWalker.walk_function` populates `WalkResult.call_sites` with `CallSite` records capturing caller function, caller file, callee name, callee owner (if attribute call), line number, and corresponding transition ID.
- [x] `JavascriptWalker.walk_function` populates `WalkResult.call_sites` with `CallSite` records capturing caller function, caller file, callee name, callee owner (if MemberExpression call), line number, and corresponding transition ID.
- [x] Unit tests in `test_python_walker.py` and `test_javascript_walker.py` verify that `collect_variable_bindings` and `CallSite` extraction faithfully extract constructor targets and call records.
