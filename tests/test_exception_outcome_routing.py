import ast
import os
import tempfile
import unittest

from code2petri.inline import inline_expand
from code2petri.javascript_walker import JavascriptWalker
from code2petri.python_walker import PythonWalker
from code2petri.symbol_table import SymbolTable


def reachable_markings(net, max_steps=30):
    """Return bounded Petri-net markings reachable from the net's initial tokens."""
    places = {place.id: place for place in net.places}
    inputs = {transition.id: [] for transition in net.transitions}
    outputs = {transition.id: [] for transition in net.transitions}
    for arc in net.arcs:
        if arc.target.id in inputs and arc.source.id in places:
            inputs[arc.target.id].append((arc.source.id, arc.weight))
        elif arc.source.id in outputs and arc.target.id in places:
            outputs[arc.source.id].append((arc.target.id, arc.weight))

    initial = tuple(sorted(
        (place.id, place.initial_tokens)
        for place in net.places
        if place.initial_tokens
    ))
    seen = {initial}
    frontier = [(initial, 0)]
    while frontier:
        state, depth = frontier.pop()
        if depth >= max_steps:
            continue
        marking = dict(state)
        for transition in net.transitions:
            required = inputs[transition.id]
            if not all(marking.get(place_id, 0) >= weight for place_id, weight in required):
                continue
            next_marking = dict(marking)
            for place_id, weight in required:
                next_marking[place_id] -= weight
            for place_id, weight in outputs[transition.id]:
                next_marking[place_id] = next_marking.get(place_id, 0) + weight
            next_state = tuple(sorted(
                (place_id, count)
                for place_id, count in next_marking.items()
                if count
            ))
            if next_state not in seen:
                seen.add(next_state)
                frontier.append((next_state, depth + 1))
    return [dict(state) for state in seen]


class TestExceptionOutcomeRouting(unittest.TestCase):
    def setUp(self):
        self.walker = PythonWalker()

    def _walk_source(self, source, function_name):
        tree = ast.parse(source)
        function = self.walker.find_function(tree, function_name)
        self.assertIsNotNone(function)
        return self.walker.walk_function(function, function_name).net

    def test_normal_completion_does_not_also_activate_handler(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        return 1\n"
            "    except:\n"
            "        return 2\n",
            "sample",
        )
        handler_entry = next(place for place in net.places if place.label == "except_entry")
        end = next(place for place in net.places if place.label == "end")
        markings = reachable_markings(net)

        self.assertTrue(any(marking.get(end.id, 0) for marking in markings))
        self.assertFalse(any(
            marking.get(end.id, 0) and marking.get(handler_entry.id, 0)
            for marking in markings
        ))

    def test_continue_inside_try_does_not_activate_handler(self):
        net = self._walk_source(
            "def sample():\n"
            "    while keep_going:\n"
            "        try:\n"
            "            continue\n"
            "        except:\n"
            "            return 2\n"
            "    return 1\n",
            "sample",
        )
        handler_entry = next(place for place in net.places if place.label == "except_entry")

        self.assertFalse(any(
            marking.get(handler_entry.id, 0)
            for marking in reachable_markings(net)
        ))

    def test_caught_raise_and_nested_handler_raise_reach_the_outer_handler(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        try:\n"
            "            raise ValueError()\n"
            "        except ValueError:\n"
            "            raise TypeError()\n"
            "    except TypeError:\n"
            "        return 1\n",
            "sample",
        )
        end = next(place for place in net.places if place.label == "end")
        self.assertIsNone(net.find_exception_boundary_place(), "both nested raises should reach modeled handlers")
        markings = reachable_markings(net)

        self.assertTrue(any(marking.get(end.id, 0) for marking in markings))

    def test_nested_caught_raises_remain_caught_after_inline_expansion(self):
        source = (
            "def worker():\n"
            "    try:\n"
            "        try:\n"
            "            raise ValueError()\n"
            "        except ValueError:\n"
            "            raise TypeError()\n"
            "    except TypeError:\n"
            "        return 1\n"
            "\n"
            "def caller():\n"
            "    worker()\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.py")
            with open(path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            symbols = SymbolTable()
            symbols.index_file(path)
            tree = self.walker.parse_file(path)
            caller = self.walker.find_function(tree, "caller")
            caller_result = self.walker.walk_function(caller, "caller", filepath=path)
            composite = inline_expand(
                caller_result.net,
                caller_result.call_sites,
                symbols,
                max_depth=1,
            )
            normal_end = next(place for place in composite.places if place.label == "end")
            markings = reachable_markings(composite)

        self.assertTrue(any(marking.get(normal_end.id, 0) for marking in markings))
        self.assertIsNone(composite.find_exception_boundary_place())

    def test_returned_callee_exception_is_caught_after_inline_expansion(self):
        source = (
            "def worker():\n"
            "    raise ValueError()\n"
            "\n"
            "def caller():\n"
            "    try:\n"
            "        return worker()\n"
            "    except ValueError:\n"
            "        return 1\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.py")
            with open(path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            symbols = SymbolTable()
            symbols.index_file(path)
            tree = self.walker.parse_file(path)
            caller = self.walker.find_function(tree, "caller")
            caller_result = self.walker.walk_function(caller, "caller", filepath=path)
            composite = inline_expand(
                caller_result.net,
                caller_result.call_sites,
                symbols,
                max_depth=1,
            )
            normal_end = next(place for place in composite.places if place.label == "end")
            handler_entry = next(place for place in composite.places if place.label == "except_entry")
            markings = reachable_markings(composite)

        self.assertTrue(any(marking.get(normal_end.id, 0) for marking in markings))
        self.assertTrue(any(marking.get(handler_entry.id, 0) for marking in markings))
        self.assertFalse(any(
            marking.get(normal_end.id, 0) and marking.get(handler_entry.id, 0)
            for marking in markings
        ))

    def test_uncaught_raise_reaches_exception_exit_instead_of_normal_end(self):
        net = self._walk_source(
            "def sample():\n"
            "    raise ValueError()\n",
            "sample",
        )
        exception_end = next(
            (place for place in net.places if place.label == "exception_end"),
            None,
        )
        self.assertIsNotNone(exception_end, "function net needs a distinct exceptional exit")
        end = next(place for place in net.places if place.label == "end")
        markings = reachable_markings(net)

        self.assertTrue(any(marking.get(exception_end.id, 0) for marking in markings))
        self.assertFalse(any(marking.get(end.id, 0) for marking in markings))

    def test_shared_builder_keeps_javascript_try_outcomes_alternative(self):
        source = (
            "function sample() {\n"
            "  try {\n"
            "    return 1;\n"
            "  } catch (error) {\n"
            "    return 2;\n"
            "  }\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.js")
            with open(path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            walker = JavascriptWalker()
            tree = walker.parse_file(path)
            function = walker.find_function(tree, "sample")
            net = walker.walk_function(function, "sample", filepath=path).net

        handler_entry = next(place for place in net.places if place.label == "except_entry")
        end = next(place for place in net.places if place.label == "end")
        self.assertFalse(any(
            marking.get(end.id, 0) and marking.get(handler_entry.id, 0)
            for marking in reachable_markings(net)
        ))

    def test_inlined_callee_completion_chooses_one_caller_continuation(self):
        source = (
            "def worker():\n"
            "    if should_fail:\n"
            "        raise ValueError()\n"
            "    return 1\n"
            "\n"
            "def caller():\n"
            "    try:\n"
            "        worker()\n"
            "    except:\n"
            "        recovered()\n"
            "    return 2\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.py")
            with open(path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            symbols = SymbolTable()
            symbols.index_file(path)
            tree = self.walker.parse_file(path)
            caller = self.walker.find_function(tree, "caller")
            caller_result = self.walker.walk_function(caller, "caller", filepath=path)
            call_site = caller_result.call_sites[0]
            call_transition = next(
                transition for transition in caller_result.net.transitions
                if transition.id == call_site.transition_id
            )
            call_outputs = [
                arc.target for arc in caller_result.net.arcs
                if arc.source == call_transition
            ]
            normal_continuation = next(place for place in call_outputs if place.label != "except_entry")
            exception_alternative = next(
                transition for transition in caller_result.net.transitions
                if transition.metadata
                and transition.metadata.get("exception_alternative_of") == call_transition.id
            )
            exception_continuation = next(
                arc.target for arc in caller_result.net.arcs
                if arc.source == exception_alternative
            )

            composite = inline_expand(
                caller_result.net,
                caller_result.call_sites,
                symbols,
                max_depth=1,
            )
            markings = reachable_markings(composite)

        self.assertTrue(any(marking.get(normal_continuation.id, 0) for marking in markings))
        self.assertTrue(any(marking.get(exception_continuation.id, 0) for marking in markings))
        self.assertFalse(any(
            marking.get(normal_continuation.id, 0) and marking.get(exception_continuation.id, 0)
            for marking in markings
        ))

    def test_uncaught_inlined_raise_propagates_to_caller_exception_exit(self):
        source = (
            "def worker():\n"
            "    raise ValueError()\n"
            "\n"
            "def caller():\n"
            "    worker()\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.py")
            with open(path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            symbols = SymbolTable()
            symbols.index_file(path)
            tree = self.walker.parse_file(path)
            caller = self.walker.find_function(tree, "caller")
            caller_result = self.walker.walk_function(caller, "caller", filepath=path)
            composite = inline_expand(
                caller_result.net,
                caller_result.call_sites,
                symbols,
                max_depth=1,
            )
            exception_end = composite.find_exception_boundary_place()
            normal_end = next(place for place in composite.places if place.label == "end")
            markings = reachable_markings(composite)

        self.assertIsNotNone(exception_end)
        self.assertTrue(any(marking.get(exception_end.id, 0) for marking in markings))
        self.assertFalse(any(marking.get(normal_end.id, 0) for marking in markings))


if __name__ == "__main__":
    unittest.main()
