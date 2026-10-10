import ast
from typing import Optional, Union, List, Dict, Any

from code2flow.python import Python
from code2petri.control_flow_builder import (
    ControlFlowBuilder,
    LoopRouting,
    StatementContext,
    TryContext,
)
from code2petri.model import PetriNet, Place, Transition, Arc
from code2petri.walker_protocol import WalkerProtocol, WalkResult, CallSite


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


def _source_text_for(node: ast.AST, source_text: Optional[str]) -> Optional[str]:
    if source_text:
        segment = ast.get_source_segment(source_text, node)
        if segment is not None:
            return segment
    if hasattr(ast, "unparse"):
        return ast.unparse(node)
    return None


def _function_returns(node: ast.AST) -> List[ast.Return]:
    """Collect only returns owned by this function, excluding nested scopes."""
    returns: List[ast.Return] = []

    class ReturnCollector(ast.NodeVisitor):
        def visit_Return(self, return_node: ast.Return) -> None:
            returns.append(return_node)

        def visit_FunctionDef(self, nested: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, nested: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, nested: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, nested: ast.Lambda) -> None:
            return

    collector = ReturnCollector()
    for statement in getattr(node, "body", []):
        collector.visit(statement)
    returns.sort(key=lambda item: (item.lineno, item.col_offset))
    return returns


def _function_has_yield(node: ast.AST) -> bool:
    class YieldCollector(ast.NodeVisitor):
        found = False

        def visit_Yield(self, expression: ast.Yield) -> None:
            self.found = True

        def visit_YieldFrom(self, expression: ast.YieldFrom) -> None:
            self.found = True

        def visit_FunctionDef(self, nested: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, nested: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, nested: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, nested: ast.Lambda) -> None:
            return

    collector = YieldCollector()
    for statement in getattr(node, "body", []):
        collector.visit(statement)
    return collector.found


def _direct_literal_type(expression: ast.AST) -> Optional[str]:
    if isinstance(expression, ast.Constant):
        value = expression.value
        if value is None:
            return "NoneType"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, complex):
            return "complex"
        if isinstance(value, str):
            return "str"
        if isinstance(value, bytes):
            return "bytes"
    if (isinstance(expression, ast.UnaryOp) and
            isinstance(expression.op, (ast.UAdd, ast.USub)) and
            isinstance(expression.operand, ast.Constant) and
            isinstance(expression.operand.value, (int, float, complex)) and
            not isinstance(expression.operand.value, bool)):
        return _direct_literal_type(expression.operand)
    return None


def _python_inferred_type(expression: ast.AST, bindings: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Infer a deliberately small set of Python expression types and dependencies."""
    if isinstance(expression, ast.Constant):
        value_type = _direct_literal_type(expression)
        return {"type": value_type or "unknown", "evidence": []}
    if isinstance(expression, (ast.List, ast.Dict, ast.Tuple, ast.Set)):
        return {"type": {ast.List: "list", ast.Dict: "dict", ast.Tuple: "tuple", ast.Set: "set"}[type(expression)], "evidence": []}
    if isinstance(expression, ast.JoinedStr):
        dependencies = []
        for part in expression.values:
            if isinstance(part, ast.FormattedValue):
                part_evidence = _python_inferred_type(part.value, bindings)["evidence"]
                for item in part_evidence:
                    if item not in dependencies:
                        dependencies.append(item)
        return {"type": "str", "evidence": dependencies}
    if isinstance(expression, ast.Name):
        binding = bindings.get(expression.id)
        return {"type": "unknown", "evidence": []} if binding is None else {
            "type": binding["type"], "evidence": list(binding["evidence"]),
        }
    if isinstance(expression, ast.UnaryOp):
        operand = _python_inferred_type(expression.operand, bindings)
        operand_type = operand["type"]
        if isinstance(expression.op, ast.Not) and operand_type in {"bool", "int", "float", "complex", "str", "bytes", "NoneType"}:
            value_type = "bool"
        elif isinstance(expression.op, (ast.UAdd, ast.USub)) and operand_type in {"int", "float", "complex"}:
            value_type = operand_type
        else:
            value_type = "unknown"
        return {"type": value_type, "evidence": operand["evidence"]}
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _python_inferred_type(expression.left, bindings)
        right = _python_inferred_type(expression.right, bindings)
        left_type, right_type = left["type"], right["type"]
        if isinstance(expression.op, ast.Add) and left_type == right_type == "str":
            value_type = "str"
        elif left_type in {"int", "float", "complex"} and right_type in {"int", "float", "complex"}:
            if isinstance(expression.op, ast.Div):
                value_type = "float" if "complex" not in (left_type, right_type) else "complex"
            else:
                value_type = "complex" if "complex" in (left_type, right_type) else (
                    "float" if "float" in (left_type, right_type) else "int"
                )
        else:
            value_type = "unknown"
        dependencies = []
        for item in left["evidence"] + right["evidence"]:
            if item not in dependencies:
                dependencies.append(item)
        return {"type": value_type, "evidence": dependencies}
    return {"type": "unknown", "evidence": []}


def _python_binding_names(target: ast.AST) -> List[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in _python_binding_names(element)]
    return []


def _python_local_bindings(
    statements: List[ast.stmt], source_text: Optional[str],
) -> Dict[str, Dict[str, Any]]:
    """Track direct assignments in lexical order, invalidating unsupported writes."""
    bindings: Dict[str, Dict[str, Any]] = {}
    excluded = {
        name
        for statement in statements
        if isinstance(statement, (ast.Global, ast.Nonlocal))
        for name in statement.names
    }
    for statement in statements:
        targets: List[ast.AST] = []
        value: Optional[ast.AST] = None
        if isinstance(statement, ast.Assign):
            targets, value = statement.targets, statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets, value = [statement.target], statement.value
        elif isinstance(statement, ast.AugAssign):
            targets = [statement.target]
        else:
            continue

        assigned = _python_inferred_type(value, bindings) if value is not None else {"type": "unknown", "evidence": []}
        if any(not isinstance(target, ast.Name) for target in targets):
            assigned = {"type": "unknown", "evidence": []}
        names = [name for target in targets for name in _python_binding_names(target)]
        if not names:
            continue
        assignment_evidence = {
            "expression": _source_text_for(statement, source_text) or "assignment",
            "type": assigned["type"],
            "provenance": "local_assignment",
            "source_location": {"line": getattr(statement, "lineno", None), "column": getattr(statement, "col_offset", None)},
        }
        chain = list(assigned["evidence"])
        if assignment_evidence not in chain:
            chain.append(assignment_evidence)
        for name in names:
            if name not in excluded:
                bindings[name] = {"type": assigned["type"], "evidence": chain}
    return bindings


def _is_simple_sequential_body(node: ast.AST) -> bool:
    """Reject control-flow constructs whose normal-return coverage is not proven here."""
    unsupported_nodes = [
        ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With,
        ast.AsyncWith, ast.Raise, ast.Assert, ast.Break, ast.Continue,
    ]
    match_node = getattr(ast, "Match", None)
    if match_node is not None:
        unsupported_nodes.append(match_node)
    unsupported = tuple(unsupported_nodes)

    class ControlFlowCheck(ast.NodeVisitor):
        supported = True

        def generic_visit(self, child: ast.AST) -> None:
            if isinstance(child, unsupported):
                self.supported = False
                return
            super().generic_visit(child)

        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is not node:
                self.supported = False

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is not node:
                self.supported = False

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            self.supported = False

        def visit_Lambda(self, child: ast.Lambda) -> None:
            self.supported = False

    check = ControlFlowCheck()
    for statement in getattr(node, "body", []):
        check.visit(statement)
    return check.supported


def _extract_python_return_metadata(
    node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    function_name: str,
    qualified_name: str,
    source_file: str,
    source_text: Optional[str],
) -> Dict[str, Any]:
    """Extract declared evidence and bounded return-expression evidence."""
    line = getattr(node, "lineno", None)
    column = getattr(node, "col_offset", None)
    is_global = function_name == "(global)" or getattr(node, "name", None) == "(global)"
    declared_expression = (
        None if is_global or node.returns is None
        else _source_text_for(node.returns, source_text)
    )
    metadata: Dict[str, Any] = {
        "function_name": "Global Scope" if is_global else function_name,
        "source_file": source_file,
        "qualified_name": "Global Scope" if is_global else qualified_name,
        "definition_location": {"line": line, "column": column},
        "declared": None if declared_expression is None else {
            "expression": declared_expression,
            "provenance": "annotation",
            "source_location": {"line": line, "column": column},
        },
        "analysis_status": "not_applicable" if is_global else "unknown",
        "inferred": [],
    }
    if is_global:
        return metadata

    # Async and generator return roles are introduced by the later role-specific tickets.
    if isinstance(node, ast.AsyncFunctionDef) or _function_has_yield(node):
        return metadata

    returns = _function_returns(node)
    evidence: List[Dict[str, Any]] = []
    simple_body = _is_simple_sequential_body(node)
    if not returns and simple_body:
        # Sequential bodies without explicit returns complete normally with None.
        evidence.append({
            "expression": "implicit fall-through",
            "type": "NoneType",
            "provenance": "normal_fallthrough",
            "role": "call_result",
            "source_location": {"line": getattr(node, "end_lineno", line), "column": None},
        })
    elif len(returns) == 1 and node.body and returns[0] is node.body[-1]:
        # The return must be the final statement; branches and loops can still
        # make a local binding incomplete, so such expressions remain unknown.
        return_node = returns[0]
        expression = "None" if return_node.value is None else _source_text_for(return_node.value, source_text)
        inferred = (
            {"type": "NoneType", "evidence": []} if return_node.value is None
            else _python_inferred_type(return_node.value, _python_local_bindings(node.body[:-1], source_text))
        )
        if not simple_body:
            inferred = {"type": "unknown", "evidence": []}
        provenance = "direct_literal" if return_node.value is not None and _direct_literal_type(return_node.value) is not None else (
            "local_assignment" if isinstance(return_node.value, ast.Name) and inferred["evidence"] else "expression_inference"
        )
        evidence.append({
            "expression": expression or "unknown expression",
            "type": inferred["type"],
            "provenance": provenance,
            "role": "call_result",
            "source_location": {"line": return_node.lineno, "column": return_node.col_offset},
            "expression_location": {
                "line": getattr(return_node.value, "lineno", return_node.lineno),
                "column": getattr(return_node.value, "col_offset", return_node.col_offset),
            },
            "evidence": inferred["evidence"],
        })
        if inferred["type"] != "unknown" and simple_body:
            metadata["analysis_status"] = "complete"
        metadata["inferred"] = evidence
        return metadata
    elif not returns:
        return metadata
    else:
        # Other return shapes need normal-return coverage analysis, outside this ticket.
        return metadata

    metadata["analysis_status"] = "complete"
    metadata["inferred"] = evidence
    return metadata



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


def _find_calls_in_expr(node: Optional[ast.AST]) -> List[ast.Call]:
    """Finds all ast.Call nodes within an expression subtree."""
    if node is None:
        return []
    calls: List[ast.Call] = []
    for subnode in ast.walk(node):
        if isinstance(subnode, ast.Call):
            calls.append(subnode)
    calls.sort(key=lambda c: (getattr(c, "lineno", 0), getattr(c, "col_offset", 0)))
    return calls


def _extract_call_site_from_ast_call(
    call_node: ast.Call,
    caller_function: str,
    caller_file: str,
    transition_id: str,
    default_lineno: int = 0,
) -> CallSite:
    func = call_node.func
    callee_owner = None
    if isinstance(func, ast.Name):
        callee_name = func.id
    elif isinstance(func, ast.Attribute):
        callee_name = func.attr
        if isinstance(func.value, ast.Name):
            callee_owner = func.value.id
        elif hasattr(ast, "unparse"):
            callee_owner = ast.unparse(func.value)
        else:
            callee_owner = "attr"
    else:
        callee_name = ast.unparse(func) if hasattr(ast, "unparse") else "call"

    line_number = getattr(call_node, "lineno", default_lineno)
    return CallSite(
        caller_function=caller_function,
        caller_file=caller_file,
        callee_name=callee_name,
        callee_owner=callee_owner,
        line_number=line_number,
        transition_id=transition_id,
    )


class _PythonControlFlowWalker:
    """Internal recursive walker constructing PetriNet places, transitions, and arcs."""

    def __init__(
        self,
        builder: ControlFlowBuilder,
        func_name: str = "",
        filepath: str = "",
    ) -> None:
        self.builder = builder
        self.func_name = func_name
        self.filepath = filepath
        self.call_sites: List[CallSite] = []
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

    def _record_calls_in_expr(
        self,
        expr_node: Optional[ast.AST],
        transition_id: str,
        default_lineno: int = 0,
    ) -> None:
        if expr_node is None:
            return
        calls = _find_calls_in_expr(expr_node)
        for call in calls:
            cs = _extract_call_site_from_ast_call(
                call_node=call,
                caller_function=self.func_name,
                caller_file=self.filepath,
                transition_id=transition_id,
                default_lineno=default_lineno,
            )
            self.call_sites.append(cs)

    def _walk_return(self, stmt: ast.Return, ctx: StatementContext) -> Optional[Place]:
        trans = self.builder.wire_return(ctx.current_place, _format_statement_label(stmt), stmt.lineno)
        self._record_calls_in_expr(stmt.value, trans.id, stmt.lineno)
        return None

    def _walk_break(self, stmt: ast.Break, ctx: StatementContext) -> Optional[Place]:
        self.builder.wire_break(ctx.current_place, "break", stmt.lineno)
        return None

    def _walk_continue(self, stmt: ast.Continue, ctx: StatementContext) -> Optional[Place]:
        self.builder.wire_continue(ctx.current_place, "continue", stmt.lineno)
        return None

    def _walk_raise(self, stmt: ast.Raise, ctx: StatementContext) -> Optional[Place]:
        trans = self.builder.wire_terminal_exception(
            current_place=ctx.current_place,
            label=_format_statement_label(stmt),
            line_number=stmt.lineno,
        )
        self._record_calls_in_expr(stmt.exc, trans.id, stmt.lineno)
        return None

    def _walk_if(self, stmt: ast.If, ctx: StatementContext) -> Optional[Place]:
        else_lineno = _get_block_lineno(stmt.orelse, stmt.lineno)
        return self.builder.wire_if_split(
            ctx=ctx,
            true_label=_format_statement_label(stmt),
            consequent_stmts=stmt.body,
            false_lineno=else_lineno,
            alternate_stmts=stmt.orelse,
            walk_block_fn=self.walk_block,
            on_true_trans=lambda t: self._record_calls_in_expr(stmt.test, t.id, stmt.lineno),
        )

    def _walk_loop(self, stmt: Union[ast.While, ast.For, ast.AsyncFor], ctx: StatementContext) -> Optional[Place]:
        loop_trans = self.builder.new_transition(
            label=_format_statement_label(stmt),
            line_number=stmt.lineno,
        )
        test_expr = stmt.test if isinstance(stmt, ast.While) else getattr(stmt, "iter", None)
        self._record_calls_in_expr(test_expr, loop_trans.id, stmt.lineno)

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

        has_exit_inflow = self.builder.has_incoming_arcs(loop_exit)
        if else_exit is None and not has_exit_inflow:
            return None

        return loop_exit

    def _walk_try(self, stmt: ast.Try, ctx: StatementContext) -> Optional[Place]:
        handlers = [
            (_format_handler_label(handler), handler.lineno, handler.body)
            for handler in stmt.handlers
        ]
        finally_lineno = _get_block_lineno(stmt.finalbody, stmt.lineno)
        else_lineno = _get_block_lineno(stmt.orelse, stmt.lineno)
        return self.builder.wire_try_catch(
            ctx=ctx,
            try_body=stmt.body,
            handlers=handlers,
            finally_stmts=stmt.finalbody,
            finally_lineno=finally_lineno,
            walk_block_fn=self.walk_block,
            else_stmts=stmt.orelse,
            else_lineno=else_lineno,
        )

    def _walk_default(self, stmt: ast.stmt, ctx: StatementContext) -> Optional[Place]:
        label = _format_statement_label(stmt)
        return self.builder.wire_sequential_statement(
            current_place=ctx.current_place,
            label=label,
            lineno=stmt.lineno,
            is_last=ctx.is_last,
            target_exit=ctx.target_exit,
            on_trans=lambda t: self._record_calls_in_expr(stmt, t.id, stmt.lineno),
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


def _extract_constructor_class_name(value_node: Optional[ast.AST]) -> Optional[str]:
    """Extracts class name if an AST expression is an object constructor instantiation (ast.Call)."""
    if not isinstance(value_node, ast.Call):
        return None
    func = value_node.func
    if isinstance(func, ast.Name):
        if func.id and func.id[0].isupper():
            return func.id
    elif isinstance(func, ast.Attribute):
        if func.attr and func.attr[0].isupper():
            return func.attr
    return None


def _extract_target_name(target_node: ast.AST) -> Optional[str]:
    """Extracts variable name identifier or attribute path (e.g. 'x', 'self.engine')."""
    if isinstance(target_node, ast.Name):
        return target_node.id
    if isinstance(target_node, ast.Attribute):
        if isinstance(target_node.value, ast.Name):
            return f"{target_node.value.id}.{target_node.attr}"
        if hasattr(ast, "unparse"):
            return ast.unparse(target_node)
    return None


class PythonWalker(WalkerProtocol):
    """Python AST walker implementing WalkerProtocol."""

    def __init__(self) -> None:
        self.filepath: Optional[str] = None
        self.source_text: Optional[str] = None
        self.parsed_tree: Optional[ast.AST] = None

    def get_node_lineno(self, ast_node: Any) -> int:
        """Returns the line number for an AST node, defaulting to 0."""
        return getattr(ast_node, "lineno", 0)

    def parse_file(self, filepath: str) -> ast.AST:
        """Parses a Python source file into an AST."""
        self.filepath = filepath
        try:
            with open(filepath, "r", encoding="utf-8") as source_file:
                self.source_text = source_file.read()
        except OSError:
            self.source_text = None
        self.parsed_tree = Python.get_tree(filepath, None)
        return self.parsed_tree

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

    def collect_variable_bindings(self, tree: Any) -> Dict[str, str]:
        """Collects variable to class name bindings from constructor calls in the AST."""
        if not isinstance(tree, ast.AST):
            return {}

        bindings: Dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue

            class_name = _extract_constructor_class_name(node.value)
            if class_name:
                for target in targets:
                    target_name = _extract_target_name(target)
                    if target_name:
                        bindings[target_name] = class_name
        return bindings

    def walk_function(
        self,
        ast_node: Any,
        func_name: str = "",
        filepath: Optional[str] = None,
    ) -> WalkResult:
        """Walks a Python function definition AST and constructs a PetriNet model packaged in a WalkResult."""
        if not isinstance(ast_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise TypeError(
                f"walk_function expects an ast.FunctionDef or ast.AsyncFunctionDef, "
                f"got {type(ast_node).__name__}"
            )

        active_func_name = func_name or getattr(ast_node, "name", "")
        active_filepath = filepath or getattr(self, "filepath", "") or ""
        source_text = self.source_text
        if (self.parsed_tree is None or
                not any(candidate is ast_node for candidate in ast.walk(self.parsed_tree))):
            source_text = None
        qualified_name = active_func_name
        if self.parsed_tree is not None:
            qualified_name = next(
                (name for name, candidate in _collect_functions(self.parsed_tree) if candidate is ast_node),
                active_func_name,
            )
        return_metadata = _extract_python_return_metadata(
            ast_node,
            function_name=active_func_name,
            qualified_name=qualified_name,
            source_file=active_filepath,
            source_text=source_text,
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
        walker = _PythonControlFlowWalker(
            builder=builder,
            func_name=active_func_name,
            filepath=active_filepath,
        )
        walker.walk_block(ast_node.body, current_place=start_place, target_exit=end_place)
        net.return_metadata = return_metadata
        return WalkResult(net=net, call_sites=walker.call_sites, return_metadata=return_metadata)
