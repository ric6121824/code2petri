from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from code2petri.model import CallResolution, PetriNet, Place, Transition
from code2petri.symbol_table import SUPPORTED_WALKERS, Symbol, SymbolTable, normalize_language
from code2petri.walker_protocol import CallSite, WalkerProtocol


@dataclass(frozen=True)
class CallFrame:
    """Represents an activation record in the expansion call stack."""
    filepath: str
    name: str


def _is_start_place(place: Place) -> bool:
    """Returns True if place is designated as a workflow net start place."""
    return place.initial_tokens > 0 or place.label == "start"


def _mark_recursive_cycle(trans: Transition) -> None:
    """Annotates an opaque transition with recursive cycle metadata."""
    if trans.metadata is None:
        trans.metadata = {}
    trans.metadata["recursive_cycle"] = True


def _get_callee_net(
    symbol: Symbol,
    walker_cache: Optional[Dict[str, Tuple[WalkerProtocol, Any]]] = None,
) -> Tuple[Optional[PetriNet], List[CallSite]]:
    """Walks the callee symbol's AST node to produce its PetriNet and CallSite records."""
    ext = os.path.splitext(symbol.filepath)[1].lower() if symbol.filepath else ""
    norm_lang = normalize_language(symbol.language or ext)
    walker_cls = SUPPORTED_WALKERS.get(ext) or SUPPORTED_WALKERS.get(f".{norm_lang}")
    if walker_cls is None:
        return None, []

    cache = walker_cache if walker_cache is not None else {}
    cache_key = f"{walker_cls.__name__}:{symbol.filepath}"

    if cache_key in cache:
        walker, tree = cache[cache_key]
    else:
        walker = walker_cls()
        tree = None
        if symbol.filepath and os.path.exists(symbol.filepath):
            try:
                tree = walker.parse_file(symbol.filepath)
            except Exception:
                tree = None
        cache[cache_key] = (walker, tree)

    ast_node = symbol.ast_node
    if ast_node is None and tree is not None:
        ast_node = walker.find_function(tree, symbol.name) or walker.find_function(tree, symbol.bare_name)

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

    callee_source_place, callee_sink_place = callee_net.find_boundary_places()
    if (
        callee_source_place is None
        or callee_sink_place is None
        or callee_source_place.id == callee_sink_place.id
    ):
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
        cloned_t = caller_net.add_transition(
            id=new_id,
            label=ct.label,
            line_number=ct.line_number,
            metadata=new_meta,
            resolution=ct.resolution,
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


def _is_self_referencing_game_loop(
    net: PetriNet,
    cs: CallSite,
    trans: Transition,
) -> bool:
    """Checks whether a call site is a self-referencing game loop cycle like requestAnimationFrame(loop)."""
    if cs.callee_name != "requestAnimationFrame":
        return False
    # Structural check: JavascriptWalker wires recursive RAF loop back-arcs directly to the start place
    start_places = {p.id for p in net.places if _is_start_place(p)}
    if any(a.source.id == trans.id and a.target.id in start_places for a in net.arcs):
        return True

    # Fallback check: label explicitly references caller function
    if cs.caller_function:
        bare_name = cs.caller_function.split(".")[-1]
        return (
            f"({cs.caller_function})" in trans.label
            or f"({bare_name})" in trans.label
            or f"this.{bare_name}" in trans.label
        )
    return False


def _inline_expand_recursive(
    net: PetriNet,
    call_sites: List[CallSite],
    symbol_table: SymbolTable,
    max_depth: int,
    call_stack: Set[CallFrame],
) -> PetriNet:
    """Internal recursive worker for inline expansion."""
    composite_net = net.clone()
    if max_depth <= 0:
        return composite_net

    used_prefixes: Set[str] = set()
    walker_cache: Dict[str, Tuple[WalkerProtocol, Any]] = {}
    processed_trans_ids: Set[str] = set()

    for cs in call_sites:
        if cs.transition_id in processed_trans_ids:
            continue
        processed_trans_ids.add(cs.transition_id)

        node_map = composite_net.get_node_map()
        trans = node_map.get(cs.transition_id)
        if trans is None or not isinstance(trans, Transition):
            continue

        # Check self-referencing game loop (e.g. requestAnimationFrame(loop)) before external symbol lookup
        if _is_self_referencing_game_loop(composite_net, cs, trans):
            _mark_recursive_cycle(trans)
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

        # Recursion Guard: check matching call frames in the active expansion call stack
        callee_file = sym.filepath or (os.path.abspath(cs.caller_file) if cs.caller_file else "")
        callee_frames = {
            CallFrame(filepath=callee_file, name=sym.name),
        }
        if sym.bare_name:
            callee_frames.add(CallFrame(filepath=callee_file, name=sym.bare_name))

        if any(f in call_stack for f in callee_frames):
            _mark_recursive_cycle(trans)
            continue

        callee_net, callee_call_sites = _get_callee_net(sym, walker_cache=walker_cache)
        if callee_net is None:
            continue

        new_stack = set(call_stack)
        new_stack.update(callee_frames)

        if max_depth > 1:
            callee_net = _inline_expand_recursive(
                net=callee_net,
                call_sites=callee_call_sites,
                symbol_table=symbol_table,
                max_depth=max_depth - 1,
                call_stack=new_stack,
            )

        _splice_callee_net(
            caller_net=composite_net,
            call_transition=trans,
            callee_net=callee_net,
            callee_id=sym.name or cs.callee_name,
            used_prefixes=used_prefixes,
        )

    return composite_net


def inline_expand(
    net: PetriNet,
    call_sites: List[CallSite],
    symbol_table: SymbolTable,
    max_depth: int = 1,
) -> PetriNet:
    """Recursively inlines resolved callee Petri nets into caller net producing a Composite Net.

    Args:
        net: The caller PetriNet instance.
        call_sites: List of CallSite records extracted from the caller net.
        symbol_table: Multi-file symbol table used for cross-file call resolution.
        max_depth: Maximum recursion depth for expanding nested callee calls (default 1).

    Returns:
        A new PetriNet instance with resolved callee subnets spliced in.
    """
    initial_stack: Set[CallFrame] = set()
    for cs in call_sites:
        if cs.caller_function:
            c_file = os.path.abspath(cs.caller_file) if cs.caller_file else ""
            initial_stack.add(CallFrame(filepath=c_file, name=cs.caller_function))
            if "." in cs.caller_function:
                initial_stack.add(CallFrame(filepath=c_file, name=cs.caller_function.split(".")[-1]))

    return _inline_expand_recursive(
        net=net,
        call_sites=call_sites,
        symbol_table=symbol_table,
        max_depth=max_depth,
        call_stack=initial_stack,
    )

