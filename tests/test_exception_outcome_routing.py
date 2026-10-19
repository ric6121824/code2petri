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


def reachable_completion_traces(net, max_steps=50):
    """Return simple transition traces ending at normal or exceptional boundaries."""
    places = {place.id: place for place in net.places}
    inputs = {transition.id: [] for transition in net.transitions}
    outputs = {transition.id: [] for transition in net.transitions}
    transitions = {transition.id: transition for transition in net.transitions}
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
    frontier = [(initial, tuple(), frozenset({initial}))]
    completions = []
    boundary_ids = {
        place.id for place in net.places
        if place.label in {"end", "exception_end"}
    }
    while frontier:
        state, trace, path_states = frontier.pop()
        marking = dict(state)
        if any(marking.get(place_id, 0) for place_id in boundary_ids):
            completions.append((marking, trace))
            continue
        if len(trace) >= max_steps:
            continue
        for transition_id, required in inputs.items():
            if not all(marking.get(place_id, 0) >= weight for place_id, weight in required):
                continue
            next_marking = dict(marking)
            for place_id, weight in required:
                next_marking[place_id] -= weight
            for place_id, weight in outputs[transition_id]:
                next_marking[place_id] = next_marking.get(place_id, 0) + weight
            next_state = tuple(sorted(
                (place_id, count)
                for place_id, count in next_marking.items()
                if count
            ))
            if next_state in path_states:
                continue
            frontier.append((next_state, trace + (transition_id,), path_states | {next_state}))

    return [
        (marking, tuple(transitions[transition_id].label for transition_id in trace), trace)
        for marking, trace in completions
    ]


class TestExceptionOutcomeRouting(unittest.TestCase):
    def setUp(self):
        self.walker = PythonWalker()

    def _walk_source(self, source, function_name):
        tree = ast.parse(source)
        function = self.walker.find_function(tree, function_name)
        self.assertIsNotNone(function)
        return self.walker.walk_function(function, function_name).net

    def _walk_javascript_source(self, source, function_name):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "sample.js")
            with open(path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            walker = JavascriptWalker()
            tree = walker.parse_file(path)
            function = walker.find_function(tree, function_name)
            self.assertIsNotNone(function)
            return walker.walk_function(function, function_name, filepath=path).net

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

    def test_uncaught_raise_runs_finally_before_exception_exit(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        raise ValueError()\n"
            "    finally:\n"
            "        cleanup()\n",
            "sample",
        )
        normal_end = next(place for place in net.places if place.label == "end")
        exception_end = net.find_exception_boundary_place()
        cleanup_ids = {
            transition.id for transition in net.transitions
            if transition.label in {"call: cleanup()", "exception: call: cleanup()"}
        }
        traces = reachable_completion_traces(net)

        self.assertIsNotNone(exception_end)
        self.assertFalse(any(marking.get(normal_end.id, 0) for marking, _, _ in traces))
        exceptional = [
            (labels, transition_ids) for marking, labels, transition_ids in traces
            if marking.get(exception_end.id, 0)
        ]
        self.assertTrue(exceptional)
        self.assertTrue(all(cleanup_ids.intersection(transition_ids) for _, transition_ids in exceptional))

    def test_uncaught_raise_through_nonfinal_try_skips_following_statement(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        raise ValueError()\n"
            "    finally:\n"
            "        cleanup()\n"
            "    after()\n",
            "sample",
        )
        after = next(transition for transition in net.transitions if transition.label == "call: after()")
        traces = reachable_completion_traces(net)

        self.assertTrue(traces)
        self.assertFalse(any(after.id in transition_ids for _, _, transition_ids in traces))

    def test_normal_completion_runs_finally_and_reaches_normal_exit(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        work()\n"
            "    finally:\n"
            "        cleanup()\n",
            "sample",
        )
        cleanup_ids = {
            transition.id for transition in net.transitions
            if transition.label == "call: cleanup()"
        }
        traces = reachable_completion_traces(net)
        normal = [
            (marking, trace, ids) for marking, trace, ids in traces
            if next(place for place in net.places if place.label == "end").id in marking
        ]

        self.assertTrue(normal)
        self.assertTrue(all(cleanup_ids.intersection(ids) for _, _, ids in normal))

    def test_handled_exception_runs_finally_then_completes_normally(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        raise ValueError()\n"
            "    except ValueError:\n"
            "        handled()\n"
            "    finally:\n"
            "        cleanup()\n",
            "sample",
        )
        cleanup_ids = {
            transition.id for transition in net.transitions
            if transition.label == "call: cleanup()"
        }
        traces = reachable_completion_traces(net)
        normal = [
            (marking, labels, ids) for marking, labels, ids in traces
            if any(place.label == "end" and marking.get(place.id, 0) for place in net.places)
        ]

        self.assertTrue(normal)
        self.assertTrue(all(cleanup_ids.intersection(ids) for _, _, ids in normal))
        self.assertTrue(all("call: handled()" in labels for _, labels, _ in normal))

    def test_raise_in_finally_overrides_pending_normal_completion(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        work()\n"
            "    finally:\n"
            "        raise ValueError()\n",
            "sample",
        )
        traces = reachable_completion_traces(net)
        exception_end = net.find_exception_boundary_place()
        normal_end = next(place for place in net.places if place.label == "end")
        exceptional = [
            (marking, labels) for marking, labels, _ in traces
            if exception_end is not None and marking.get(exception_end.id, 0)
        ]

        self.assertTrue(exceptional)
        self.assertFalse(any(marking.get(normal_end.id, 0) for marking, _, _ in traces))
        self.assertTrue(all("raise ValueError()" in labels for _, labels in exceptional))

    def test_nested_finally_preserves_exception_and_cleanup_order(self):
        net = self._walk_source(
            "def sample():\n"
            "    try:\n"
            "        try:\n"
            "            raise ValueError()\n"
            "        finally:\n"
            "            inner_cleanup()\n"
            "    finally:\n"
            "        outer_cleanup()\n",
            "sample",
        )
        traces = reachable_completion_traces(net)
        exception_end = net.find_exception_boundary_place()
        exceptional = [
            labels for marking, labels, _ in traces
            if exception_end is not None and marking.get(exception_end.id, 0)
        ]

        self.assertTrue(exceptional)
        for labels in exceptional:
            inner_attempts = [
                i for i, label in enumerate(labels)
                if label in {"call: inner_cleanup()", "exception: call: inner_cleanup()"}
            ]
            outer_attempts = [
                i for i, label in enumerate(labels)
                if label in {"call: outer_cleanup()", "exception: call: outer_cleanup()"}
            ]
            self.assertTrue(inner_attempts)
            self.assertTrue(outer_attempts)
            self.assertLess(inner_attempts[0], outer_attempts[0])

    def test_javascript_throw_runs_finally_before_exception_exit(self):
        net = self._walk_javascript_source(
            "function sample() {\n"
            "  try {\n"
            "    throw new Error();\n"
            "  } finally {\n"
            "    cleanup();\n"
            "  }\n"
            "}\n",
            "sample",
        )
        traces = reachable_completion_traces(net)
        exception_end = net.find_exception_boundary_place()
        normal_end = next(place for place in net.places if place.label == "end")
        exceptional = [
            (marking, labels) for marking, labels, _ in traces
            if exception_end is not None and marking.get(exception_end.id, 0)
        ]

        self.assertTrue(exceptional)
        self.assertFalse(any(marking.get(normal_end.id, 0) for marking, _, _ in traces))
        self.assertTrue(all(
            any(label in {"call: cleanup()", "exception: call: cleanup()"} for label in labels)
            for _, labels in exceptional
        ))

    def test_inlined_finally_exception_runs_cleanup_before_caller_handler(self):
        source = (
            "def worker():\n"
            "    try:\n"
            "        raise ValueError()\n"
            "    finally:\n"
            "        cleanup()\n"
            "\n"
            "def caller():\n"
            "    try:\n"
            "        worker()\n"
            "        after_in_try()\n"
            "    except:\n"
            "        recovered()\n"
            "    after_catch()\n"
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

        traces = reachable_completion_traces(composite)
        normal_end = next(place for place in composite.places if place.label == "end")
        normal = [
            (marking, labels, ids) for marking, labels, ids in traces
            if marking.get(normal_end.id, 0)
        ]
        self.assertTrue(normal)
        self.assertTrue(all(
            any(label in {"call: cleanup()", "exception: call: cleanup()"} for label in labels)
            for _, labels, _ in normal
        ))
        self.assertTrue(all("call: recovered()" in labels for _, labels, _ in normal))
        self.assertTrue(all("call: after_catch()" in labels for _, labels, _ in normal))
        self.assertTrue(all("call: after_in_try()" not in labels for _, labels, _ in normal))

        cleanup_calls = [t for t in composite.transitions if t.label == "call: cleanup()"]
        self.assertEqual(len(cleanup_calls), 2)
        self.assertEqual(len({t.id for t in cleanup_calls}), 2)
        for transition in cleanup_calls:
            call_results = (transition.metadata or {}).get("call_results", [])
            self.assertEqual(call_results[0]["transition_id"], transition.id)
            self.assertEqual(transition.get_tau(), 1.0)

        after_in_try = next(t for t in composite.transitions if t.label == "call: after_in_try()")
        after_in_try_entry = next(arc.source for arc in composite.arcs if arc.target == after_in_try)
        handler_entry = next(place for place in composite.places if place.label == "except_entry")
        self.assertFalse(any(
            marking.get(after_in_try_entry.id, 0) and marking.get(handler_entry.id, 0)
            for marking in reachable_markings(composite)
        ))

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
