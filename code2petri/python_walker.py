import ast
from typing import Optional, Union, List

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

    if hasattr(ast, "unparse"):
        summary = ast.unparse(stmt)
        # Take first line if statement is multiline
        return summary.strip().split("\n")[0]

    return type(stmt).__name__


class _PythonControlFlowWalker:
    """Internal recursive walker constructing PetriNet places, transitions, and arcs."""

    def __init__(self, net: PetriNet, end_place: Place) -> None:
        self.net = net
        self.end_place = end_place
        self.place_counter = 0
        self.trans_counter = 0

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
    ) -> Transition:
        self.trans_counter += 1
        t_id = f"t{self.trans_counter}"
        return self.net.add_transition(
            id_=t_id,
            label=label,
            line_number=line_number,
        )

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

            elif isinstance(stmt, ast.If):
                cond_trans = self.new_transition(
                    label=_format_statement_label(stmt),
                    line_number=stmt.lineno,
                )
                self.net.add_arc(source=current_place, target=cond_trans)

                # Determine the merge place for this branching construct
                if is_last:
                    merge_place = target_exit
                else:
                    merge_place = self.new_place(label=f"merge_{cond_trans.id}", line_number=stmt.lineno)

                # True branch
                true_exit = self._walk_branch(stmt.body, cond_trans, merge_place, stmt.lineno)

                # False branch
                if stmt.orelse:
                    false_exit = self._walk_branch(stmt.orelse, cond_trans, merge_place, stmt.lineno)
                else:
                    # if without else: false-branch arc skips directly to merge place
                    self.net.add_arc(source=cond_trans, target=merge_place)
                    false_exit = merge_place

                # If both branches returned, no sequential flow reaches merge_place
                if true_exit is None and false_exit is None:
                    return None

                current_place = merge_place

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
