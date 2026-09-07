"""Shared control flow builder infrastructure for Petri net generation.

To comply with the project architecture rule ('Avoid: walker base class'), language
walkers compose this builder internally rather than inheriting from a walker base class.
"""

from typing import Optional, List, NamedTuple, Any, Union, Tuple
from code2petri.model import PetriNet, Place, Transition, Arc


class StatementContext(NamedTuple):
    """Context information for walking a single statement within a block."""
    current_place: Place
    is_last: bool
    target_exit: Place
    lineno: Optional[int] = None


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

    def add_arc(
        self,
        source: Union[Place, Transition],
        target: Union[Place, Transition],
    ) -> Arc:
        """Adds an arc between a place and transition."""
        return self.net.add_arc(source=source, target=target)

    def push_try(self, try_context: TryContext) -> None:
        """Pushes a try context onto the try stack."""
        self.try_stack.append(try_context)

    def pop_try(self) -> Optional[TryContext]:
        """Pops and returns the innermost try context, or None if empty."""
        return self.try_stack.pop() if self.try_stack else None

    def push_loop(self, head: Optional[Place], exit: Place) -> None:
        """Pushes a loop context onto the loop stack."""
        self.loop_stack.append(LoopContext(head=head, exit=exit))

    def pop_loop(self) -> Optional[LoopContext]:
        """Pops and returns the innermost loop context, or None if empty."""
        return self.loop_stack.pop() if self.loop_stack else None

    def has_incoming_arcs(self, node: Union[Place, Transition]) -> bool:
        """Returns True if any arc in the net has node as its target."""
        return any(arc.target == node for arc in self.net.arcs)

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

    def wire_sequential_statement(
        self,
        current_place: Place,
        label: str,
        lineno: Optional[int],
        is_last: bool,
        target_exit: Place,
    ) -> Place:
        """Wires a standard sequential statement from current_place to next place."""
        next_place = target_exit if is_last else self.new_place(line_number=lineno)
        trans = self.new_transition(label=label, line_number=lineno)
        self.net.add_arc(source=current_place, target=trans)
        self.net.add_arc(source=trans, target=next_place)
        return next_place

    def wire_if_split(
        self,
        ctx: StatementContext,
        true_label: str,
        consequent_stmts: Any,
        false_lineno: Optional[int],
        alternate_stmts: Any,
        walk_block_fn: Any,
        false_label: str = "else",
    ) -> Optional[Place]:
        """Wires an if/else XOR branching split and merges paths."""
        true_trans = self.new_transition(
            label=true_label,
            line_number=ctx.lineno,
        )
        self.add_arc(source=ctx.current_place, target=true_trans)

        false_trans = self.new_transition(
            label=false_label,
            line_number=false_lineno,
        )
        self.add_arc(source=ctx.current_place, target=false_trans)

        merge_place = ctx.target_exit if ctx.is_last else self.new_place(
            label=f"merge_{true_trans.id}", line_number=ctx.lineno
        )

        true_exit = self.walk_branch(
            consequent_stmts,
            source_transition=true_trans,
            target_exit=merge_place,
            walk_block_fn=walk_block_fn,
            line_number=ctx.lineno,
        )
        false_exit = self.walk_branch(
            alternate_stmts,
            source_transition=false_trans,
            target_exit=merge_place,
            walk_block_fn=walk_block_fn,
            line_number=false_lineno,
        )

        if true_exit is None and false_exit is None:
            return None

        return merge_place

    def wire_try_catch(
        self,
        ctx: StatementContext,
        try_body: Any,
        handlers: List[Tuple[str, Optional[int], Any]],
        finally_stmts: Optional[Any],
        finally_lineno: Optional[int],
        walk_block_fn: Any,
        else_stmts: Optional[Any] = None,
        else_lineno: Optional[int] = None,
    ) -> Place:
        """Wires try/catch/else/finally exception handling constructs."""
        except_entry = self.new_place(label="except_entry", line_number=ctx.lineno)
        try_exit = ctx.target_exit if ctx.is_last else self.new_place(label="try_exit", line_number=ctx.lineno)

        if finally_stmts:
            finally_entry = self.new_place(label="finally_entry", line_number=finally_lineno)
            finally_target = finally_entry
        else:
            finally_entry = None
            finally_target = try_exit

        if else_stmts:
            else_entry = self.new_place(label="else_entry", line_number=else_lineno)
            try_normal_exit = else_entry
        else:
            else_entry = None
            try_normal_exit = finally_target

        self.push_try(TryContext(
            except_entry=except_entry,
            finally_entry=finally_entry,
            loop_depth=len(self.loop_stack),
        ))
        walk_block_fn(try_body, current_place=ctx.current_place, target_exit=try_normal_exit)
        self.pop_try()

        if else_stmts and else_entry is not None:
            walk_block_fn(else_stmts, current_place=else_entry, target_exit=finally_target)

        if handlers:
            for h_label, h_lineno, h_body in handlers:
                h_trans = self.new_transition(
                    label=h_label,
                    line_number=h_lineno,
                    hook_exception=False,
                )
                self.add_arc(source=except_entry, target=h_trans)
                self.walk_branch(
                    h_body,
                    source_transition=h_trans,
                    target_exit=finally_target,
                    walk_block_fn=walk_block_fn,
                    line_number=h_lineno,
                )
        elif finally_stmts:
            exc_trans = self.new_transition(
                label="exception",
                line_number=ctx.lineno,
                hook_exception=False,
            )
            self.add_arc(source=except_entry, target=exc_trans)
            self.add_arc(source=exc_trans, target=finally_target)

        if finally_stmts and finally_entry is not None:
            walk_block_fn(finally_stmts, current_place=finally_entry, target_exit=try_exit)

        return try_exit

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
            target = self.end_place
            if target is not None:
                self.net.add_arc(source=trans, target=target)
        return trans

