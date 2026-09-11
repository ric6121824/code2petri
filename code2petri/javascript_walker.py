import shutil
from typing import Optional, List, Any, Union, NamedTuple, Dict
from code2flow.engine import LanguageParams
from code2flow.javascript import Javascript
from code2petri.control_flow_builder import (
    ControlFlowBuilder,
    LoopContext,
    LoopRouting,
    StatementContext,
    TryContext,
)
from code2petri.model import PetriNet, Place, Transition
from code2petri.walker_protocol import WalkerProtocol, WalkResult, CallSite


class FunctionInfo(NamedTuple):
    """Metadata for a discovered JavaScript function, method, or callback."""
    qual_name: str
    bare_name: str
    lineno: int
    node: dict


def slice_source(source: str, node: Optional[dict]) -> str:
    """Extracts raw source substring for an AST node using character offsets."""
    if not node or not isinstance(node, dict) or "start" not in node or "end" not in node:
        return ""
    return source[node["start"]:node["end"]].strip()


def _to_stmt_list(node: Any) -> List[dict]:
    """Converts an AST node or list into a list of statement dicts."""
    if not node:
        return []
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        if node.get("type") == "BlockStatement":
            return node.get("body", [])
        return [node]
    return []


def get_nested(d: Any, *keys: str, default: Any = None) -> Any:
    """Safely traverses nested dictionaries along given keys."""
    curr = d
    for k in keys:
        if not isinstance(curr, dict):
            return default
        curr = curr.get(k)
    return curr if curr is not None else default


def _get_node_lineno(node: Optional[dict], default: Optional[int] = None) -> Optional[int]:
    """Extracts start line number from AST node's location metadata."""
    if not isinstance(node, dict):
        return default
    return get_nested(node, "loc", "start", "line", default=default)


def _get_block_lineno(stmts: List[dict], default: Optional[int] = None) -> Optional[int]:
    """Returns the line number of the first statement in a block, or default."""
    if stmts and isinstance(stmts, list):
        return _get_node_lineno(stmts[0], default)
    return default


def _get_class_name(node: dict) -> str:
    """Extracts class name from ClassDeclaration node, defaulting to (anonymous_class)."""
    return get_nested(node, "id", "name", default="(anonymous_class)")


def _get_class_body_elements(node: dict) -> List[dict]:
    """Extracts method/property elements from ClassDeclaration body."""
    return get_nested(node, "body", "body", default=[])


def _find_js_calls_in_node(node: Any) -> List[dict]:
    """Recursively finds CallExpression nodes within an expression subtree (avoiding nested functions)."""
    calls: List[dict] = []

    def _visit(n: Any) -> None:
        if isinstance(n, dict):
            ntype = n.get("type")
            if ntype in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
                return
            if ntype == "CallExpression":
                calls.append(n)
            for k, v in n.items():
                if k != "loc":
                    _visit(v)
        elif isinstance(n, list):
            for item in n:
                _visit(item)

    _visit(node)
    calls.sort(key=lambda c: _get_node_lineno(c, 0) or 0)
    return calls


class _JavascriptControlFlowWalker:
    """Internal recursive walker constructing PetriNet places, transitions, and arcs for JavaScript."""

    def __init__(
        self,
        builder: ControlFlowBuilder,
        start_place: Place,
        raw_source: str,
        func_name: Optional[str] = None,
        filepath: str = "",
    ) -> None:
        self.builder = builder
        self.start_place = start_place
        self.raw_source = raw_source
        self.func_name = func_name
        self.filepath = filepath
        self.call_sites: List[CallSite] = []
        self._statement_formatters = {
            "ReturnStatement": self._format_return,
            "BreakStatement": lambda s: "break",
            "ContinueStatement": lambda s: "continue",
            "ThrowStatement": self._format_throw,
            "SwitchStatement": self._format_switch,
            "IfStatement": self._format_if,
            "WhileStatement": self._format_while,
            "DoWhileStatement": self._format_do_while,
            "ForStatement": self._format_for,
            "ForInStatement": lambda s: self._format_for_in_of(s, "in"),
            "ForOfStatement": lambda s: self._format_for_in_of(s, "of"),
            "ExpressionStatement": self._format_expression_stmt,
            "VariableDeclaration": self._format_var_decl,
            "TryStatement": lambda s: "try",
        }
        self._statement_handlers = {
            "ReturnStatement": self._walk_return,
            "BreakStatement": self._walk_break,
            "ContinueStatement": self._walk_continue,
            "ThrowStatement": self._walk_throw,
            "IfStatement": self._walk_if,
            "WhileStatement": self._walk_standard_loop,
            "ForStatement": self._walk_standard_loop,
            "ForInStatement": self._walk_standard_loop,
            "ForOfStatement": self._walk_standard_loop,
            "TryStatement": self._walk_try,
            "SwitchStatement": self._walk_switch,
            "DoWhileStatement": self._walk_do_while,
        }

    def _extract_js_call_site(
        self,
        call_expr: dict,
        transition_id: str,
        default_lineno: int = 0,
    ) -> CallSite:
        callee = call_expr.get("callee", {})
        callee_type = callee.get("type")
        callee_owner = None

        if callee_type == "Identifier":
            callee_name = callee.get("name", "")
        elif callee_type == "MemberExpression":
            prop = callee.get("property", {})
            callee_name = prop.get("name") if prop.get("type") == "Identifier" else self._slice(prop)
            obj = callee.get("object", {})
            obj_type = obj.get("type")
            if obj_type == "ThisExpression":
                callee_owner = "this"
            elif obj_type == "Identifier":
                callee_owner = obj.get("name")
            else:
                callee_owner = self._slice(obj)
        else:
            callee_name = self._slice(callee)

        line_number = _get_node_lineno(call_expr) or default_lineno
        return CallSite(
            caller_function=self.func_name or "",
            caller_file=self.filepath or "",
            callee_name=callee_name,
            callee_owner=callee_owner,
            line_number=line_number,
            transition_id=transition_id,
        )

    def _record_calls_in_node(
        self,
        node: Any,
        transition_id: str,
        default_lineno: int = 0,
    ) -> None:
        if not node:
            return
        calls = _find_js_calls_in_node(node)
        for c in calls:
            self.call_sites.append(self._extract_js_call_site(c, transition_id, default_lineno))

    def _slice(self, node: Optional[dict]) -> str:
        """Extracts source text substring for an AST node using character offsets."""
        return slice_source(self.raw_source, node)

    def _get_lineno(self, node: Optional[dict], default: Optional[int] = None) -> Optional[int]:
        """Returns the 1-indexed start line number of an AST node."""
        return _get_node_lineno(node, default)

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

    def _format_return(self, stmt: dict) -> str:
        arg = stmt.get("argument")
        return f"return {self._slice(arg)}" if arg else "return"

    def _format_throw(self, stmt: dict) -> str:
        arg = stmt.get("argument")
        return f"throw {self._slice(arg)}" if arg else "throw"

    def _format_switch(self, stmt: dict) -> str:
        cases = stmt.get("cases", [])
        if cases and isinstance(cases[0], dict) and "start" in cases[0]:
            header = self.raw_source[stmt["start"]:cases[0]["start"]].strip().rstrip("{").strip()
            if header.startswith("switch"):
                return header
        disc = stmt.get("discriminant")
        if isinstance(disc, dict) and "end" in disc:
            brace_idx = self.raw_source.find("{", disc["end"])
            if brace_idx != -1:
                return self.raw_source[stmt["start"]:brace_idx].strip()
        return f"switch ({self._slice(disc)})"

    def _format_if(self, stmt: dict) -> str:
        consequent = stmt.get("consequent")
        if "start" in stmt and isinstance(consequent, dict) and "start" in consequent:
            header = self.raw_source[stmt["start"]:consequent["start"]].strip()
            if header.startswith("if"):
                return header
        return self._format_parenthesized_condition("if", stmt.get("test"))

    def _format_while(self, stmt: dict) -> str:
        body = stmt.get("body")
        if "start" in stmt and isinstance(body, dict) and "start" in body:
            header = self.raw_source[stmt["start"]:body["start"]].strip()
            if header.startswith("while"):
                return header
        return self._format_parenthesized_condition("while", stmt.get("test"))

    def _format_do_while(self, stmt: dict) -> str:
        body = stmt.get("body")
        if isinstance(body, dict) and "end" in body and "end" in stmt:
            sliced = self.raw_source[body["end"]:stmt["end"]].strip().rstrip(";").strip()
            if sliced.startswith("while"):
                return sliced
        return self._format_parenthesized_condition("while", stmt.get("test"))

    def _format_for(self, stmt: dict) -> str:
        header = self._get_loop_header_slice(stmt)
        if header:
            return header
        init_str = self._slice(stmt.get("init")).rstrip(";")
        test_str = self._slice(stmt.get("test"))
        update_str = self._slice(stmt.get("update"))
        return f"for ({init_str}; {test_str}; {update_str})"

    def _format_for_in_of(self, stmt: dict, op: str) -> str:
        header = self._get_loop_header_slice(stmt)
        if header:
            return header
        left_str = self._slice(stmt.get("left")).rstrip(";")
        right_str = self._slice(stmt.get("right"))
        return f"for ({left_str} {op} {right_str})"

    def _format_expression_stmt(self, stmt: dict) -> str:
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
        raw = self._slice(stmt)
        first_line = raw.split("\n")[0].strip().rstrip(";")
        return first_line or "statement"

    def _format_var_decl(self, stmt: dict) -> str:
        decls = stmt.get("declarations", [])
        if len(decls) == 1 and get_nested(decls[0], "init", "type") == "CallExpression":
            kind = stmt.get("kind", "let")
            var_name = self._slice(decls[0].get("id"))
            call_str = self._format_call_expression(decls[0]["init"])
            return f"{kind} {var_name} = {call_str}"
        raw = self._slice(stmt)
        first_line = raw.split("\n")[0].strip().rstrip(";")
        return first_line or "statement"

    def _format_statement_label(self, stmt: dict) -> str:
        """Returns a readable summary of the statement for transition labeling."""
        stmt_type = stmt.get("type")
        formatter = self._statement_formatters.get(stmt_type)
        if formatter:
            return formatter(stmt)

        raw = self._slice(stmt)
        first_line = raw.split("\n")[0].strip().rstrip(";")
        return first_line or stmt_type or "statement"

    def _find_raf_call(self, stmt: dict) -> Optional[dict]:
        """Finds a requestAnimationFrame CallExpression within a statement if present."""
        if not stmt or not isinstance(stmt, dict):
            return None
        stmt_type = stmt.get("type")
        call_expr = None
        if stmt_type == "ExpressionStatement":
            expr = stmt.get("expression") or {}
            if expr.get("type") == "CallExpression":
                call_expr = expr
            elif expr.get("type") == "AssignmentExpression":
                right = expr.get("right") or {}
                if right.get("type") == "CallExpression":
                    call_expr = right
        elif stmt_type == "VariableDeclaration":
            for decl in stmt.get("declarations", []):
                init = decl.get("init") or {}
                if init.get("type") == "CallExpression":
                    call_expr = init
                    break
        elif stmt_type == "ReturnStatement":
            arg = stmt.get("argument") or {}
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

    # TODO: Extend game-loop cycle detection to setTimeout or setInterval.
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
        if not isinstance(first_arg, dict):
            return False

        arg_type = first_arg.get("type")
        bare_func_name = self.func_name.split(".")[-1]

        # Case 1: Direct identifier, e.g. requestAnimationFrame(loop)
        if arg_type == "Identifier":
            name = first_arg.get("name")
            return name in (self.func_name, bare_func_name)

        # Case 2: Member expression, e.g. requestAnimationFrame(this.step) or requestAnimationFrame(WebGLEngine.step)
        if arg_type == "MemberExpression":
            prop = first_arg.get("property") or {}
            prop_name = prop.get("name") if prop.get("type") == "Identifier" else self._slice(prop)

            obj = first_arg.get("object") or {}
            obj_type = obj.get("type")

            if obj_type == "ThisExpression":
                # this.step matches enclosing method 'step' or 'ClassName.step'
                return prop_name in (self.func_name, bare_func_name)

            obj_name = obj.get("name") if obj_type == "Identifier" else self._slice(obj)
            full_member = f"{obj_name}.{prop_name}"
            return prop_name == bare_func_name or full_member == self.func_name

        # Case 3: Sliced string fallback (stripping 'this.')
        sliced = self._slice(first_arg)
        if sliced.startswith("this."):
            sliced = sliced[5:]
        return sliced in (self.func_name, bare_func_name)

    def _walk_return(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        trans = self.builder.wire_return(
            current_place=ctx.current_place,
            label=self._format_statement_label(stmt),
            line_number=ctx.lineno,
        )
        self._record_calls_in_node(stmt.get("argument"), trans.id, ctx.lineno or 0)
        return None

    def _walk_break(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        self.builder.wire_break(
            current_place=ctx.current_place,
            label=self._format_statement_label(stmt),
            line_number=ctx.lineno,
        )
        return None

    def _walk_continue(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        self.builder.wire_continue(
            current_place=ctx.current_place,
            label=self._format_statement_label(stmt),
            line_number=ctx.lineno,
        )
        return None

    def _walk_throw(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        trans = self.builder.wire_terminal_exception(
            current_place=ctx.current_place,
            label=self._format_statement_label(stmt),
            line_number=ctx.lineno,
        )
        self._record_calls_in_node(stmt.get("argument"), trans.id, ctx.lineno or 0)
        return None

    def _walk_if(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        alternate = stmt.get("alternate")
        else_lineno = self._get_lineno(alternate, ctx.lineno)
        return self.builder.wire_if_split(
            ctx=ctx,
            true_label=self._format_statement_label(stmt),
            consequent_stmts=_to_stmt_list(stmt.get("consequent")),
            false_lineno=else_lineno,
            alternate_stmts=_to_stmt_list(alternate),
            walk_block_fn=self.walk_block,
            on_true_trans=lambda t: self._record_calls_in_node(stmt.get("test"), t.id, ctx.lineno or 0),
        )

    def _walk_standard_loop(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        loop_trans = self.builder.new_transition(
            label=self._format_statement_label(stmt),
            line_number=ctx.lineno,
        )
        stmt_type = stmt.get("type")
        if stmt_type == "WhileStatement":
            self._record_calls_in_node(stmt.get("test"), loop_trans.id, ctx.lineno or 0)
        elif stmt_type == "ForStatement":
            self._record_calls_in_node(stmt.get("init"), loop_trans.id, ctx.lineno or 0)
            self._record_calls_in_node(stmt.get("test"), loop_trans.id, ctx.lineno or 0)
            self._record_calls_in_node(stmt.get("update"), loop_trans.id, ctx.lineno or 0)
        elif stmt_type in ("ForInStatement", "ForOfStatement"):
            self._record_calls_in_node(stmt.get("right"), loop_trans.id, ctx.lineno or 0)

        exit_trans = self.builder.new_transition(
            label="exit",
            line_number=ctx.lineno,
        )
        loop_exit = ctx.target_exit if ctx.is_last else self.builder.new_place(label=f"exit_{loop_trans.id}", line_number=ctx.lineno)

        body_stmts = _to_stmt_list(stmt.get("body"))
        routing = LoopRouting(
            head=ctx.current_place,
            loop_trans=loop_trans,
            exit_trans=exit_trans,
            exit_place=loop_exit,
        )
        self.builder.wire_standard_loop(
            routing=routing,
            body_stmts=body_stmts,
            walk_block_fn=self.walk_block,
            lineno=ctx.lineno,
        )
        self.builder.add_arc(source=exit_trans, target=loop_exit)
        return loop_exit

    def _walk_try(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        finalizer = stmt.get("finalizer")
        finally_stmts = _to_stmt_list(finalizer) if finalizer else None
        finally_lineno = self._get_lineno(finalizer, ctx.lineno) if finalizer else None

        handler = stmt.get("handler")
        handlers = []
        if handler:
            handler_lineno = self._get_lineno(handler, ctx.lineno)
            param = handler.get("param")
            if param:
                param_str = self._slice(param)
                handler_label = f"catch ({param_str})"
            else:
                handler_label = "catch"
            handlers.append((handler_label, handler_lineno, _to_stmt_list(handler.get("body"))))

        return self.builder.wire_try_catch(
            ctx=ctx,
            try_body=_to_stmt_list(stmt.get("block")),
            handlers=handlers,
            finally_stmts=finally_stmts,
            finally_lineno=finally_lineno,
            walk_block_fn=self.walk_block,
        )

    def _walk_switch(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        decision_place = ctx.current_place
        switch_exit = ctx.target_exit if ctx.is_last else self.builder.new_place(label="exit_switch", line_number=ctx.lineno)

        self.builder.push_loop(head=None, exit=switch_exit)
        cases = stmt.get("cases", [])
        has_default = any(case.get("test") is None for case in cases)

        if not cases:
            default_trans = self.builder.new_transition(label="default", line_number=ctx.lineno)
            self.builder.add_arc(source=decision_place, target=default_trans)
            self.builder.add_arc(source=default_trans, target=switch_exit)
            self.builder.pop_loop()
            return switch_exit

        case_entry_places: List[Place] = []
        for case in cases:
            case_lineno = self._get_lineno(case, ctx.lineno)
            case_label = "case_entry" if case.get("test") is not None else "default_entry"
            case_entry_places.append(self.builder.new_place(label=case_label, line_number=case_lineno))

        for case, case_entry in zip(cases, case_entry_places):
            case_test = case.get("test")
            case_lineno = self._get_lineno(case, ctx.lineno)
            if case_test is not None:
                test_str = self._slice(case_test)
                case_label = f"case {test_str}"
            else:
                case_label = "default"

            case_trans = self.builder.new_transition(label=case_label, line_number=case_lineno)
            self.builder.add_arc(source=decision_place, target=case_trans)
            self.builder.add_arc(source=case_trans, target=case_entry)

        if not has_default:
            default_trans = self.builder.new_transition(label="default", line_number=ctx.lineno)
            self.builder.add_arc(source=decision_place, target=default_trans)
            self.builder.add_arc(source=default_trans, target=switch_exit)

        for i, (case, case_entry) in enumerate(zip(cases, case_entry_places)):
            case_lineno = self._get_lineno(case, ctx.lineno)
            case_body = _to_stmt_list(case.get("consequent", []))
            next_target = case_entry_places[i + 1] if i + 1 < len(cases) else switch_exit

            if not case_body:
                pass_trans = self.builder.new_transition(label="fallthrough", line_number=case_lineno)
                self.builder.add_arc(source=case_entry, target=pass_trans)
                self.builder.add_arc(source=pass_trans, target=next_target)
            else:
                self.walk_block(case_body, current_place=case_entry, target_exit=next_target)

        self.builder.pop_loop()

        incoming_to_exit = self.builder.has_incoming_arcs(switch_exit)
        if not incoming_to_exit:
            return None

        return switch_exit

    def _walk_do_while(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        body_head = ctx.current_place
        test_node = stmt.get("test")
        test_lineno = self._get_lineno(test_node, ctx.lineno)
        check_place = self.builder.new_place(label="check_do_while", line_number=test_lineno)
        loop_exit = ctx.target_exit if ctx.is_last else self.builder.new_place(label="exit_do_while", line_number=ctx.lineno)

        self.builder.push_loop(head=check_place, exit=loop_exit)
        body_stmts = _to_stmt_list(stmt.get("body"))
        self.walk_block(body_stmts, current_place=body_head, target_exit=check_place)
        self.builder.pop_loop()

        cond_label = self._format_do_while(stmt)
        cond_trans = self.builder.new_transition(label=cond_label, line_number=test_lineno)
        self._record_calls_in_node(test_node, cond_trans.id, test_lineno or 0)
        self.builder.add_arc(source=check_place, target=cond_trans)
        self.builder.add_arc(source=cond_trans, target=body_head)

        exit_trans = self.builder.new_transition(label="exit", line_number=test_lineno)
        self.builder.add_arc(source=check_place, target=exit_trans)
        self.builder.add_arc(source=exit_trans, target=loop_exit)

        return loop_exit

    def _walk_raf_cycle(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        label = self._format_statement_label(stmt)
        trans = self.builder.new_transition(label=label, line_number=ctx.lineno)
        self._record_calls_in_node(stmt, trans.id, ctx.lineno or 0)
        self.builder.add_arc(source=ctx.current_place, target=trans)
        self.builder.add_arc(source=trans, target=self.start_place)

        stmt_type = stmt.get("type")
        if stmt_type == "ReturnStatement":
            target = self.builder.get_active_finally() or self.builder.end_place
            if target is not None:
                self.builder.add_arc(source=trans, target=target)
            return None
        else:
            next_place = ctx.target_exit if ctx.is_last else self.builder.new_place(line_number=ctx.lineno)
            self.builder.add_arc(source=trans, target=next_place)
            return next_place

    def _walk_default_stmt(
        self,
        stmt: dict,
        ctx: StatementContext,
    ) -> Optional[Place]:
        label = self._format_statement_label(stmt)
        return self.builder.wire_sequential_statement(
            current_place=ctx.current_place,
            label=label,
            lineno=ctx.lineno,
            is_last=ctx.is_last,
            target_exit=ctx.target_exit,
            on_trans=lambda t: self._record_calls_in_node(stmt, t.id, ctx.lineno or 0),
        )

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
            ctx = StatementContext(
                current_place=current_place,
                is_last=is_last,
                target_exit=target_exit,
                lineno=lineno,
            )

            if self._is_raf_cycle_call(stmt):
                res = self._walk_raf_cycle(stmt, ctx)
                if res is None:
                    return None
                current_place = res
                continue

            handler = self._statement_handlers.get(stmt_type, self._walk_default_stmt)
            res = handler(stmt, ctx)
            if res is None:
                return None
            current_place = res

        return current_place


class JavascriptWalker(WalkerProtocol):
    """JavaScript AST walker implementing WalkerProtocol."""

    def __init__(self) -> None:
        self.raw_source: str = ""
        self.tree: Optional[dict] = None
        self.filepath: Optional[str] = None

    def get_node_lineno(self, ast_node: Any) -> int:
        """Returns the start line number for a JavaScript AST node, defaulting to 0."""
        return _get_node_lineno(ast_node, 0)

    def parse_file(self, filepath: str) -> dict:
        """Parses a JavaScript file using Acorn, caching raw source text.

        Requires Node.js and the 'acorn' npm package.
        """
        if not shutil.which("node"):
            raise RuntimeError(
                "Node.js is required to parse JavaScript files with code2petri. "
                "Please ensure Node.js is installed and available in PATH."
            )

        self.filepath = filepath
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.raw_source = f.read()
        except UnicodeDecodeError:
            with open(filepath, "r", encoding="latin-1") as f:
                self.raw_source = f.read()

        try:
            tree = Javascript.get_tree(filepath, LanguageParams(source_type="script"))
        except AssertionError as exc:
            raise RuntimeError(
                f"Failed to parse JavaScript file {filepath!r} with Acorn. "
                "Ensure that Node.js and the 'acorn' npm package are installed. "
                f"Details: {exc}"
            ) from exc

        self.tree = tree
        return tree

    def _slice_node(self, node: Optional[dict]) -> str:
        """Extracts raw source substring for an AST node."""
        return slice_source(self.raw_source, node)

    def _get_executable_statements(self, tree: dict) -> List[dict]:
        """Returns top-level executable statements outside functions/classes."""
        return [
            s for s in tree.get("body", [])
            if s.get("type") not in ("FunctionDeclaration", "ClassDeclaration")
        ]

    def _collect_all_functions(self, tree: dict) -> List[FunctionInfo]:
        """Recursively collects all function declarations, class methods, and callbacks."""
        results: List[FunctionInfo] = []

        def _traverse(node: Any, scope: List[str]) -> None:
            if isinstance(node, dict):
                ntype = node.get("type")
                if ntype == "ClassDeclaration":
                    cls_name = _get_class_name(node)
                    body = _get_class_body_elements(node)
                    cls_qual = f"{'.'.join(scope)}.{cls_name}" if scope else cls_name
                    for elem in body:
                        if elem.get("type") == "MethodDefinition":
                            key = get_nested(elem, "key", "name")
                            if not key and "key" in elem:
                                key = self._slice_node(elem["key"])
                            val = elem.get("value", {})
                            lineno = _get_node_lineno(elem) or _get_node_lineno(val, 0)
                            qual_name = f"{cls_qual}.{key}"
                            if isinstance(val, dict):
                                val["_qual_name"] = qual_name
                                val["_bare_name"] = key
                            results.append(FunctionInfo(
                                qual_name=qual_name,
                                bare_name=key,
                                lineno=lineno,
                                node=val,
                            ))
                            new_scope = scope + [cls_name, key]
                            _traverse(val.get("body"), new_scope)
                    return

                elif ntype in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
                    func_id = node.get("id")
                    name = func_id.get("name") if func_id else None
                    lineno = _get_node_lineno(node, 0)
                    if name:
                        qual_name = f"{'.'.join(scope)}.{name}" if scope else name
                        bare_name = name
                    else:
                        qual_name = f"{'.'.join(scope)}.(anonymous@{lineno})" if scope else f"(anonymous@{lineno})"
                        bare_name = f"(anonymous@{lineno})"

                    node["_qual_name"] = qual_name
                    node["_bare_name"] = bare_name

                    results.append(FunctionInfo(
                        qual_name=qual_name,
                        bare_name=bare_name,
                        lineno=lineno,
                        node=node,
                    ))
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
        collected.sort(key=lambda item: item.lineno)
        funcs.extend([item.qual_name for item in collected])
        return funcs

    def find_function(self, tree: dict, func_name: str) -> Optional[dict]:
        """Finds a function AST node by name or returns synthetic wrapper for (global)."""
        if func_name == "(global)":
            executable_stmts = self._get_executable_statements(tree)
            if not executable_stmts:
                return None
            first_lineno = _get_node_lineno(executable_stmts[0], 1)

            wrapper = {
                "type": "FunctionDeclaration",
                "id": {"type": "Identifier", "name": "(global)"},
                "loc": {"start": {"line": first_lineno, "column": 0}},
                "body": {
                    "type": "BlockStatement",
                    "body": executable_stmts,
                },
            }
            return wrapper

        collected = self._collect_all_functions(tree)

        # 1. Exact match on qualified name
        for item in collected:
            if item.qual_name == func_name:
                return item.node

        # 2. Exact match on bare name
        for item in collected:
            if item.bare_name == func_name:
                return item.node

        # 3. Anonymous callback substring match (e.g. (anonymous@151) in qual_name)
        if "(anonymous@" in func_name:
            for item in collected:
                if func_name in item.qual_name or func_name in item.bare_name:
                    return item.node

        return None

    def _extract_new_class_name(self, node: Any) -> Optional[str]:
        """Extracts the instantiated class name from a NewExpression AST node."""
        if not isinstance(node, dict) or node.get("type") != "NewExpression":
            return None
        callee = node.get("callee", {})
        if callee.get("type") == "Identifier":
            return callee.get("name")
        return self._slice_node(callee)

    def collect_variable_bindings(self, tree: Any) -> Dict[str, str]:
        """Collects variable to class name bindings from constructor calls in the AST."""
        if not tree:
            return {}

        bindings: Dict[str, str] = {}

        def _traverse(node: Any) -> None:
            if isinstance(node, dict):
                ntype = node.get("type")
                if ntype == "VariableDeclaration":
                    for decl in node.get("declarations", []):
                        class_name = self._extract_new_class_name(decl.get("init"))
                        id_node = decl.get("id", {})
                        if id_node.get("type") == "Identifier":
                            var_name = id_node.get("name")
                            if var_name and class_name:
                                bindings[var_name] = class_name
                elif ntype == "AssignmentExpression" and node.get("operator") == "=":
                    class_name = self._extract_new_class_name(node.get("right"))
                    if class_name:
                        left = node.get("left", {})
                        left_type = left.get("type")
                        var_name = None
                        if left_type == "Identifier":
                            var_name = left.get("name")
                        elif left_type == "MemberExpression":
                            obj = left.get("object", {})
                            prop = left.get("property", {})
                            prop_name = (
                                prop.get("name")
                                if prop.get("type") == "Identifier"
                                else self._slice_node(prop)
                            )
                            if obj.get("type") == "ThisExpression":
                                var_name = f"this.{prop_name}"
                            elif obj.get("type") == "Identifier":
                                var_name = f"{obj.get('name')}.{prop_name}"
                            else:
                                sliced_obj = self._slice_node(obj)
                                if sliced_obj:
                                    var_name = f"{sliced_obj}.{prop_name}"
                        if var_name and class_name:
                            bindings[var_name] = class_name

                for k, v in node.items():
                    if k != "loc":
                        _traverse(v)
            elif isinstance(node, list):
                for item in node:
                    _traverse(item)

        _traverse(tree)
        return bindings

    def walk_function(
        self,
        ast_node: Any,
        func_name: str = "",
        filepath: Optional[str] = None,
    ) -> WalkResult:
        """Walks a JavaScript function AST node and constructs a PetriNet model packaged in a WalkResult."""
        if not isinstance(ast_node, dict):
            raise TypeError(f"walk_function expects a dict AST node, got {type(ast_node).__name__}")

        if ast_node.get("type") == "MethodDefinition":
            func_node = ast_node.get("value", {})
            if not func_name:
                func_name = ast_node.get("_qual_name") or get_nested(ast_node, "key", "name", default="")
        else:
            func_node = ast_node

        if not func_name:
            func_name = (
                ast_node.get("_qual_name")
                or get_nested(func_node, "_qual_name", default="")
                or get_nested(func_node, "id", "name", default="")
            )

        active_filepath = filepath or getattr(self, "filepath", "") or ""

        net = PetriNet()
        start_lineno = _get_node_lineno(func_node) or _get_node_lineno(ast_node, 1)

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

        builder = ControlFlowBuilder(net=net, end_place=end_place)
        walker = _JavascriptControlFlowWalker(
            builder=builder,
            start_place=start_place,
            raw_source=self.raw_source,
            func_name=func_name or None,
            filepath=active_filepath,
        )
        walker.walk_block(statements, current_place=start_place, target_exit=end_place)

        return WalkResult(net=net, call_sites=walker.call_sites)

