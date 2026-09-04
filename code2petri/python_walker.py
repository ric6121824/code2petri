import ast
from typing import Optional, Union, List, NamedTuple

from code2flow.python import Python
from code2petri.model import PetriNet, Place, Transition, Arc


def parse_file(filepath: str) -> ast.AST:
    """Parses a Python source file into an AST using code2flow's Python.get_tree."""
    return Python.get_tree(filepath, None)


def find_function(
    tree: ast.AST,
    func_name: str,
) -> Optional[Union[ast.FunctionDef, ast.AsyncFunctionDef]]:
    """Locates a function definition AST node by name within an AST."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return node
    return None


def _format_call_expression(call_node: ast.Call) -> str:
    """Formats an ast.Call node into an opaque label: call: func_name()."""
    func = call_node.func
    if isinstance(func, ast.Name):
        func_str = func.id
    elif isinstance(func, ast.Attribute):
        attribute_parts = []
        current_node = func
        while isinstance(current_node, ast.Attribute):
            attribute_parts.append(current_node.attr)
            current_node = current_node.value
        if isinstance(current_node, ast.Name):
            attribute_parts.append(current_node.id)
        func_str = ".".join(reversed(attribute_parts))
    else:
        func_str = ast.unparse(func) if hasattr(ast, "unparse") else "func"
    return f"call: {func_str}()"


def _format_statement_label(stmt: ast.stmt) -> str:
    """Returns a readable summary of the statement for transition labeling."""
    # Expression statement wrapping a bare Call
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        return _format_call_expression(stmt.value)

    # Assignment wrapping a Call
    if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call) and stmt.targets:
        target_str = ast.unparse(stmt.targets[0])
        return f"{target_str} = {_format_call_expression(stmt.value)}"

    # If condition statement
    if isinstance(stmt, ast.If):
        test_str = ast.unparse(stmt.test) if hasattr(ast, "unparse") else "condition"
        return f"if {test_str}"

    # While loop statement
    if isinstance(stmt, ast.While):
        test_str = ast.unparse(stmt.test) if hasattr(ast, "unparse") else "condition"
        return f"while {test_str}"

    # For loop statement
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        prefix = "async for" if isinstance(stmt, ast.AsyncFor) else "for"
        if hasattr(ast, "unparse"):
            target_str = ast.unparse(stmt.target)
            iter_str = ast.unparse(stmt.iter)
            return f"{prefix} {target_str} in {iter_str}"
        return f"{prefix} loop"

    if isinstance(stmt, ast.Break):
        return "break"

    if isinstance(stmt, ast.Continue):
        return "continue"

    if isinstance(stmt, ast.Try):
        return "try"

    if hasattr(ast, "unparse"):
        summary = ast.unparse(stmt)
        # Take first line if statement is multiline
        return summary.strip().split("\n")[0]

    return type(stmt).__name__


def _format_handler_label(handler: ast.ExceptHandler) -> str:
    """Formats an ast.ExceptHandler into a transition label."""
    if handler.type is not None:
        type_str = ast.unparse(handler.type) if hasattr(ast, "unparse") else "Exception"
        if handler.name:
            return f"except {type_str} as {handler.name}"
        return f"except {type_str}"
    return "except"


def _get_block_lineno(stmts: List[ast.AST], default: Optional[int] = None) -> Optional[int]:
    """Returns the line number of the first statement in a block, or default."""
    if stmts and hasattr(stmts[0], "lineno"):
        return stmts[0].lineno
    return default


class _LoopContext(NamedTuple):
    """Enclosing loop context tracking head and exit places."""
    head: Place
    exit: Place


class _TryContext(NamedTuple):
    """Enclosing try context tracking the exception entry place."""
    except_entry: Place


class _PythonControlFlowWalker:
    """Internal recursive walker constructing PetriNet places, transitions, and arcs."""

    def __init__(self, net: PetriNet, end_place: Place) -> None:
        self.net = net
        self.end_place = end_place
        self.place_counter = 0
        self.trans_counter = 0
        self.loop_stack: List[_LoopContext] = []
        self.try_stack: List[_TryContext] = []

    def new_place(
        self,
        label: Optional[str] = None,
        line_number: Optional[int] = None,
    ) -> Place:
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

    def _handle_loop_jump(
        self,
        stmt: Union[ast.Break, ast.Continue],
        current_place: Place,
    ) -> None:
        """Handles break or continue jump statements to loop exit or head."""
        is_break = isinstance(stmt, ast.Break)
        keyword = "break" if is_break else "continue"
        if not self.loop_stack:
            raise SyntaxError(f"'{keyword}' outside loop at line {stmt.lineno}")
        target_place = self.loop_stack[-1].exit if is_break else self.loop_stack[-1].head
        trans = self.new_transition(
            label=_format_statement_label(stmt),
            line_number=stmt.lineno,
        )
        self.net.add_arc(source=current_place, target=trans)
        self.net.add_arc(source=trans, target=target_place)

    def _walk_branch(
        self,
        statements: List[ast.stmt],
        source_transition: Transition,
        target_exit: Place,
        line_number: Optional[int] = None,
    ) -> Optional[Place]:
        """Creates an entry place from source_transition and walks statements to target_exit."""
        entry_place = self.new_place(line_number=line_number)
        self.net.add_arc(source=source_transition, target=entry_place)
        return self.walk_block(statements, current_place=entry_place, target_exit=target_exit)

    def walk_block(
        self,
        statements: List[ast.stmt],
        current_place: Place,
        target_exit: Place,
    ) -> Optional[Place]:
        total_stmts = len(statements)

        for i, stmt in enumerate(statements):
            is_last = (i == total_stmts - 1)

            if isinstance(stmt, ast.Return):
                trans = self.new_transition(
                    label=_format_statement_label(stmt),
                    line_number=stmt.lineno,
                )
                self.net.add_arc(source=current_place, target=trans)
                self.net.add_arc(source=trans, target=self.end_place)
                return None

            elif isinstance(stmt, (ast.Break, ast.Continue)):
                self._handle_loop_jump(stmt, current_place)
                return None

            elif isinstance(stmt, ast.If):
                # Standard Petri net choice semantics (XOR-split):
                # current_place acts as the decision place connecting to mutually exclusive transitions.
                true_trans = self.new_transition(
                    label=_format_statement_label(stmt),
                    line_number=stmt.lineno,
                )
                self.net.add_arc(source=current_place, target=true_trans)

                else_lineno = _get_block_lineno(stmt.orelse, stmt.lineno)
                false_trans = self.new_transition(
                    label="else",
                    line_number=else_lineno,
                )
                self.net.add_arc(source=current_place, target=false_trans)

                # Determine the merge place for this branching construct
                if is_last:
                    merge_place = target_exit
                else:
                    merge_place = self.new_place(label=f"merge_{true_trans.id}", line_number=stmt.lineno)

                # True branch
                true_exit = self._walk_branch(stmt.body, true_trans, merge_place, stmt.lineno)

                # False branch
                if stmt.orelse:
                    false_exit = self._walk_branch(stmt.orelse, false_trans, merge_place, else_lineno)
                else:
                    # if without else: false transition skips directly to merge place
                    self.net.add_arc(source=false_trans, target=merge_place)
                    false_exit = merge_place

                # If both branches returned, no sequential flow reaches merge_place
                if true_exit is None and false_exit is None:
                    return None

                current_place = merge_place

            elif isinstance(stmt, (ast.While, ast.For, ast.AsyncFor)):
                loop_head = current_place
                loop_trans = self.new_transition(
                    label=_format_statement_label(stmt),
                    line_number=stmt.lineno,
                )
                self.net.add_arc(source=loop_head, target=loop_trans)

                else_lineno = stmt.orelse[0].lineno if stmt.orelse and hasattr(stmt.orelse[0], "lineno") else stmt.lineno
                exit_label = "else" if stmt.orelse else "exit"
                exit_trans = self.new_transition(
                    label=exit_label,
                    line_number=else_lineno,
                )
                self.net.add_arc(source=loop_head, target=exit_trans)

                if is_last:
                    loop_exit = target_exit
                else:
                    loop_exit = self.new_place(label=f"exit_{loop_trans.id}", line_number=stmt.lineno)

                self.loop_stack.append(_LoopContext(head=loop_head, exit=loop_exit))
                self._walk_branch(stmt.body, loop_trans, loop_head, stmt.lineno)
                self.loop_stack.pop()

                if stmt.orelse:
                    else_exit = self._walk_branch(stmt.orelse, exit_trans, loop_exit, else_lineno)
                else:
                    self.net.add_arc(source=exit_trans, target=loop_exit)
                    else_exit = loop_exit

                # If loop exit is unreachable, sequential flow stops
                has_exit_inflow = any(arc.target == loop_exit for arc in self.net.arcs)
                if else_exit is None and not has_exit_inflow:
                    return None

                current_place = loop_exit

            elif isinstance(stmt, ast.Try):
                except_entry = self.new_place(label="except_entry", line_number=stmt.lineno)

                if is_last:
                    try_exit = target_exit
                else:
                    try_exit = self.new_place(label="try_exit", line_number=stmt.lineno)

                if stmt.finalbody:
                    finally_lineno = _get_block_lineno(stmt.finalbody, stmt.lineno)
                    finally_entry = self.new_place(label="finally_entry", line_number=finally_lineno)
                else:
                    finally_entry = try_exit

                if stmt.orelse:
                    else_lineno = _get_block_lineno(stmt.orelse, stmt.lineno)
                    else_entry = self.new_place(label="else_entry", line_number=else_lineno)
                    try_normal_exit = else_entry
                else:
                    try_normal_exit = finally_entry

                # Walk try body with try_stack active
                self.try_stack.append(_TryContext(except_entry=except_entry))
                self.walk_block(stmt.body, current_place=current_place, target_exit=try_normal_exit)
                self.try_stack.pop()

                # Walk else clause if present
                if stmt.orelse:
                    self.walk_block(stmt.orelse, current_place=else_entry, target_exit=finally_entry)

                # Walk except handlers
                if stmt.handlers:
                    for handler in stmt.handlers:
                        h_label = _format_handler_label(handler)
                        h_trans = self.new_transition(
                            label=h_label,
                            line_number=handler.lineno,
                            hook_exception=False,
                        )
                        self.net.add_arc(source=except_entry, target=h_trans)
                        self._walk_branch(
                            handler.body,
                            source_transition=h_trans,
                            target_exit=finally_entry,
                            line_number=handler.lineno,
                        )
                elif stmt.finalbody:
                    # try...finally without except handlers: unhandled exception flows to finally
                    exc_trans = self.new_transition(
                        label="exception",
                        line_number=stmt.lineno,
                        hook_exception=False,
                    )
                    self.net.add_arc(source=except_entry, target=exc_trans)
                    self.net.add_arc(source=exc_trans, target=finally_entry)

                # Walk finally block if present
                if stmt.finalbody:
                    self.walk_block(stmt.finalbody, current_place=finally_entry, target_exit=try_exit)

                current_place = try_exit

            else:
                next_place = target_exit if is_last else self.new_place(line_number=stmt.lineno)
                label = _format_statement_label(stmt)
                trans = self.new_transition(
                    label=label,
                    line_number=stmt.lineno,
                )
                self.net.add_arc(source=current_place, target=trans)
                self.net.add_arc(source=trans, target=next_place)
                current_place = next_place

        return current_place


def walk_function(ast_node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> PetriNet:
    """Walks a Python function definition AST and constructs a PetriNet model."""
    if not isinstance(ast_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise TypeError(
            f"walk_function expects an ast.FunctionDef or ast.AsyncFunctionDef, "
            f"got {type(ast_node).__name__}"
        )

    net = PetriNet()

    start_place = net.add_place(
        id_="p0",
        label="start",
        line_number=ast_node.lineno,
        initial_tokens=1,
    )
    end_place = net.add_place(
        id_="p_end",
        label="end",
        line_number=None,
        initial_tokens=0,
    )

    walker = _PythonControlFlowWalker(net=net, end_place=end_place)
    walker.walk_block(ast_node.body, current_place=start_place, target_exit=end_place)

    return net
