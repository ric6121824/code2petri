import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from code2petri.javascript_walker import JavascriptWalker
from code2petri.model import CallResolution, PetriNet, Transition
from code2petri.python_walker import PythonWalker
from code2petri.walker_protocol import CallSite, WalkerProtocol


SUPPORTED_WALKERS = {
    ".py": PythonWalker,
    ".js": JavascriptWalker,
}


def normalize_language(lang_or_ext: str) -> str:
    """Normalizes a file extension or language identifier to canonical 'python' or 'javascript'."""
    clean = lang_or_ext.lower().strip()
    if clean in (".py", "py", "python"):
        return "python"
    if clean in (".js", "js", "javascript"):
        return "javascript"
    return clean


@dataclass
class Symbol:
    """Represents a callable function, method, or callback symbol in the symbol table."""
    name: str
    bare_name: str
    filepath: str
    language: str
    class_name: Optional[str] = None
    line_number: int = 0
    ast_node: Optional[Any] = None

    @property
    def is_method(self) -> bool:
        """Returns True if the symbol is a class method."""
        return self.class_name is not None


def _find_unique_bare_symbol_match(
    symbols: Sequence[Symbol],
    callee_name: str,
) -> Tuple[Optional[Symbol], int]:
    """Matches free/standalone functions (never class methods) by name or bare_name."""
    standalone = [s for s in symbols if not s.is_method]
    exact = [s for s in standalone if s.name == callee_name]
    matches = exact if exact else [s for s in standalone if s.bare_name == callee_name]
    if len(matches) == 1:
        return matches[0], 1
    return None, len(matches)


class SymbolTable:
    """Multi-file symbol table partitioning callable symbols by language and providing call resolution."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("code2petri")
        self._symbols: List[Symbol] = []
        self._symbols_by_language: Dict[str, List[Symbol]] = {
            "python": [],
            "javascript": [],
        }
        self._symbols_by_qual_name: Dict[Tuple[str, str], List[Symbol]] = {}
        self._symbols_by_bare_name: Dict[Tuple[str, str], List[Symbol]] = {}
        self._symbols_by_file: Dict[str, List[Symbol]] = {}
        self._variable_bindings_by_file: Dict[str, Dict[str, str]] = {}
        self._files_indexed: Set[str] = set()

    def add_symbol(self, symbol: Symbol) -> None:
        """Inserts a symbol into the partitioned indexes."""
        norm_lang = normalize_language(symbol.language)
        norm_path = os.path.abspath(symbol.filepath)
        sym = Symbol(
            name=symbol.name,
            bare_name=symbol.bare_name,
            filepath=norm_path,
            language=norm_lang,
            class_name=symbol.class_name,
            line_number=symbol.line_number,
            ast_node=symbol.ast_node,
        )
        self._symbols.append(sym)
        self._symbols_by_language.setdefault(norm_lang, []).append(sym)
        self._symbols_by_qual_name.setdefault((norm_lang, sym.name), []).append(sym)
        self._symbols_by_bare_name.setdefault((norm_lang, sym.bare_name), []).append(sym)
        self._symbols_by_file.setdefault(norm_path, []).append(sym)

    def index_file(self, filepath: str, walker: Optional[WalkerProtocol] = None) -> None:
        """Parses a source file, extracts variable bindings and callable definitions, and indexes them."""
        norm_path = os.path.abspath(filepath)
        if norm_path in self._files_indexed:
            return
        if not os.path.exists(norm_path):
            raise FileNotFoundError(f"File not found: '{norm_path}'")

        ext = os.path.splitext(norm_path)[1].lower()
        lang = normalize_language(ext)

        if walker is None:
            walker_cls = SUPPORTED_WALKERS.get(ext)
            if walker_cls is None:
                self.logger.debug("Unsupported extension '%s' for file '%s', skipping indexing", ext, norm_path)
                return
            walker = walker_cls()

        try:
            tree = walker.parse_file(norm_path)
        except Exception as exc:
            self.logger.debug("Failed to parse '%s': %s", norm_path, exc)
            return

        if tree is None:
            return

        # Harvest variable bindings
        bindings = walker.collect_variable_bindings(tree)
        self._variable_bindings_by_file[norm_path] = dict(bindings)

        # Discover and index all callable functions and methods
        func_names = walker.find_all_functions(tree)
        for name in func_names:
            if name == "(global)":
                continue
            node = walker.find_function(tree, name)
            lineno = walker.get_node_lineno(node) if node is not None else 0

            if "." in name:
                class_name = name.rsplit(".", 1)[0]
                bare_name = name.rsplit(".", 1)[1]
            else:
                class_name = None
                bare_name = name

            symbol = Symbol(
                name=name,
                bare_name=bare_name,
                filepath=norm_path,
                language=lang,
                class_name=class_name,
                line_number=lineno,
                ast_node=node,
            )
            self.add_symbol(symbol)

        self._files_indexed.add(norm_path)

    def index_files(self, filepaths: Sequence[str]) -> None:
        """Indexes a sequence of source files."""
        for fp in filepaths:
            self.index_file(fp)

    def get_symbols(self, language: Optional[str] = None) -> List[Symbol]:
        """Returns all indexed symbols, optionally filtered by language."""
        if language is None:
            return list(self._symbols)
        norm_lang = normalize_language(language)
        return list(self._symbols_by_language.get(norm_lang, []))

    def get_symbols_for_file(self, filepath: str) -> List[Symbol]:
        """Returns all symbols defined in a specific file."""
        norm_path = os.path.abspath(filepath)
        return list(self._symbols_by_file.get(norm_path, []))

    def get_variable_bindings(self, filepath: str) -> Dict[str, str]:
        """Returns extracted variable bindings for a file."""
        norm_path = os.path.abspath(filepath)
        return dict(self._variable_bindings_by_file.get(norm_path, {}))

    def lookup(self, name: str, language: str) -> List[Symbol]:
        """Looks up symbols by exact qualified name within a language."""
        norm_lang = normalize_language(language)
        return list(self._symbols_by_qual_name.get((norm_lang, name), []))

    def lookup_bare(self, bare_name: str, language: str) -> List[Symbol]:
        """Looks up symbols by bare function name within a language."""
        norm_lang = normalize_language(language)
        return list(self._symbols_by_bare_name.get((norm_lang, bare_name), []))

    def _resolve_bare_in_symbols(
        self,
        symbols: Sequence[Symbol],
        call_site: CallSite,
    ) -> Tuple[Optional[Symbol], bool]:
        """Resolves a bare call in a symbol sequence. Returns (match, is_ambiguous)."""
        match, count = _find_unique_bare_symbol_match(symbols, call_site.callee_name)
        if count == 1:
            return match, False
        if count > 1:
            self.logger.debug(
                "Unresolved call site '%s' in '%s': ambiguous match (%d symbols found)",
                call_site.callee_name,
                call_site.caller_file,
                count,
            )
            return None, True
        return None, False

    def resolve_call(
        self,
        call_site: CallSite,
        variable_bindings: Optional[Dict[str, str]] = None,
        language: Optional[str] = None,
    ) -> Optional[Symbol]:
        """Resolves a CallSite against the symbol table, returning the matching Symbol or None."""
        if language is not None:
            norm_lang = normalize_language(language)
        else:
            if not call_site.caller_file:
                self.logger.debug(
                    "Unresolved call site '%s': caller_file is empty and language not specified",
                    call_site.callee_name,
                )
                return None
            ext = os.path.splitext(call_site.caller_file)[1].lower()
            norm_lang = normalize_language(ext)

        if norm_lang not in self._symbols_by_language:
            self.logger.debug(
                "Unresolved call site '%s': unsupported language '%s'",
                call_site.callee_name,
                norm_lang,
            )
            return None

        norm_caller_file = os.path.abspath(call_site.caller_file) if call_site.caller_file else ""
        bindings = (
            dict(variable_bindings)
            if variable_bindings is not None
            else self.get_variable_bindings(norm_caller_file)
        )

        # Case 1: Call site has an owner (e.g. obj.method, this.method, self.method)
        if call_site.callee_owner is not None:
            target_candidate = None
            if call_site.callee_owner in ("this", "self"):
                if "." in call_site.caller_function:
                    enclosing_class = call_site.caller_function.rsplit(".", 1)[0]
                    target_candidate = f"{enclosing_class}.{call_site.callee_name}"
            elif call_site.callee_owner in bindings:
                target_class = bindings[call_site.callee_owner]
                target_candidate = f"{target_class}.{call_site.callee_name}"
            else:
                # Direct class invocation or qualified receiver candidate
                target_candidate = f"{call_site.callee_owner}.{call_site.callee_name}"

            if target_candidate is not None:
                matches = self.lookup(target_candidate, language=norm_lang)
                if len(matches) == 1:
                    return matches[0]
                elif len(matches) > 1:
                    self.logger.debug(
                        "Unresolved call site '%s' in '%s': ambiguous match (%d symbols found)",
                        call_site.callee_name,
                        call_site.caller_file,
                        len(matches),
                    )
                    return None
                else:
                    self.logger.debug(
                        "Unresolved call site '%s' in '%s': no matching symbol found",
                        call_site.callee_name,
                        call_site.caller_file,
                    )
                    return None

            self.logger.debug(
                "Unresolved call site '%s' in '%s': no matching symbol found",
                call_site.callee_name,
                call_site.caller_file,
            )
            return None

        # Case 2: Bare function call (func())
        # First priority: check local caller file definitions
        if norm_caller_file:
            local_symbols = self.get_symbols_for_file(norm_caller_file)
            match, ambiguous = self._resolve_bare_in_symbols(local_symbols, call_site)
            if match:
                return match
            if ambiguous:
                return None

        # Second priority: check across context files of the same language
        context_symbols = [
            s for s in self._symbols_by_language.get(norm_lang, [])
            if s.filepath != norm_caller_file
        ]
        match, ambiguous = self._resolve_bare_in_symbols(context_symbols, call_site)
        if match:
            return match
        if ambiguous:
            return None

        self.logger.debug(
            "Unresolved call site '%s' in '%s': no matching symbol found",
            call_site.callee_name,
            call_site.caller_file,
        )
        return None

    def resolve_call_sites(
        self,
        net: PetriNet,
        call_sites: List[CallSite],
        variable_bindings: Optional[Dict[str, str]] = None,
    ) -> None:
        """Resolves call sites against the symbol table and decorates net transitions with resolution metadata."""
        trans_map = {t.id: t for t in net.transitions}

        for cs in call_sites:
            t = trans_map.get(cs.transition_id)
            if t is None:
                continue

            sym = self.resolve_call(cs, variable_bindings=variable_bindings)
            if sym is not None:
                t.resolution = CallResolution(
                    resolved=True,
                    resolved_to=sym.name,
                    target_file=sym.filepath,
                )
                res_meta: Dict[str, Any] = {
                    "resolved": True,
                    "resolved_to": sym.name,
                    "target_file": sym.filepath,
                }
            else:
                t.resolution = CallResolution(resolved=False)
                res_meta = {
                    "resolved": False,
                    "status": "[unresolved]",
                }

            if t.metadata is not None:
                t.metadata = {**t.metadata, **res_meta}
            else:
                t.metadata = dict(res_meta)
