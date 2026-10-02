#!/usr/bin/env python3
"""
Phase 2.7 Prototype Runner: Live Fold Reduction
One-command script to launch and inspect the interactive prototype.

Usage:
    python3 run_prototype.py           # Starts local server and opens browser
    python3 run_prototype.py --check   # Runs self-check validation and exits
    python3 run_prototype.py --port 8888 --no-browser
"""

import argparse
import functools
import http.server
import os
import socketserver
import sys
import time
import urllib.request
import webbrowser

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PROTOTYPE_DIR = os.path.join(REPO_ROOT, "code2petri", "viewer", "prototype")
ENGINE_DIR = os.path.join(REPO_ROOT, "code2petri", "viewer", "engine")
VENDOR_DIR = os.path.join(REPO_ROOT, "code2petri", "viewer", "vendor")
PROTOTYPE_HTML = os.path.join(PROTOTYPE_DIR, "index.html")


def validate_prototype_files() -> bool:
    """Verifies all required files for the prototype exist."""
    required_files = [
        PROTOTYPE_HTML,
        os.path.join(ENGINE_DIR, "reduction_engine.js"),
        os.path.join(ENGINE_DIR, "pnml_exporter.js"),
        os.path.join(PROTOTYPE_DIR, "sample_data.js"),
        os.path.join(VENDOR_DIR, "cytoscape.min.js"),
        os.path.join(VENDOR_DIR, "dagre.min.js"),
        os.path.join(VENDOR_DIR, "cytoscape-dagre.js"),
    ]
    all_ok = True
    for fpath in required_files:
        if not os.path.exists(fpath):
            print(f"  [FAIL] Missing required file: {fpath}", file=sys.stderr)
            all_ok = False
        else:
            print(f"  [OK] Found {os.path.relpath(fpath, REPO_ROOT)}")
    return all_ok


def run_check(port: int = 8089) -> int:
    """Performs a non-blocking automated verification of the prototype."""
    print("==================================================")
    print(" Running Phase 2.7 Prototype Automated Check...")
    print("==================================================")

    if not validate_prototype_files():
        return 1

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=REPO_ROOT)
    # Find free port if 8089 in use
    test_port = port
    for offset in range(10):
        try:
            with socketserver.TCPServer(("", test_port + offset), handler) as httpd:
                server_port = test_port + offset
                print(f"  [OK] Server bind successful on port {server_port}")
                break
        except OSError:
            continue
    else:
        print("  [FAIL] Could not bind any test port.", file=sys.stderr)
        return 1

    print("  [SUCCESS] All prototype assets and server checks passed.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run Phase 2.7 Live Fold Reduction Prototype")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind server (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Do not launch default browser")
    parser.add_argument("--check", action="store_true", help="Run automated file and asset check and exit")
    args = parser.parse_args()

    if args.check:
        sys.exit(run_check(args.port))

    if not validate_prototype_files():
        sys.exit(1)

    port = args.port
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=REPO_ROOT)

    try:
        httpd = socketserver.TCPServer(("", port), handler)
    except OSError:
        print(f"Port {port} in use, trying {port + 1}...")
        port += 1
        httpd = socketserver.TCPServer(("", port), handler)

    url = f"http://localhost:{port}/code2petri/viewer/prototype/index.html"

    print("\n" + "=" * 60)
    print(" 🚀 Phase 2.7 Live Fold Reduction Interactive Prototype")
    print("=" * 60)
    print(f" Prototype URL: {url}")
    print(" Features:")
    print("   • Place-Centric Live Fold (left-click any intermediate place)")
    print("   • Component-Local Unfold (click folded component to reverse)")
    print("   • Collapsed Compound State (nested functions collapse to folders)")
    print("   • Component Node Renaming (live editing of transition labels)")
    print("   • Client-Side ISO/IEC PNML XML Export")
    print("   • 3 UI Variants: [A] Docked Sidebar, [B] Popover HUD, [C] Bottom Drawer")
    print("   • Switch variants using the bottom floating bar or [← / →] arrow keys")
    print("=" * 60)
    print(" Press Ctrl+C to stop the server.\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping prototype server...")
        httpd.server_close()
        print("Server stopped.")


if __name__ == "__main__":
    main()
