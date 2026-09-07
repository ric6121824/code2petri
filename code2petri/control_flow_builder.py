"""Shared control flow builder infrastructure for Petri net generation.

To comply with the project architecture rule ('Avoid: walker base class'), language
walkers compose this builder internally rather than inheriting from a walker base class.
"""

from typing import Optional, List, NamedTuple, Any
from code2petri.model import PetriNet, Place, Transition


class LoopContext(NamedTuple):
    """Enclosing loop context tracking head and exit places."""
    head: Optional[Place]
    exit: Place


class LoopRouting(NamedTuple):
    """Routing endpoints and transitions for standard loop control flow."""
    head: Place
    loop_trans: Transition
    exit_trans: Transition
    exit_place: Place


class TryContext(NamedTuple):
    """Enclosing try context tracking exception and finally entry places."""
    except_entry: Place
    finally_entry: Optional[Place] = None
    loop_depth: int = 0


class ControlFlowBuilder:
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

    def walk_branch(
        self,
        statements: Any,
        source_transition: Transition,
        target_exit: Place,
        walk_block_fn: Any,
        line_number: Optional[int] = None,
    ) -> Optional[Place]:
        """Creates an entry place from source_transition and walks statements to target_exit using walk_block_fn.

        If statements is empty/None, connects source_transition directly to target_exit and returns target_exit.
        """
        if not statements:
            self.net.add_arc(source=source_transition, target=target_exit)
            return target_exit
        entry_place = self.new_place(line_number=line_number)
        self.net.add_arc(source=source_transition, target=entry_place)
        return walk_block_fn(statements, current_place=entry_place, target_exit=target_exit)

    def get_active_finally(self) -> Optional[Place]:
        """Returns the innermost finally entry that must execute on return/termination."""
        for ctx in reversed(self.try_stack):
            if ctx.finally_entry is not None:
                return ctx.finally_entry
        return None

    def get_active_finally_for_loop(self) -> Optional[Place]:
        """Returns the innermost finally entry that is nested within the current loop."""
        curr_loop_depth = len(self.loop_stack)
        for ctx in reversed(self.try_stack):
            if ctx.loop_depth >= curr_loop_depth and ctx.finally_entry is not None:
                return ctx.finally_entry
        return None

    def wire_standard_loop(
        self,
        routing: LoopRouting,
        body_stmts: Any,
        walk_block_fn: Any,
        lineno: Optional[int] = None,
    ) -> None:
        """Wires standard loop head, body branch with back-arc, and exit transition."""
        self.net.add_arc(source=routing.head, target=routing.loop_trans)
        self.net.add_arc(source=routing.head, target=routing.exit_trans)

        self.loop_stack.append(LoopContext(head=routing.head, exit=routing.exit_place))
        self.walk_branch(body_stmts, routing.loop_trans, routing.head, walk_block_fn, lineno)
        self.loop_stack.pop()

    def wire_return(
        self,
        current_place: Place,
        label: str,
        line_number: Optional[int] = None,
    ) -> Transition:
        """Wires a return transition arcing to active finally block or end_place."""
        trans = self.new_transition(label=label, line_number=line_number)
        self.net.add_arc(source=current_place, target=trans)
        target = self.get_active_finally() or self.end_place
        if target is not None:
            self.net.add_arc(source=trans, target=target)
        return trans

    def wire_break(
        self,
        current_place: Place,
        label: str,
        line_number: Optional[int] = None,
    ) -> Transition:
        """Wires a break transition arcing to active loop finally block or loop exit."""
        if not self.loop_stack:
            raise SyntaxError(f"'break' outside loop at line {line_number}")
        loop_ctx = self.loop_stack[-1]
        target = self.get_active_finally_for_loop() or loop_ctx.exit
        trans = self.new_transition(label=label, line_number=line_number)
        self.net.add_arc(source=current_place, target=trans)
        self.net.add_arc(source=trans, target=target)
        return trans

    def wire_continue(
        self,
        current_place: Place,
        label: str,
        line_number: Optional[int] = None,
    ) -> Transition:
        """Wires a continue transition arcing to active loop finally block or loop head."""
        if not self.loop_stack:
            raise SyntaxError(f"'continue' outside loop at line {line_number}")
        target = self.get_active_finally_for_loop()
        if target is None:
            for ctx in reversed(self.loop_stack):
                if ctx.head is not None:
                    target = ctx.head
                    break
        if target is None:
            raise SyntaxError(f"'continue' outside loop at line {line_number}")
        trans = self.new_transition(label=label, line_number=line_number)
        self.net.add_arc(source=current_place, target=trans)
        self.net.add_arc(source=trans, target=target)
        return trans

    def wire_terminal_exception(
        self,
        current_place: Place,
        label: str,
        line_number: Optional[int] = None,
    ) -> Transition:
        """Wires a terminal exception (raise/throw) transition.

        Connects current_place to the transition. If outside any try block,
        arcs directly to self.end_place. Inside a try block, new_transition adds exception arcs.
        """
        trans = self.new_transition(label=label, line_number=line_number)
        self.net.add_arc(source=current_place, target=trans)
        if not self.try_stack:
            target = self.get_active_finally() or self.end_place
            if target is not None:
                self.net.add_arc(source=trans, target=target)
        return trans

