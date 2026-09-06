import unittest
from code2petri.model import PetriNet, Place, Transition, Arc


def assert_has_start_and_end(test_case: unittest.TestCase, net: PetriNet) -> tuple[Place, Place]:
    """Asserts that the net has exactly one start place and one end place with proper tokens and arcs."""
    start_places = [p for p in net.places if p.initial_tokens == 1]
    test_case.assertEqual(len(start_places), 1, "Expected exactly 1 start place with initial_tokens=1")
    start_place = start_places[0]
    test_case.assertEqual(start_place.label, "start", "Start place must have label 'start'")

    end_places = [p for p in net.places if p.label == "end"]
    test_case.assertEqual(len(end_places), 1, "Expected exactly 1 end place with label 'end'")
    end_place = end_places[0]
    test_case.assertEqual(end_place.initial_tokens, 0, "End place must have initial_tokens=0")

    # Start place has outgoing arc
    outgoing_start = [a for a in net.arcs if a.source == start_place]
    test_case.assertGreaterEqual(len(outgoing_start), 1, "Start place must have at least 1 outgoing arc")

    # End place has incoming arc and no outgoing arcs
    incoming_end = [a for a in net.arcs if a.target == end_place]
    test_case.assertGreaterEqual(len(incoming_end), 1, "End place must have at least 1 incoming arc")
    outgoing_end = [a for a in net.arcs if a.source == end_place]
    test_case.assertEqual(len(outgoing_end), 0, "End place must have 0 outgoing arcs")

    return start_place, end_place


def assert_bipartite(test_case: unittest.TestCase, net: PetriNet) -> None:
    """Asserts that all arcs in the net strictly alternate between Place and Transition."""
    for arc in net.arcs:
        is_p_to_t = isinstance(arc.source, Place) and isinstance(arc.target, Transition)
        is_t_to_p = isinstance(arc.source, Transition) and isinstance(arc.target, Place)
        test_case.assertTrue(
            is_p_to_t or is_t_to_p,
            f"Arc {arc} violates bipartite property (source={type(arc.source).__name__}, target={type(arc.target).__name__})"
        )


def assert_valid_petri_net(test_case: unittest.TestCase, net: PetriNet) -> tuple[Place, Place]:
    """Asserts that the net is non-empty, bipartite, and has valid start and end places."""
    test_case.assertIsInstance(net, PetriNet)
    test_case.assertGreater(len(net.places), 0, "Net has no places")
    test_case.assertGreater(len(net.transitions), 0, "Net has no transitions")
    test_case.assertGreater(len(net.arcs), 0, "Net has no arcs")
    assert_bipartite(test_case, net)
    return assert_has_start_and_end(test_case, net)
