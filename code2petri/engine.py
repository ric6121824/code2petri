import argparse
import logging
import os
import subprocess
import sys
from typing import Optional, List

from code2petri.javascript_walker import JavascriptWalker
from code2petri.python_walker import PythonWalker

WALKERS = {
    ".py": PythonWalker,
    ".js": JavascriptWalker,
}


IMAGE_EXTENSIONS = {"png", "svg"}
TEXT_SERIALIZERS = {
    "pnml": lambda net: net.to_pnml(),
    "dot": lambda net: net.to_dot(),
    "gv": lambda net: net.to_dot(),
    "json": lambda net: net.to_json(),
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


def code2petri(
    source_path: str,
    output_file: Optional[str] = "out.pnml",
    target_function: Optional[str] = None,
    list_functions: bool = False,
    level: Optional[int] = None,
) -> Optional[PetriNet]:
    """Generates a Petri net from a source file and writes the serialized output.

    :param source_path: Path to the source file.
    :param output_file: Destination file path (.pnml, .dot, .gv, .json, .png, .svg).
    :param target_function: Name of the function to extract and convert.
    :param list_functions: If True, prints all function names found and exits without analyzing.
    :param level: Optional logging level to set on the logger.
    :return: The generated PetriNet instance, or None if list_functions is True.
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

    lineno = getattr(func_node, "lineno", 0)
    logger.info("Analyzing function '%s' at line %d...", target_function, lineno)
    logger.debug("Walking AST node for '%s'...", target_function)
    net = walker.walk_function(func_node)
    logger.info(
        "Constructed Petri net with %d places, %d transitions, and %d arcs.",
        len(net.places),
        len(net.transitions),
        len(net.arcs),
    )

    if output_file:
        ext = os.path.splitext(output_file)[1].lstrip(".").lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise AssertionError(
                f"Unsupported output extension '.{ext}'. Supported extensions are: "
                f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        logger.debug("Writing serialized net to format '.%s' at '%s'...", ext, output_file)
        if ext in TEXT_SERIALIZERS:
            content = TEXT_SERIALIZERS[ext](net)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
        elif ext in IMAGE_EXTENSIONS:
            if not is_installed("dot") and not is_installed("dot.exe"):
                raise AssertionError(
                    "Cannot generate image because Graphviz 'dot' executable was not found on PATH. "
                    "Install Graphviz or use a text extension (.pnml, .dot, .gv, .json)."
                )
            dot_content = net.to_dot()
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

        logger.info("Wrote output file to '%s'.", output_file)

    return net


def main(sys_argv: Optional[List[str]] = None) -> None:
    """CLI entry point for code2petri."""
    parser = argparse.ArgumentParser(
        prog="code2petri",
        description="Convert function control flow into Petri nets (PNML, DOT, JSON, SVG, PNG).",
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
        help="Output file path (.pnml, .dot, .gv, .json, .png, .svg).",
    )
    parser.add_argument(
        "--list-functions",
        action="store_true",
        help="List all function names in the source file and exit.",
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
    )


if __name__ == "__main__":
    main()
