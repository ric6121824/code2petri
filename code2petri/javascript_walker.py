import os
from typing import Optional, List, Any

from code2flow.engine import LanguageParams
from code2flow.javascript import Javascript
from code2petri.base_walker import _BaseControlFlowWalker
from code2petri.model import PetriNet, Place, Transition
from code2petri.walker_protocol import WalkerProtocol

# Ensure NODE_PATH contains global node_modules if not already set
if "NODE_PATH" not in os.environ:
    os.environ["NODE_PATH"] = "/usr/local/lib/node_modules"


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

    def _get_lineno(self, node: dict, default: Optional[int] = None) -> Optional[int]:
        """Returns the 1-indexed start line number of an AST node."""
        if isinstance(node, dict) and "loc" in node and "start" in node["loc"]:
            return node["loc"]["start"].get("line", default)
        return default

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

        # Expression statement wrapping a call
        if stmt_type == "ExpressionStatement":
            expr = stmt.get("expression", {})
            if expr.get("type") == "CallExpression":
                callee = expr.get("callee", {})
                if callee.get("type") == "Identifier":
                    return f"call: {callee.get('name')}()"
                elif callee.get("type") == "MemberExpression":
                    obj_str = self._slice(callee.get("object"))
                    prop = callee.get("property", {})
                    prop_str = prop.get("name") or self._slice(prop)
                    return f"call: {obj_str}.{prop_str}()"
                else:
                    return f"call: {self._slice(callee)}()"

        # Default source slice
        raw = self._slice(stmt)
        first_line = raw.split("\n")[0].strip().rstrip(";")
        return first_line or stmt_type or "statement"

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

    def _has_executable_global_statements(self, tree: dict) -> bool:
        """Checks whether the program has top-level executable statements outside functions/classes."""
        for stmt in tree.get("body", []):
            if stmt.get("type") not in ("FunctionDeclaration", "ClassDeclaration"):
                return True
        return False

    def find_all_functions(self, tree: dict) -> List[str]:
        """Finds all function names and (global) if top-level code exists."""
        funcs = []
        if self._has_executable_global_statements(tree):
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
            executable_stmts = [
                s for s in tree.get("body", [])
                if s.get("type") not in ("FunctionDeclaration", "ClassDeclaration")
            ]
            first_lineno = 1
            if executable_stmts and "loc" in executable_stmts[0]:
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


# Module-level convenience functions
def parse_file(filepath: str) -> dict:
    return JavascriptWalker().parse_file(filepath)


def find_function(tree: dict, func_name: str) -> Optional[dict]:
    return JavascriptWalker().find_function(tree, func_name)


def find_all_functions(tree: dict) -> List[str]:
    return JavascriptWalker().find_all_functions(tree)


def walk_function(ast_node: dict) -> PetriNet:
    return JavascriptWalker().walk_function(ast_node)
