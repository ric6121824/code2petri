import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from code2petri.model import PetriNet, Transition, CallResolution
from code2petri.walker_protocol import CallSite, WalkResult
from code2petri.symbol_table import Symbol, SymbolTable, normalize_language


class TestSymbolTableIndexing(unittest.TestCase):
    def setUp(self):
        self.table = SymbolTable()
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")

    def test_normalize_language(self):
        self.assertEqual(normalize_language(".py"), "python")
        self.assertEqual(normalize_language("Python"), "python")
        self.assertEqual(normalize_language(".js"), "javascript")
        self.assertEqual(normalize_language("JAVASCRIPT"), "javascript")
        self.assertEqual(normalize_language(".unknown"), ".unknown")

    def test_index_javascript_files(self):
        self.table.index_file(self.app_js)
        self.table.index_file(self.webgl_js)

        js_symbols = self.table.get_symbols(language="javascript")
        py_symbols = self.table.get_symbols(language="python")
        self.assertEqual(len(py_symbols), 0)
        self.assertGreater(len(js_symbols), 0)

        # Check app.js symbols
        app_symbols = self.table.get_symbols_for_file(self.app_js)
        app_names = {s.name for s in app_symbols}
        self.assertIn("loop", app_names)
        self.assertIn("init", app_names)
        self.assertIn("stepCpu", app_names)
        self.assertIn("randomizeBoth", app_names)

        # Check variable bindings extracted for app.js
        bindings = self.table.get_variable_bindings(self.app_js)
        self.assertEqual(bindings.get("gpuEngine"), "WebGLEngine")

        # Check webgl-engine.js symbols
        webgl_symbols = self.table.get_symbols_for_file(self.webgl_js)
        webgl_names = {s.name for s in webgl_symbols}
        self.assertIn("WebGLEngine.step", webgl_names)
        self.assertIn("WebGLEngine.randomize", webgl_names)
        self.assertIn("WebGLEngine.drawToScreen", webgl_names)
        self.assertIn("WebGLEngine.initShaders", webgl_names)

        # Verify Symbol attributes
        step_sym = next(s for s in webgl_symbols if s.name == "WebGLEngine.step")
        self.assertEqual(step_sym.bare_name, "step")
        self.assertEqual(step_sym.class_name, "WebGLEngine")
        self.assertEqual(step_sym.language, "javascript")
        self.assertEqual(step_sym.filepath, self.webgl_js)
        self.assertGreater(step_sym.line_number, 0)

    def test_index_python_file(self):
        py_file = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "petri_py", "mixed_pipeline.py")
        )
        self.table.index_file(py_file)

        py_symbols = self.table.get_symbols(language="python")
        py_names = {s.name for s in py_symbols}
        self.assertIn("mixed_pipeline_func", py_names)
        self.assertIn("helper_calc", py_names)
        self.assertIn("secondary_func", py_names)

        calc_sym = next(s for s in py_symbols if s.name == "helper_calc")
        self.assertEqual(calc_sym.bare_name, "helper_calc")
        self.assertIsNone(calc_sym.class_name)
        self.assertEqual(calc_sym.language, "python")
        self.assertEqual(calc_sym.filepath, py_file)

    def test_index_files_sequence(self):
        self.table.index_files([self.app_js, self.webgl_js])
        lookup_res = self.table.lookup("WebGLEngine.step", language="javascript")
        self.assertEqual(len(lookup_res), 1)
        self.assertEqual(lookup_res[0].name, "WebGLEngine.step")


class TestCrossLanguageIsolation(unittest.TestCase):
    def setUp(self):
        self.table = SymbolTable()
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create Python file defining calculate()
        self.py_file = os.path.join(self.temp_dir.name, "worker.py")
        with open(self.py_file, "w", encoding="utf-8") as f:
            f.write("def calculate():\n    return 42\n")

        # Create JavaScript file defining calculate()
        self.js_file = os.path.join(self.temp_dir.name, "worker.js")
        with open(self.js_file, "w", encoding="utf-8") as f:
            f.write("function calculate() {\n    return 42;\n}\n")

        self.table.index_files([self.py_file, self.js_file])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_python_call_cannot_match_javascript_symbol(self):
        # A Python caller calls calculate()
        cs = CallSite(
            caller_function="main",
            caller_file=self.py_file,
            callee_name="calculate",
            callee_owner=None,
            line_number=1,
            transition_id="t1",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.language, "python")
        self.assertEqual(resolved.filepath, self.py_file)

        # Explicitly asking with language="python"
        resolved_py = self.table.resolve_call(cs, language="python")
        self.assertIsNotNone(resolved_py)
        self.assertEqual(resolved_py.language, "python")

    def test_javascript_call_cannot_match_python_symbol(self):
        # A JavaScript caller calls calculate()
        cs = CallSite(
            caller_function="run",
            caller_file=self.js_file,
            callee_name="calculate",
            callee_owner=None,
            line_number=1,
            transition_id="t1",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.language, "javascript")
        self.assertEqual(resolved.filepath, self.js_file)

    def test_strict_language_rejection(self):
        # If JS file calls something only present in Python, it must NOT match
        temp_py = os.path.join(self.temp_dir.name, "py_only.py")
        with open(temp_py, "w", encoding="utf-8") as f:
            f.write("def python_exclusive():\n    pass\n")
        self.table.index_file(temp_py)

        cs = CallSite(
            caller_function="run",
            caller_file=self.js_file,
            callee_name="python_exclusive",
            callee_owner=None,
            line_number=1,
            transition_id="t2",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNone(resolved)


class TestVariableBindingCallResolution(unittest.TestCase):
    def setUp(self):
        self.table = SymbolTable()
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")
        self.table.index_files([self.app_js, self.webgl_js])

    def test_resolve_variable_binding_receiver(self):
        # In app.js, gpuEngine.step() where gpuEngine = new WebGLEngine(...)
        cs = CallSite(
            caller_function="loop",
            caller_file=self.app_js,
            callee_name="step",
            callee_owner="gpuEngine",
            line_number=117,
            transition_id="t_step",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.name, "WebGLEngine.step")
        self.assertEqual(resolved.filepath, self.webgl_js)
        self.assertEqual(resolved.language, "javascript")

    def test_resolve_this_receiver(self):
        # In webgl-engine.js, this.drawToScreen() inside WebGLEngine.step
        cs = CallSite(
            caller_function="WebGLEngine.step",
            caller_file=self.webgl_js,
            callee_name="drawToScreen",
            callee_owner="this",
            line_number=194,
            transition_id="t_draw",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.name, "WebGLEngine.drawToScreen")
        self.assertEqual(resolved.filepath, self.webgl_js)

    def test_resolve_python_self_receiver(self):
        table = SymbolTable()
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        service_py = os.path.join(temp_dir.name, "service.py")
        with open(service_py, "w", encoding="utf-8") as f:
            f.write(
                "class TaskService:\n"
                "    def execute(self):\n"
                "        self.run_internal()\n"
                "    def run_internal(self):\n"
                "        pass\n"
            )
        table.index_file(service_py)

        cs = CallSite(
            caller_function="TaskService.execute",
            caller_file=service_py,
            callee_name="run_internal",
            callee_owner="self",
            line_number=3,
            transition_id="t_internal",
        )
        resolved = table.resolve_call(cs)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.name, "TaskService.run_internal")
        self.assertEqual(resolved.filepath, service_py)

    def test_unbound_receiver_returns_none(self):
        # gl.bindTexture() has no class binding
        cs = CallSite(
            caller_function="WebGLEngine.step",
            caller_file=self.webgl_js,
            callee_name="bindTexture",
            callee_owner="gl",
            line_number=120,
            transition_id="t_gl",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNone(resolved)


class TestBareFunctionCallResolution(unittest.TestCase):
    def setUp(self):
        self.table = SymbolTable()
        self.temp_dir = tempfile.TemporaryDirectory()

        self.main_py = os.path.join(self.temp_dir.name, "main.py")
        with open(self.main_py, "w", encoding="utf-8") as f:
            f.write(
                "def local_helper():\n"
                "    return 1\n"
                "def caller():\n"
                "    local_helper()\n"
                "    remote_unique()\n"
                "    ambiguous_func()\n"
            )

        self.lib1_py = os.path.join(self.temp_dir.name, "lib1.py")
        with open(self.lib1_py, "w", encoding="utf-8") as f:
            f.write(
                "def remote_unique():\n"
                "    return 2\n"
                "def ambiguous_func():\n"
                "    return 3\n"
            )

        self.lib2_py = os.path.join(self.temp_dir.name, "lib2.py")
        with open(self.lib2_py, "w", encoding="utf-8") as f:
            f.write(
                "def ambiguous_func():\n"
                "    return 4\n"
            )

        self.table.index_files([self.main_py, self.lib1_py, self.lib2_py])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_local_file_definition_priority(self):
        # Calls local_helper() defined in main.py
        cs = CallSite(
            caller_function="caller",
            caller_file=self.main_py,
            callee_name="local_helper",
            callee_owner=None,
            line_number=4,
            transition_id="t_local",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.name, "local_helper")
        self.assertEqual(resolved.filepath, self.main_py)

    def test_unique_context_file_resolution(self):
        # Calls remote_unique() defined only in lib1.py
        cs = CallSite(
            caller_function="caller",
            caller_file=self.main_py,
            callee_name="remote_unique",
            callee_owner=None,
            line_number=5,
            transition_id="t_remote",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.name, "remote_unique")
        self.assertEqual(resolved.filepath, self.lib1_py)

    def test_ambiguous_matches_return_none(self):
        # Calls ambiguous_func() defined in both lib1.py and lib2.py
        cs = CallSite(
            caller_function="caller",
            caller_file=self.main_py,
            callee_name="ambiguous_func",
            callee_owner=None,
            line_number=6,
            transition_id="t_ambig",
        )
        with self.assertLogs("code2petri", level="DEBUG") as log_ctx:
            resolved = self.table.resolve_call(cs)
        self.assertIsNone(resolved)
        self.assertTrue(any("ambiguous" in msg.lower() for msg in log_ctx.output))

    def test_missing_match_returns_none(self):
        # Calls non_existent_api()
        cs = CallSite(
            caller_function="caller",
            caller_file=self.main_py,
            callee_name="non_existent_api",
            callee_owner=None,
            line_number=7,
            transition_id="t_none",
        )
        with self.assertLogs("code2petri", level="DEBUG") as log_ctx:
            resolved = self.table.resolve_call(cs)
        self.assertIsNone(resolved)
        self.assertTrue(any("unresolved" in msg.lower() for msg in log_ctx.output))

    def test_bare_call_does_not_match_class_method(self):
        # A file has a class with method `step()`.
        # A bare call `step()` must not resolve to `MyClass.step`.
        class_file = os.path.join(self.temp_dir.name, "my_class.py")
        with open(class_file, "w", encoding="utf-8") as f:
            f.write(
                "class MyClass:\n"
                "    def step(self):\n"
                "        pass\n"
            )
        self.table.index_file(class_file)
        cs = CallSite(
            caller_function="caller",
            caller_file=self.main_py,
            callee_name="step",
            callee_owner=None,
            line_number=10,
            transition_id="t_step",
        )
        resolved = self.table.resolve_call(cs)
        self.assertIsNone(resolved)

        # Also test local class method: if caller file itself has a class with a method,
        # bare call still must not resolve to it.
        local_class_file = os.path.join(self.temp_dir.name, "local_class.py")
        with open(local_class_file, "w", encoding="utf-8") as f:
            f.write(
                "class LocalEngine:\n"
                "    def run(self):\n"
                "        pass\n"
                "def caller():\n"
                "    run()\n"
            )
        self.table.index_file(local_class_file)
        cs_local = CallSite(
            caller_function="caller",
            caller_file=local_class_file,
            callee_name="run",
            callee_owner=None,
            line_number=5,
            transition_id="t_run",
        )
        self.assertIsNone(self.table.resolve_call(cs_local))


class TestTransitionDecoration(unittest.TestCase):
    def setUp(self):
        self.table = SymbolTable()
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")
        self.table.index_files([self.app_js, self.webgl_js])

    def test_resolve_call_sites_decorates_net(self):
        net = PetriNet()
        p0 = net.add_place("p0", initial_tokens=1)
        p1 = net.add_place("p1")
        p2 = net.add_place("p2")

        t_res = net.add_transition("t_res", label="call: gpuEngine.step()", line_number=117)
        t_unres = net.add_transition("t_unres", label="call: requestAnimationFrame()", line_number=125)

        net.add_arc(p0, t_res)
        net.add_arc(t_res, p1)
        net.add_arc(p1, t_unres)
        net.add_arc(t_unres, p2)

        call_sites = [
            CallSite(
                caller_function="loop",
                caller_file=self.app_js,
                callee_name="step",
                callee_owner="gpuEngine",
                line_number=117,
                transition_id="t_res",
            ),
            CallSite(
                caller_function="loop",
                caller_file=self.app_js,
                callee_name="requestAnimationFrame",
                callee_owner=None,
                line_number=125,
                transition_id="t_unres",
            ),
        ]

        self.table.resolve_call_sites(net, call_sites)

        # Verify t_res metadata and resolution
        self.assertIsNotNone(t_res.metadata)
        self.assertTrue(t_res.metadata.get("resolved"))
        self.assertEqual(t_res.metadata.get("resolved_to"), "WebGLEngine.step")
        self.assertEqual(t_res.metadata.get("target_file"), self.webgl_js)
        self.assertIsNotNone(t_res.resolution)
        self.assertTrue(t_res.resolution.resolved)
        self.assertEqual(t_res.resolution.resolved_to, "WebGLEngine.step")
        self.assertEqual(t_res.resolution.target_file, self.webgl_js)

        # Verify t_unres metadata and resolution
        self.assertIsNotNone(t_unres.metadata)
        self.assertFalse(t_unres.metadata.get("resolved"))
        self.assertIsNotNone(t_unres.resolution)
        self.assertFalse(t_unres.resolution.resolved)

        # Verify Serialization Formats
        # 1. PNML
        pnml = net.to_pnml()
        self.assertIn('<toolspecific tool="code2petri" version="1.0">', pnml)
        self.assertIn('<resolved target="WebGLEngine.step"', pnml)
        self.assertIn('<unresolved />', pnml)

        # 2. DOT
        dot = net.to_dot()
        self.assertIn('color="#2e7d32"', dot)  # resolved
        self.assertIn('color="#e65100"', dot)  # unresolved
        self.assertIn('tooltip="Resolved to WebGLEngine.step in', dot)
        self.assertIn('tooltip="Unresolved call"', dot)

        # 3. JSON
        d = net.to_dict()
        t_res_dict = next(t for t in d["transitions"] if t["id"] == "t_res")
        self.assertTrue(t_res_dict["resolved"])
        self.assertEqual(t_res_dict["resolved_to"], "WebGLEngine.step")
        self.assertEqual(t_res_dict["target_file"], self.webgl_js)

        t_unres_dict = next(t for t in d["transitions"] if t["id"] == "t_unres")
        self.assertFalse(t_unres_dict["resolved"])


if __name__ == "__main__":
    unittest.main()
