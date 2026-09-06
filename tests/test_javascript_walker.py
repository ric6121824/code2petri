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

    def test_find_function_global_returns_none_when_no_executable_statements(self):
        tree = self.walker.parse_file(self.seq_fixture)
        # sequential.js only contains function sequential_func()
        global_node = self.walker.find_function(tree, "(global)")
        self.assertIsNone(global_node)

    def test_walk_assignment_with_call_expression(self):
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_js",
            "assign_call.js",
        )
        tree = self.walker.parse_file(fixture_path)
        node = self.walker.find_function(tree, "calc_caller")
        net = self.walker.walk_function(node)
        labels = [t.label for t in net.transitions]
        self.assertEqual(labels, ["let res = call: calculate()", "return res"])



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


class TestJavascriptIfBranching(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_if_else(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "if_else.js"))
        node = self.walker.find_function(tree, "if_else_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        branch_places = [p for p in net.places if len([a for a in net.arcs if a.source == p]) == 2]
        self.assertEqual(len(branch_places), 1)

        labels = [t.label for t in net.transitions]
        self.assertIn("if (x > 0)", labels)
        self.assertIn("else", labels)
        self.assertIn("result = 1", labels)
        self.assertIn("result = -1", labels)
        self.assertIn("return result", labels)

    def test_if_elif_else(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "if_elif_else.js"))
        node = self.walker.find_function(tree, "if_elif_else_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("if (x > 10)", labels)
        self.assertIn("if (x > 0)", labels)
        self.assertIn("result = 1", labels)
        self.assertIn("result = 2", labels)
        self.assertIn("result = 3", labels)

    def test_if_no_else(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "if_no_else.js"))
        node = self.walker.find_function(tree, "if_no_else_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("if (x > 0)", labels)
        self.assertIn("else", labels)
        self.assertIn("result = 1", labels)
        self.assertIn("return result", labels)


class TestJavascriptLoops(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_while_loop(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "while_loop.js"))
        node = self.walker.find_function(tree, "while_loop_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        loop_trans = next(t for t in net.transitions if "while" in t.label)
        head_place = next(a.source for a in net.arcs if a.target == loop_trans)
        back_arcs = [a for a in net.arcs if a.target == head_place and a.source != net.places[0]]
        self.assertGreaterEqual(len(back_arcs), 1)

    def test_for_loop(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "for_loop.js"))
        node = self.walker.find_function(tree, "for_loop_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertTrue(any("for" in l for l in labels))
        self.assertIn("exit", labels)

    def test_for_in_of_loops(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "for_in_of.js"))
        node = self.walker.find_function(tree, "for_in_of_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertTrue(any("for" in l and "in" in l for l in labels))
        self.assertTrue(any("for" in l and "of" in l for l in labels))

    def test_loop_break_continue(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "loop_break_continue.js"))
        node = self.walker.find_function(tree, "loop_break_continue_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("continue", labels)
        self.assertIn("break", labels)

    def test_break_outside_loop_raises_syntax_error(self):
        stmt = {"type": "BreakStatement", "loc": {"start": {"line": 1, "column": 0}}}
        func = {
            "type": "FunctionDeclaration",
            "id": {"type": "Identifier", "name": "bad"},
            "loc": {"start": {"line": 1, "column": 0}},
            "body": {"type": "BlockStatement", "body": [stmt]},
        }
        with self.assertRaises(SyntaxError):
            self.walker.walk_function(func)


class TestJavascriptTryCatch(unittest.TestCase):
    def setUp(self):
        self.walker = JavascriptWalker()
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), "test_code", "petri_js")

    def test_try_catch(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "try_catch.js"))
        node = self.walker.find_function(tree, "try_catch_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("catch (err)", labels)
        self.assertIn("val = call: riskyOperation()", labels)

        risky_trans = next(t for t in net.transitions if "riskyOperation" in t.label)
        catch_trans = next(t for t in net.transitions if "catch" in t.label)
        except_entry = next(a.source for a in net.arcs if a.target == catch_trans)
        exc_arc = next(a for a in net.arcs if a.source == risky_trans and a.target == except_entry)
        self.assertIsNotNone(exc_arc)

    def test_try_catch_finally(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "try_catch_finally.js"))
        node = self.walker.find_function(tree, "try_catch_finally_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("catch (err)", labels)
        self.assertIn("call: cleanup()", labels)

    def test_try_finally(self):
        tree = self.walker.parse_file(os.path.join(self.fixtures_dir, "try_finally.js"))
        node = self.walker.find_function(tree, "try_finally_func")
        net = self.walker.walk_function(node)
        assert_valid_petri_net(self, net)

        labels = [t.label for t in net.transitions]
        self.assertIn("val = call: riskyOperation()", labels)
        self.assertIn("call: cleanup()", labels)
        self.assertIn("exception", labels)


if __name__ == '__main__':
    unittest.main()

