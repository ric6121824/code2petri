import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.javascript_walker import JavascriptWalker
from code2petri.walker_protocol import WalkerProtocol
from code2petri.engine import code2petri, WALKERS
from tests.petri_assertions import assert_valid_petri_net, assert_has_start_and_end, assert_bipartite


class TestJavascriptWalkerSkeleton(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.seq_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "sequential.js",
        )
        self.global_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "global_script.js",
        )

    def test_implements_walker_protocol(self):
        self.assertIsInstance(self.walker, WalkerProtocol)

    def test_parse_file_and_caching(self):
        tree = self.walker.parse_file(self.seq_fixture)
        self.assertIsInstance(tree, dict)
        self.assertEqual(tree.get("type"), "Program")
        self.assertIsNotNone(self.walker.raw_source)
        self.assertIn("function sequential_func()", self.walker.raw_source)

    def test_find_all_functions_in_file(self):
        tree = self.walker.parse_file(self.seq_fixture)
        funcs = self.walker.find_all_functions(tree)
        self.assertIn("sequential_func", funcs)

    def test_global_scope_discovery(self):
        tree = self.walker.parse_file(self.global_fixture)
        funcs = self.walker.find_all_functions(tree)
        self.assertEqual(funcs, ["(global)", "init"])

    def test_find_function_regular(self):
        tree = self.walker.parse_file(self.seq_fixture)
        node = self.walker.find_function(tree, "sequential_func")
        self.assertIsNotNone(node)
        self.assertEqual(node.get("type"), "FunctionDeclaration")
        self.assertEqual(node["id"]["name"], "sequential_func")

    def test_find_function_global(self):
        tree = self.walker.parse_file(self.global_fixture)
        global_node = self.walker.find_function(tree, "(global)")
        self.assertIsNotNone(global_node)
        self.assertEqual(global_node.get("type"), "FunctionDeclaration")
        self.assertEqual(global_node["id"]["name"], "(global)")
        # Body contains the 3 executable statements (let x, let y, init()), not function init
        body_stmts = global_node["body"]["body"]
        self.assertEqual(len(body_stmts), 3)

    def test_walk_sequential_function(self):
        tree = self.walker.parse_file(self.seq_fixture)
        node = self.walker.find_function(tree, "sequential_func")
        net = self.walker.walk_function(node)

        # 5 sequential statements + 1 return -> 6 transitions, 7 places, 12 arcs
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 6)
        self.assertEqual(len(net.places), 7)
        self.assertEqual(len(net.arcs), 12)

        # Sliced transition labels
        labels = [t.label for t in net.transitions]
        expected_labels = [
            "let a = 1",
            "let b = 2",
            "let c = a + b",
            "let d = c * 2",
            "call: print()",
            "return d",
        ]
        self.assertEqual(labels, expected_labels)

        # Line numbers
        lines = [t.line_number for t in net.transitions]
        self.assertEqual(lines, [2, 3, 4, 5, 6, 7])

    def test_walk_global_scope(self):
        tree = self.walker.parse_file(self.global_fixture)
        global_node = self.walker.find_function(tree, "(global)")
        net = self.walker.walk_function(global_node)

        # 3 sequential statements, no return -> 3 transitions, 4 places, 6 arcs
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 3)
        self.assertEqual(len(net.places), 4)
        self.assertEqual(len(net.arcs), 6)

        labels = [t.label for t in net.transitions]
        expected_labels = [
            "let x = 10",
            "let y = 20",
            "call: init()",
        ]
        self.assertEqual(labels, expected_labels)


class TestEngineJavascriptIntegration(unittest.TestCase):
    def setUp(self):
        self.seq_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "sequential.js",
        )
        self.global_fixture = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "global_script.js",
        )

    def test_walkers_registry_has_javascript(self):
        self.assertIn(".js", WALKERS)
        self.assertEqual(WALKERS[".js"], JavascriptWalker)

    def test_engine_end_to_end_sequential_js(self):
        net = code2petri(self.seq_fixture, output_file=None, target_function="sequential_func")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 6)

    def test_engine_end_to_end_global_js(self):
        net = code2petri(self.global_fixture, output_file=None, target_function="(global)")
        self.assertIsNotNone(net)
        assert_valid_petri_net(self, net)
        self.assertEqual(len(net.transitions), 3)


if __name__ == '__main__':
    unittest.main()
