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

    @property
    def is_qualified(self) -> bool:
        """Returns True if the name is qualified with an owner or class."""
        return "." in self.name

    @property
    def bare_name(self) -> str:
        """Extracts the unqualified function or method name."""
        return self.name.rsplit(".", 1)[-1] if "." in self.name else self.name

    def variants(self) -> Set["CallFrame"]:
        """Returns matching CallFrame representations.

        For qualified class methods (e.g. 'ClassA.step'), bare name ('step')
        is excluded to prevent false-positive recursion detection between distinct
        classes sharing a method name in the same file.
        """
        result = {self}
        if not self.is_qualified and self.bare_name != self.name:
            result.add(CallFrame(filepath=self.filepath, name=self.bare_name))
        return result

    @classmethod
    def from_caller(cls, cs: CallSite) -> Optional["CallFrame"]:
        """Creates a CallFrame for the caller of a CallSite if defined."""
        if not cs.caller_function:
            return None
        c_file = os.path.abspath(cs.caller_file) if cs.caller_file else ""
        return cls(filepath=c_file, name=cs.caller_function)


def _get_callee_net(
    symbol: Symbol,
    symbol_table: Optional[SymbolTable] = None,
) -> Tuple[Optional[PetriNet], List[CallSite]]:
    """Walks the callee symbol's AST node to produce its PetriNet and CallSite records."""
    ext = os.path.splitext(symbol.filepath)[1].lower() if symbol.filepath else ""
    norm_lang = normalize_language(symbol.language or ext)
    walker_cls = SUPPORTED_WALKERS.get(ext) or SUPPORTED_WALKERS.get(f".{norm_lang}")
    if walker_cls is None:
        return None, []

    walker = walker_cls()
    tree = None
    if symbol.filepath and os.path.exists(symbol.filepath):
        try:
            tree = walker.parse_file(symbol.filepath)
        except Exception:
            tree = None

    ast_node = symbol.ast_node
    if ast_node is None and tree is not None:
        ast_node = walker.find_function(tree, symbol.name) or walker.find_function(tree, symbol.bare_name)

    if ast_node is None:
        return None, []

    try:
        walk_res = walker.walk_function(ast_node, symbol.name, filepath=symbol.filepath)
        callee_net = walk_res.net
        callee_call_sites = walk_res.call_sites
        if symbol_table is not None and callee_net is not None and callee_call_sites:
            symbol_table.resolve_call_sites(callee_net, callee_call_sites)
        return callee_net, callee_call_sites
    except Exception:
        return None, []



def _splice_callee_net(
    caller_net: PetriNet,
    call_transition: Transition,
    callee_net: PetriNet,
    callee_id: str,
    used_prefixes: Set[str],
    callee_name: Optional[str] = None,
    callee_file: Optional[str] = None,
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

    # Note on spec deviation: The spec requested wiring directly to callee source and sink places.
    # To preserve the bipartite property of Petri nets (preventing illegal Place -> Place arcs),
    # the callee's boundary places are merged into caller preset and postset places, and caller arcs
    # connect directly between caller places and callee internal transitions.
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

    # Determine unique compound container ID for this inlined callee
    fn_name = callee_name or callee_id
    clean_fn = fn_name.replace(".", "_")
    base_compound_id = f"compound_{clean_fn}"
    existing_compound_ids = {c["id"] for c in caller_net.compounds}
    if base_compound_id not in existing_compound_ids:
        compound_id = base_compound_id
    else:
        compound_id = f"compound_{prefix.rstrip('_')}"
        idx = 2
        while compound_id in existing_compound_ids:
            compound_id = f"compound_{prefix.rstrip('_')}_{idx}"
            idx += 1

    caller_parent = call_transition.parent

    # Register compound container in caller_net
    caller_net.add_compound(
        id=compound_id,
        label=f"{fn_name}()",
        function_name=fn_name,
        file=callee_file or "",
        parent=caller_parent,
    )

    # Re-parent and register any nested compounds from callee_net
    for c in callee_net.compounds:
        c_copy = dict(c)
        orig_id = c_copy["id"]
        prefixed_id = f"{prefix}{orig_id}" if prefix else orig_id
        c_copy["id"] = prefixed_id
        if c_copy.get("parent") is None:
            c_copy["parent"] = compound_id
        elif prefix and c_copy.get("parent"):
            c_copy["parent"] = f"{prefix}{c_copy['parent']}"
        caller_net.add_compound(
            id=c_copy["id"],
            label=c_copy.get("label", c_copy["id"]),
            function_name=c_copy.get("function_name", ""),
            file=c_copy.get("file", ""),
            parent=c_copy.get("parent"),
        )

    cloned_transitions: Dict[str, Transition] = {}
    for ct in callee_net.transitions:
        new_id = f"{prefix}{ct.id}"
        new_meta = dict(ct.metadata) if ct.metadata is not None else {}
        new_meta["inline_expansion"] = True
        if "parent" not in new_meta or new_meta["parent"] is None:
            new_meta["parent"] = compound_id
        elif prefix and new_meta.get("parent"):
            new_meta["parent"] = f"{prefix}{new_meta['parent']}"
        if "enclosing_function" not in new_meta or new_meta["enclosing_function"] is None:
            new_meta["enclosing_function"] = fn_name

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
        new_meta = dict(cp.metadata) if cp.metadata is not None else {}
        new_meta["inline_expansion"] = True
        if "parent" not in new_meta or new_meta["parent"] is None:
            new_meta["parent"] = compound_id
        elif prefix and new_meta.get("parent"):
            new_meta["parent"] = f"{prefix}{new_meta['parent']}"
        if "enclosing_function" not in new_meta or new_meta["enclosing_function"] is None:
            new_meta["enclosing_function"] = fn_name

        cloned_p = caller_net.add_place(
            id=new_id,
            label=cp.label,
            line_number=cp.line_number,
            initial_tokens=0,
            metadata=new_meta,
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


def _is_self_referencing_loop(
    net: PetriNet,
    cs: CallSite,
    trans: Transition,
) -> bool:
    """Checks whether a call site is an annotated or structural self-referencing loop cycle."""
    if cs.is_callback_loop:
        return True
    if trans.metadata and (trans.metadata.get("is_callback_loop") or trans.metadata.get("recursive_cycle")):
        return True

    # Structural check: Walker wired loop back-arc directly to start place
    start_places = {p.id for p in net.places if p.is_start}
    if any(a.source.id == trans.id and a.target.id in start_places for a in net.arcs):
        return True

    return False


def _get_callee_frames(cs: CallSite, sym: Symbol) -> List[CallFrame]:
    """Builds CallFrame variants for a resolved callee symbol."""
    callee_file = sym.filepath or (os.path.abspath(cs.caller_file) if cs.caller_file else "")
    return CallFrame(filepath=callee_file, name=sym.name).variants()


def _inline_expand_recursive(
    net: PetriNet,
    call_sites: List[CallSite],
    symbol_table: SymbolTable,
    max_depth: int,
    call_stack: Optional[Set[CallFrame]] = None,
    used_prefixes: Optional[Set[str]] = None,
    caller_function: Optional[str] = None,
) -> PetriNet:
    """Internal recursive worker for inline expansion."""
    composite_net = net.clone()
    if caller_function is None and call_sites:
        caller_function = next((cs.caller_function for cs in call_sites if cs.caller_function), None)

    # Ensure caller net root nodes have enclosing_function and parent initialized
    for p in composite_net.places:
        if p.metadata is None or "parent" not in p.metadata:
            p.parent = None
        if p.enclosing_function is None and caller_function:
            p.enclosing_function = caller_function

    for t in composite_net.transitions:
        if t.metadata is None or "parent" not in t.metadata:
            t.parent = None
        if t.enclosing_function is None and caller_function:
            t.enclosing_function = caller_function

    if max_depth <= 0:
        return composite_net

    if used_prefixes is None:
        used_prefixes = set()
    processed_trans_ids: Set[str] = set()

    for cs in call_sites:
        if cs.transition_id in processed_trans_ids:
            continue
        processed_trans_ids.add(cs.transition_id)

        node_map = composite_net.get_node_map()
        trans = node_map.get(cs.transition_id)
        if trans is None or not isinstance(trans, Transition):
            continue

        # Check self-referencing loop (e.g. recursive callback) before external symbol lookup
        if _is_self_referencing_loop(composite_net, cs, trans):
            trans.mark_recursive_cycle()
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

        # Build path-dependent vertical call stack for this call site
        if call_stack is not None:
            active_stack = set(call_stack)
        else:
            active_stack = set()
            caller_frame = CallFrame.from_caller(cs)
            if caller_frame:
                active_stack.update(caller_frame.variants())

        # Recursion Guard: check matching call frames in the active vertical expansion call stack
        callee_frames = _get_callee_frames(cs, sym)
        if any(f in active_stack for f in callee_frames):
            trans.mark_recursive_cycle()
            continue

        callee_net, callee_call_sites = _get_callee_net(sym, symbol_table=symbol_table)
        if callee_net is None:
            continue

        new_stack = set(active_stack)
        new_stack.update(callee_frames)
        callee_fn_name = sym.name or cs.callee_name
        callee_file_path = sym.filepath or (os.path.abspath(cs.caller_file) if cs.caller_file else "")

        if max_depth > 1:
            callee_net = _inline_expand_recursive(
                net=callee_net,
                call_sites=callee_call_sites,
                symbol_table=symbol_table,
                max_depth=max_depth - 1,
                call_stack=new_stack,
                used_prefixes=used_prefixes,
                caller_function=callee_fn_name,
            )

        _splice_callee_net(
            caller_net=composite_net,
            call_transition=trans,
            callee_net=callee_net,
            callee_id=callee_fn_name,
            used_prefixes=used_prefixes,
            callee_name=callee_fn_name,
            callee_file=callee_file_path,
        )

    return composite_net


def inline_expand(
    net: PetriNet,
    call_sites: List[CallSite],
    symbol_table: SymbolTable,
    max_depth: int = 1,
    caller_function: Optional[str] = None,
) -> PetriNet:
    """Recursively inlines resolved callee Petri nets into caller net producing a Composite Net.

    Args:
        net: The caller PetriNet instance.
        call_sites: List of CallSite records extracted from the caller net.
        symbol_table: Multi-file symbol table used for cross-file call resolution.
        max_depth: Maximum recursion depth for expanding nested callee calls (default 1).
        caller_function: Optional name of the root caller function.

    Returns:
        A new PetriNet instance with resolved callee subnets spliced in and hierarchy metadata.
    """
    return _inline_expand_recursive(
        net=net,
        call_sites=call_sites,
        symbol_table=symbol_table,
        max_depth=max_depth,
        call_stack=None,
        caller_function=caller_function,
    )


def precompute_callee_nets(
    call_sites: List[CallSite],
    symbol_table: SymbolTable,
    max_depth: int = 1,
) -> Dict[str, Dict[str, Any]]:
    """Discovers and pre-computes raw Petri net dicts for resolved callees up to max_depth.

    Args:
        call_sites: List of CallSite records extracted from the caller net.
        symbol_table: Multi-file symbol table used for cross-file call resolution.
        max_depth: Maximum recursion depth for exploring nested callee calls (default 1).

    Returns:
        A dictionary mapping callee identifiers (fully qualified symbol names, bare names,
        and call site callee names) to their raw serialized Petri net dictionaries.
    """
    callee_nets: Dict[str, Dict[str, Any]] = {}
    if max_depth <= 0 or not call_sites:
        return callee_nets

    def _collect(cs_list: List[CallSite], current_depth: int, active_stack: Set[CallFrame]) -> None:
        if current_depth > max_depth or not cs_list:
            return

        for cs in cs_list:
            sym = symbol_table.resolve_call(cs)
            if sym is None:
                continue

            # Recursion guard against cycles in active expansion stack
            callee_frames = _get_callee_frames(cs, sym)
            if any(f in active_stack for f in callee_frames):
                continue

            sym_key = sym.name
            if sym_key not in callee_nets:
                callee_net, nested_call_sites = _get_callee_net(sym, symbol_table=symbol_table)
                if callee_net is not None:
                    net_dict = callee_net.to_dict()
                    callee_nets[sym_key] = net_dict
                    if sym.bare_name and sym.bare_name not in callee_nets:
                        callee_nets[sym.bare_name] = net_dict
                    if cs.callee_name and cs.callee_name not in callee_nets:
                        callee_nets[cs.callee_name] = net_dict

                    if current_depth < max_depth and nested_call_sites:
                        new_stack = set(active_stack)
                        new_stack.update(callee_frames)
                        _collect(nested_call_sites, current_depth + 1, new_stack)

    caller_stack: Set[CallFrame] = set()
    for cs in call_sites:
        cf = CallFrame.from_caller(cs)
        if cf:
            caller_stack.update(cf.variants())

    _collect(call_sites, 1, caller_stack)
    return callee_nets


