import os
import tempfile
import unittest

from code2petri.inline import inline_expand
from code2petri.javascript_walker import JavascriptWalker
from code2petri.model import PetriNet, Place, Transition
from code2petri.python_walker import PythonWalker
from code2petri.symbol_table import SymbolTable
from tests.petri_assertions import assert_valid_petri_net


class TestInlineExpansionEngine(unittest.TestCase):
    def setUp(self):
        self.py_walker = PythonWalker()
        self.js_walker = JavascriptWalker()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_temp_file(self, filename: str, content: str) -> str:
        filepath = os.path.join(self.temp_dir.name, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_single_callee_splicing(self):
        """Validates single resolved callee splicing, correct node count, and arc wiring."""
        code = (
            "def target_func():\n"
            "    inner_a = 1\n"
            "    inner_b = 2\n"
            "\n"
            "def caller_func():\n"
            "    step1 = 1\n"
            "    target_func()\n"
            "    step2 = 2\n"
        )
        fp = self._write_temp_file("single_call.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        caller_node = self.py_walker.find_function(tree, "caller_func")
        target_node = self.py_walker.find_function(tree, "target_func")

        caller_res = self.py_walker.walk_function(caller_node, "caller_func", filepath=fp)
        target_res = self.py_walker.walk_function(target_node, "target_func", filepath=fp)

        caller_net = caller_res.net
        callee_net = target_res.net

        call_trans_id = caller_res.call_sites[0].transition_id

        # Perform inline expansion
        composite_net = inline_expand(caller_net, caller_res.call_sites, symbol_table, max_depth=1)

        # 1. Composite net passes assert_valid_petri_net (bipartite, has start/end, non-empty)
        assert_valid_petri_net(self, composite_net)

        # 2. Call transition is removed
        trans_ids = {t.id for t in composite_net.transitions}
        self.assertNotIn(call_trans_id, trans_ids)

        # 3. Node count check:
        # Places: caller places + callee places - 2 (source and sink merged)
        expected_place_count = len(caller_net.places) + len(callee_net.places) - 2
        self.assertEqual(len(composite_net.places), expected_place_count)

        # Transitions: caller transitions - 1 (call removed) + callee transitions
        expected_trans_count = len(caller_net.transitions) - 1 + len(callee_net.transitions)
        self.assertEqual(len(composite_net.transitions), expected_trans_count)

        # 4. Callee nodes exist with namespace prefix
        self.assertTrue(any(t.id.startswith("inline_target_func__") for t in composite_net.transitions))
        self.assertTrue(any(p.id.startswith("inline_target_func__") for p in composite_net.places))

        # 5. No orphaned nodes: every node must have >= 1 incident arc
        connected_node_ids = set()
        for a in composite_net.arcs:
            connected_node_ids.add(a.source.id)
            connected_node_ids.add(a.target.id)

        all_node_ids = {p.id for p in composite_net.places} | {t.id for t in composite_net.transitions}
        self.assertEqual(connected_node_ids, all_node_ids)

    def test_callee_namespace_prefix_collision_prevention(self):
        """Validates that calling the same function twice produces non-colliding unique IDs."""
        code = (
            "def worker():\n"
            "    x = 10\n"
            "\n"
            "def caller_func():\n"
            "    worker()\n"
            "    worker()\n"
        )
        fp = self._write_temp_file("duplicate_calls.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        caller_node = self.py_walker.find_function(tree, "caller_func")
        caller_res = self.py_walker.walk_function(caller_node, "caller_func", filepath=fp)

        composite_net = inline_expand(caller_res.net, caller_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)

        # All place and transition IDs must be completely unique
        place_ids = [p.id for p in composite_net.places]
        trans_ids = [t.id for t in composite_net.transitions]
        self.assertEqual(len(place_ids), len(set(place_ids)))
        self.assertEqual(len(trans_ids), len(set(trans_ids)))

        # Two inlined sets of worker transitions
        inlined_trans = [t for t in composite_net.transitions if "inline_worker" in t.id]
        self.assertGreaterEqual(len(inlined_trans), 2)

    def test_unresolved_call_remains_opaque(self):
        """Validates that unresolved call transitions are left untouched."""
        code = (
            "def caller_func():\n"
            "    step1 = 1\n"
            "    missing_function()\n"
            "    step2 = 2\n"
        )
        fp = self._write_temp_file("unresolved_call.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        caller_node = self.py_walker.find_function(tree, "caller_func")
        caller_res = self.py_walker.walk_function(caller_node, "caller_func", filepath=fp)

        composite_net = inline_expand(caller_res.net, caller_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)

        # The unresolved transition must remain in composite_net
        call_cs = caller_res.call_sites[0]
        unresolved_trans = next((t for t in composite_net.transitions if t.id == call_cs.transition_id), None)
        self.assertIsNotNone(unresolved_trans)
        self.assertEqual(unresolved_trans.id, call_cs.transition_id)
        self.assertEqual(len(composite_net.transitions), len(caller_res.net.transitions))

    def test_direct_recursion_guard(self):
        """Validates that a self-referencing call retains the call transition as opaque with recursive_cycle metadata."""
        code = (
            "def loop():\n"
            "    x = 1\n"
            "    loop()\n"
        )
        fp = self._write_temp_file("direct_recursion.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        loop_node = self.py_walker.find_function(tree, "loop")
        loop_res = self.py_walker.walk_function(loop_node, "loop", filepath=fp)

        composite_net = inline_expand(loop_res.net, loop_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)

        # Call transition must remain and have metadata={"recursive_cycle": True}
        call_cs = loop_res.call_sites[0]
        cycle_trans = next(t for t in composite_net.transitions if t.id == call_cs.transition_id)
        self.assertIsNotNone(cycle_trans.metadata)
        self.assertTrue(cycle_trans.metadata.get("recursive_cycle"))

    def test_request_animation_frame_recursion_guard(self):
        """Validates that requestAnimationFrame(loop) retains the call transition with recursive_cycle metadata."""
        code = (
            "function gameLoop() {\n"
            "    update();\n"
            "    requestAnimationFrame(gameLoop);\n"
            "}\n"
        )
        fp = self._write_temp_file("raf_loop.js", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.js_walker.parse_file(fp)
        loop_node = self.js_walker.find_function(tree, "gameLoop")
        loop_res = self.js_walker.walk_function(loop_node, "gameLoop", filepath=fp)

        composite_net = inline_expand(loop_res.net, loop_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)

        raf_trans = next(
            t for t in composite_net.transitions
            if "requestAnimationFrame" in t.label
        )
        self.assertIsNotNone(raf_trans.metadata)
        self.assertTrue(raf_trans.metadata.get("recursive_cycle"))

    def test_mutual_recursion_guard(self):
        """Validates that mutual/indirect recursion (f -> g -> f) halts and annotates the cycle point."""
        code = (
            "def ping():\n"
            "    pong()\n"
            "\n"
            "def pong():\n"
            "    ping()\n"
        )
        fp = self._write_temp_file("mutual_recursion.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        ping_node = self.py_walker.find_function(tree, "ping")
        ping_res = self.py_walker.walk_function(ping_node, "ping", filepath=fp)

        # Expand ping with max_depth=2 so it tries to expand pong -> ping
        composite_net = inline_expand(ping_res.net, ping_res.call_sites, symbol_table, max_depth=2)
        assert_valid_petri_net(self, composite_net)

        # Pong is inlined into ping
        pong_trans = [t for t in composite_net.transitions if "inline_pong__" in t.id]
        self.assertGreater(len(pong_trans), 0)

        # The ping call inside pong must be tagged as recursive_cycle
        cycle_trans = next((t for t in pong_trans if t.metadata and t.metadata.get("recursive_cycle")), None)
        self.assertIsNotNone(cycle_trans)

    def test_depth_capping_multi_level(self):
        """Validates that max_depth controls how many levels of nesting are expanded."""
        code = (
            "def level_3():\n"
            "    result = 42\n"
            "\n"
            "def level_2():\n"
            "    level_3()\n"
            "\n"
            "def level_1():\n"
            "    level_2()\n"
        )
        fp = self._write_temp_file("depth_chain.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        l1_node = self.py_walker.find_function(tree, "level_1")
        l1_res = self.py_walker.walk_function(l1_node, "level_1", filepath=fp)

        # Depth 1: level_2 is inlined, level_3 call inside level_2 remains opaque
        net_d1 = inline_expand(l1_res.net, l1_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, net_d1)
        self.assertTrue(any("inline_level_2__" in t.id for t in net_d1.transitions))
        self.assertFalse(any("inline_level_3__" in t.id for t in net_d1.transitions))

        # Depth 2: level_2 and level_3 are inlined
        net_d2 = inline_expand(l1_res.net, l1_res.call_sites, symbol_table, max_depth=2)
        assert_valid_petri_net(self, net_d2)
        self.assertTrue(any("inline_level_2__" in t.id for t in net_d2.transitions))
        self.assertTrue(any("inline_level_3__" in t.id for t in net_d2.transitions))

    def test_empty_callee_splicing(self):
        """Validates that inlining a single-statement callee produces a valid bipartite net."""
        code = (
            "def noop():\n"
            "    pass\n"
            "\n"
            "def main():\n"
            "    noop()\n"
        )
        fp = self._write_temp_file("empty_callee.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        main_node = self.py_walker.find_function(tree, "main")
        main_res = self.py_walker.walk_function(main_node, "main", filepath=fp)

        composite_net = inline_expand(main_res.net, main_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)

        inlined_t = next(t for t in composite_net.transitions if "inline_noop__" in t.id)
        self.assertEqual(inlined_t.label, "pass")

    def test_javascript_inline_expansion(self):
        """Validates inline expansion across JavaScript functions."""
        code = (
            "function add(a, b) {\n"
            "    return a + b;\n"
            "}\n"
            "function compute() {\n"
            "    let x = add(1, 2);\n"
            "}\n"
        )
        fp = self._write_temp_file("math.js", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.js_walker.parse_file(fp)
        compute_node = self.js_walker.find_function(tree, "compute")
        compute_res = self.js_walker.walk_function(compute_node, "compute", filepath=fp)

        composite_net = inline_expand(compute_res.net, compute_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)
        self.assertTrue(any("inline_add__" in t.id for t in composite_net.transitions))

    def test_game_of_life_loop_inline(self):
        """Validates inlining WebGLEngine.step into loop in GameOfLife Simulator."""
        game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        app_js = os.path.join(game_of_life_dir, "app.js")
        webgl_js = os.path.join(game_of_life_dir, "webgl-engine.js")

        symbol_table = SymbolTable()
        symbol_table.index_file(app_js)
        symbol_table.index_file(webgl_js)

        tree = self.js_walker.parse_file(app_js)
        loop_node = self.js_walker.find_function(tree, "loop")
        loop_res = self.js_walker.walk_function(loop_node, "loop", filepath=app_js)

        # In GameOfLife:
        # loop calls gpuEngine.step() which resolves to WebGLEngine.step
        # and stepCpu() which resolves to stepCpu
        composite_net = inline_expand(loop_res.net, loop_res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)

        # WebGLEngine.step nodes must be inlined into loop
        webgl_inlined = [t for t in composite_net.transitions if "inline_WebGLEngine.step__" in t.id]
        self.assertGreater(len(webgl_inlined), 0)

        # stepCpu nodes must be inlined into loop
        step_cpu_inlined = [t for t in composite_net.transitions if "inline_stepCpu__" in t.id]
        self.assertGreater(len(step_cpu_inlined), 0)

    def test_class_method_recursion_guard(self):
        """Validates recursion guard on class method where caller_function is qualified or bare."""
        code = (
            "class Worker:\n"
            "    def process(self):\n"
            "        self.process()\n"
        )
        fp = self._write_temp_file("method_recursion.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        worker_node = self.py_walker.find_function(tree, "Worker.process")
        res = self.py_walker.walk_function(worker_node, "Worker.process", filepath=fp)

        composite_net = inline_expand(res.net, res.call_sites, symbol_table, max_depth=1)
        assert_valid_petri_net(self, composite_net)

        rec_trans = next(t for t in composite_net.transitions if "process" in t.label)
        self.assertIsNotNone(rec_trans.metadata)
        self.assertTrue(rec_trans.metadata.get("recursive_cycle"))

    def test_multi_caller_initial_stack(self):
        """Validates that call sites from multiple callers maintain path-dependent vertical stacks."""
        from code2petri.walker_protocol import CallSite
        code = (
            "def worker_a():\n"
            "    worker_a()\n"
            "def worker_b():\n"
            "    worker_a()\n"
        )
        fp = self._write_temp_file("multi_callers.py", code)
        symbol_table = SymbolTable()
        symbol_table.index_file(fp)

        tree = self.py_walker.parse_file(fp)
        node_a = self.py_walker.find_function(tree, "worker_a")
        res_a = self.py_walker.walk_function(node_a, "worker_a", filepath=fp)

        node_b = self.py_walker.find_function(tree, "worker_b")
        res_b = self.py_walker.walk_function(node_b, "worker_b", filepath=fp)

        # Build composite net and combine call sites
        combined_net = PetriNet()
        for p in res_a.net.places:
            combined_net.add_place(id=f"a_{p.id}", label=p.label, initial_tokens=p.initial_tokens)
        for t in res_a.net.transitions:
            combined_net.add_transition(id=f"a_{t.id}", label=t.label)
        node_map_a = combined_net.get_node_map()
        for a in res_a.net.arcs:
            combined_net.add_arc(source=node_map_a[f"a_{a.source.id}"], target=node_map_a[f"a_{a.target.id}"])

        for p in res_b.net.places:
            combined_net.add_place(id=f"b_{p.id}", label=p.label, initial_tokens=0)
        for t in res_b.net.transitions:
            combined_net.add_transition(id=f"b_{t.id}", label=t.label)
        node_map_b = combined_net.get_node_map()
        for a in res_b.net.arcs:
            combined_net.add_arc(source=node_map_b[f"b_{a.source.id}"], target=node_map_b[f"b_{a.target.id}"])

        cs_a = [CallSite(cs.caller_function, cs.caller_file, cs.callee_name, cs.callee_owner, cs.line_number, f"a_{cs.transition_id}") for cs in res_a.call_sites]
        cs_b = [CallSite(cs.caller_function, cs.caller_file, cs.callee_name, cs.callee_owner, cs.line_number, f"b_{cs.transition_id}") for cs in res_b.call_sites]
        combined_call_sites = cs_a + cs_b

        composite_net = inline_expand(combined_net, combined_call_sites, symbol_table, max_depth=1)
        # worker_a calling worker_a is recursive and halts
        cycle_transitions = [t for t in composite_net.transitions if t.metadata and t.metadata.get("recursive_cycle")]
        self.assertEqual(len(cycle_transitions), 1)

        # worker_b calling worker_a is NOT recursive and inlines successfully
        inlined_worker_a = [t for t in composite_net.transitions if "inline_worker_a__" in t.id]
        self.assertGreater(len(inlined_worker_a), 0)


    def test_petrinet_find_boundary_places(self):
        """Validates PetriNet.find_boundary_places identifies source and sink."""
        net = PetriNet()
        p_start = net.add_place(id="p_start", label="start", initial_tokens=1)
        t1 = net.add_transition(id="t1", label="t1")
        p_end = net.add_place(id="p_end", label="end", initial_tokens=0)
        net.add_arc(p_start, t1)
        net.add_arc(t1, p_end)

        source, sink = net.find_boundary_places()
        self.assertEqual(source.id, "p_start")
        self.assertEqual(sink.id, "p_end")


if __name__ == "__main__":
    unittest.main()
