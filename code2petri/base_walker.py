from typing import Optional, List, NamedTuple, Any
from code2petri.model import PetriNet, Place, Transition


class LoopContext(NamedTuple):
    """Enclosing loop context tracking head and exit places."""
    head: Optional[Place]
    exit: Place


class TryContext(NamedTuple):
    """Enclosing try context tracking the exception entry place."""
    except_entry: Place


class _BaseControlFlowWalker:

    """Internal control flow builder managing places, transitions, stacks, and counters."""

    def __init__(
        self,
        net: Optional[PetriNet] = None,
        end_place: Optional[Place] = None,
    ) -> None:
        self.net = net if net is not None else PetriNet()
        self.end_place = end_place
        self.place_counter = 0
        self.trans_counter = 0
        self.loop_stack: List[LoopContext] = []
        self.try_stack: List[TryContext] = []

    def new_place(
        self,
        label: Optional[str] = None,
        line_number: Optional[int] = None,
    ) -> Place:
        """Creates and registers a new Place with auto-incremented ID."""
        self.place_counter += 1
        p_id = f"p{self.place_counter}"
        p_label = label or p_id
        return self.net.add_place(
            id_=p_id,
            label=p_label,
            line_number=line_number,
            initial_tokens=0,
        )

    def new_transition(
        self,
        label: str,
        line_number: Optional[int] = None,
        hook_exception: bool = True,
    ) -> Transition:
        """Creates and registers a new Transition with auto-incremented ID, hooking into try_stack if active."""
        self.trans_counter += 1
        t_id = f"t{self.trans_counter}"
        trans = self.net.add_transition(
            id_=t_id,
            label=label,
            line_number=line_number,
        )
        if hook_exception and self.try_stack:
            self.net.add_arc(source=trans, target=self.try_stack[-1].except_entry)
        return trans

    def _walk_branch(
        self,
        statements: Any,
        source_transition: Transition,
        target_exit: Place,
        line_number: Optional[int] = None,
    ) -> Optional[Place]:
        """Creates an entry place from source_transition and walks statements to target_exit."""
        entry_place = self.new_place(line_number=line_number)
        self.net.add_arc(source=source_transition, target=entry_place)
        return self.walk_block(statements, current_place=entry_place, target_exit=target_exit)

    def _wire_standard_loop(
        self,
        loop_head: Place,
        loop_trans: Transition,
        exit_trans: Transition,
        loop_exit: Place,
        body_stmts: Any,
        lineno: Optional[int] = None,
    ) -> None:
        """Wires standard loop head, body branch with back-arc, and exit transition."""
        self.net.add_arc(source=loop_head, target=loop_trans)
        self.net.add_arc(source=loop_head, target=exit_trans)

        self.loop_stack.append(LoopContext(head=loop_head, exit=loop_exit))
        self._walk_branch(body_stmts, loop_trans, loop_head, lineno)
        self.loop_stack.pop()

    def _wire_terminal_exception(
        self,
        current_place: Place,
        label: str,
        line_number: Optional[int] = None,
    ) -> Transition:
        """Wires a terminal exception (raise/throw) transition.

        Connects current_place to the transition. If outside any try block,
        arcs directly to self.end_place. Inside a try block, _walk_branch adds exception arcs.
        """
        trans = self.new_transition(label=label, line_number=line_number)
        self.net.add_arc(source=current_place, target=trans)
        if not self.try_stack:
            self.net.add_arc(source=trans, target=self.end_place)
        return trans

    def walk_block(
        self,
        statements: Any,
        current_place: Place,
        target_exit: Place,
    ) -> Optional[Place]:
        """Subclasses must implement statement traversal."""
        raise NotImplementedError("Subclasses must implement walk_block")

