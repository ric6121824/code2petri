import ast
import builtins as _python_builtins
from typing import Optional, Union, List, Dict, Any, Tuple

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


def _collect_functions(tree: ast.AST) -> List[Tuple[str, Union[ast.FunctionDef, ast.AsyncFunctionDef]]]:
    """Traverses tree to collect (qualified_name, node) pairs ordered by line number."""
    results: List[Tuple[str, Union[ast.FunctionDef, ast.AsyncFunctionDef]]] = []

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


def _python_inferred_type(expression: ast.AST, bindings: Dict[str, Dict[str, Any]],
                          call_results: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Infer a deliberately small set of Python expression types and dependencies."""
    if isinstance(expression, ast.Constant):
        value_type = _direct_literal_type(expression)
        return {"type": value_type or "unknown", "evidence": []}
    if isinstance(expression, (ast.List, ast.Dict, ast.Tuple, ast.Set)):
        return {"type": {ast.List: "list", ast.Dict: "dict", ast.Tuple: "tuple", ast.Set: "set"}[type(expression)], "evidence": []}
    if isinstance(expression, ast.ListComp):
        value_type = "unknown" if any(generator.is_async for generator in expression.generators) else "list"
        return {"type": value_type, "evidence": []}
    if isinstance(expression, ast.JoinedStr):
        dependencies = []
        for part in expression.values:
            if isinstance(part, ast.FormattedValue):
                part_evidence = _python_inferred_type(part.value, bindings, call_results)["evidence"]
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
        operand = _python_inferred_type(expression.operand, bindings, call_results)
        operand_type = operand["type"]
        if isinstance(expression.op, ast.Not) and operand_type in {"bool", "int", "float", "complex", "str", "bytes", "NoneType"}:
            value_type = "bool"
        elif isinstance(expression.op, (ast.UAdd, ast.USub)) and operand_type in {"int", "float", "complex"}:
            value_type = operand_type
        else:
            value_type = "unknown"
        return {"type": value_type, "evidence": operand["evidence"]}
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _python_inferred_type(expression.left, bindings, call_results)
        right = _python_inferred_type(expression.right, bindings, call_results)
        left_type, right_type = left["type"], right["type"]
        if isinstance(expression.op, ast.Add) and left_type == right_type == "list":
            value_type = "list"
        elif isinstance(expression.op, ast.Add) and left_type == right_type == "str":
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
    if isinstance(expression, ast.Call):
        location = (getattr(expression, "lineno", 0), getattr(expression, "col_offset", 0))
        record = (call_results or {}).get(location)
        if record is not None and record.get("state") == "known":
            return {
                "type": record["type"],
                "evidence": [{
                    "expression": record["expression"],
                    "type": record["type"],
                    "provenance": record["provenance"],
                    "source_location": record["source_location"],
                }],
            }
    return {"type": "unknown", "evidence": []}


def _python_binding_names(target: ast.AST) -> List[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in _python_binding_names(element)]
    return []


def _python_named_expression_names(expression: Optional[ast.AST]) -> set:
    """Find walrus targets that can escape an expression's nested comprehension."""
    names = set()

    class NamedExpressionCollector(ast.NodeVisitor):
        def visit_NamedExpr(self, item: ast.NamedExpr) -> None:
            if isinstance(item.target, ast.Name):
                names.add(item.target.id)
            self.visit(item.value)

        def visit_FunctionDef(self, nested: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, nested: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, nested: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, nested: ast.Lambda) -> None:
            return

    if expression is not None:
        NamedExpressionCollector().visit(expression)
    return names


def _python_local_bindings(
    statements: List[ast.stmt], source_text: Optional[str],
    call_results: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None,
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
        elif isinstance(statement, ast.Expr):
            value = statement.value
        else:
            continue

        for name in _python_named_expression_names(value):
            if name not in excluded:
                bindings[name] = {"type": "unknown", "evidence": []}
        if isinstance(statement, ast.Expr):
            continue

        assigned = _python_inferred_type(value, bindings, call_results) if value is not None else {"type": "unknown", "evidence": []}
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


def _extract_python_return_metadata(
    node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
    function_name: str,
    qualified_name: str,
    source_file: str,
    source_text: Optional[str],
    call_results: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract declared evidence and bounded return-expression evidence."""
    line = getattr(node, "lineno", None)
    column = getattr(node, "col_offset", None)
    is_global = function_name == "(global)" or getattr(node, "name", None) == "(global)"
    declared_expression = (
        None if is_global or node.returns is None
        else _source_text_for(node.returns, source_text)
    )
    declared = None if declared_expression is None else {
        "expression": declared_expression,
        "provenance": "annotation",
        "source_location": {"line": line, "column": column},
    }
    metadata: Dict[str, Any] = {
        "function_name": "Global Scope" if is_global else function_name,
        "source_file": source_file,
        "qualified_name": "Global Scope" if is_global else qualified_name,
        "definition_location": {"line": line, "column": column},
        "declared": declared,
        "analysis_status": "not_applicable" if is_global else "unknown",
        "inferred": [],
        "inferred_types": [],
        "observed": [],
        "observed_types": [],
    }
    if is_global:
        return metadata

    has_yield = _function_has_yield(node)
    if has_yield:
        async_generator = isinstance(node, ast.AsyncFunctionDef)
        generator_kind = "async_generator" if async_generator else "generator"
        annotation_roles = _python_annotation_role_declarations(node, source_text)
        immediate_type = generator_kind
        immediate_evidence = [{
            "expression": "async generator object" if async_generator else "generator object",
            "type": immediate_type,
            "provenance": "function_syntax",
            "role": "immediate_result",
            "source_location": {"line": line, "column": column},
        }]
        yielded_evidence = _python_yield_evidence(node, source_text, call_results)
        yielded_role = _python_role_record(yielded_evidence, annotation_roles.get("yielded"))

        if async_generator:
            completion_role = {
                "declared": annotation_roles.get("completion"),
                "analysis_status": "not_applicable",
                "inferred": [], "inferred_types": [], "observed": [], "observed_types": [],
            }
        else:
            outcomes, uncertain = _python_return_outcomes(node, source_text, call_results)
            uncertain = uncertain or bool(getattr(node, "decorator_list", []))
            completion_evidence = [
                evidence for kind, evidence in outcomes
                if kind == "return" and evidence is not None
            ]
            no_normal_return = (
                not completion_evidence
                and not any(kind == "normal" for kind, _ in outcomes)
                and bool(outcomes)
                and all(kind == "raise" for kind, _ in outcomes)
                and not uncertain
            )
            for kind, _ in outcomes:
                if kind == "normal":
                    completion_evidence.append({
                        "expression": "implicit fall-through", "type": "NoneType",
                        "provenance": "normal_fallthrough", "role": "generator_completion",
                        "source_location": {"line": getattr(node, "end_lineno", line), "column": None},
                    })
            for evidence in completion_evidence:
                evidence["role"] = "generator_completion"
            completion_role = _python_role_record(
                completion_evidence,
                annotation_roles.get("completion"),
                unknown_coverage=uncertain or any(kind == "unknown" for kind, _ in outcomes),
                no_normal_return=no_normal_return,
            )
        metadata.update({
            "function_kind": generator_kind,
            "roles": {
                "immediate": {
                    "declared": metadata["declared"],
                    "analysis_status": "complete",
                    "inferred": immediate_evidence,
                    "inferred_types": [immediate_type],
                    "observed": [], "observed_types": [],
                },
                "yielded": yielded_role,
                "completion": completion_role,
            },
        })
        return metadata

    if isinstance(node, ast.AsyncFunctionDef):
        metadata["function_kind"] = "async_function"
        metadata["declared"] = None
        metadata["roles"] = {
            "immediate": _python_known_wrapper_role("coroutine", "async_function_syntax", line, column),
            "awaited": _python_result_role(node, source_text, declared, "awaited", call_results),
        }
        return metadata

    outcomes, uncertain_coverage = _python_return_outcomes(node, source_text, call_results)
    uncertain_coverage = uncertain_coverage or bool(getattr(node, "decorator_list", []))
    normal = [outcome for outcome in outcomes if outcome[0] == "normal"]
    returns = [outcome[1] for outcome in outcomes if outcome[0] == "return"]
    has_unknown = uncertain_coverage or any(item.get("type") == "unknown" for item in returns)
    if not normal and not returns and outcomes and all(kind == "raise" for kind, _ in outcomes) and not has_unknown:
        metadata["analysis_status"] = "no_normal_return"
        metadata["inferred_types"] = []
        metadata["observed"] = []
        metadata["observed_types"] = []
        return metadata

    for outcome in normal:
        line_number = getattr(node, "end_lineno", line)
        returns.append({
            "expression": "implicit fall-through", "type": "NoneType",
            "provenance": "normal_fallthrough", "role": "call_result",
            "source_location": {"line": line_number, "column": None},
        })

    observed = [item for item in returns if item.get("type") != "unknown"]
    observed_types = _unique_return_types(observed)
    is_complete = not has_unknown and all(item.get("type") != "unknown" for item in returns)
    metadata["analysis_status"] = "complete" if is_complete else "unknown"
    # Keep return-site records (including unknown expressions) for inspection;
    # inferred_types is the complete union and is empty when coverage is unknown.
    metadata["inferred"] = returns
    metadata["inferred_types"] = _unique_return_types(returns) if is_complete else []
    metadata["observed"] = [] if is_complete else observed
    metadata["observed_types"] = [] if is_complete else observed_types
    return metadata


def _python_known_wrapper_role(wrapper_type: str, provenance: str, line: Optional[int], column: Optional[int]) -> Dict[str, Any]:
    return {
        "declared": None,
        "analysis_status": "complete",
        "inferred": [{
            "expression": "async function syntax", "type": wrapper_type,
            "provenance": provenance, "role": "immediate",
            "source_location": {"line": line, "column": column},
        }],
        "inferred_types": [wrapper_type], "observed": [], "observed_types": [],
    }


def _python_result_role(node: ast.AST, source_text: Optional[str],
                        declared: Optional[Dict[str, Any]], role: str,
                        call_results: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None) -> Dict[str, Any]:
    outcomes, uncertain = _python_return_outcomes(node, source_text, call_results)
    uncertain = uncertain or bool(getattr(node, "decorator_list", []))
    evidence = [value for kind, value in outcomes if kind == "return" and value is not None]
    no_normal = (
        not evidence and not any(kind == "normal" for kind, _ in outcomes) and bool(outcomes)
        and all(kind == "raise" for kind, _ in outcomes) and not uncertain
    )
    for kind, _ in outcomes:
        if kind == "normal":
            evidence.append({
                "expression": "implicit fall-through", "type": "NoneType",
                "provenance": "normal_fallthrough", "role": role,
                "source_location": {"line": getattr(node, "end_lineno", getattr(node, "lineno", None)), "column": None},
            })
    for item in evidence:
        item["role"] = role
    return _python_role_record(
        evidence, declared,
        unknown_coverage=uncertain or any(kind == "unknown" for kind, _ in outcomes),
        no_normal_return=no_normal,
    )


def _unique_return_types(evidence: List[Dict[str, Any]]) -> List[str]:
    result: List[str] = []
    for item in evidence:
        value = item.get("type")
        if isinstance(value, str) and value != "unknown" and value not in result:
            result.append(value)
    return result


def _python_return_evidence_by_site(metadata: Dict[str, Any]):
    records = list(metadata.get("inferred", [])) + list(metadata.get("observed", []))
    for role in (metadata.get("roles") or {}).values():
        records.extend(role.get("inferred", []))
        records.extend(role.get("observed", []))
    by_site = {}
    for record in records:
        location = record.get("source_location") or {}
        if isinstance(location.get("line"), int) and isinstance(location.get("column"), int):
            by_site[(location["line"], location["column"])] = dict(record)
    return by_site


def _python_annotation_role_declarations(node: ast.AST, source_text: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Return contained-type declarations only for recognized iterator wrappers."""
    annotation = getattr(node, "returns", None)
    synthetic_annotation = False
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        try:
            annotation = ast.parse(annotation.value, mode="eval").body
            synthetic_annotation = True
        except SyntaxError:
            return {}
    if not isinstance(annotation, ast.Subscript):
        return {}
    wrapper = annotation.value
    wrapper_name = wrapper.id if isinstance(wrapper, ast.Name) else (
        wrapper.attr if isinstance(wrapper, ast.Attribute) else ""
    )
    arguments = list(annotation.slice.elts) if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
    indexes: Dict[str, int] = {}
    if wrapper_name in {"Iterator", "Iterable", "AsyncIterator", "AsyncIterable"}:
        indexes["yielded"] = 0
    elif wrapper_name == "Generator" and len(arguments) == 3:
        indexes.update(yielded=0, completion=2)
    elif wrapper_name == "AsyncGenerator" and len(arguments) == 2:
        indexes["yielded"] = 0
    result = {}
    for role, index in indexes.items():
        argument = arguments[index]
        expression = ast.unparse(argument) if synthetic_annotation and hasattr(ast, "unparse") else _source_text_for(argument, source_text)
        if expression is not None:
            result[role] = {
                "expression": expression,
                "provenance": "annotation",
                "source_location": {
                    "line": getattr(argument, "lineno", getattr(annotation, "lineno", None)),
                    "column": getattr(argument, "col_offset", getattr(annotation, "col_offset", None)),
                },
            }
    return result


def _python_yield_evidence(node: ast.AST, source_text: Optional[str],
                           call_results: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    statements = list(getattr(node, "body", []))
    evidence: List[Dict[str, Any]] = []

    class YieldCollector(ast.NodeVisitor):
        def __init__(self, history: List[ast.stmt], ambiguous: bool, blocked_names: Optional[set] = None):
            self.history = history
            self.ambiguous = ambiguous
            self.blocked_names = blocked_names or set()

        def visit_FunctionDef(self, nested: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, nested: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, nested: ast.ClassDef) -> None:
            return

        def visit_Lambda(self, nested: ast.Lambda) -> None:
            return

        def _record(self, yield_node: ast.AST, expression_node: Optional[ast.AST], delegated: bool = False) -> None:
            expression = "None" if expression_node is None else (
                _source_text_for(expression_node, source_text) or "unknown expression"
            )
            if delegated:
                inferred = {"type": "unknown", "evidence": []}
            elif expression_node is None:
                inferred = {"type": "NoneType", "evidence": []}
            elif _direct_literal_type(expression_node) is not None:
                inferred = _python_inferred_type(expression_node, {}, call_results)
            else:
                expression_names = _python_expression_names(expression_node)
                bindings = {} if expression_names & self.blocked_names else _python_local_bindings(self.history, source_text, call_results)
                inferred = _python_inferred_type(expression_node, bindings, call_results)
            provenance = "delegated_yield" if delegated else (
                "bare_yield" if expression_node is None else (
                    "direct_literal" if _direct_literal_type(expression_node) is not None else (
                        "local_assignment" if isinstance(expression_node, ast.Name) and inferred["evidence"]
                        else "expression_inference"
                    )
                )
            )
            evidence.append({
                "expression": expression,
                "type": inferred["type"],
                "provenance": provenance,
                "role": "yielded_item",
                "source_location": {
                    "line": getattr(yield_node, "lineno", None),
                    "column": getattr(yield_node, "col_offset", None),
                },
                "expression_location": {
                    "line": getattr(expression_node, "lineno", getattr(yield_node, "lineno", None)),
                    "column": getattr(expression_node, "col_offset", getattr(yield_node, "col_offset", None)),
                },
                "evidence": inferred["evidence"],
            })

        def visit_Yield(self, yield_node: ast.Yield) -> None:
            self._record(yield_node, yield_node.value)
            self.generic_visit(yield_node.value) if yield_node.value is not None else None

        def visit_YieldFrom(self, yield_node: ast.YieldFrom) -> None:
            self._record(yield_node, yield_node.value, delegated=True)
            self.generic_visit(yield_node.value)

    for index, statement in enumerate(statements):
        direct_history = statements[:index]
        branch_types = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)
        relevant_mutations = [item for item in direct_history if isinstance(item, branch_types)]
        if isinstance(statement, branch_types):
            relevant_mutations.append(statement)
        blocked_names = set().union(*(_python_written_names([item]) for item in relevant_mutations)) if relevant_mutations else set()
        YieldCollector(direct_history, False, blocked_names).visit(statement)
    evidence.sort(key=lambda item: (item["source_location"]["line"] or 0, item["source_location"]["column"] or 0))
    return evidence


def _python_expression_names(expression: ast.AST) -> set:
    return {item.id for item in ast.walk(expression) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}


def _python_written_names(statements: List[ast.stmt]) -> set:
    names = set()

    def collect_target(target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                collect_target(item)

    class WriteCollector(ast.NodeVisitor):
        def visit_FunctionDef(self, nested: ast.FunctionDef) -> None: return
        def visit_AsyncFunctionDef(self, nested: ast.AsyncFunctionDef) -> None: return
        def visit_ClassDef(self, nested: ast.ClassDef) -> None: return
        def visit_Lambda(self, nested: ast.Lambda) -> None: return
        def visit_Assign(self, item: ast.Assign) -> None:
            for target in item.targets: collect_target(target)
            self.generic_visit(item.value)
        def visit_AnnAssign(self, item: ast.AnnAssign) -> None:
            collect_target(item.target)
            if item.value is not None: self.generic_visit(item.value)
        def visit_AugAssign(self, item: ast.AugAssign) -> None:
            collect_target(item.target)
            self.generic_visit(item.value)
        def visit_NamedExpr(self, item: ast.NamedExpr) -> None:
            collect_target(item.target)
            self.generic_visit(item.value)

    collector = WriteCollector()
    for statement in statements:
        collector.visit(statement)
    return names


def _python_role_record(evidence: List[Dict[str, Any]], declared: Optional[Dict[str, Any]] = None,
                        unknown_coverage: bool = False, no_normal_return: bool = False) -> Dict[str, Any]:
    known = [item for item in evidence if item.get("type") != "unknown"]
    complete = not unknown_coverage and len(known) == len(evidence)
    status = "no_normal_return" if no_normal_return else ("complete" if complete else "unknown")
    return {
        "declared": declared,
        "analysis_status": status,
        "inferred": evidence,
        "inferred_types": _unique_return_types(evidence) if status == "complete" else [],
        "observed": [] if status == "complete" else known,
        "observed_types": [] if status == "complete" else _unique_return_types(known),
    }


def _python_return_outcomes(node: ast.AST, source_text: Optional[str],
                            call_results: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None):
    """Summarize supported sequential/if paths without merging branch environments."""
    uncertain = False

    def known_evidence(return_node: ast.Return, history: List[ast.stmt], ambiguous: bool, nested: bool,
                       blocked_names: Optional[set] = None):
        expression_node = return_node.value
        if expression_node is None:
            inferred = {"type": "NoneType", "evidence": []}
            expression = "None"
        else:
            expression = _source_text_for(expression_node, source_text) or "unknown expression"
            if _direct_literal_type(expression_node) is not None:
                inferred = _python_inferred_type(expression_node, {}, call_results)
            elif ambiguous or nested:
                names = _python_expression_names(expression_node)
                bindings = {} if names & (blocked_names or set()) else _python_local_bindings(history, source_text, call_results)
                inferred = _python_inferred_type(expression_node, bindings, call_results)
            else:
                inferred = _python_inferred_type(expression_node, _python_local_bindings(history, source_text, call_results), call_results)
        provenance = "bare_return" if expression_node is None else (
            "direct_literal" if _direct_literal_type(expression_node) is not None else (
                "local_assignment" if isinstance(expression_node, ast.Name) and inferred["evidence"] else "expression_inference"
            )
        )
        return {
            "expression": expression, "type": inferred["type"], "provenance": provenance,
            "role": "call_result", "source_location": {"line": return_node.lineno, "column": return_node.col_offset},
            "expression_location": {
                "line": getattr(expression_node, "lineno", return_node.lineno),
                "column": getattr(expression_node, "col_offset", return_node.col_offset),
            },
            "evidence": inferred["evidence"],
        }

    def collect_known_nested(statement: ast.stmt) -> List[Dict[str, Any]]:
        found = []
        class Collector(ast.NodeVisitor):
            def visit_Return(self, item: ast.Return):
                evidence = known_evidence(item, [], True, True, set())
                if evidence["type"] != "unknown":
                    found.append(evidence)
            def visit_FunctionDef(self, item: ast.FunctionDef):
                return
            def visit_AsyncFunctionDef(self, item: ast.AsyncFunctionDef):
                return
            def visit_Lambda(self, item: ast.Lambda):
                return
            def visit_ClassDef(self, item: ast.ClassDef):
                return
        Collector().visit(statement)
        return found

    def sequence(statements: List[ast.stmt], history: List[ast.stmt], ambiguous: bool = False,
                 nested: bool = False, blocked_names: Optional[set] = None):
        nonlocal uncertain
        active = [("normal", None, history, ambiguous, blocked_names or set())]
        done = []
        for statement in statements:
            next_active = []
            for _, _, prior, path_ambiguous, path_blocked_names in active:
                if isinstance(statement, ast.Return):
                    done.append(("return", known_evidence(statement, prior, path_ambiguous, nested, path_blocked_names)))
                elif isinstance(statement, ast.Raise):
                    done.append(("raise", None))
                elif isinstance(statement, ast.If):
                    branch_blocked_names = path_blocked_names | _python_written_names(statement.body + statement.orelse)
                    yes = sequence(statement.body, list(prior), path_ambiguous, True, branch_blocked_names)
                    if statement.orelse:
                        no = sequence(statement.orelse, list(prior), path_ambiguous, True, branch_blocked_names)
                    else:
                        no = ([ ("normal", None) ], False)
                    branch_outcomes = yes[0] + no[0]
                    uncertain = uncertain or yes[1] or no[1]
                    has_normal_branch = False
                    for kind, evidence in branch_outcomes:
                        if kind == "normal":
                            has_normal_branch = True
                        else:
                            done.append((kind, evidence))
                    if has_normal_branch:
                        next_active.append(("normal", None, prior + [statement], True, branch_blocked_names))
                elif isinstance(statement, (ast.Pass, ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign,
                                            ast.Global, ast.Nonlocal, ast.FunctionDef, ast.AsyncFunctionDef,
                                            ast.ClassDef)):
                    next_active.append(("normal", None, prior + [statement], path_ambiguous, path_blocked_names))
                else:
                    uncertain = True
                    done.extend(("return", item) for item in collect_known_nested(statement))
                    done.append(("unknown", None))
            active = next_active
            if not active:
                break
        done.extend(("normal", None) for _ in active)
        return done, uncertain

    outcomes, _ = sequence(list(getattr(node, "body", [])), [])
    return outcomes, uncertain



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


_PYTHON_BUILTIN_RESULT_TYPES = {
    "range": "range", "len": "int", "str": "str", "int": "int", "float": "float",
    "bool": "bool", "list": "list", "tuple": "tuple", "dict": "dict", "set": "set",
}
_PYTHON_BUILTIN_CATALOG_PROVENANCE = "Python 3 built-in callable normal-result contracts (docs.python.org/3/library/functions.html)."


def _python_scope_bindings(scope: ast.AST, is_module: bool = False):
    """Collect names bound in one lexical scope without entering nested scopes."""
    bound = set()
    imported = set()
    global_names = set()
    nonlocal_names = set()

    class Collector(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node is scope:
                bound.add(node.name) if is_module else None
                for arg in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
                    bound.add(arg.arg)
                if node.args.vararg:
                    bound.add(node.args.vararg.arg)
                if node.args.kwarg:
                    bound.add(node.args.kwarg.arg)
                for statement in node.body:
                    self.visit(statement)
            elif is_module:
                bound.add(node.name)
            else:
                bound.add(node.name)

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

        def visit_ClassDef(self, node):
            bound.add(node.name)
            if not is_module and node is scope:
                for statement in node.body:
                    self.visit(statement)

        def visit_Lambda(self, node):
            if node is scope:
                self.generic_visit(node.body)

        def visit_Import(self, node):
            for alias in node.names:
                imported.add(alias.asname or alias.name.split(".")[0])

        def visit_ImportFrom(self, node):
            for alias in node.names:
                if alias.name != "*":
                    imported.add(alias.asname or alias.name)

        def visit_Global(self, node):
            global_names.update(node.names)

        def visit_Nonlocal(self, node):
            nonlocal_names.update(node.names)

        def visit_comprehension(self, node, value_nodes):
            for generator in node.generators:
                self.visit(generator.iter)
                for condition in generator.ifs:
                    self.visit(condition)
            for value_node in value_nodes:
                self.visit(value_node)

        def visit_ListComp(self, node):
            self.visit_comprehension(node, [node.elt])

        def visit_SetComp(self, node):
            self.visit_comprehension(node, [node.elt])

        def visit_GeneratorExp(self, node):
            self.visit_comprehension(node, [node.elt])

        def visit_DictComp(self, node):
            self.visit_comprehension(node, [node.key, node.value])

        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store) or isinstance(node.ctx, ast.Del):
                bound.add(node.id)

        def visit_ExceptHandler(self, node):
            if node.name:
                bound.add(node.name)
            self.generic_visit(node)

        def visit_MatchAs(self, node):
            if node.name:
                bound.add(node.name)
            if node.pattern:
                self.visit(node.pattern)

        def visit_MatchStar(self, node):
            if node.name:
                bound.add(node.name)

        def visit_MatchMapping(self, node):
            if node.rest:
                bound.add(node.rest)
            self.generic_visit(node)

    Collector().visit(scope)
    if not is_module:
        bound.difference_update(global_names | nonlocal_names)
    return bound - imported, imported, global_names, nonlocal_names


def _python_direct_builtin_imports(statements, before_line):
    imported_names = {}
    builtin_modules = set()
    other_import_names = set()
    has_wildcard_import = False
    for statement in statements:
        if before_line is not None and getattr(statement, "lineno", 0) >= before_line:
            continue
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                bound_name = alias.asname or alias.name.split(".")[0]
                if alias.name == "builtins":
                    builtin_modules.add(bound_name)
                else:
                    other_import_names.add(bound_name)
        elif isinstance(statement, ast.ImportFrom):
            for alias in statement.names:
                if alias.name == "*":
                    has_wildcard_import = True
                    continue
                bound_name = alias.asname or alias.name
                if statement.module == "builtins":
                    imported_names[bound_name] = alias.name
                else:
                    other_import_names.add(bound_name)
    return imported_names, builtin_modules, other_import_names, has_wildcard_import


def _python_function_global_rebindings(function_node):
    """Return globals rebound by this function, excluding nested lexical scopes."""
    rebound = set()
    _, _, global_names, _ = _python_scope_bindings(function_node)
    if not global_names:
        return rebound

    class GlobalWrites(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node is function_node:
                for statement in node.body:
                    self.visit(statement)
            elif node.name in global_names:
                rebound.add(node.name)

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

        def visit_ClassDef(self, node):
            if node.name in global_names:
                rebound.add(node.name)

        def visit_Lambda(self, node):
            return

        def visit_comprehension(self, node, value_nodes):
            for generator in node.generators:
                self.visit(generator.iter)
                for condition in generator.ifs:
                    self.visit(condition)
            for value_node in value_nodes:
                self.visit(value_node)

        def visit_ListComp(self, node):
            self.visit_comprehension(node, [node.elt])

        def visit_SetComp(self, node):
            self.visit_comprehension(node, [node.elt])

        def visit_GeneratorExp(self, node):
            self.visit_comprehension(node, [node.elt])

        def visit_DictComp(self, node):
            self.visit_comprehension(node, [node.key, node.value])

        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in global_names:
                rebound.add(node.id)

        def visit_Import(self, node):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                if name in global_names:
                    rebound.add(name)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                name = alias.asname or alias.name
                if name in global_names:
                    rebound.add(name)

    GlobalWrites().visit(function_node)
    return rebound


def _python_module_global_rebindings(module_node):
    """Return module names any function can rebind through a global declaration."""
    rebound = set()
    for _, function_node in _collect_functions(module_node):
        rebound |= _python_function_global_rebindings(function_node)
    return rebound


def _python_call_result_records(function_node, module_node, source_text, caller_function, caller_file):
    local_non_imports, local_import_names, global_names, nonlocal_names = _python_scope_bindings(function_node)
    module_non_imports, module_import_names, _, _ = _python_scope_bindings(module_node, is_module=True)
    module_non_imports |= _python_module_global_rebindings(module_node)
    module_imported_names, module_aliases, module_other_imports, module_has_wildcard_import = _python_direct_builtin_imports(
        getattr(module_node, "body", []), None
    )

    def has_wildcard_import(root):
        return any(
            isinstance(item, ast.ImportFrom) and any(alias.name == "*" for alias in item.names)
            for item in ast.walk(root)
        )

    module_has_wildcard_import = module_has_wildcard_import or has_wildcard_import(module_node)

    # Module imports can only establish the binding when no separate module write shadows them.
    module_imported_names = {
        local: canonical for local, canonical in module_imported_names.items()
        if local not in module_non_imports
    }
    module_aliases = {name for name in module_aliases if name not in module_non_imports}
    module_other_imports |= module_import_names - set(module_imported_names) - module_aliases
    module_imported_names = {
        local: canonical for local, canonical in module_imported_names.items()
        if local not in module_other_imports
    }
    module_aliases -= module_other_imports

    global_writes = _python_function_global_rebindings(function_node)
    local_writes = local_non_imports | global_writes
    dynamic_namespace = False
    for root in (module_node, function_node):
        for item in ast.walk(root):
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id in {"exec", "eval", "globals", "locals"}:
                dynamic_namespace = True

    def attributes_written(module_alias, attribute):
        if not module_alias:
            return False
        for root in (module_node, function_node):
            for item in ast.walk(root):
                if isinstance(item, ast.Attribute) and item.attr == attribute and isinstance(item.ctx, (ast.Store, ast.Del)):
                    if isinstance(item.value, ast.Name) and item.value.id == module_alias:
                        return True
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id in {"setattr", "delattr"}:
                    if item.args and isinstance(item.args[0], ast.Name) and item.args[0].id == module_alias:
                        if len(item.args) < 2 or not isinstance(item.args[1], ast.Constant):
                            return True
                        if item.args[1].value == attribute:
                            return True
                if isinstance(item, ast.Subscript) and isinstance(item.ctx, (ast.Store, ast.Del)):
                    module_dict = isinstance(item.value, ast.Attribute) and item.value.attr == "__dict__" and isinstance(item.value.value, ast.Name) and item.value.value.id == module_alias
                    vars_dict = isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "vars" and item.value.args and isinstance(item.value.args[0], ast.Name) and item.value.args[0].id == module_alias
                    if module_dict or vars_dict:
                        if not isinstance(item.slice, ast.Constant) or item.slice.value == attribute:
                            return True
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr == "update":
                    owner = item.func.value
                    module_dict = isinstance(owner, ast.Attribute) and owner.attr == "__dict__" and isinstance(owner.value, ast.Name) and owner.value.id == module_alias
                    vars_dict = isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) and owner.func.id == "vars" and owner.args and isinstance(owner.args[0], ast.Name) and owner.args[0].id == module_alias
                    if module_dict or vars_dict:
                        return True
        return False

    class Calls(ast.NodeVisitor):
        def __init__(self):
            self.nodes = []
        def visit_FunctionDef(self, node):
            if node is function_node:
                for statement in node.body:
                    self.visit(statement)
        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)
        def visit_ClassDef(self, node):
            return
        def visit_Lambda(self, node):
            return
        def visit_Call(self, node):
            self.nodes.append(node)
            self.generic_visit(node)

    collector = Calls()
    collector.visit(function_node)
    records = {}
    for call in collector.nodes:
        func = call.func
        original = _source_text_for(call, source_text) or ast.unparse(call)
        local_imported_names, local_module_aliases, local_other_imports, local_has_wildcard_import = _python_direct_builtin_imports(
            getattr(function_node, "body", []), getattr(call, "lineno", 0)
        )
        local_has_wildcard_import = local_has_wildcard_import or has_wildcard_import(function_node)
        local_imported_names = {
            local: canonical for local, canonical in local_imported_names.items()
            if local not in local_writes and local not in local_other_imports
        }
        local_module_aliases = {
            name for name in local_module_aliases
            if name not in local_writes and name not in local_other_imports
        }
        canonical = None
        uncertain = dynamic_namespace or local_has_wildcard_import or module_has_wildcard_import
        unsupported_builtin = False
        if isinstance(func, ast.Name):
            name = func.id
            imported_target = local_imported_names.get(name)
            if imported_target is None and name not in local_import_names and name not in local_writes and name not in nonlocal_names:
                if name in module_imported_names:
                    imported_target = module_imported_names[name]
                elif name in module_other_imports:
                    uncertain = True
                elif name not in module_non_imports and name not in module_other_imports and not module_has_wildcard_import and not local_has_wildcard_import:
                    imported_target = name if name in _PYTHON_BUILTIN_RESULT_TYPES else None
                    unsupported_builtin = name in _python_builtins.__dict__
                else:
                    uncertain = True
            elif imported_target is None:
                uncertain = True
            if imported_target is not None:
                canonical = imported_target
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            alias = func.value.id
            if alias in local_module_aliases and alias not in local_non_imports:
                canonical = func.attr
            elif alias in module_aliases and alias not in local_non_imports:
                canonical = func.attr
            elif alias in local_writes or alias in local_import_names or alias in local_other_imports or alias in module_non_imports or alias in module_other_imports:
                uncertain = True

        known = canonical in _PYTHON_BUILTIN_RESULT_TYPES and not uncertain
        if canonical is not None and not known:
            unsupported_builtin = True
        if known:
            recognized_module_aliases = set(module_aliases) | set(local_module_aliases)
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                recognized_module_aliases.add(func.value.id)
            if any(attributes_written(alias, canonical) for alias in recognized_module_aliases):
                known = False
                uncertain = True
        line = getattr(call, "lineno", 0)
        column = getattr(call, "col_offset", 0)
        record = {
            "expression": original,
            "source_location": {"line": line, "column": column},
            "transition_id": None,
            "call_site_id": f"{caller_file}::{caller_function}@{line}:{column}",
            "caller_function": caller_function,
            "caller_file": caller_file,
            "state": "known" if known else "unknown",
            "type": _PYTHON_BUILTIN_RESULT_TYPES[canonical] if known else "unknown",
            "canonical_builtin": "builtins." + canonical if known else None,
            "provenance": "python_builtin_static_contract" if known else None,
            "unknown_reason": None if known else (
                "shadowed_or_uncertain_binding" if uncertain else
                "unsupported_builtin" if unsupported_builtin else "no_available_contract"
            ),
        }
        records[(line, column)] = record
    return records


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
        call_results: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None,
        return_evidence: Optional[Dict[Tuple[int, int], Dict[str, Any]]] = None,
    ) -> None:
        self.builder = builder
        self.func_name = func_name
        self.filepath = filepath
        self.call_results = call_results or {}
        self.return_evidence = return_evidence or {}
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
            call_result = self.call_results.get((getattr(call, "lineno", 0), getattr(call, "col_offset", 0)))
            if call_result is not None:
                call_result = dict(call_result)
                call_result["transition_id"] = transition_id
                transition = next((item for item in self.builder.net.transitions if item.id == transition_id), None)
                if transition is not None:
                    if transition.metadata is None:
                        transition.metadata = {}
                    transition.metadata.setdefault("call_results", []).append(call_result)
            self.call_sites.append(cs)

    def _walk_return(self, stmt: ast.Return, ctx: StatementContext) -> Optional[Place]:
        trans = self.builder.wire_return(ctx.current_place, _format_statement_label(stmt), stmt.lineno)
        evidence = self.return_evidence.get((stmt.lineno, stmt.col_offset))
        if evidence is not None:
            if trans.metadata is None:
                trans.metadata = {}
            trans.metadata["function_return_evidence"] = evidence
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
        call_results = _python_call_result_records(
            ast_node,
            self.parsed_tree if isinstance(self.parsed_tree, ast.Module) else ast.Module(body=[]),
            source_text,
            qualified_name,
            active_filepath,
        )
        return_metadata = _extract_python_return_metadata(
            ast_node,
            function_name=active_func_name,
            qualified_name=qualified_name,
            source_file=active_filepath,
            source_text=source_text,
            call_results=call_results,
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
            call_results=call_results,
            return_evidence=_python_return_evidence_by_site(return_metadata),
        )
        walker.walk_block(ast_node.body, current_place=start_place, target_exit=end_place)
        net.return_metadata = return_metadata
        return WalkResult(net=net, call_sites=walker.call_sites, return_metadata=return_metadata)
