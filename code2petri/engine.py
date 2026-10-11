import argparse
import logging
import os
import subprocess
import sys
from typing import Optional, List, Sequence, Set, Union

from code2petri.model import PetriNet
from code2petri.symbol_table import SymbolTable, SUPPORTED_WALKERS
from code2petri.fold import FoldConfig, FoldResult, fold_net
from code2petri.inline import inline_expand, precompute_callee_nets
from code2petri.viewer import generate_html

WALKERS = SUPPORTED_WALKERS


def discover_context_files(context_paths: Sequence[str]) -> List[str]:
    """Recursively scans context paths and collects all supported source files (.py, .js)."""
    discovered: List[str] = []
    seen: Set[str] = set()

    def add_file(file_path: str) -> None:
        abs_file = os.path.abspath(file_path)
        if abs_file not in seen:
            seen.add(abs_file)
            discovered.append(abs_file)

    for path in context_paths:
        if not os.path.exists(path):
            raise AssertionError(f"Context path '{path}' does not exist.")

        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for f in sorted(files):
                    if f.startswith("._") or (f.startswith(".") and not f.endswith(tuple(WALKERS.keys()))):
                        continue
                    ext = os.path.splitext(f)[1].lower()
                    if ext in WALKERS:
                        add_file(os.path.join(root, f))
        elif os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in WALKERS:
                add_file(path)
            else:
                supported_src = ", ".join(sorted(WALKERS.keys()))
                raise AssertionError(
                    f"Unsupported context file extension '{ext}' in '{path}'. "
                    f"Supported extensions are: {supported_src}"
                )
    return discovered


UNLIMITED_DEPTH: Optional[int] = None

IMAGE_EXTENSIONS = {"png", "svg"}
TEXT_SERIALIZERS = {
    "pnml": lambda model, **_: model.to_pnml(),
    "dot": lambda model, **_: model.to_dot(),
    "gv": lambda model, **_: model.to_dot(),
    "json": lambda model, **_: model.to_json(),
    "html": lambda model, **kwargs: generate_html(model, **kwargs),
}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | set(TEXT_SERIALIZERS.keys())


def is_installed(executable_cmd: str) -> bool:
    """Checks whether an executable command is available on PATH."""
    for path in os.environ.get("PATH", "").split(os.pathsep):
        path = path.strip('"')
        exe_file = os.path.join(path, executable_cmd)
        if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
            return True
    return False


def _render_dot_to_image(dot_content: str, ext: str, output_file: str) -> None:
    """Renders Graphviz DOT content to an image file via the 'dot' CLI tool."""
    if not is_installed("dot") and not is_installed("dot.exe"):
        raise AssertionError(
            "Cannot generate image because Graphviz 'dot' executable was not found on PATH. "
            "Install Graphviz or use a text extension (.pnml, .dot, .gv, .json)."
        )
    cmd = ["dot", f"-T{ext}", "-o", output_file]
    result = subprocess.run(
        cmd,
        input=dot_content.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Graphviz command failed with exit code {result.returncode}: "
            f"{result.stderr.decode('utf-8', errors='replace')}"
        )


def code2petri(
    source_path: str,
    output_file: Optional[str] = "out.pnml",
    target_function: Optional[str] = None,
    list_functions: bool = False,
    level: Optional[int] = None,
    context: Optional[List[str]] = None,
    fold: bool = False,
    no_fold: bool = False,
    weights: Optional[Union[str, FoldConfig]] = None,
    inline: bool = False,
    inline_depth: Optional[int] = None,
) -> Union[PetriNet, FoldResult, None]:
    """Generates a Petri net from a source file and writes the serialized output.

    :param source_path: Path to the source file.
    :param output_file: Destination file path (.pnml, .dot, .gv, .json, .png, .svg).
    :param target_function: Name of the function to extract and convert.
    :param list_functions: If True, prints all function names found and exits without analyzing.
    :param level: Optional logging level to set on the logger.
    :param context: Optional list of context file or directory paths for cross-file call resolution.
    :param fold: If True, activates structural fold analysis.
    :param no_fold: If True, explicitly disables fold analysis.
    :param weights: Path or JSON string overriding default FoldConfig penalty weights.
    :param inline: If True, activates inline expansion of resolved call transitions (requires context).
    :param inline_depth: Maximum recursion depth for inline expansion (default: unlimited for composite HTML, 1 otherwise).
    :return: The generated PetriNet instance (or FoldResult if fold is active), or None if list_functions is True.
    """
    logger = logging.getLogger("code2petri")
    if level is not None:
        logger.setLevel(level)

    if not os.path.exists(source_path):
        raise AssertionError(f"Source file '{source_path}' does not exist.")

    src_ext = os.path.splitext(source_path)[1].lower()
    if src_ext not in WALKERS:
        supported_src = ", ".join(sorted(WALKERS.keys()))
        raise AssertionError(
            f"Unsupported source extension '{src_ext}'. Supported extensions are: {supported_src}"
        )

    ext = ""
    if output_file and not list_functions:
        ext = os.path.splitext(output_file)[1].lstrip(".").lower()
        if ext not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise AssertionError(
                f"Unsupported output extension '.{ext}'. Supported extensions are: {supported}"
            )

    symbol_table = None
    if context:
        logger.debug("Discovering context files from %s...", context)
        context_files = discover_context_files(context)
        logger.info("Found %d context file(s) for resolution.", len(context_files))
        symbol_table = SymbolTable()
        symbol_table.index_file(source_path)
        for cf in context_files:
            symbol_table.index_file(cf)
    elif ext == "html":
        logger.debug("Initializing local symbol table for HTML callee precomputation...")
        symbol_table = SymbolTable()
        symbol_table.index_file(source_path)

    walker = WALKERS[src_ext]()

    logger.debug("Parsing source file '%s'...", source_path)
    try:
        tree = walker.parse_file(source_path)
    except Exception as exc:
        raise AssertionError(f"Could not parse file '{source_path}': {exc}") from exc

    if tree is None:
        raise AssertionError(f"Could not parse file '{source_path}'.")

    if list_functions:
        funcs = walker.find_all_functions(tree)
        logger.debug("Discovered %d functions in '%s': %s", len(funcs), source_path, funcs)
        for fn in funcs:
            print(fn)
        return None

    if not target_function:
        raise AssertionError(
            "A target function must be specified via --target-function "
            "(or use --list-functions to see available functions)."
        )

    func_node = walker.find_function(tree, target_function)
    if func_node is None:
        available = walker.find_all_functions(tree)
        avail_str = f" Available functions: {', '.join(available)}" if available else ""
        raise AssertionError(
            f"Target function '{target_function}' not found in '{source_path}'.{avail_str}"
        )

    lineno = walker.get_node_lineno(func_node)
    logger.info("Analyzing function '%s' at line %d...", target_function, lineno)
    logger.debug("Walking AST node for '%s'...", target_function)
    walk_res = walker.walk_function(func_node, target_function, filepath=source_path)
    net, call_sites = walk_res.net, walk_res.call_sites
    logger.debug("Extracted %d call site(s) from '%s'", len(call_sites), target_function)

    if symbol_table is not None:
        logger.debug("Resolving %d call site(s) against symbol table...", len(call_sites))
        symbol_table.resolve_call_sites(net, call_sites)

    # Determine execution modes
    is_html = (ext == "html")
    effective_inline = inline or (
        is_html and (bool(context) or target_function == "(global)") and not fold
    )
    is_composite_html = is_html and (inline or effective_inline)

    if is_composite_html and fold:
        logger.warning("--fold is not compatible with composite HTML output and will be ignored.")

    fold_active = (fold or (is_html and not effective_inline)) and not no_fold and not is_composite_html

    if inline_depth is None:
        actual_inline_depth = UNLIMITED_DEPTH if is_composite_html else 1
    else:
        actual_inline_depth = inline_depth

    # Inline Expansion (runs first if active)
    if effective_inline:
        if not context and not (is_html and target_function == "(global)" and not inline):
            raise AssertionError("Inline expansion requires --context to be provided.")
        if symbol_table is None:
            symbol_table = SymbolTable()
        if actual_inline_depth is None:
            logger.info("Executing inline expansion until fixpoint...")
        else:
            logger.info("Executing inline expansion with depth %d...", actual_inline_depth)
        net = inline_expand(
            net,
            call_sites,
            symbol_table,
            max_depth=actual_inline_depth,
            caller_function=target_function,
        )

    logger.info(
        "Constructed Petri net with %d places, %d transitions, and %d arcs.",
        len(net.places),
        len(net.transitions),
        len(net.arcs),
    )

    fold_result: Optional[FoldResult] = None
    if fold_active:
        fold_config: FoldConfig
        if weights is not None:
            if isinstance(weights, FoldConfig):
                fold_config = weights
            else:
                fold_config = FoldConfig.load(weights)
        else:
            fold_config = FoldConfig()

        logger.info("Executing structural fold analysis...")
        fold_result = fold_net(net, config=fold_config)
        sys.stderr.write(f"Code2Petri: SM score = {fold_result.final_sm}\n")
        sys.stderr.flush()

    if output_file:
        logger.debug("Writing serialized net to format '.%s' at '%s'...", ext, output_file)
        if ext in IMAGE_EXTENSIONS:
            dot_content = fold_result.to_dot() if (fold_active and fold_result is not None) else net.to_dot()
            _render_dot_to_image(dot_content, ext, output_file)
        else:
            model_to_serialize = fold_result if (fold_active and fold_result is not None) else net
            serializer_kwargs = {}
            if ext == "html":
                serializer_kwargs["source_file"] = source_path
                serializer_kwargs["function_name"] = target_function
                serializer_kwargs["return_metadata"] = walk_res.return_metadata
                if symbol_table is not None:
                    serializer_kwargs["callee_nets"] = precompute_callee_nets(
                        call_sites=call_sites,
                        symbol_table=symbol_table,
                        max_depth=actual_inline_depth,
                    )
            content = TEXT_SERIALIZERS[ext](model_to_serialize, **serializer_kwargs)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)

        logger.info("Wrote output file to '%s'.", output_file)

    if fold_active and fold_result is not None:
        return fold_result
    return net


def main(sys_argv: Optional[List[str]] = None) -> None:
    """CLI entry point for code2petri."""
    parser = argparse.ArgumentParser(
        prog="code2petri",
        description="Convert function control flow into Petri nets (PNML, DOT, JSON, SVG, PNG, HTML).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "source",
        help="Path to source file.",
    )
    parser.add_argument(
        "--target-function", "-t",
        help="Target function name to analyze.",
    )
    parser.add_argument(
        "--output", "-o",
        default="out.pnml",
        help="Output file path (.pnml, .dot, .gv, .json, .png, .svg, .html).",
    )
    parser.add_argument(
        "--list-functions",
        action="store_true",
        help="List all function names in the source file and exit.",
    )

    parser.add_argument(
        "--context", "-c",
        nargs="+",
        help="One or more context file or directory paths for cross-file call resolution.",
    )
    parser.add_argument(
        "--fold",
        action="store_true",
        default=False,
        help="Activate structural fold analysis on the generated Petri net.",
    )
    parser.add_argument(
        "--no-fold",
        action="store_true",
        default=False,
        help="Explicitly disable fold analysis (overrides implicit activation).",
    )
    parser.add_argument(
        "--weights",
        help="Override default FoldConfig penalty weights via a JSON file path or JSON string.",
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        default=False,
        help="Activate inline expansion of resolved call transitions (requires --context).",
    )
    parser.add_argument(
        "--inline-depth",
        type=int,
        default=None,
        help="Maximum depth for inline expansion of nested callee calls (default: unlimited for composite HTML, 1 otherwise).",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress informational logging.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable detailed debug logging.",
    )

    args = parser.parse_args(sys_argv if sys_argv is not None else sys.argv[1:])

    if args.quiet and args.verbose:
        raise AssertionError("Passed both --verbose and --quiet flags.")

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.WARNING

    logging.basicConfig(format="Code2Petri: %(message)s", level=level)

    code2petri(
        source_path=args.source,
        output_file=args.output,
        target_function=args.target_function,
        list_functions=args.list_functions,
        level=level,
        context=args.context,
        fold=args.fold,
        no_fold=args.no_fold,
        weights=args.weights,
        inline=args.inline,
        inline_depth=args.inline_depth,
    )


if __name__ == "__main__":
    main()
