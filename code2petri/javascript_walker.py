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

    def __init__(
        self,
        net: PetriNet,
        start_place: Place,
        end_place: Place,
        raw_source: str,
        func_name: Optional[str] = None,
    ) -> None:
        super().__init__(net, end_place)
        self.start_place = start_place
        self.raw_source = raw_source
        self.func_name = func_name

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

        # Throw statement
        if stmt_type == "ThrowStatement":
            arg = stmt.get("argument")
            if arg:
                return f"throw {self._slice(arg)}"
            return "throw"

        # Switch statement
        if stmt_type == "SwitchStatement":
            disc = self._slice(stmt.get("discriminant"))
            return f"switch ({disc})"

        # If statement
        if stmt_type == "IfStatement":
            return self._format_parenthesized_condition("if", stmt.get("test"))

        # While statement
        if stmt_type == "WhileStatement":
            return self._format_parenthesized_condition("while", stmt.get("test"))

        # Do-while statement
        if stmt_type == "DoWhileStatement":
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
        """Handles break or continue jump statements to loop/switch exit or loop head."""
        stmt_type = stmt.get("type")
        is_break = stmt_type == "BreakStatement"
        keyword = "break" if is_break else "continue"
        lineno = self._get_lineno(stmt)
        if not self.loop_stack:
            raise SyntaxError(f"'{keyword}' outside loop at line {lineno}")
        if is_break:
            target_place = self.loop_stack[-1].exit
        else:
            target_place = None
            for ctx in reversed(self.loop_stack):
                if ctx.head is not None:
                    target_place = ctx.head
                    break
            if target_place is None:
                raise SyntaxError(f"'continue' outside loop at line {lineno}")
        trans = self.new_transition(
            label=self._format_statement_label(stmt),
            line_number=lineno,
        )
        self.net.add_arc(source=current_place, target=trans)
        self.net.add_arc(source=trans, target=target_place)

    def _find_raf_call(self, stmt: dict) -> Optional[dict]:
        """Finds a requestAnimationFrame CallExpression within a statement if present."""
        if not stmt or not isinstance(stmt, dict):
            return None
        stmt_type = stmt.get("type")
        call_expr = None
        if stmt_type == "ExpressionStatement":
            expr = stmt.get("expression", {})
            if expr.get("type") == "CallExpression":
                call_expr = expr
            elif expr.get("type") == "AssignmentExpression":
                right = expr.get("right", {})
                if right.get("type") == "CallExpression":
                    call_expr = right
        elif stmt_type == "VariableDeclaration":
            for decl in stmt.get("declarations", []):
                init = decl.get("init", {})
                if init.get("type") == "CallExpression":
                    call_expr = init
                    break
        elif stmt_type == "ReturnStatement":
            arg = stmt.get("argument", {})
            if arg.get("type") == "CallExpression":
                call_expr = arg

        if not call_expr:
            return None

        callee = call_expr.get("callee", {})
        callee_name = None
        if callee.get("type") == "Identifier":
            callee_name = callee.get("name")
        elif callee.get("type") == "MemberExpression":
            prop = callee.get("property", {})
            callee_name = prop.get("name") or self._slice(prop)

        if callee_name == "requestAnimationFrame":
            return call_expr
        return None

    def _is_raf_cycle_call(self, stmt: dict) -> bool:
        """Determines if a statement is a recursive requestAnimationFrame call to enclosing func."""
        if not self.func_name:
            return False
        call_expr = self._find_raf_call(stmt)
        if not call_expr:
            return False
        args = call_expr.get("arguments", [])
        if not args:
            return False
        first_arg = args[0]
        arg_name = first_arg.get("name") if first_arg.get("type") == "Identifier" else self._slice(first_arg)
        bare_func_name = self.func_name.split(".")[-1]
        return arg_name in (self.func_name, bare_func_name)

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

            elif stmt_type == "SwitchStatement":
                decision_place = current_place
                if is_last:
                    switch_exit = target_exit
                else:
                    switch_exit = self.new_place(label="exit_switch", line_number=lineno)

                self.loop_stack.append(_LoopContext(head=None, exit=switch_exit))
                cases = stmt.get("cases", [])
                has_default = any(case.get("test") is None for case in cases)

                for case in cases:
                    case_test = case.get("test")
                    case_lineno = self._get_lineno(case, lineno)
                    if case_test:
                        case_label = f"case {self._slice(case_test)}"
                    else:
                        case_label = "default"

                    case_trans = self.new_transition(
                        label=case_label,
                        line_number=case_lineno,
                    )
                    self.net.add_arc(source=decision_place, target=case_trans)
                    case_stmts = case.get("consequent", [])
                    self._walk_branch(
                        case_stmts,
                        source_transition=case_trans,
                        target_exit=switch_exit,
                        line_number=case_lineno,
                    )

                if not has_default:
                    default_trans = self.new_transition(
                        label="default",
                        line_number=lineno,
                    )
                    self.net.add_arc(source=decision_place, target=default_trans)
                    self.net.add_arc(source=default_trans, target=switch_exit)

                self.loop_stack.pop()

                incoming_to_exit = [a for a in self.net.arcs if a.target == switch_exit]
                if not incoming_to_exit:
                    return None

                current_place = switch_exit

            elif stmt_type == "DoWhileStatement":
                body_head = current_place
                test_node = stmt.get("test")
                test_lineno = self._get_lineno(test_node, lineno)
                check_place = self.new_place(label="check_do_while", line_number=test_lineno)

                if is_last:
                    loop_exit = target_exit
                else:
                    loop_exit = self.new_place(label="exit_do_while", line_number=lineno)

                self.loop_stack.append(_LoopContext(head=check_place, exit=loop_exit))
                body_stmts = _to_stmt_list(stmt.get("body"))
                self.walk_block(body_stmts, current_place=body_head, target_exit=check_place)
                self.loop_stack.pop()

                cond_label = self._format_parenthesized_condition("while", test_node)
                cond_trans = self.new_transition(
                    label=cond_label,
                    line_number=test_lineno,
                )
                self.net.add_arc(source=check_place, target=cond_trans)
                self.net.add_arc(source=cond_trans, target=body_head)

                exit_trans = self.new_transition(
                    label="exit",
                    line_number=test_lineno,
                )
                self.net.add_arc(source=check_place, target=exit_trans)
                self.net.add_arc(source=exit_trans, target=loop_exit)

                current_place = loop_exit

            elif stmt_type == "ThrowStatement":
                label = self._format_statement_label(stmt)
                trans = self.new_transition(
                    label=label,
                    line_number=lineno,
                )
                self.net.add_arc(source=current_place, target=trans)
                if not self.try_stack:
                    self.net.add_arc(source=trans, target=self.end_place)
                return None

            elif self._is_raf_cycle_call(stmt):
                label = self._format_statement_label(stmt)
                trans = self.new_transition(
                    label=label,
                    line_number=lineno,
                )
                self.net.add_arc(source=current_place, target=trans)
                self.net.add_arc(source=trans, target=self.start_place)
                if is_last:
                    return None
                else:
                    next_place = self.new_place(line_number=lineno)
                    self.net.add_arc(source=trans, target=next_place)
                    current_place = next_place

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

    def _slice_node(self, node: Optional[dict]) -> str:
        """Extracts raw source substring for an AST node."""
        if not node or "start" not in node or "end" not in node:
            return ""
        return self.raw_source[node["start"]:node["end"]].strip()

    def _get_executable_statements(self, tree: dict) -> List[dict]:
        """Returns top-level executable statements outside functions/classes."""
        return [
            s for s in tree.get("body", [])
            if s.get("type") not in ("FunctionDeclaration", "ClassDeclaration")
        ]

    def _collect_all_functions(self, tree: dict) -> List[dict]:
        """Recursively collects all function declarations, class methods, and callbacks."""
        results = []

        def _traverse(node: Any, scope: List[str]) -> None:
            if isinstance(node, dict):
                ntype = node.get("type")
                if ntype == "ClassDeclaration":
                    cls_name = node.get("id", {}).get("name", "(anonymous_class)")
                    body = node.get("body", {}).get("body", [])
                    for elem in body:
                        if elem.get("type") == "MethodDefinition":
                            key = elem.get("key", {}).get("name")
                            if not key and "key" in elem:
                                key = self._slice_node(elem["key"])
                            val = elem.get("value", {})
                            lineno = (
                                elem.get("loc", {}).get("start", {}).get("line")
                                or val.get("loc", {}).get("start", {}).get("line", 0)
                            )
                            qual_name = f"{cls_name}.{key}"
                            results.append({
                                "qual_name": qual_name,
                                "bare_name": key,
                                "lineno": lineno,
                                "node": val,
                            })
                            _traverse(val.get("body"), scope + [cls_name, key])
                    return

                elif ntype == "FunctionDeclaration":
                    name = node.get("id", {}).get("name")
                    lineno = node.get("loc", {}).get("start", {}).get("line", 0)
                    if name:
                        qual_name = f"{'.'.join(scope)}.{name}" if scope else name
                        bare_name = name
                    else:
                        qual_name = f"{'.'.join(scope)}.(anonymous@{lineno})" if scope else f"(anonymous@{lineno})"
                        bare_name = f"(anonymous@{lineno})"

                    results.append({
                        "qual_name": qual_name,
                        "bare_name": bare_name,
                        "lineno": lineno,
                        "node": node,
                    })
                    new_scope = scope + [bare_name]
                    _traverse(node.get("body"), new_scope)
                    return

                elif ntype in ("FunctionExpression", "ArrowFunctionExpression"):
                    lineno = node.get("loc", {}).get("start", {}).get("line", 0)
                    func_id = node.get("id")
                    if func_id and func_id.get("name"):
                        name = func_id.get("name")
                        qual_name = f"{'.'.join(scope)}.{name}" if scope else name
                        bare_name = name
                    else:
                        qual_name = f"{'.'.join(scope)}.(anonymous@{lineno})" if scope else f"(anonymous@{lineno})"
                        bare_name = f"(anonymous@{lineno})"

                    results.append({
                        "qual_name": qual_name,
                        "bare_name": bare_name,
                        "lineno": lineno,
                        "node": node,
                    })
                    new_scope = scope + [bare_name]
                    _traverse(node.get("body"), new_scope)
                    return

                for k, v in node.items():
                    if k != "loc":
                        _traverse(v, scope)

            elif isinstance(node, list):
                for item in node:
                    _traverse(item, scope)

        _traverse(tree, [])
        return results

    def find_all_functions(self, tree: dict) -> List[str]:
        """Finds all function names and (global) if top-level code exists."""
        funcs = []
        if self._get_executable_statements(tree):
            funcs.append("(global)")

        collected = self._collect_all_functions(tree)
        collected.sort(key=lambda item: item["lineno"])
        funcs.extend([item["qual_name"] for item in collected])
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

            wrapper = {
                "type": "FunctionDeclaration",
                "id": {"type": "Identifier", "name": "(global)"},
                "loc": {"start": {"line": first_lineno, "column": 0}},
                "body": {
                    "type": "BlockStatement",
                    "body": executable_stmts,
                },
                "_petri_func_name": "(global)",
            }
            return wrapper

        collected = self._collect_all_functions(tree)

        # 1. Exact match on qualified name
        for item in collected:
            if item["qual_name"] == func_name:
                item["node"]["_petri_func_name"] = item["qual_name"]
                return item["node"]

        # 2. Exact match on bare name
        for item in collected:
            if item["bare_name"] == func_name:
                item["node"]["_petri_func_name"] = item["qual_name"]
                return item["node"]

        # 3. Suffix match (e.g. .func_name)
        for item in collected:
            if item["qual_name"].endswith(f".{func_name}"):
                item["node"]["_petri_func_name"] = item["qual_name"]
                return item["node"]

        # 4. Anonymous callback substring match (e.g. (anonymous@151) in qual_name)
        if "(anonymous@" in func_name:
            for item in collected:
                if func_name in item["qual_name"] or func_name in item["bare_name"]:
                    item["node"]["_petri_func_name"] = item["qual_name"]
                    return item["node"]

        return None

    def walk_function(self, ast_node: dict, func_name: Optional[str] = None) -> PetriNet:
        """Walks a JavaScript function AST node and constructs a PetriNet model."""
        if not isinstance(ast_node, dict):
            raise TypeError(f"walk_function expects a dict AST node, got {type(ast_node).__name__}")

        if ast_node.get("type") == "MethodDefinition":
            func_node = ast_node.get("value", {})
            if func_name is None and ast_node.get("key"):
                func_name = ast_node["key"].get("name")
        else:
            func_node = ast_node

        if func_name is None:
            func_name = func_node.get("_petri_func_name") or ast_node.get("_petri_func_name")
            if func_name is None and func_node.get("id"):
                func_name = func_node["id"].get("name")

        net = PetriNet()
        start_lineno = 1
        loc = func_node.get("loc") or ast_node.get("loc")
        if loc and "start" in loc:
            start_lineno = loc["start"].get("line", 1)

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
        body_node = func_node.get("body", {})
        if body_node.get("type") == "BlockStatement":
            statements = body_node.get("body", [])
        elif isinstance(body_node, list):
            statements = body_node
        elif isinstance(body_node, dict) and body_node:
            statements = [{
                "type": "ExpressionStatement",
                "expression": body_node,
                "loc": body_node.get("loc"),
                "start": body_node.get("start"),
                "end": body_node.get("end"),
            }]
        else:
            statements = []

        walker = _JavascriptControlFlowWalker(
            net=net,
            start_place=start_place,
            end_place=end_place,
            raw_source=self.raw_source,
            func_name=func_name,
        )
        walker.walk_block(statements, current_place=start_place, target_exit=end_place)

        return net

