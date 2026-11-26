"""Command line: `rag search "question"` and `rag eval --step step-4`."""

import argparse
import textwrap

from . import search_bm25, search_bm25_stem, search_hybrid, search_substring, search_vector
from .chunk import load_units
from .eval import score

MODES = {
    "substring": search_substring.search,
    "bm25": search_bm25.search,
    "bm25-stem": search_bm25_stem.search,
    "vector": search_vector.search,
    "hybrid": search_hybrid.search,
}


def main():
    ap = argparse.ArgumentParser(prog="rag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("search", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--mode", default="bm25", choices=MODES)
        p.add_argument("--chunking", default="paragraph",
                       help="'paragraph', or 'r<tokens>' such as r256 for recursive chunks")
        if name == "search":
            p.add_argument("query")
            p.add_argument("-k", type=int, default=5)
        else:
            p.add_argument("--step", required=True)
    args = ap.parse_args()

    units = load_units(args.chunking)
    search = lambda q: MODES[args.mode](q, units)

    if args.cmd == "search":
        results = search(args.query)
        print(f"{len(results)} matching chunks (showing {min(args.k, len(results))})\n")
        for p in results[:args.k]:
            print(f"[ch {p.chapter}, chunk {p.id}]")
            print(textwrap.indent(textwrap.fill(p.text[:400], 88), "  "), "\n")
    else:
        label = args.mode if args.chunking == "paragraph" else f"{args.mode}+{args.chunking}"
        out = score(search, args.step, label)
        for q in out["questions"]:
            mark = {True: "HIT ", False: "miss", None: "n/a "}[q["hit"]]
            print(f"{mark} {q['id']} {q['category']:<12} matches={q['n_results']:<5} "
                  f"top={q['top_chapters']}  {q['question']}")
        print("\n", out["summary"])


if __name__ == "__main__":
    main()
