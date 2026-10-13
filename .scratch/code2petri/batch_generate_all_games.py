#!/usr/bin/env python3
import os
import sys
from datetime import datetime
import time
import traceback

# Ensure repository root is in sys.path regardless of execution environment or CWD
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri.engine import code2petri
from code2petri.python_walker import PythonWalker
from code2petri.model import PetriNet
from code2petri.fold import FoldResult

GAMES_DIR = "/Volumes/SharedDrive/Documents/GitHub/Python-Games"
GRAPHS_BASE = "/Volumes/SharedDrive/Documents/GitHub/code2flow/.scratch/code2petri/graphs"
DATE_SUFFIX = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%y%m%d")

GAME_GENRES = {
    "Aeroblasters": "2D Plane Shooter / Arcade",
    "Angry Walls": "Hypercasual",
    "Arc Dash": "Endless Hypercasual Arcade",
    "Asteroids": "Space Shooter / Arcade",
    "Bounce": "Platformer / Adventure",
    "Car Racing 2d": "Obstacle Dodge / Racing",
    "Cave Story": "2D Adventure Platformer",
    "Connected": "Endless Hypercasual",
    "Dino": "Endless Runner",
    "Dodgy Walls": "Endless Hypercasual Arcade",
    "Dots & Boxes": "Strategy / Board Game",
    "Egg Catching Game": "Casual Arcade",
    "Flappy Bird": "Endless Side-Scroller Arcade",
    "GhostBusters": "Platformer (Parallax Scrolling)",
    "Hangman": "Word Guessing / Puzzle",
    "Hex Dash": "Endless Hypercasual Arcade",
    "HyperTile Dash": "Endless Hypercasual Arcade",
    "Jungle Dash": "2D Platformer",
    "Level Designer": "Tool / Level Editor",
    "Memory Puzzle": "Memory Card Matching / Puzzle",
    "MineSweeper": "Puzzle / Logic",
    "Piano Tiles": "Rhythm / Music",
    "Picture Sliding Puzzle": "Sliding Tile Puzzle (15 Puzzle)",
    "Pong": "Sports / Arcade",
    "Qircle Rush": "Endless Hypercasual Arcade",
    "Rock Paper Scissor": "Casual Hand Game",
    "Rotate Dash": "Endless Hypercasual Arcade",
    "Snake": "Classic Arcade",
    "SpriteSheet Cutter": "Tool / Image Utility",
    "Tetris": "Tile-Matching Puzzle",
    "Tic Tac Toe": "Strategy / Board Game",
}

walker = PythonWalker()

def normalize_game_name(raw_name: str) -> str:
    return raw_name.replace(" ", "_").replace("&", "and")

def get_game_py_files(gdir: str):
    py_files = []
    for root, dirs, files in os.walk(gdir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "env", "__pycache__")]
        for f in files:
            if f.endswith(".py") and not f.startswith("._") and not f.startswith("."):
                py_files.append(os.path.join(root, f))
    return sorted(py_files)

def pick_entry_file(gdir: str, py_files):
    for cand in ["main.py", "game.py"]:
        matches = [f for f in py_files if os.path.basename(f) == cand]
        if matches:
            top_level = [f for f in matches if os.path.dirname(f) == gdir]
            return top_level[0] if top_level else matches[0]
    # Fallback to subfolder main/game
    for f in py_files:
        if os.path.basename(f) in ("main.py", "game.py"):
            return f
    return py_files[0] if py_files else None

def inspect_net(res):
    if isinstance(res, FoldResult):
        net = res.initial_net
        sm = res.final_sm
    elif isinstance(res, PetriNet):
        net = res
        sm = None
    else:
        return 0, 0, 0, None
    return len(net.places), len(net.transitions), len(net.arcs), sm

def process_game(game_name: str):
    t_start = time.time()
    gdir = os.path.join(GAMES_DIR, game_name)
    norm_name = normalize_game_name(game_name)
    out_dir = os.path.join(GRAPHS_BASE, f"{norm_name}-{DATE_SUFFIX}")
    os.makedirs(out_dir, exist_ok=True)

    py_files = get_game_py_files(gdir)
    if not py_files:
        print(f"Skipping {game_name}: no python files found.")
        return None

    entry_file = pick_entry_file(gdir, py_files)
    context_files = [f for f in py_files if f != entry_file]
    prefix = norm_name.lower()

    catalog_entries = []

    print(f"\n=======================================================")
    print(f"Processing: {game_name} -> {out_dir}")
    print(f"  Entry: {os.path.relpath(entry_file, gdir)}")
    print(f"  Context files: {len(context_files)}")
    print(f"=======================================================")

    # 1. Primary Global Net
    global_meta = {"name": "(global)", "file": os.path.relpath(entry_file, gdir), "formats": []}
    try:
        # HTML Foldable
        out_html = os.path.join(out_dir, f"{prefix}_global_foldable.html")
        res_html = code2petri(
            source_path=entry_file,
            target_function="(global)",
            context=context_files if context_files else None,
            output_file=out_html,
            project_title=game_name,
        )
        p_cnt, t_cnt, a_cnt, sm = inspect_net(res_html)
        global_meta["places"] = p_cnt
        global_meta["transitions"] = t_cnt
        global_meta["arcs"] = a_cnt
        global_meta["sm"] = sm
        global_meta["formats"].append(".html")

        # Visual exports
        for ext in ["dot", "svg", "png"]:
            out_v = os.path.join(out_dir, f"{prefix}_global.{ext}")
            try:
                code2petri(
                    source_path=entry_file,
                    target_function="(global)",
                    context=context_files if context_files else None,
                    output_file=out_v
                )
                global_meta["formats"].append(f".{ext}")
            except Exception as ve:
                print(f"    Warning: visual export .{ext} failed: {ve}")

        catalog_entries.append(global_meta)
        print(f"  [OK] (global): {p_cnt} places, {t_cnt} transitions, {a_cnt} arcs")
    except Exception as ge:
        print(f"  [FAIL] (global) failed: {ge}")
        traceback.print_exc()

    # 2. All functions and class methods
    seen_targets = set()
    for pyf in py_files:
        rel_pyf = os.path.relpath(pyf, gdir)
        ctx = [f for f in py_files if f != pyf]
        try:
            tree = walker.parse_file(pyf)
            funcs = walker.find_all_functions(tree)
        except Exception as pe:
            print(f"  [WARN] Could not parse {rel_pyf}: {pe}")
            continue

        for fn in funcs:
            if fn == "(global)":
                continue
            target_key = (rel_pyf, fn)
            if target_key in seen_targets:
                continue
            seen_targets.add(target_key)

            clean_fn = fn.replace(".", "_")
            # If subfolder, prefix with subfolder name to prevent collision
            sub_prefix = os.path.dirname(rel_pyf).replace("/", "_").replace("\\", "_")
            if sub_prefix:
                base_fname = f"{sub_prefix}_{clean_fn}"
            else:
                base_fname = clean_fn

            f_meta = {"name": fn, "file": rel_pyf, "formats": []}
            try:
                out_html = os.path.join(out_dir, f"{base_fname}_foldable.html")
                res = code2petri(
                    source_path=pyf,
                    target_function=fn,
                    context=ctx if ctx else None,
                    output_file=out_html,
                    project_title=game_name,
                )
                p_cnt, t_cnt, a_cnt, sm = inspect_net(res)
                f_meta["places"] = p_cnt
                f_meta["transitions"] = t_cnt
                f_meta["arcs"] = a_cnt
                f_meta["sm"] = sm
                f_meta["formats"].append(".html")

                for ext in ["dot", "svg", "png"]:
                    out_v = os.path.join(out_dir, f"{base_fname}.{ext}")
                    try:
                        code2petri(
                            source_path=pyf,
                            target_function=fn,
                            context=ctx if ctx else None,
                            output_file=out_v
                        )
                        f_meta["formats"].append(f".{ext}")
                    except Exception:
                        pass

                catalog_entries.append(f_meta)
                print(f"  [OK] {fn} ({rel_pyf}): {p_cnt}P, {t_cnt}T, {a_cnt}A")
            except Exception as fe:
                print(f"  [WARN] Failed {fn} in {rel_pyf}: {fe}")

    # 3. Generate README.md
    readme_path = os.path.join(out_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as rf:
        rf.write(f"# {game_name} — Petri Net & Structural Complexity Analysis ({DATE_SUFFIX})\n\n")
        rf.write(f"This directory contains the Petri net models, visual graphs, and Phase 2.8 interactive foldable HTML viewers generated by `code2petri` for [`{game_name}`](file://{gdir}).\n\n")
        rf.write(f"Output folder: [`{out_dir}`](file://{out_dir})\n\n")
        rf.write("## Catalog of Analyzed Components\n\n")
        rf.write("| Component / Function | Source File | Places | Transitions | Arcs | SM Score | Formats |\n")
        rf.write("|---|---|:---:|:---:|:---:|:---:|---|\n")
        for ent in catalog_entries:
            sm_str = f"{ent.get('sm'):.2f}" if ent.get('sm') is not None else "—"
            fmts_str = ", ".join(ent.get("formats", []))
            rf.write(f"| **`{ent['name']}`** | `{ent['file']}` | {ent.get('places', 0)} | {ent.get('transitions', 0)} | {ent.get('arcs', 0)} | {sm_str} | {fmts_str} |\n")
        rf.write("\n---\n")
        rf.write("## Reproduction Command\n\n")
        rf.write("```bash\n")
        rf.write(f'code2petri "{entry_file}" -t "(global)" ')
        if context_files:
            rf.write(f'--context "{" ".join(context_files)}" ')
        rf.write(f'-o "{os.path.join(out_dir, f"{prefix}_global_foldable.html")}"\n')
        rf.write("```\n")

    t_elapsed = time.time() - t_start
    print(f"Finished {game_name} in {t_elapsed:.2f}s ({len(catalog_entries)} components, {len(os.listdir(out_dir))} files created)")

    return {
        "game_name": game_name,
        "norm_name": norm_name,
        "out_dir": out_dir,
        "components_count": len(catalog_entries),
        "files_count": len(os.listdir(out_dir)),
        "global_places": catalog_entries[0].get("places", 0) if catalog_entries else 0,
        "global_transitions": catalog_entries[0].get("transitions", 0) if catalog_entries else 0,
        "global_arcs": catalog_entries[0].get("arcs", 0) if catalog_entries else 0,
        "global_sm": catalog_entries[0].get("sm") if catalog_entries else None,
        "time_s": t_elapsed
    }

def main():
    games = sorted([
        d for d in os.listdir(GAMES_DIR)
        if os.path.isdir(os.path.join(GAMES_DIR, d)) and not d.startswith(".")
    ])
    print(f"Found {len(games)} games in {GAMES_DIR}")

    summary_list = []
    total_start = time.time()

    for i, g in enumerate(games, 1):
        print(f"\n>>> [{i}/{len(games)}] STARTING {g} <<<")
        info = process_game(g)
        if info:
            summary_list.append(info)

    total_time = time.time() - total_start

    # Master Catalog
    master_catalog_path = os.path.join(GRAPHS_BASE, f"Python_Games_Catalog_{DATE_SUFFIX}.md")
    with open(master_catalog_path, "w", encoding="utf-8") as mf:
        mf.write(f"# Python Games — Petri Net Complexity Catalog ({DATE_SUFFIX})\n\n")
        mf.write(f"Batch generation completed on **{len(summary_list)} games** from [`Python-Games`](file://{GAMES_DIR}) using the Phase 2.8 live foldable `code2petri` tool.\n\n")
        mf.write(f"Total processing time: **{total_time:.2f} seconds** ({total_time/60:.2f} minutes).\n\n")
        mf.write("| # | Game Name | Genre | Folder | Components | Global Places | Global Trans | Global Arcs | Global SM | Time (s) |\n")
        mf.write("|---|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|\n")
        for idx, s in enumerate(summary_list, 1):
            sm_val = f"{s['global_sm']:.2f}" if s['global_sm'] is not None else "—"
            genre_val = GAME_GENRES.get(s['game_name'], "Arcade / Casual")
            mf.write(f"| {idx} | **{s['game_name']}** | {genre_val} | [`{os.path.basename(s['out_dir'])}`](file://{s['out_dir']}) | {s['components_count']} | {s['global_places']} | {s['global_transitions']} | {s['global_arcs']} | {sm_val} | {s['time_s']:.1f} |\n")

    print(f"\n=======================================================")
    print(f"🎉 ALL {len(summary_list)} GAMES PROCESSED SUCCESSFULLY!")
    print(f"Master Catalog: {master_catalog_path}")
    print(f"Total time: {total_time:.2f}s")
    print(f"=======================================================")

if __name__ == "__main__":
    main()
