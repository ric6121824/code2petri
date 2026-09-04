import ast
import os
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
        parts = []
        cur = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        func_str = ".".join(reversed(parts))
    else:
        func_str = ast.unparse(func) if hasattr(ast, "unparse") else "func"
    return f"call: {func_str}()"


def _format_statement_label(stmt: ast.stmt) -> str:
    """Returns a readable summary of the statement for transition labeling."""
    # Check if the statement is an expression or assignment wrapping a Call
    call_node = None
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        call_node = stmt.value
    elif isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
        call_node = stmt.value
    elif isinstance(stmt, getattr(ast, "AnnAssign", ())) and isinstance(getattr(stmt, "value", None), ast.Call):
        call_node = stmt.value

    if call_node is not None:
        return _format_call_expression(call_node)

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

    def walk_block(
        self,
        statements: List[ast.stmt],
        current_place: Place,
    ) -> Place:
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
                return self.end_place

            elif isinstance(stmt, ast.If):
                cond_label = f"if {ast.unparse(stmt.test)}" if hasattr(ast, "unparse") else "if condition"
                cond_trans = self.new_transition(label=cond_label, line_number=stmt.lineno)
                self.net.add_arc(source=current_place, target=cond_trans)

                p_true = self.new_place(line_number=stmt.lineno)
                self.net.add_arc(source=cond_trans, target=p_true)

                exit_true = self.walk_block(stmt.body, p_true)

                p_false = self.new_place(line_number=stmt.lineno)
                self.net.add_arc(source=cond_trans, target=p_false)

                if stmt.orelse:
                    exit_false = self.walk_block(stmt.orelse, p_false)
                else:
                    exit_false = p_false

                if exit_true == self.end_place and exit_false == self.end_place:
                    return self.end_place
                elif exit_true == self.end_place:
                    current_place = exit_false
                elif exit_false == self.end_place:
                    current_place = exit_true
                else:
                    current_place = exit_false

            else:
                next_place = self.end_place if is_last else self.new_place(line_number=stmt.lineno)
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
    walker.walk_block(ast_node.body, current_place=start_place)

    return net
