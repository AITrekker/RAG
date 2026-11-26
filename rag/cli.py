"""Command line: `rag search "question"` and `rag eval --step step-1`."""

import argparse
import textwrap

from . import search_bm25, search_substring
from .corpus import load_paragraphs
from .eval import score

MODES = {"substring": search_substring.search, "bm25": search_bm25.search}


def main():
    ap = argparse.ArgumentParser(prog="rag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--mode", default="bm25", choices=MODES)
    s.add_argument("-k", type=int, default=5)
    e = sub.add_parser("eval")
    e.add_argument("--step", required=True)
    e.add_argument("--mode", default="bm25", choices=MODES)
    args = ap.parse_args()

    paragraphs = load_paragraphs()
    search = lambda q: MODES[args.mode](q, paragraphs)

    if args.cmd == "search":
        results = search(args.query)
        print(f"{len(results)} matching paragraphs (showing {min(args.k, len(results))})\n")
        for p in results[:args.k]:
            print(f"[ch {p.chapter}, para {p.id}]")
            print(textwrap.indent(textwrap.fill(p.text[:400], 88), "  "), "\n")
    else:
        out = score(search, args.step, args.mode)
        for q in out["questions"]:
            mark = {True: "HIT ", False: "miss", None: "n/a "}[q["hit"]]
            print(f"{mark} {q['id']} {q['category']:<12} matches={q['n_results']:<5} "
                  f"top={q['top_chapters']}  {q['question']}")
        print("\n", out["summary"])


if __name__ == "__main__":
    main()
