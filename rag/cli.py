"""Command line: `rag ingest`, `rag search "question"`, and `rag eval --step step-6`."""

import argparse
import textwrap

from . import search_bm25, search_bm25_stem, search_hybrid, search_substring, search_vector
from .chunk import load_units
from .eval import score

# In-memory modes take (query, units) and work on chunks built on the fly.
MODES = {
    "substring": search_substring.search,
    "bm25": search_bm25.search,
    "bm25-stem": search_bm25_stem.search,
    "vector": search_vector.search,
    "hybrid": search_hybrid.search,
}
# Postgres modes read chunks and embeddings from the database (run `rag ingest` first).
PG_MODES = ["pg-vector", "pg-vector-exact", "pg-hybrid"]


def build(mode: str, chunking: str):
    if mode not in PG_MODES:
        return MODES[mode], load_units(chunking)
    from . import db, search_pg
    fn = {
        "pg-vector": search_pg.vector(chunking),
        "pg-vector-exact": search_pg.vector(chunking, exact=True),
        "pg-hybrid": search_pg.hybrid(chunking),
    }[mode]
    return fn, db.load_chunks(chunking)


def main():
    ap = argparse.ArgumentParser(prog="rag")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest", help="chunk, embed, and store the corpus in Postgres")
    i.add_argument("--chunking", default="r128")
    for name in ("search", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--mode", default="pg-hybrid", choices=[*MODES, *PG_MODES])
        p.add_argument("--chunking", default="r128",
                       help="'paragraph', or 'r<tokens>' such as r128 for recursive chunks")
        if name == "search":
            p.add_argument("query")
            p.add_argument("-k", type=int, default=5)
        else:
            p.add_argument("--step", required=True)
    args = ap.parse_args()

    if args.cmd == "ingest":
        from . import db
        print(db.ingest(args.chunking))
        return

    fn, units = build(args.mode, args.chunking)
    search = lambda q: fn(q, units)

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
