import ast
from typing import Optional, Union, List

from code2flow.python import Python
from code2petri.control_flow_builder import (
    ControlFlowBuilder,
    LoopRouting,
    StatementContext,
    TryContext,
)
from code2petri.model import PetriNet, Place, Transition, Arc
from code2petri.walker_protocol import WalkerProtocol


def _get_executable_statements(tree: ast.AST) -> List[ast.stmt]:
    """Returns top-level executable statements outside functions/classes."""
    if not isinstance(tree, ast.Module):
        return []
    return [
        stmt for stmt in tree.body
        if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]


def _collect_functions(tree: ast.AST) -> List[tuple[str, Union[ast.FunctionDef, ast.AsyncFunctionDef]]]:
    """Traverses tree to collect (qualified_name, node) pairs ordered by line number."""
    results: List[tuple[str, Union[ast.FunctionDef, ast.AsyncFunctionDef]]] = []

    def visit(node: ast.AST, scope_stack: List[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, scope_stack + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual_name = f"{'.'.join(scope_stack)}.{child.name}" if scope_stack else child.name
                results.append((qual_name, child))
                visit(child, scope_stack + [child.name])
            else:
                visit(child, scope_stack)

    visit(tree, [])
    results.sort(key=lambda item: getattr(item[1], "lineno", 0))
    return results



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


class _PythonControlFlowWalker:
    """Internal recursive walker constructing PetriNet places, transitions, and arcs."""

    def __init__(self, builder: ControlFlowBuilder) -> None:
        self.builder = builder
        self._statement_handlers = {
            ast.Return: self._walk_return,
            ast.Break: self._walk_break,
            ast.Continue: self._walk_continue,
            ast.If: self._walk_if,
            ast.While: self._walk_loop,
            ast.For: self._walk_loop,
            ast.AsyncFor: self._walk_loop,
            ast.Try: self._walk_try,
            ast.Raise: self._walk_raise,
        }

    def _walk_return(self, stmt: ast.Return, ctx: StatementContext) -> Optional[Place]:
        self.builder.wire_return(ctx.current_place, _format_statement_label(stmt), stmt.lineno)
        return None

    def _walk_break(self, stmt: ast.Break, ctx: StatementContext) -> Optional[Place]:
        self.builder.wire_break(ctx.current_place, "break", stmt.lineno)
        return None

    def _walk_continue(self, stmt: ast.Continue, ctx: StatementContext) -> Optional[Place]:
        self.builder.wire_continue(ctx.current_place, "continue", stmt.lineno)
        return None

    def _walk_raise(self, stmt: ast.Raise, ctx: StatementContext) -> Optional[Place]:
        self.builder.wire_terminal_exception(
            current_place=ctx.current_place,
            label=_format_statement_label(stmt),
            line_number=stmt.lineno,
        )
        return None

    def _walk_if(self, stmt: ast.If, ctx: StatementContext) -> Optional[Place]:
        true_trans = self.builder.new_transition(
            label=_format_statement_label(stmt),
            line_number=stmt.lineno,
        )
        self.builder.add_arc(source=ctx.current_place, target=true_trans)

        else_lineno = _get_block_lineno(stmt.orelse, stmt.lineno)
        false_trans = self.builder.new_transition(
            label="else",
            line_number=else_lineno,
        )
        self.builder.add_arc(source=ctx.current_place, target=false_trans)

        merge_place = ctx.target_exit if ctx.is_last else self.builder.new_place(
            label=f"merge_{true_trans.id}", line_number=stmt.lineno
        )

        true_exit = self.builder.walk_branch(
            stmt.body,
            source_transition=true_trans,
            target_exit=merge_place,
            walk_block_fn=self.walk_block,
            line_number=stmt.lineno,
        )
        false_exit = self.builder.walk_branch(
            stmt.orelse,
            source_transition=false_trans,
            target_exit=merge_place,
            walk_block_fn=self.walk_block,
            line_number=else_lineno,
        )

        if true_exit is None and false_exit is None:
            return None

        return merge_place

    def _walk_loop(self, stmt: Union[ast.While, ast.For, ast.AsyncFor], ctx: StatementContext) -> Optional[Place]:
        loop_trans = self.builder.new_transition(
            label=_format_statement_label(stmt),
            line_number=stmt.lineno,
        )
        else_lineno = stmt.orelse[0].lineno if stmt.orelse and hasattr(stmt.orelse[0], "lineno") else stmt.lineno
        exit_label = "else" if stmt.orelse else "exit"
        exit_trans = self.builder.new_transition(
            label=exit_label,
            line_number=else_lineno,
        )

        loop_exit = ctx.target_exit if ctx.is_last else self.builder.new_place(
            label=f"exit_{loop_trans.id}", line_number=stmt.lineno
        )

        routing = LoopRouting(
            head=ctx.current_place,
            loop_trans=loop_trans,
            exit_trans=exit_trans,
            exit_place=loop_exit,
        )
        self.builder.wire_standard_loop(
            routing=routing,
            body_stmts=stmt.body,
            walk_block_fn=self.walk_block,
            lineno=stmt.lineno,
        )

        else_exit = self.builder.walk_branch(
            stmt.orelse,
            source_transition=exit_trans,
            target_exit=loop_exit,
            walk_block_fn=self.walk_block,
            line_number=else_lineno,
        )

        has_exit_inflow = any(arc.target == loop_exit for arc in self.builder.net.arcs)
        if else_exit is None and not has_exit_inflow:
            return None

        return loop_exit

    def _walk_try(self, stmt: ast.Try, ctx: StatementContext) -> Optional[Place]:
        except_entry = self.builder.new_place(label="except_entry", line_number=stmt.lineno)
        try_exit = ctx.target_exit if ctx.is_last else self.builder.new_place(label="try_exit", line_number=stmt.lineno)

        if stmt.finalbody:
            finally_lineno = _get_block_lineno(stmt.finalbody, stmt.lineno)
            finally_entry = self.builder.new_place(label="finally_entry", line_number=finally_lineno)
            finally_target = finally_entry
        else:
            finally_entry = None
            finally_target = try_exit

        if stmt.orelse:
            else_lineno = _get_block_lineno(stmt.orelse, stmt.lineno)
            else_entry = self.builder.new_place(label="else_entry", line_number=else_lineno)
            try_normal_exit = else_entry
        else:
            try_normal_exit = finally_target

        self.builder.push_try(TryContext(
            except_entry=except_entry,
            finally_entry=finally_entry,
            loop_depth=len(self.builder.loop_stack),
        ))
        self.walk_block(stmt.body, current_place=ctx.current_place, target_exit=try_normal_exit)
        self.builder.pop_try()

        if stmt.orelse:
            self.walk_block(stmt.orelse, current_place=else_entry, target_exit=finally_target)

        if stmt.handlers:
            for handler in stmt.handlers:
                h_label = _format_handler_label(handler)
                h_trans = self.builder.new_transition(
                    label=h_label,
                    line_number=handler.lineno,
                    hook_exception=False,
                )
                self.builder.add_arc(source=except_entry, target=h_trans)
                self.builder.walk_branch(
                    handler.body,
                    source_transition=h_trans,
                    target_exit=finally_target,
                    walk_block_fn=self.walk_block,
                    line_number=handler.lineno,
                )
        elif stmt.finalbody:
            exc_trans = self.builder.new_transition(
                label="exception",
                line_number=stmt.lineno,
                hook_exception=False,
            )
            self.builder.add_arc(source=except_entry, target=exc_trans)
            self.builder.add_arc(source=exc_trans, target=finally_entry)

        if stmt.finalbody:
            self.walk_block(stmt.finalbody, current_place=finally_entry, target_exit=try_exit)

        return try_exit

    def _walk_default(self, stmt: ast.stmt, ctx: StatementContext) -> Optional[Place]:
        label = _format_statement_label(stmt)
        return self.builder.wire_sequential_statement(
            current_place=ctx.current_place,
            label=label,
            lineno=stmt.lineno,
            is_last=ctx.is_last,
            target_exit=ctx.target_exit,
        )

    def walk_block(
        self,
        statements: List[ast.stmt],
        current_place: Place,
        target_exit: Place,
    ) -> Optional[Place]:
        total_stmts = len(statements)

        for i, stmt in enumerate(statements):
            is_last = (i == total_stmts - 1)
            ctx = StatementContext(
                current_place=current_place,
                is_last=is_last,
                target_exit=target_exit,
                lineno=getattr(stmt, "lineno", None),
            )
            handler = self._statement_handlers.get(type(stmt), self._walk_default)
            res = handler(stmt, ctx)
            if res is None:
                return None
            current_place = res

        return current_place


class PythonWalker(WalkerProtocol):
    """Python AST walker implementing WalkerProtocol."""

    def __init__(self) -> None:
        pass

    def get_node_lineno(self, ast_node: Any) -> int:
        """Returns the line number for an AST node, defaulting to 0."""
        return getattr(ast_node, "lineno", 0)

    def parse_file(self, filepath: str) -> ast.AST:
        """Parses a Python source file into an AST."""
        return Python.get_tree(filepath, None)

    def find_function(
        self,
        tree: ast.AST,
        func_name: str,
    ) -> Optional[Union[ast.FunctionDef, ast.AsyncFunctionDef]]:
        """Locates a function or method definition AST node by name within an AST."""
        if func_name == "(global)":
            executable_stmts = _get_executable_statements(tree)
            if not executable_stmts:
                return None
            first_lineno = getattr(executable_stmts[0], "lineno", 1)
            wrapper = ast.FunctionDef(
                name="(global)",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=executable_stmts,
                decorator_list=[],
                returns=None,
                lineno=first_lineno,
                col_offset=0,
            )
            return wrapper

        funcs = _collect_functions(tree)
        # Exact match first (covers qualified names and top-level functions)
        for name, node in funcs:
            if name == func_name:
                return node
        # Fallback match for bare name if method was qualified
        for name, node in funcs:
            if node.name == func_name:
                return node
        return None

    def find_all_functions(self, tree: ast.AST) -> List[str]:
        """Finds all function and method definition names within an AST, including (global) if top-level code exists."""
        funcs = []
        if _get_executable_statements(tree):
            funcs.append("(global)")
        funcs.extend([name for name, _ in _collect_functions(tree)])
        return funcs

    def walk_function(
        self,
        ast_node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    ) -> PetriNet:
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

        builder = ControlFlowBuilder(net=net, end_place=end_place)
        walker = _PythonControlFlowWalker(builder=builder)
        walker.walk_block(ast_node.body, current_place=start_place, target_exit=end_place)

        return net
