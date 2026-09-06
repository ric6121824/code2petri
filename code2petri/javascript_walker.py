from typing import Optional, List, Any, Union
from code2flow.engine import LanguageParams
from code2flow.javascript import Javascript
from code2petri.base_walker import (
    _BaseControlFlowWalker,
    LoopContext,
    TryContext,
    _LoopContext,
    _TryContext,
)
from code2petri.model import PetriNet, Place, Transition
from code2petri.walker_protocol import WalkerProtocol


def _to_stmt_list(node: Any) -> List[dict]:
    """Normalizes an AST node or list into a list of statement dicts."""
    if not node:
        return []
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        if node.get("type") == "BlockStatement":
            return node.get("body", [])
        return [node]
    return []


def _get_block_lineno(stmts: List[dict], default: Optional[int] = None) -> Optional[int]:
    """Returns the line number of the first statement in a block, or default."""
    if stmts and isinstance(stmts[0], dict) and "loc" in stmts[0] and "start" in stmts[0]["loc"]:
        return stmts[0]["loc"]["start"].get("line", default)
    return default


class _JavascriptControlFlowWalker(_BaseControlFlowWalker):
    """Internal recursive walker constructing PetriNet places, transitions, and arcs for JavaScript."""

    def __init__(self, net: PetriNet, end_place: Place, raw_source: str) -> None:
        super().__init__(net, end_place)
        self.raw_source = raw_source

    def _slice(self, node: Optional[dict]) -> str:
        """Extracts source text substring for an AST node using character offsets."""
        if not node or "start" not in node or "end" not in node:
            return ""
        return self.raw_source[node["start"]:node["end"]].strip()

    def _get_lineno(self, node: Optional[dict], default: Optional[int] = None) -> Optional[int]:
        """Returns the 1-indexed start line number of an AST node."""
        if isinstance(node, dict) and "loc" in node and "start" in node["loc"]:
            return node["loc"]["start"].get("line", default)
        return default

    def _format_call_expression(self, expr: dict) -> str:
        """Formats a CallExpression into call: callee()."""
        callee = expr.get("callee", {})
        if callee.get("type") == "Identifier":
            return f"call: {callee.get('name')}()"
        elif callee.get("type") == "MemberExpression":
            obj_str = self._slice(callee.get("object"))
            prop = callee.get("property", {})
            prop_str = prop.get("name") or self._slice(prop)
            return f"call: {obj_str}.{prop_str}()"
        return f"call: {self._slice(callee)}()"

    def _format_parenthesized_condition(self, keyword: str, test_node: Optional[dict]) -> str:
        """Formats a condition with parentheses: e.g. if (x > 0) or while (x > 0)."""
        test_slice = self._slice(test_node)
        if test_slice.startswith("(") and test_slice.endswith(")"):
            return f"{keyword} {test_slice}"
        return f"{keyword} ({test_slice})"

    def _get_loop_header_slice(self, stmt: dict) -> Optional[str]:
        """Extracts loop header text up to the body block start from raw source."""
        body = stmt.get("body", {})
        if "start" in stmt and "start" in body:
            return self.raw_source[stmt["start"]:body["start"]].strip()
        return None

    def _format_statement_label(self, stmt: dict) -> str:
        """Returns a readable summary of the statement for transition labeling."""
        stmt_type = stmt.get("type")

        # Return statement
        if stmt_type == "ReturnStatement":
            arg = stmt.get("argument")
            if arg:
                arg_str = self._slice(arg)
                return f"return {arg_str}"
            return "return"

        # Break and Continue
        if stmt_type == "BreakStatement":
            return "break"

        if stmt_type == "ContinueStatement":
            return "continue"

        # If statement
        if stmt_type == "IfStatement":
            return self._format_parenthesized_condition("if", stmt.get("test"))

        # While statement
        if stmt_type == "WhileStatement":
            return self._format_parenthesized_condition("while", stmt.get("test"))

        # For statement
        if stmt_type == "ForStatement":
            header = self._get_loop_header_slice(stmt)
            if header:
                return header
            init_str = self._slice(stmt.get("init")).rstrip(";")
            test_str = self._slice(stmt.get("test"))
            update_str = self._slice(stmt.get("update"))
            return f"for ({init_str}; {test_str}; {update_str})"

        # ForInStatement and ForOfStatement
        if stmt_type in ("ForInStatement", "ForOfStatement"):
            header = self._get_loop_header_slice(stmt)
            if header:
                return header
            left_str = self._slice(stmt.get("left")).rstrip(";")
            right_str = self._slice(stmt.get("right"))
            op = "in" if stmt_type == "ForInStatement" else "of"
            return f"for ({left_str} {op} {right_str})"

        # Expression statement
        if stmt_type == "ExpressionStatement":
            expr = stmt.get("expression", {})
            expr_type = expr.get("type")
            if expr_type == "CallExpression":
                return self._format_call_expression(expr)
            if expr_type == "AssignmentExpression":
                left_str = self._slice(expr.get("left"))
                op = expr.get("operator", "=")
                right = expr.get("right", {})
                if right.get("type") == "CallExpression":
                    return f"{left_str} {op} {self._format_call_expression(right)}"
                right_str = self._slice(right)
                return f"{left_str} {op} {right_str}"
            if expr_type == "UpdateExpression":
                return self._slice(expr)

        # VariableDeclaration with CallExpression initializer (e.g. let res = calc())
        if stmt_type == "VariableDeclaration":
            decls = stmt.get("declarations", [])
            if len(decls) == 1 and decls[0].get("init", {}).get("type") == "CallExpression":
                kind = stmt.get("kind", "let")
                var_name = self._slice(decls[0].get("id"))
                call_str = self._format_call_expression(decls[0]["init"])
                return f"{kind} {var_name} = {call_str}"

        # Try statement
        if stmt_type == "TryStatement":
            return "try"

        # Default source slice
        raw = self._slice(stmt)
        first_line = raw.split("\n")[0].strip().rstrip(";")
        return first_line or stmt_type or "statement"

    def _walk_branch(
        self,
        statements: Any,
        source_transition: Transition,
        target_exit: Place,
        line_number: Optional[int] = None,
    ) -> Optional[Place]:
        """Creates an entry place from source_transition and walks statements to target_exit."""
        stmt_list = _to_stmt_list(statements)
        if not stmt_list:
            self.net.add_arc(source=source_transition, target=target_exit)
            return target_exit
        entry_place = self.new_place(line_number=line_number)
        self.net.add_arc(source=source_transition, target=entry_place)
        return self.walk_block(stmt_list, current_place=entry_place, target_exit=target_exit)

    def _handle_loop_jump(
        self,
        stmt: dict,
        current_place: Place,
    ) -> None:
        """Handles break or continue jump statements to loop exit or head."""
        stmt_type = stmt.get("type")
        is_break = stmt_type == "BreakStatement"
        keyword = "break" if is_break else "continue"
        lineno = self._get_lineno(stmt)
        if not self.loop_stack:
            raise SyntaxError(f"'{keyword}' outside loop at line {lineno}")
        target_place = self.loop_stack[-1].exit if is_break else self.loop_stack[-1].head
        trans = self.new_transition(
            label=self._format_statement_label(stmt),
            line_number=lineno,
        )
        self.net.add_arc(source=current_place, target=trans)
        self.net.add_arc(source=trans, target=target_place)

    def walk_block(
        self,
        statements: List[dict],
        current_place: Place,
        target_exit: Place,
    ) -> Optional[Place]:
        """Iterates sequentially through statements, constructing places and transitions."""
        total_stmts = len(statements)

        for i, stmt in enumerate(statements):
            is_last = (i == total_stmts - 1)
            lineno = self._get_lineno(stmt)
            stmt_type = stmt.get("type")

            if stmt_type == "ReturnStatement":
                trans = self.new_transition(
                    label=self._format_statement_label(stmt),
                    line_number=lineno,
                )
                self.net.add_arc(source=current_place, target=trans)
                self.net.add_arc(source=trans, target=self.end_place)
                return None

            elif stmt_type in ("BreakStatement", "ContinueStatement"):
                self._handle_loop_jump(stmt, current_place)
                return None

            elif stmt_type == "IfStatement":
                true_trans = self.new_transition(
                    label=self._format_statement_label(stmt),
                    line_number=lineno,
                )
                self.net.add_arc(source=current_place, target=true_trans)

                alternate = stmt.get("alternate")
                else_lineno = self._get_lineno(alternate, lineno)
                false_trans = self.new_transition(
                    label="else",
                    line_number=else_lineno,
                )
                self.net.add_arc(source=current_place, target=false_trans)

                if is_last:
                    merge_place = target_exit
                else:
                    merge_place = self.new_place(label=f"merge_{true_trans.id}", line_number=lineno)

                consequent_stmts = _to_stmt_list(stmt.get("consequent"))
                true_exit = self._walk_branch(consequent_stmts, true_trans, merge_place, lineno)

                if alternate:
                    alternate_stmts = _to_stmt_list(alternate)
                    false_exit = self._walk_branch(alternate_stmts, false_trans, merge_place, else_lineno)
                else:
                    self.net.add_arc(source=false_trans, target=merge_place)
                    false_exit = merge_place

                if true_exit is None and false_exit is None:
                    return None

                current_place = merge_place

            elif stmt_type in ("WhileStatement", "ForStatement", "ForInStatement", "ForOfStatement"):
                loop_head = current_place
                loop_trans = self.new_transition(
                    label=self._format_statement_label(stmt),
                    line_number=lineno,
                )
                self.net.add_arc(source=loop_head, target=loop_trans)

                exit_trans = self.new_transition(
                    label="exit",
                    line_number=lineno,
                )
                self.net.add_arc(source=loop_head, target=exit_trans)

                if is_last:
                    loop_exit = target_exit
                else:
                    loop_exit = self.new_place(label=f"exit_{loop_trans.id}", line_number=lineno)

                self.loop_stack.append(_LoopContext(head=loop_head, exit=loop_exit))
                body_stmts = _to_stmt_list(stmt.get("body"))
                self._walk_branch(body_stmts, loop_trans, loop_head, lineno)
                self.loop_stack.pop()

                self.net.add_arc(source=exit_trans, target=loop_exit)
                current_place = loop_exit

            elif stmt_type == "TryStatement":
                except_entry = self.new_place(label="except_entry", line_number=lineno)

                if is_last:
                    try_exit = target_exit
                else:
                    try_exit = self.new_place(label="try_exit", line_number=lineno)

                finalizer = stmt.get("finalizer")
                if finalizer:
                    finally_lineno = self._get_lineno(finalizer, lineno)
                    finally_entry = self.new_place(label="finally_entry", line_number=finally_lineno)
                    finally_stmts = _to_stmt_list(finalizer)
                else:
                    finally_entry = try_exit
                    finally_stmts = []

                try_normal_exit = finally_entry

                # Walk try body with try_stack active
                self.try_stack.append(_TryContext(except_entry=except_entry))
                try_stmts = _to_stmt_list(stmt.get("block"))
                self.walk_block(try_stmts, current_place=current_place, target_exit=try_normal_exit)
                self.try_stack.pop()

                # Walk catch handler if present
                handler = stmt.get("handler")
                if handler:
                    handler_lineno = self._get_lineno(handler, lineno)
                    param = handler.get("param")
                    if param:
                        param_str = self._slice(param)
                        handler_label = f"catch ({param_str})"
                    else:
                        handler_label = "catch"

                    handler_trans = self.new_transition(
                        label=handler_label,
                        line_number=handler_lineno,
                        hook_exception=False,
                    )
                    self.net.add_arc(source=except_entry, target=handler_trans)
                    catch_stmts = _to_stmt_list(handler.get("body"))
                    self._walk_branch(
                        catch_stmts,
                        source_transition=handler_trans,
                        target_exit=finally_entry,
                        line_number=handler_lineno,
                    )
                elif finalizer:
                    # try...finally without catch: unhandled exception flows to finally
                    exc_trans = self.new_transition(
                        label="exception",
                        line_number=lineno,
                        hook_exception=False,
                    )
                    self.net.add_arc(source=except_entry, target=exc_trans)
                    self.net.add_arc(source=exc_trans, target=finally_entry)

                # Walk finally block if present
                if finalizer:
                    self.walk_block(finally_stmts, current_place=finally_entry, target_exit=try_exit)

                current_place = try_exit

            else:
                next_place = target_exit if is_last else self.new_place(line_number=lineno)
                label = self._format_statement_label(stmt)
                trans = self.new_transition(
                    label=label,
                    line_number=lineno,
                )
                self.net.add_arc(source=current_place, target=trans)
                self.net.add_arc(source=trans, target=next_place)
                current_place = next_place

        return current_place


class JavascriptWalker(WalkerProtocol):
    """JavaScript AST walker implementing WalkerProtocol."""

    def __init__(self) -> None:
        self.raw_source: str = ""
        self.tree: Optional[dict] = None

    def parse_file(self, filepath: str) -> dict:
        """Parses a JavaScript file using Acorn, caching raw source text."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.raw_source = f.read()
        except UnicodeDecodeError:
            with open(filepath, "r", encoding="latin-1") as f:
                self.raw_source = f.read()

        # Try script first, fallback to module if required
        try:
            tree = Javascript.get_tree(filepath, LanguageParams(source_type="script"))
        except AssertionError as exc:
            if "source-type=module" in str(exc) or "SyntaxError" in str(exc):
                tree = Javascript.get_tree(filepath, LanguageParams(source_type="module"))
            else:
                raise

        self.tree = tree
        return tree

    def _get_executable_statements(self, tree: dict) -> List[dict]:
        """Returns top-level executable statements outside functions/classes."""
        return [
            s for s in tree.get("body", [])
            if s.get("type") not in ("FunctionDeclaration", "ClassDeclaration")
        ]

    def find_all_functions(self, tree: dict) -> List[str]:
        """Finds all function names and (global) if top-level code exists."""
        funcs = []
        if self._get_executable_statements(tree):
            funcs.append("(global)")

        declared_funcs = []
        for stmt in tree.get("body", []):
            if stmt.get("type") == "FunctionDeclaration" and stmt.get("id"):
                name = stmt["id"].get("name")
                lineno = stmt.get("loc", {}).get("start", {}).get("line", 0)
                if name:
                    declared_funcs.append((lineno, name))

        declared_funcs.sort(key=lambda item: item[0])
        funcs.extend([name for _, name in declared_funcs])
        return funcs

    def find_function(self, tree: dict, func_name: str) -> Optional[dict]:
        """Finds a function AST node by name or returns synthetic wrapper for (global)."""
        if func_name == "(global)":
            executable_stmts = self._get_executable_statements(tree)
            if not executable_stmts:
                return None
            first_lineno = 1
            if "loc" in executable_stmts[0]:
                first_lineno = executable_stmts[0]["loc"]["start"].get("line", 1)

            return {
                "type": "FunctionDeclaration",
                "id": {"type": "Identifier", "name": "(global)"},
                "loc": {"start": {"line": first_lineno, "column": 0}},
                "body": {
                    "type": "BlockStatement",
                    "body": executable_stmts,
                },
            }

        for stmt in tree.get("body", []):
            if stmt.get("type") == "FunctionDeclaration" and stmt.get("id"):
                if stmt["id"].get("name") == func_name:
                    return stmt

        return None

    def walk_function(self, ast_node: dict) -> PetriNet:
        """Walks a JavaScript function AST node and constructs a PetriNet model."""
        if not isinstance(ast_node, dict):
            raise TypeError(f"walk_function expects a dict AST node, got {type(ast_node).__name__}")

        net = PetriNet()
        start_lineno = 1
        if "loc" in ast_node and "start" in ast_node["loc"]:
            start_lineno = ast_node["loc"]["start"].get("line", 1)

        start_place = net.add_place(
            id_="p0",
            label="start",
            line_number=start_lineno,
            initial_tokens=1,
        )
        end_place = net.add_place(
            id_="p_end",
            label="end",
            line_number=None,
            initial_tokens=0,
        )

        # Extract statement block
        body_node = ast_node.get("body", {})
        if body_node.get("type") == "BlockStatement":
            statements = body_node.get("body", [])
        elif isinstance(body_node, list):
            statements = body_node
        else:
            statements = [body_node]

        walker = _JavascriptControlFlowWalker(
            net=net,
            end_place=end_place,
            raw_source=self.raw_source,
        )
        walker.walk_block(statements, current_place=start_place, target_exit=end_place)

        return net

