import ast
import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.walker_protocol import WalkerProtocol
from code2petri.base_walker import _BaseControlFlowWalker, LoopContext, TryContext
from code2petri.python_walker import PythonWalker, find_all_functions, find_function
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

            def walk_function(self, ast_node):
                return PetriNet()

        walker = CompleteWalker()
        self.assertIsInstance(walker, WalkerProtocol)


class TestBaseControlFlowWalker(unittest.TestCase):
    def setUp(self):
        self.net = PetriNet()
        self.end_place = self.net.add_place("p_end", "end")
        self.walker = _BaseControlFlowWalker(self.net, self.end_place)

    def test_id_counters_and_places(self):
        p1 = self.walker.new_place(line_number=10)
        p2 = self.walker.new_place(label="custom_p", line_number=12)
        self.assertEqual(p1.id, "p1")
        self.assertEqual(p1.label, "p1")
        self.assertEqual(p1.line_number, 10)
        self.assertEqual(p2.id, "p2")
        self.assertEqual(p2.label, "custom_p")
        self.assertEqual(self.walker.place_counter, 2)

    def test_transitions_and_exception_hook(self):
        t1 = self.walker.new_transition("op_1", line_number=5)
        self.assertEqual(t1.id, "t1")
        self.assertEqual(t1.label, "op_1")
        self.assertEqual(len(self.net.arcs), 0)

        # Push try context and test hook_exception
        exc_entry = self.walker.new_place("except_entry")
        self.walker.try_stack.append(TryContext(except_entry=exc_entry))

        t2 = self.walker.new_transition("op_in_try", line_number=6, hook_exception=True)
        # Should create an arc from t2 to exc_entry
        exc_arcs = [a for a in self.net.arcs if a.source == t2 and a.target == exc_entry]
        self.assertEqual(len(exc_arcs), 1)

        t3 = self.walker.new_transition("no_hook", line_number=7, hook_exception=False)
        no_hook_arcs = [a for a in self.net.arcs if a.source == t3]
        self.assertEqual(len(no_hook_arcs), 0)


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
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)


class TestEngineLanguageDispatch(unittest.TestCase):
    def test_engine_has_python_registered(self):
        self.assertIn(".py", WALKERS)
        self.assertEqual(WALKERS[".py"], PythonWalker)

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


if __name__ == '__main__':
    unittest.main()

