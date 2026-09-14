import os
from typing import Any, Dict, List, Optional, Set, Tuple

from code2petri.model import CallResolution, PetriNet, Place, Transition
from code2petri.symbol_table import SUPPORTED_WALKERS, Symbol, SymbolTable
from code2petri.walker_protocol import CallSite, WalkerProtocol


def _find_boundary_places(
    net: PetriNet,
) -> Tuple[Optional[Place], Optional[Place]]:
    """Identifies the single source and sink places of a PetriNet."""
    start_places = [p for p in net.places if p.initial_tokens > 0 or p.label == "start"]
    source_place = start_places[0] if start_places else (net.places[0] if net.places else None)

    end_places = [p for p in net.places if p.label == "end"]
    sink_place = end_places[0] if end_places else (net.places[-1] if net.places else None)

    return source_place, sink_place


def _get_callee_net(
    symbol: Symbol,
    walker_cache: Optional[Dict[str, WalkerProtocol]] = None,
) -> Tuple[Optional[PetriNet], List[CallSite]]:
    """Walks the callee symbol's AST node to produce its PetriNet and CallSite records."""
    if hasattr(symbol, "net") and symbol.net is not None:
        return symbol.net.clone(), list(getattr(symbol, "call_sites", []))

    ext = os.path.splitext(symbol.filepath)[1].lower() if symbol.filepath else ""
    walker_cls = SUPPORTED_WALKERS.get(ext)
    if walker_cls is None:
        if symbol.language == "javascript":
            from code2petri.javascript_walker import JavascriptWalker
            walker_cls = JavascriptWalker
        else:
            from code2petri.python_walker import PythonWalker
            walker_cls = PythonWalker

    cache = walker_cache if walker_cache is not None else {}
    cache_key = f"{walker_cls.__name__}:{symbol.filepath}"
    if cache_key in cache:
        walker = cache[cache_key]
    else:
        walker = walker_cls()
        if symbol.filepath and os.path.exists(symbol.filepath):
            try:
                walker.parse_file(symbol.filepath)
            except Exception:
                pass
        cache[cache_key] = walker

    ast_node = symbol.ast_node
    if ast_node is None and symbol.filepath and os.path.exists(symbol.filepath):
        try:
            tree = walker.parse_file(symbol.filepath)
            ast_node = walker.find_function(tree, symbol.name) or walker.find_function(tree, symbol.bare_name)
        except Exception:
            return None, []

    if ast_node is None:
        return None, []

    try:
        walk_res = walker.walk_function(ast_node, symbol.name, filepath=symbol.filepath)
        return walk_res.net, walk_res.call_sites
    except Exception:
        return None, []


def _splice_callee_net(
    caller_net: PetriNet,
    call_transition: Transition,
    callee_net: PetriNet,
    callee_id: str,
    used_prefixes: Set[str],
) -> None:
    """Splices a callee Petri net into caller_net replacing call_transition."""
    preset_places = [
        a.source for a in caller_net.arcs
        if a.target.id == call_transition.id and isinstance(a.source, Place)
    ]
    postset_places = [
        a.target for a in caller_net.arcs
        if a.source.id == call_transition.id and isinstance(a.target, Place)
    ]

    if not preset_places or not postset_places:
        return

    callee_source_place, callee_sink_place = _find_boundary_places(callee_net)
    if callee_source_place is None or callee_sink_place is None:
        return

    base_prefix = f"inline_{callee_id}__"
    if base_prefix not in used_prefixes:
        prefix = base_prefix
    else:
        prefix = f"inline_{callee_id}_{call_transition.id}__"
        idx = 2
        while prefix in used_prefixes:
            prefix = f"inline_{callee_id}_{call_transition.id}_{idx}__"
            idx += 1
    used_prefixes.add(prefix)

    cloned_transitions: Dict[str, Transition] = {}
    for ct in callee_net.transitions:
        new_id = f"{prefix}{ct.id}"
        new_meta = dict(ct.metadata) if ct.metadata is not None else None
        new_res = (
            CallResolution(
                resolved=ct.resolution.resolved,
                resolved_to=ct.resolution.resolved_to,
                target_file=ct.resolution.target_file,
            )
            if ct.resolution is not None
            else None
        )
        cloned_t = caller_net.add_transition(
            id=new_id,
            label=ct.label,
            line_number=ct.line_number,
            metadata=new_meta,
            resolution=new_res,
        )
        cloned_transitions[ct.id] = cloned_t

    cloned_places: Dict[str, Place] = {}
    for cp in callee_net.places:
        if cp.id in (callee_source_place.id, callee_sink_place.id):
            continue
        new_id = f"{prefix}{cp.id}"
        cloned_p = caller_net.add_place(
            id=new_id,
            label=cp.label,
            line_number=cp.line_number,
            initial_tokens=0,
        )
        cloned_places[cp.id] = cloned_p

    for a in callee_net.arcs:
        if a.source.id == callee_source_place.id:
            target_t = cloned_transitions.get(a.target.id)
            if target_t is not None:
                for p_in in preset_places:
                    caller_net.add_arc(source=p_in, target=target_t, weight=a.weight)
        elif a.target.id == callee_source_place.id:
            source_t = cloned_transitions.get(a.source.id)
            if source_t is not None:
                for p_in in preset_places:
                    caller_net.add_arc(source=source_t, target=p_in, weight=a.weight)
        elif a.target.id == callee_sink_place.id:
            source_t = cloned_transitions.get(a.source.id)
            if source_t is not None:
                for p_out in postset_places:
                    caller_net.add_arc(source=source_t, target=p_out, weight=a.weight)
        elif a.source.id == callee_sink_place.id:
            target_t = cloned_transitions.get(a.target.id)
            if target_t is not None:
                for p_out in postset_places:
                    caller_net.add_arc(source=p_out, target=target_t, weight=a.weight)
        elif isinstance(a.source, Place) and isinstance(a.target, Transition):
            source_p = cloned_places.get(a.source.id)
            target_t = cloned_transitions.get(a.target.id)
            if source_p is not None and target_t is not None:
                caller_net.add_arc(source=source_p, target=target_t, weight=a.weight)
        elif isinstance(a.source, Transition) and isinstance(a.target, Place):
            source_t = cloned_transitions.get(a.source.id)
            target_p = cloned_places.get(a.target.id)
            if source_t is not None and target_p is not None:
                caller_net.add_arc(source=source_t, target=target_p, weight=a.weight)

    caller_net.remove_nodes({call_transition.id})


def inline_expand(
    net: PetriNet,
    call_sites: List[CallSite],
    symbol_table: SymbolTable,
    max_depth: int = 1,
    current_stack: Optional[Set[str]] = None,
    caller_function: Optional[str] = None,
) -> PetriNet:
    """Recursively inlines resolved callee Petri nets into caller net producing a Composite Net.

    Args:
        net: The caller PetriNet instance.
        call_sites: List of CallSite records extracted from the caller net.
        symbol_table: Multi-file symbol table used for cross-file call resolution.
        max_depth: Maximum recursion depth for expanding nested callee calls (default 1).
        current_stack: Internal call stack tracking active function identifiers to guard against recursion.
        caller_function: Optional name of the caller function to initialize the call stack.

    Returns:
        A new PetriNet instance with resolved callee subnets spliced in.
    """
    composite_net = net.clone()
    if max_depth <= 0:
        return composite_net

    stack = set(current_stack) if current_stack is not None else set()
    if caller_function:
        stack.add(caller_function)
        if "." in caller_function:
            stack.add(caller_function.rsplit(".", 1)[1])
    elif call_sites and call_sites[0].caller_function:
        c_func = call_sites[0].caller_function
        stack.add(c_func)
        if "." in c_func:
            stack.add(c_func.rsplit(".", 1)[1])

    used_prefixes: Set[str] = set()
    walker_cache: Dict[str, WalkerProtocol] = {}
    processed_trans_ids: Set[str] = set()

    for cs in call_sites:
        if cs.transition_id in processed_trans_ids:
            continue
        processed_trans_ids.add(cs.transition_id)

        node_map = composite_net.get_node_map()
        trans = node_map.get(cs.transition_id)
        if trans is None or not isinstance(trans, Transition):
            continue

        sym = symbol_table.resolve_call(cs)
        if sym is None:
            # Unresolved call transition remains untouched
            continue

        trans.resolution = CallResolution(
            resolved=True,
            resolved_to=sym.name,
            target_file=sym.filepath,
        )
        if trans.metadata is None:
            trans.metadata = {}
        trans.metadata["resolved"] = True
        trans.metadata["resolved_to"] = sym.name
        trans.metadata["target_file"] = sym.filepath

        # Recursion Guard: check if callee appears in the active expansion call stack
        callee_identifiers = {sym.name, sym.bare_name, cs.callee_name}
        is_recursive = any(ident in stack for ident in callee_identifiers if ident)
        if not is_recursive and cs.caller_function and cs.caller_function in stack:
            if cs.callee_name == "requestAnimationFrame" and f"({cs.caller_function})" in trans.label:
                is_recursive = True

        if is_recursive:
            trans.metadata["recursive_cycle"] = True
            continue

        callee_net, callee_call_sites = _get_callee_net(sym, walker_cache=walker_cache)
        if callee_net is None:
            continue

        new_stack = set(stack)
        if sym.name:
            new_stack.add(sym.name)
        if sym.bare_name:
            new_stack.add(sym.bare_name)
        if cs.callee_name:
            new_stack.add(cs.callee_name)

        if max_depth > 1:
            callee_net = inline_expand(
                net=callee_net,
                call_sites=callee_call_sites,
                symbol_table=symbol_table,
                max_depth=max_depth - 1,
                current_stack=new_stack,
                caller_function=sym.name,
            )
        else:
            symbol_table.resolve_call_sites(callee_net, callee_call_sites)

        _splice_callee_net(
            caller_net=composite_net,
            call_transition=trans,
            callee_net=callee_net,
            callee_id=sym.name or cs.callee_name,
            used_prefixes=used_prefixes,
        )

    return composite_net
