import unittest
import sys
import os
from typing import List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.python_walker import PythonWalker  # noqa: E402
from code2petri.model import PetriNet, Place, Transition, Arc  # noqa: E402
from tests.petri_assertions import walk_net  # noqa: E402

walker = PythonWalker()
parse_file = walker.parse_file
find_function = walker.find_function


def find_directed_cycles(net: PetriNet) -> List[List[str]]:
    """Finds simple directed cycles in the Petri net using DFS."""
    adj = {p.id: [] for p in net.places}
    for t in net.transitions:
        adj[t.id] = []
    for arc in net.arcs:
        adj[arc.source.id].append(arc.target.id)

    visited = {}  # 0 = unvisited, 1 = visiting, 2 = visited
    cycles = []

    def dfs(node: str, path: List[str]) -> None:
        visited[node] = 1
        path.append(node)
        for neighbor in adj.get(node, []):
            if visited.get(neighbor, 0) == 1:
                cycle_start = path.index(neighbor)
                cycles.append(path[cycle_start:] + [neighbor])
            elif visited.get(neighbor, 0) == 0:
                dfs(neighbor, path)
        path.pop()
        visited[node] = 2

    for node in list(adj.keys()):
        if visited.get(node, 0) == 0:
            dfs(node, [])

    return cycles


class TestWhileLoop(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "while_loop.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "while_loop_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_while_loop_counts(self):
        net = walk_net(walker, self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 5 transitions: count = 0, while count < 10, count = count + 1, else, return count
        self.assertEqual(len(net.transitions), 5)
        # 5 places: p0(start), p1(loop_head), p2(body_entry), p3(loop_exit), p_end
        self.assertEqual(len(net.places), 5)
        # 10 arcs
        self.assertEqual(len(net.arcs), 10)

    def test_while_loop_cycle_and_xor_split(self):
        net = walk_net(walker, self.func_node)

        # Transition for count = 0 leads to the loop head place
        t_init = next(t for t in net.transitions if "count = 0" in t.label)
        init_outputs = [a.target for a in net.arcs if a.source == t_init]
        self.assertEqual(len(init_outputs), 1)
        loop_head = init_outputs[0]

        # Standard XOR-split at loop head: 2 competing transitions
        head_outputs = [a.target for a in net.arcs if a.source == loop_head]
        self.assertEqual(len(head_outputs), 2)

        t_while = next(t for t in head_outputs if "while count < 10" in t.label)
        t_exit = next(t for t in head_outputs if t.label == "exit")

        # Loop transition leads to body entry place
        while_outputs = [a.target for a in net.arcs if a.source == t_while]
        self.assertEqual(len(while_outputs), 1)
        body_entry = while_outputs[0]

        # Body statement count = count + 1
        body_trans = [a.target for a in net.arcs if a.source == body_entry]
        self.assertEqual(len(body_trans), 1)
        t_body = body_trans[0]
        self.assertIn("count = count + 1", t_body.label)

        # The body's terminal transition arcs BACK to the loop head place, creating a cycle!
        body_exit_arcs = [a for a in net.arcs if a.source == t_body]
        self.assertEqual(len(body_exit_arcs), 1)
        self.assertIs(body_exit_arcs[0].target, loop_head)

        # Assert cycle exists in the graph
        cycles = find_directed_cycles(net)
        self.assertGreaterEqual(len(cycles), 1)
        # Verify the cycle contains loop_head, t_while, body_entry, t_body
        cycle_node_set = set(cycles[0])
        self.assertIn(loop_head.id, cycle_node_set)
        self.assertIn(t_while.id, cycle_node_set)
        self.assertIn(body_entry.id, cycle_node_set)
        self.assertIn(t_body.id, cycle_node_set)

        # Exit transition leads to loop exit place
        exit_outputs = [a.target for a in net.arcs if a.source == t_exit]
        self.assertEqual(len(exit_outputs), 1)
        loop_exit = exit_outputs[0]
        self.assertNotEqual(loop_exit, loop_head)

        # Loop exit place flows into return count
        t_ret = next(t for t in net.transitions if "return count" in t.label)
        ret_inputs = [a.source for a in net.arcs if a.target == t_ret]
        self.assertEqual(ret_inputs, [loop_exit])


class TestForLoop(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "for_loop.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "for_loop_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_for_loop_counts(self):
        net = walk_net(walker, self.func_node)
        self.assertIsInstance(net, PetriNet)
        # 6 transitions: total = 0, items = [1, 2, 3], for item in items, else, total = total + item, return total
        self.assertEqual(len(net.transitions), 6)
        # 6 places: p0(start), p1, p2(loop_head), p3(body_entry), p4(loop_exit), p_end
        self.assertEqual(len(net.places), 6)
        # 12 arcs
        self.assertEqual(len(net.arcs), 12)

    def test_for_loop_cycle_and_xor_split(self):
        net = walk_net(walker, self.func_node)

        # Transition for items = [1, 2, 3] leads to loop head place
        t_items = next(t for t in net.transitions if "items = [1, 2, 3]" in t.label)
        items_outputs = [a.target for a in net.arcs if a.source == t_items]
        self.assertEqual(len(items_outputs), 1)
        loop_head = items_outputs[0]

        # Standard XOR-split at loop head: 2 competing transitions
        head_outputs = [a.target for a in net.arcs if a.source == loop_head]
        self.assertEqual(len(head_outputs), 2)

        t_for = next(t for t in head_outputs if "for item in items" in t.label)
        t_exit = next(t for t in head_outputs if t.label == "exit")

        # Loop transition leads to body entry place
        for_outputs = [a.target for a in net.arcs if a.source == t_for]
        self.assertEqual(len(for_outputs), 1)
        body_entry = for_outputs[0]

        # Body statement total = total + item
        body_trans = [a.target for a in net.arcs if a.source == body_entry]
        self.assertEqual(len(body_trans), 1)
        t_body = body_trans[0]
        self.assertIn("total = total + item", t_body.label)

        # Body's terminal transition arcs back to loop head
        body_exit_arcs = [a for a in net.arcs if a.source == t_body]
        self.assertEqual(len(body_exit_arcs), 1)
        self.assertIs(body_exit_arcs[0].target, loop_head)

        # Assert cycle exists in graph
        cycles = find_directed_cycles(net)
        self.assertGreaterEqual(len(cycles), 1)
        cycle_node_set = set(cycles[0])
        self.assertIn(loop_head.id, cycle_node_set)
        self.assertIn(t_for.id, cycle_node_set)
        self.assertIn(body_entry.id, cycle_node_set)
        self.assertIn(t_body.id, cycle_node_set)

        # Exit transition leads to loop exit place
        exit_outputs = [a.target for a in net.arcs if a.source == t_exit]
        self.assertEqual(len(exit_outputs), 1)
        loop_exit = exit_outputs[0]
        self.assertNotEqual(loop_exit, loop_head)

        # Loop exit place flows into return total
        t_ret = next(t for t in net.transitions if "return total" in t.label)
        ret_inputs = [a.source for a in net.arcs if a.target == t_ret]
        self.assertEqual(ret_inputs, [loop_exit])



class TestLoopBreakContinue(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "loop_break_continue.py",
        )
        self.tree = parse_file(self.fixture_path)
        self.func_node = find_function(self.tree, "loop_break_continue_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.func_node)

    def test_break_continue_counts(self):
        net = walk_net(walker, self.func_node)
        self.assertIsInstance(net, PetriNet)
        self.assertEqual(len(net.transitions), 11)
        self.assertEqual(len(net.places), 9)
        self.assertEqual(len(net.arcs), 22)

    def test_break_and_continue_targets(self):
        net = walk_net(walker, self.func_node)

        t_while = next(t for t in net.transitions if "while i < 10" in t.label)
        loop_head = [a.source for a in net.arcs if a.target == t_while][0]

        t_exit = next(t for t in net.transitions if t.label == "exit" and t.line_number == 3)
        loop_exit = [a.target for a in net.arcs if a.source == t_exit][0]

        # Break transition targets loop_exit directly
        t_break = next(t for t in net.transitions if t.label == "break")
        break_targets = [a.target for a in net.arcs if a.source == t_break]
        self.assertEqual(break_targets, [loop_exit])

        # Continue transition targets loop_head
        t_continue = next(t for t in net.transitions if t.label == "continue")
        continue_targets = [a.target for a in net.arcs if a.source == t_continue]
        self.assertEqual(continue_targets, [loop_head])

        # Verify cycles exist
        cycles = find_directed_cycles(net)
        self.assertGreaterEqual(len(cycles), 2)

    def test_break_outside_loop_raises(self):
        code = "def bad():\n    break\n"
        import ast
        tree = ast.parse(code)
        func = tree.body[0]
        with self.assertRaises(SyntaxError):
            walk_net(walker, func)

    def test_continue_outside_loop_raises(self):
        code = "def bad():\n    continue\n"
        import ast
        tree = ast.parse(code)
        func = tree.body[0]
        with self.assertRaises(SyntaxError):
            walk_net(walker, func)

    def test_nested_loops_break_continue(self):
        code = (
            "def nested():\n"
            "    out = 0\n"
            "    while out < 5:\n"
            "        in_val = 0\n"
            "        while in_val < 3:\n"
            "            in_val = in_val + 1\n"
            "            if in_val == 1:\n"
            "                continue\n"
            "            if in_val == 2:\n"
            "                break\n"
            "        out = out + 1\n"
            "    return out\n"
        )
        import ast
        tree = ast.parse(code)
        func = tree.body[0]
        net = walk_net(walker, func)

        # Outer while and inner while
        t_out_while = next(t for t in net.transitions if "while out < 5" in t.label)
        t_in_while = next(t for t in net.transitions if "while in_val < 3" in t.label)

        p_out_head = [a.source for a in net.arcs if a.target == t_out_while][0]
        p_in_head = [a.source for a in net.arcs if a.target == t_in_while][0]
        self.assertNotEqual(p_out_head, p_in_head)

        # Break targets inner loop exit, not outer loop exit
        t_break = next(t for t in net.transitions if t.label == "break")
        break_target = [a.target for a in net.arcs if a.source == t_break][0]
        self.assertNotEqual(break_target, p_out_head)

        # Continue targets inner loop head, not outer loop head
        t_continue = next(t for t in net.transitions if t.label == "continue")
        continue_target = [a.target for a in net.arcs if a.source == t_continue][0]
        self.assertEqual(continue_target, p_in_head)
        self.assertNotEqual(continue_target, p_out_head)





class TestLoopElse(unittest.TestCase):
    def setUp(self):
        self.while_else_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "while_else.py",
        )
        self.while_tree = parse_file(self.while_else_path)
        self.while_func = find_function(self.while_tree, "while_else_func")

        self.for_else_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "for_else.py",
        )
        self.for_tree = parse_file(self.for_else_path)
        self.for_func = find_function(self.for_tree, "for_else_func")

    def test_fixture_loaded(self):
        self.assertIsNotNone(self.while_func)
        self.assertIsNotNone(self.for_func)

    def test_while_else_structure(self):
        net = walk_net(walker, self.while_func)
        t_while = next(t for t in net.transitions if "while i < 3" in t.label)
        loop_head = [a.source for a in net.arcs if a.target == t_while][0]

        # The competing exit transition is t_exit (label="else")
        head_outputs = [a.target for a in net.arcs if a.source == loop_head]
        t_exit = next(t for t in head_outputs if t.label == "else")

        # t_exit leads to else-branch entry place
        else_entry = [a.target for a in net.arcs if a.source == t_exit][0]

        # Transition for i = 99 in else body
        t_else_body = next(t for t in net.transitions if "i = 99" in t.label)
        self.assertEqual([a.source for a in net.arcs if a.target == t_else_body], [else_entry])

        # t_else_body leads to loop exit place
        loop_exit = [a.target for a in net.arcs if a.source == t_else_body][0]

        # break transition targets loop_exit directly, bypassing else_entry and t_else_body
        t_break = next(t for t in net.transitions if t.label == "break")
        break_targets = [a.target for a in net.arcs if a.source == t_break]
        self.assertEqual(break_targets, [loop_exit])
        self.assertNotEqual(break_targets[0], else_entry)

        # Loop exit leads to return i
        t_ret = next(t for t in net.transitions if "return i" in t.label)
        self.assertEqual([a.source for a in net.arcs if a.target == t_ret], [loop_exit])

    def test_for_else_structure(self):
        net = walk_net(walker, self.for_func)
        t_for = next(t for t in net.transitions if "for item in items" in t.label)
        loop_head = [a.source for a in net.arcs if a.target == t_for][0]

        head_outputs = [a.target for a in net.arcs if a.source == loop_head]
        t_exit = next(t for t in head_outputs if t.label == "else")

        else_entry = [a.target for a in net.arcs if a.source == t_exit][0]
        t_else_body = next(t for t in net.transitions if "item = 0" in t.label)
        self.assertEqual([a.source for a in net.arcs if a.target == t_else_body], [else_entry])

        loop_exit = [a.target for a in net.arcs if a.source == t_else_body][0]
        t_break = next(t for t in net.transitions if t.label == "break")
        break_targets = [a.target for a in net.arcs if a.source == t_break]
        self.assertEqual(break_targets, [loop_exit])


if __name__ == '__main__':
    unittest.main()



