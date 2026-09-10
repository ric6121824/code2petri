import unittest
import sys
import os
import ast
import xml.etree.ElementTree as ET

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.python_walker import PythonWalker  # noqa: E402
from code2petri.walker_protocol import WalkResult, CallSite  # noqa: E402
from code2petri.model import PetriNet, Place, Transition, Arc  # noqa: E402
from tests.petri_assertions import (  # noqa: E402
    assert_has_start_and_end,
    assert_bipartite,
    assert_valid_petri_net,
    walk_net,
)

walker = PythonWalker()
parse_file = walker.parse_file
find_function = walker.find_function
find_all_functions = walker.find_all_functions


class TestPythonWalkerSequential(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "sequential.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "sequential_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)
        self.assertIsInstance(self.func_node, (ast.FunctionDef, ast.AsyncFunctionDef))

    def test_walk_function_returns_walk_result(self):
        walk_res = walker.walk_function(self.func_node, "sequential_func")
        self.assertIsInstance(walk_res, WalkResult)
        self.assertIsInstance(walk_res.net, PetriNet)
        self.assertIsInstance(walk_res.call_sites, list)
        self.assertEqual(walk_res.call_sites, [])
        assert_valid_petri_net(self, walk_res.net)

    def test_sequential_counts(self):
        walk_res = walker.walk_function(self.func_node)
        self.assertIsInstance(walk_res, WalkResult)
        self.assertEqual(walk_res.call_sites, [])
        net = walk_res.net
        self.assertIsInstance(net, PetriNet)
        # 5 sequential statements + 1 return: 6 transitions, 7 places, 12 arcs
        self.assertEqual(len(net.transitions), 6)
        self.assertEqual(len(net.places), 7)
        self.assertEqual(len(net.arcs), 12)

    def test_collect_variable_bindings_baseline(self):
        bindings = walker.collect_variable_bindings(self.tree)
        self.assertEqual(bindings, {})

    def test_start_and_end_places(self):
        net = walk_net(walker, self.func_node)
        start_place, end_place = assert_has_start_and_end(self, net)
        assert_bipartite(self, net)

        # The start place has an outgoing arc to the first transition
        outgoing_start = [a for a in net.arcs if a.source == start_place]
        self.assertEqual(outgoing_start[0].target, net.transitions[0])

        # End place is the target of the last transition (return statement)
        incoming_end = [a for a in net.arcs if a.target == end_place]
        self.assertEqual(incoming_end[0].source, net.transitions[-1])


    def test_linear_connectivity(self):
        net = walk_net(walker, self.func_node)
        # Check that the net forms a strict linear alternating path
        current_place = [p for p in net.places if p.initial_tokens == 1][0]
        for t in net.transitions:
            # Arc from current_place to t
            p_to_t = [a for a in net.arcs if a.source == current_place and a.target == t]
            self.assertEqual(len(p_to_t), 1, f"Missing arc from {current_place.id} to {t.id}")

            # Arc from t to next place
            t_to_next = [a for a in net.arcs if a.source == t]
            self.assertEqual(len(t_to_next), 1, f"Expected 1 outgoing arc from {t.id}")
            current_place = t_to_next[0].target

        self.assertEqual(current_place.label, "end")

    def test_statement_labels_and_line_numbers(self):
        net = walk_net(walker, self.func_node)
        labels = [t.label for t in net.transitions]
        expected_labels = [
            "a = 1",
            "b = 2",
            "c = a + b",
            "d = c * 2",
            "call: print()",
            "return d",
        ]
        self.assertEqual(labels, expected_labels)

        # Verify line numbers match source lines in sequential.py
        line_numbers = [t.line_number for t in net.transitions]
        self.assertEqual(line_numbers, [2, 3, 4, 5, 6, 7])

    def test_call_expression_variations(self):
        code = """def call_variations():
    plain_call()
    pkg.sub.func()
    res = helper()
    return res
"""
        tree = ast.parse(code)
        func_node = find_function(tree, "call_variations")
        net = walk_net(walker, func_node)
        labels = [t.label for t in net.transitions]
        self.assertEqual(labels[0], "call: plain_call()")
        self.assertEqual(labels[1], "call: pkg.sub.func()")
        self.assertEqual(labels[2], "res = call: helper()")
        self.assertEqual(labels[3], "return res")



class TestPythonWalkerMultiReturn(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "multi_return.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "multi_return_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_all_returns_converge_on_single_end_place(self):
        net = walk_net(walker, self.func_node)
        # Find single terminal end place
        end_places = [p for p in net.places if p.label == "end"]
        self.assertEqual(len(end_places), 1, "There must be exactly one shared terminal 'end' place")
        end_place = end_places[0]

        # Find all return transitions
        return_transitions = [t for t in net.transitions if t.label.startswith("return")]
        self.assertEqual(len(return_transitions), 2, "Expected 2 return transitions in multi_return_func")

        # Assert every return transition has an outgoing arc directly to end_place
        for ret_t in return_transitions:
            outgoing = [a for a in net.arcs if a.source == ret_t]
            self.assertEqual(len(outgoing), 1, f"Return transition {ret_t.id} must have exactly 1 outgoing arc")
            self.assertIs(
                outgoing[0].target,
                end_place,
                f"Return transition {ret_t.id} must target the shared end place, got {outgoing[0].target.id}",
            )

    def test_multi_return_pnml_and_dot_serialization(self):
        net = walk_net(walker, self.func_node)
        pnml = net.to_pnml()
        root = ET.fromstring(pnml)
        self.assertIsNotNone(root)

        dot = net.to_dot()
        self.assertTrue(dot.strip().startswith("digraph"))
        self.assertTrue(dot.strip().endswith("}"))


class TestPythonWalkerEdgeCases(unittest.TestCase):
    def test_invalid_ast_node_type_raises(self):
        invalid_node = ast.Pass()
        with self.assertRaises(TypeError):
            walk_net(walker, invalid_node)  # type: ignore

    def test_find_function_not_found(self):
        tree = ast.parse("def existing_func(): pass")
        self.assertIsNone(find_function(tree, "non_existent"))

    def test_async_function_support(self):
        code = """async def async_worker():
    await do_work()
    return 42
"""
        tree = ast.parse(code)
        func_node = find_function(tree, "async_worker")
        self.assertIsNotNone(func_node)
        net = walk_net(walker, func_node)
        self.assertEqual(len(net.places), 3)  # p0, p1, p_end
        self.assertEqual(len(net.transitions), 2)  # await, return

    def test_find_all_functions(self):
        code = (
            "def alpha(): pass\n"
            "def beta(): pass\n"
            "async def gamma(): pass\n"
        )
        tree = ast.parse(code)
        func_names = find_all_functions(tree)
        self.assertEqual(func_names, ["alpha", "beta", "gamma"])

    def test_global_scope_discovery(self):
        code = (
            "x = 1\n"
            "y = 2\n"
            "def helper(): pass\n"
        )
        tree = ast.parse(code)
        func_names = find_all_functions(tree)
        self.assertEqual(func_names, ["(global)", "helper"])

    def test_find_function_global_synthetic_wrapper(self):
        code = (
            "a = 10\n"
            "b = 20\n"
            "print(a + b)\n"
        )
        tree = ast.parse(code)
        global_node = find_function(tree, "(global)")
        self.assertIsNotNone(global_node)
        self.assertIsInstance(global_node, ast.FunctionDef)
        self.assertEqual(global_node.name, "(global)")
        self.assertEqual(len(global_node.body), 3)

        net = walk_net(walker, global_node)
        assert_valid_petri_net(self, net)
        assert_bipartite(self, net)
        start_p, end_p = assert_has_start_and_end(self, net)
        self.assertIsNotNone(start_p)
        self.assertIsNotNone(end_p)

    def test_find_function_global_none_when_no_executable_statements(self):
        code = (
            "def func_a(): pass\n"
            "class ClassB: pass\n"
        )
        tree = ast.parse(code)
        self.assertIsNone(find_function(tree, "(global)"))

    def test_raise_statement_unhandled(self):
        code = (
            "def func_with_raise():\n"
            "    x = 1\n"
            "    raise ValueError('error')\n"
            "    y = 2\n"
        )
        tree = ast.parse(code)
        func_node = find_function(tree, "func_with_raise")
        net = walk_net(walker, func_node)
        assert_valid_petri_net(self, net)
        start_p, end_p = assert_has_start_and_end(self, net)

        raise_trans = next(t for t in net.transitions if "raise" in t.label)
        self.assertIsNotNone(raise_trans)
        # Unhandled raise arcs to end_place
        self.assertTrue(any(a.source == raise_trans and a.target == end_p for a in net.arcs))
        # Dead statement after raise is not present in net
        self.assertFalse(any("y = 2" in t.label for t in net.transitions))

    def test_raise_statement_in_try(self):
        code = (
            "def func_with_try_raise():\n"
            "    try:\n"
            "        raise RuntimeError('fail')\n"
            "    except RuntimeError:\n"
            "        pass\n"
        )
        tree = ast.parse(code)
        func_node = find_function(tree, "func_with_try_raise")
        net = walk_net(walker, func_node)
        assert_valid_petri_net(self, net)

        raise_trans = next(t for t in net.transitions if "raise" in t.label)
        except_place = next(p for p in net.places if p.label == "except_entry")
        self.assertTrue(any(a.source == raise_trans and a.target == except_place for a in net.arcs))


if __name__ == '__main__':
    unittest.main()
