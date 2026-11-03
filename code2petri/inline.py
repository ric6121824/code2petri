from dataclasses import dataclass
import json
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



def _decorate_node_hierarchy(
    meta: Dict[str, Any],
    compound_id: str,
    fn_name: str,
    prefix: str,
) -> None:
    """Decorates a node's metadata dictionary with parent compound and enclosing function hierarchy."""
    meta["inline_expansion"] = True
    if "parent" not in meta or meta["parent"] is None:
        meta["parent"] = compound_id
    elif prefix and meta.get("parent"):
        meta["parent"] = f"{prefix}{meta['parent']}"
    if "enclosing_function" not in meta or meta["enclosing_function"] is None:
        meta["enclosing_function"] = fn_name


def _occurrence_call_refolding_record(
    caller_net: PetriNet,
    call_transition: Transition,
    exception_alternatives: List[Transition],
    callee_has_exception_exit: bool,
    exception_postset_places: List[Place],
    caller_parent: Optional[str],
) -> Dict[str, Any]:
    """Capture a call occurrence's external interface before it is spliced away."""
    call_input_arcs = [
        arc.to_dict() for arc in caller_net.arcs if arc.target.id == call_transition.id
    ]
    call_output_arcs = [
        arc.to_dict() for arc in caller_net.arcs if arc.source.id == call_transition.id
    ]
    exception_input_arcs = [
        arc.to_dict() for arc in caller_net.arcs
        if any(arc.target.id == transition.id for transition in exception_alternatives)
    ]
    exception_output_arcs = [
        arc.to_dict() for arc in caller_net.arcs
        if any(arc.source.id == transition.id for transition in exception_alternatives)
    ]
    exception_records = [transition.to_dict() for transition in exception_alternatives]

    # The inliner may create an exceptional caller boundary when the source call
    # had no paired alternative. Retain a separate alternative for later refolding.
    if callee_has_exception_exit and not exception_records and exception_postset_places:
        exception_id = f"{call_transition.id}__exception"
        existing_ids = {transition.id for transition in caller_net.transitions}
        suffix = 2
        while exception_id in existing_ids:
            exception_id = f"{call_transition.id}__exception_{suffix}"
            suffix += 1
        exception_records.append({
            "id": exception_id,
            "label": f"exception: {call_transition.label}",
            "line_number": call_transition.line_number,
            "metadata": {
                "exception_alternative": True,
                "exception_alternative_of": call_transition.id,
                "parent": caller_parent,
            },
            "parent": caller_parent,
        })
        exception_input_arcs = [
            {"source": arc["source"], "target": exception_id, "weight": arc["weight"]}
            for arc in call_input_arcs
        ]
        exception_output_arcs = [
            {"source": exception_id, "target": place.id, "weight": 1}
            for place in exception_postset_places
        ]

    return {
        "version": 1,
        "call_transition": call_transition.to_dict(),
        "exception_transitions": exception_records,
        "call_input_arcs": call_input_arcs,
        "call_output_arcs": call_output_arcs,
        "exception_input_arcs": exception_input_arcs,
        "exception_output_arcs": exception_output_arcs,
    }


def _prefix_occurrence_call_refolding(
    record: Optional[Dict[str, Any]],
    prefix: str,
    fallback_parent: str,
    source_place_id: str,
    preset_places: List[Place],
    sink_postsets: Dict[str, List[Place]],
) -> Optional[Dict[str, Any]]:
    """Remap a nested occurrence restoration record along with its cloned subnet."""
    if not isinstance(record, dict) or record.get("version") != 1:
        return None

    def clone_transition(transition: Dict[str, Any]) -> Dict[str, Any]:
        result = json.loads(json.dumps(transition))
        original_id = result["id"]
        result["id"] = prefix + original_id
        parent = result.get("parent") or (result.get("metadata") or {}).get("parent")
        mapped_parent = prefix + parent if parent else fallback_parent
        result["parent"] = mapped_parent
        metadata = dict(result.get("metadata") or {})
        call_results = metadata.get("call_results")
        if isinstance(call_results, list):
            metadata["call_results"] = [
                {**record, "transition_id": prefix + str(record.get("transition_id", original_id))}
                if isinstance(record, dict) else record
                for record in call_results
            ]
        metadata["parent"] = mapped_parent
        owner_id = metadata.get("exception_alternative_of")
        if owner_id:
            metadata["exception_alternative_of"] = prefix + owner_id
        result["metadata"] = metadata
        return result

    def map_arc(arc: Dict[str, Any]) -> List[Dict[str, Any]]:
        source_id = arc["source"]
        target_id = arc["target"]
        sources = (
            [place.id for place in preset_places]
            if source_id == source_place_id else [prefix + source_id]
        )
        targets = (
            [place.id for place in sink_postsets[target_id]]
            if target_id in sink_postsets else [prefix + target_id]
        )
        return [
            {"source": source, "target": target, "weight": arc.get("weight", 1)}
            for source in sources for target in targets
        ]

    cloned = {
        "version": 1,
        "call_transition": clone_transition(record["call_transition"]),
        "exception_transitions": [clone_transition(item) for item in record.get("exception_transitions", [])],
    }
    for arc_key in (
        "call_input_arcs", "call_output_arcs", "exception_input_arcs", "exception_output_arcs"
    ):
        cloned[arc_key] = [
            mapped for arc in record.get(arc_key, []) for mapped in map_arc(arc)
        ]
    return cloned


def _splice_callee_net(
    caller_net: PetriNet,
    call_transition: Transition,
    callee_net: PetriNet,
    callee_id: str,
    used_prefixes: Set[str],
    callee_name: Optional[str] = None,
    callee_file: Optional[str] = None,
    function_ref: Optional[str] = None,
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
    exception_alternatives = [
        transition for transition in caller_net.transitions
        if transition.metadata
        and transition.metadata.get("exception_alternative_of") == call_transition.id
    ]
    exception_postset_places = [
        arc.target for arc in caller_net.arcs
        if arc.source in exception_alternatives and isinstance(arc.target, Place)
    ]

    if not preset_places or not postset_places:
        return

    caller_net.function_metadata_registry.update(callee_net.function_metadata_registry)

    # Note on spec deviation: The spec requested wiring directly to callee source and sink places.
    # To preserve the bipartite property of Petri nets (preventing illegal Place -> Place arcs),
    # the callee's boundary places are merged into caller preset and postset places, and caller arcs
    # connect directly between caller places and callee internal transitions.
    callee_source_place, callee_sink_place = callee_net.find_boundary_places()
    callee_exception_sink = callee_net.find_exception_boundary_place()
    if (
        callee_source_place is None
        or callee_sink_place is None
        or callee_source_place.id == callee_sink_place.id
    ):
        return

    if callee_exception_sink is not None and not exception_postset_places:
        caller_exception_sink = caller_net.find_exception_boundary_place()
        if caller_exception_sink is None:
            caller_exception_sink = caller_net.ensure_exception_boundary_place()
        exception_postset_places = [caller_exception_sink]
    fuse_exception_sink = callee_exception_sink is not None and bool(exception_postset_places)
    sink_postsets = {callee_sink_place.id: postset_places}
    if fuse_exception_sink:
        sink_postsets[callee_exception_sink.id] = exception_postset_places

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
    existing_compound_ids = {c.id for c in caller_net.compounds}
    if base_compound_id not in existing_compound_ids:
        compound_id = base_compound_id
    else:
        compound_id = f"compound_{prefix.rstrip('_')}"
        idx = 2
        while compound_id in existing_compound_ids:
            compound_id = f"compound_{prefix.rstrip('_')}_{idx}"
            idx += 1

    caller_parent = call_transition.parent
    call_refolding = _occurrence_call_refolding_record(
        caller_net=caller_net,
        call_transition=call_transition,
        exception_alternatives=exception_alternatives,
        callee_has_exception_exit=callee_exception_sink is not None,
        exception_postset_places=exception_postset_places,
        caller_parent=caller_parent,
    )

    # Register compound container in caller_net
    compound = caller_net.add_compound(
        id=compound_id,
        label=f"{fn_name}()",
        function_name=fn_name,
        file=callee_file or "",
        parent=caller_parent,
        function_ref=function_ref,
        call_refolding=call_refolding,
    )

    # Re-parent and register any nested compounds from callee_net
    for c in callee_net.compounds:
        orig_id = c.id
        prefixed_id = f"{prefix}{orig_id}" if prefix else orig_id
        if c.parent is None:
            new_parent = compound_id
        elif prefix and c.parent:
            new_parent = f"{prefix}{c.parent}"
        else:
            new_parent = c.parent
        nested_node_ids = {f"{prefix}{nid}" if prefix else nid for nid in (c.node_ids or set())}
        caller_net.add_compound(
            id=prefixed_id,
            label=c.label or orig_id,
            function_name=c.function_name or "",
            file=c.file or "",
            parent=new_parent,
            node_ids=nested_node_ids,
            function_ref=c.function_ref,
            call_refolding=_prefix_occurrence_call_refolding(
                c.call_refolding,
                prefix,
                compound_id,
                callee_source_place.id,
                preset_places,
                sink_postsets,
            ),
        )

    cloned_transitions: Dict[str, Transition] = {}
    for ct in callee_net.transitions:
        new_id = f"{prefix}{ct.id}"
        new_meta = dict(ct.metadata) if ct.metadata is not None else {}
        call_results = new_meta.get("call_results")
        if isinstance(call_results, list):
            new_meta["call_results"] = [
                {**record, "transition_id": new_id} if isinstance(record, dict) else record
                for record in call_results
            ]
        exception_owner_id = new_meta.get("exception_alternative_of")
        if exception_owner_id:
            new_meta["exception_alternative_of"] = f"{prefix}{exception_owner_id}"
        _decorate_node_hierarchy(new_meta, compound_id, fn_name, prefix)

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
        if fuse_exception_sink and cp.id == callee_exception_sink.id:
            continue
        new_id = f"{prefix}{cp.id}"
        new_meta = dict(cp.metadata) if cp.metadata is not None else {}
        _decorate_node_hierarchy(new_meta, compound_id, fn_name, prefix)

        cloned_p = caller_net.add_place(
            id=new_id,
            label=cp.label,
            line_number=cp.line_number,
            initial_tokens=0,
            metadata=new_meta,
        )
        cloned_places[cp.id] = cloned_p

    compound.node_ids.update(t.id for t in cloned_transitions.values())
    compound.node_ids.update(p.id for p in cloned_places.values())

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
        elif isinstance(a.target, Place) and a.target.id in sink_postsets:
            source_t = cloned_transitions.get(a.source.id)
            if source_t is not None:
                for p_out in sink_postsets[a.target.id]:
                    caller_net.add_arc(source=source_t, target=p_out, weight=a.weight)
        elif isinstance(a.source, Place) and a.source.id in sink_postsets:
            target_t = cloned_transitions.get(a.target.id)
            if target_t is not None:
                for p_out in sink_postsets[a.source.id]:
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

    nodes_to_remove = {call_transition.id}
    if fuse_exception_sink:
        nodes_to_remove.update(transition.id for transition in exception_alternatives)
    caller_net.remove_nodes(nodes_to_remove)


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
    max_depth: Optional[int],
    call_stack: Optional[Set[CallFrame]] = None,
    used_prefixes: Optional[Set[str]] = None,
    caller_function: Optional[str] = None,
) -> PetriNet:
    """Internal recursive worker for inline expansion."""
    composite_net = net.clone()
    # Keep the same record association for API callers that expand directly,
    # as well as for the CLI path that resolved transitions before expansion.
    symbol_table.resolve_call_sites(composite_net, call_sites)
    if caller_function is None and call_sites:
        caller_function = next((cs.caller_function for cs in call_sites if cs.caller_function), None)

    # Ensure caller net root nodes have enclosing_function and parent initialized
    for node in list(composite_net.places) + list(composite_net.transitions):
        if node.metadata is None or "parent" not in node.metadata:
            node.parent = None
        if node.enclosing_function is None and caller_function:
            node.enclosing_function = caller_function

    if max_depth is not None and max_depth <= 0:
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

        if max_depth is None or max_depth > 1:
            callee_net = _inline_expand_recursive(
                net=callee_net,
                call_sites=callee_call_sites,
                symbol_table=symbol_table,
                max_depth=None if max_depth is None else max_depth - 1,
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
            function_ref=(trans.metadata or {}).get("function_ref"),
        )

    return composite_net


def inline_expand(
    net: PetriNet,
    call_sites: List[CallSite],
    symbol_table: SymbolTable,
    max_depth: Optional[int] = 1,
    caller_function: Optional[str] = None,
) -> PetriNet:
    """Recursively inlines resolved callee Petri nets into caller net producing a Composite Net.

    Args:
        net: The caller PetriNet instance.
        call_sites: List of CallSite records extracted from the caller net.
        symbol_table: Multi-file symbol table used for cross-file call resolution.
        max_depth: Maximum recursion depth for expanding nested callee calls (default 1, None for unlimited).
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
    max_depth: Optional[int] = 1,
) -> Dict[str, Dict[str, Any]]:
    """Discovers and pre-computes raw Petri net dicts for resolved callees up to max_depth.

    Args:
        call_sites: List of CallSite records extracted from the caller net.
        symbol_table: Multi-file symbol table used for cross-file call resolution.
        max_depth: Maximum recursion depth for exploring nested callee calls (default 1, None for unlimited).

    Returns:
        A dictionary mapping callee identifiers (fully qualified symbol names, bare names,
        and call site callee names) to their raw serialized Petri net dictionaries.
    """
    callee_nets: Dict[str, Dict[str, Any]] = {}
    if (max_depth is not None and max_depth <= 0) or not call_sites:
        return callee_nets

    def _collect(cs_list: List[CallSite], current_depth: int, active_stack: Set[CallFrame]) -> None:
        if (max_depth is not None and current_depth > max_depth) or not cs_list:
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

                    if (max_depth is None or current_depth < max_depth) and nested_call_sites:
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


