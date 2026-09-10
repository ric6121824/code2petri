import ast
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.walker_protocol import WalkerProtocol, WalkResult, CallSite
from code2petri.control_flow_builder import ControlFlowBuilder, LoopContext, TryContext
from code2petri.python_walker import PythonWalker
from code2petri.model import PetriNet, Place, Transition
from code2petri.engine import code2petri, WALKERS
from tests.petri_assertions import assert_valid_petri_net, assert_has_start_and_end, assert_bipartite


class TestWalkerProtocolABC(unittest.TestCase):
    def test_cannot_instantiate_protocol_directly(self):
        with self.assertRaises(TypeError):
            WalkerProtocol()

    def test_subclass_missing_methods_raises_type_error(self):
        class IncompleteWalker(WalkerProtocol):
            def parse_file(self, filepath):
                return None

        with self.assertRaises(TypeError):
            IncompleteWalker()

    def test_complete_subclass_can_be_instantiated(self):
        class CompleteWalker(WalkerProtocol):
            def parse_file(self, filepath):
                return None

            def find_function(self, tree, func_name):
                return None

            def find_all_functions(self, tree):
                return []

            def walk_function(self, ast_node, func_name=""):
                return WalkResult(net=PetriNet(), call_sites=[])

            def collect_variable_bindings(self, tree):
                return {}

            def get_node_lineno(self, ast_node):
                return 0

        walker = CompleteWalker()
        self.assertIsInstance(walker, WalkerProtocol)

    def test_missing_collect_variable_bindings_raises_type_error(self):
        class MissingBindingsWalker(WalkerProtocol):
            def parse_file(self, filepath):
                return None

            def find_function(self, tree, func_name):
                return None

            def find_all_functions(self, tree):
                return []

            def walk_function(self, ast_node, func_name=""):
                return WalkResult(net=PetriNet(), call_sites=[])

            def get_node_lineno(self, ast_node):
                return 0

        with self.assertRaises(TypeError):
            MissingBindingsWalker()

    def test_call_site_dataclass(self):
        from code2petri.walker_protocol import CallSite
        cs = CallSite(
            caller_function="main",
            caller_file="app.py",
            callee_name="step",
            callee_owner="gpuEngine",
            line_number=42,
            transition_id="t5",
        )
        self.assertEqual(cs.caller_function, "main")
        self.assertEqual(cs.caller_file, "app.py")
        self.assertEqual(cs.callee_name, "step")
        self.assertEqual(cs.callee_owner, "gpuEngine")
        self.assertEqual(cs.line_number, 42)
        self.assertEqual(cs.transition_id, "t5")

    def test_walk_result_namedtuple(self):
        from code2petri.walker_protocol import CallSite, WalkResult
        net = PetriNet()
        cs = CallSite(
            caller_function="run",
            caller_file="index.js",
            callee_name="log",
            callee_owner="console",
            line_number=10,
            transition_id="t1",
        )
        res = WalkResult(net=net, call_sites=[cs])
        self.assertIs(res.net, net)
        self.assertEqual(res.call_sites, [cs])
        # Unpacking support
        unpacked_net, unpacked_calls = res
        self.assertIs(unpacked_net, net)
        self.assertEqual(unpacked_calls, [cs])
        # Index access
        self.assertIs(res[0], net)
        self.assertEqual(res[1], [cs])


class TestControlFlowBuilder(unittest.TestCase):
    def setUp(self):
        self.net = PetriNet()
        self.end_place = self.net.add_place("p_end", "end")
        self.builder = ControlFlowBuilder(self.net, self.end_place)

    def test_id_counters_and_places(self):
        p1 = self.builder.new_place(line_number=10)
        p2 = self.builder.new_place(label="custom_p", line_number=12)
        self.assertEqual(p1.id, "p1")
        self.assertEqual(p1.label, "p1")
        self.assertEqual(p1.line_number, 10)
        self.assertEqual(p2.id, "p2")
        self.assertEqual(p2.label, "custom_p")
        self.assertEqual(self.builder.place_counter, 2)

    def test_transitions_and_exception_hook(self):
        t1 = self.builder.new_transition("op_1", line_number=5)
        self.assertEqual(t1.id, "t1")
        self.assertEqual(t1.label, "op_1")
        self.assertEqual(len(self.net.arcs), 0)

        # Push try context and test hook_exception
        exc_entry = self.builder.new_place("except_entry")
        self.builder.try_stack.append(TryContext(except_entry=exc_entry))

        t2 = self.builder.new_transition("op_in_try", line_number=6, hook_exception=True)
        # Should create an arc from t2 to exc_entry
        exc_arcs = [a for a in self.net.arcs if a.source == t2 and a.target == exc_entry]
        self.assertEqual(len(exc_arcs), 1)

        t3 = self.builder.new_transition("no_hook", line_number=7, hook_exception=False)
        no_hook_arcs = [a for a in self.net.arcs if a.source == t3]
        self.assertEqual(len(no_hook_arcs), 0)

    def test_loop_stack_helpers_and_incoming_arcs(self):
        head = self.builder.new_place("head")
        exit_p = self.builder.new_place("exit")
        self.builder.push_loop(head=head, exit=exit_p)
        self.assertEqual(len(self.builder.loop_stack), 1)
        self.assertFalse(self.builder.has_incoming_arcs(head))

        trans = self.builder.new_transition("step")
        self.builder.add_arc(trans, head)
        self.assertTrue(self.builder.has_incoming_arcs(head))

        popped = self.builder.pop_loop()
        self.assertIsNotNone(popped)
        self.assertEqual(popped.head, head)
        self.assertEqual(len(self.builder.loop_stack), 0)


class TestPythonWalkerProtocolAndQualifiedNames(unittest.TestCase):
    def setUp(self):
        self.walker = PythonWalker()

    def test_python_walker_is_protocol_instance(self):
        self.assertIsInstance(self.walker, WalkerProtocol)

    def test_qualified_names_for_class_methods(self):
        code = (
            "class Calculator:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n"
            "    def sub(self, a, b):\n"
            "        return a - b\n"
            "def top_func():\n"
            "    pass\n"
        )
        tree = ast.parse(code)
        func_names = self.walker.find_all_functions(tree)
        self.assertEqual(func_names, ["Calculator.add", "Calculator.sub", "top_func"])

    def test_nested_class_methods_qualification(self):
        code = (
            "class Outer:\n"
            "    class Inner:\n"
            "        def nested_method(self):\n"
            "            pass\n"
        )
        tree = ast.parse(code)
        func_names = self.walker.find_all_functions(tree)
        self.assertEqual(func_names, ["Outer.Inner.nested_method"])

    def test_nested_function_in_method_qualification(self):
        code = (
            "class Foo:\n"
            "    def method(self):\n"
            "        def local_helper():\n"
            "            pass\n"
        )
        tree = ast.parse(code)
        func_names = self.walker.find_all_functions(tree)
        self.assertEqual(func_names, ["Foo.method", "Foo.method.local_helper"])


    def test_find_function_by_qualified_and_bare_name(self):
        code = (
            "class Service:\n"
            "    def process(self):\n"
            "        return 1\n"
        )
        tree = ast.parse(code)
        # By qualified name
        node = self.walker.find_function(tree, "Service.process")
        self.assertIsNotNone(node)
        self.assertEqual(node.name, "process")

        # By bare name fallback
        node_bare = self.walker.find_function(tree, "process")
        self.assertIsNotNone(node_bare)
        self.assertEqual(node_bare.name, "process")

    def test_walk_function_returns_valid_net(self):
        code = (
            "def sample():\n"
            "    x = 1\n"
            "    return x\n"
        )
        tree = ast.parse(code)
        node = self.walker.find_function(tree, "sample")
        walk_res = self.walker.walk_function(node)
        self.assertIsInstance(walk_res, WalkResult)
        self.assertEqual(walk_res.call_sites, [])
        assert_valid_petri_net(self, walk_res.net)

    def test_python_walker_global_discovery_and_walk(self):
        code = (
            "msg = 'hello'\n"
            "print(msg)\n"
            "def worker():\n"
            "    pass\n"
        )
        tree = ast.parse(code)
        funcs = self.walker.find_all_functions(tree)
        self.assertEqual(funcs, ["(global)", "worker"])

        global_node = self.walker.find_function(tree, "(global)")
        self.assertIsNotNone(global_node)
        self.assertEqual(global_node.name, "(global)")
        walk_res = self.walker.walk_function(global_node)
        self.assertIsInstance(walk_res, WalkResult)
        self.assertEqual(walk_res.call_sites, [])
        assert_valid_petri_net(self, walk_res.net)


class TestEngineLanguageDispatch(unittest.TestCase):
    def test_engine_has_python_registered(self):
        self.assertIn(".py", WALKERS)
        self.assertEqual(WALKERS[".py"], PythonWalker)

    def test_engine_does_not_register_mjs(self):
        self.assertNotIn(".mjs", WALKERS)

    def test_engine_runs_via_instantiated_walker(self):
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "sequential.py",
        )
        net = code2petri(fixture_path, output_file=None, target_function="sequential_func")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)

    def test_package_exports_walker_protocol_not_internal_builder(self):
        import code2petri
        from code2petri.control_flow_builder import ControlFlowBuilder
        from code2petri.python_walker import PythonWalker
        from code2petri.javascript_walker import JavascriptWalker
        self.assertNotIn("ControlFlowBuilder", code2petri.__all__)
        self.assertNotIn("BaseControlFlowWalker", code2petri.__all__)
        self.assertNotIn("_BaseControlFlowWalker", code2petri.__all__)
        self.assertIn("WalkerProtocol", code2petri.__all__)
        self.assertTrue(issubclass(PythonWalker, WalkerProtocol))
        self.assertTrue(issubclass(JavascriptWalker, WalkerProtocol))
        self.assertFalse(issubclass(PythonWalker, ControlFlowBuilder))
        self.assertFalse(issubclass(JavascriptWalker, ControlFlowBuilder))

    def test_walker_protocol_get_node_lineno(self):
        import ast
        from code2petri.python_walker import PythonWalker
        from code2petri.javascript_walker import JavascriptWalker

        py_walker = PythonWalker()
        node = ast.parse("x = 1\n").body[0]
        self.assertEqual(py_walker.get_node_lineno(node), 1)

        js_walker = JavascriptWalker()
        js_node = {"type": "Identifier", "loc": {"start": {"line": 42, "column": 0}}}
        self.assertEqual(js_walker.get_node_lineno(js_node), 42)
        self.assertEqual(js_walker.get_node_lineno({}), 0)

    def test_package_exports_call_site_and_walk_result(self):
        import code2petri
        self.assertIn("CallSite", code2petri.__all__)
        self.assertIn("WalkResult", code2petri.__all__)
        self.assertIn("CallResolution", code2petri.__all__)
        self.assertTrue(hasattr(code2petri, "CallSite"))
        self.assertTrue(hasattr(code2petri, "WalkResult"))
        self.assertTrue(hasattr(code2petri, "CallResolution"))

    def test_walkers_baseline_collect_variable_bindings(self):
        import ast
        from code2petri.python_walker import PythonWalker
        from code2petri.javascript_walker import JavascriptWalker

        py_walker = PythonWalker()
        self.assertEqual(py_walker.collect_variable_bindings(ast.parse("x = 1")), {})

        js_walker = JavascriptWalker()
        self.assertEqual(js_walker.collect_variable_bindings({}), {})


if __name__ == '__main__':
    unittest.main()


