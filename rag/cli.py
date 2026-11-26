"""Command line: `rag ingest`, `rag search`, `rag eval`, `rag ask`, and `rag answer-eval`."""

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
PG_MODES = ["pg-vector", "pg-vector-exact", "pg-hybrid",
            "pg-hybrid-hyde", "pg-hybrid-rerank", "pg-hybrid-hyde-rerank"]


def build(mode: str, chunking: str):
    if mode not in PG_MODES:
        return MODES[mode], load_units(chunking)
    from . import db, search_pg
    if mode.startswith("pg-hybrid-"):  # steps 10 and 11
        from .search_advanced import make
        return make(chunking, hyde="hyde" in mode, rerank_top="rerank" in mode), db.load_chunks(chunking)
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
    sub.add_parser("ingest-books", help="chunk, embed, and store the children's books (r128)")
    sub.add_parser("books", help="list the books in the library")
    sub.add_parser("summarize", help="write a summary of every chapter with Qwen")
    c = sub.add_parser("contextualize", help="write a contextual header for every chunk with Qwen")
    c.add_argument("--chunking", default="r128")
    for name in ("search", "eval", "ask", "answer-eval", "grade"):
        p = sub.add_parser(name)
        p.add_argument("--mode", default="pg-hybrid", choices=[*MODES, *PG_MODES])
        p.add_argument("--chunking", default="r128",
                       help="'paragraph', or 'r<tokens>' such as r128 for recursive chunks")
        if name in ("ask", "answer-eval", "grade"):
            p.add_argument("--window", type=int, default=2,
                           help="widen each retrieved chunk by this many neighbors for the generator")
        if name in ("search", "ask"):
            p.add_argument("query")
            p.add_argument("-k", type=int, default=5)
            p.add_argument("--moby-only", action="store_true",
                           help="search Moby-Dick alone with --mode (the eval setup)")
            p.add_argument("--book", help="limit the library search to one book, such as peter-pan")
        else:
            p.add_argument("--step", required=True)
    args = ap.parse_args()

    if args.cmd == "ingest-books":
        from . import db
        from .books import BOOK_DIR, BOOKS, book_units
        for slug in BOOKS:
            print(db.ingest_units(BOOK_DIR / f"{slug}.txt", book_units(slug), "r128"))
        print(db.ingest("r128"))
        return
    if args.cmd == "books":
        from . import db
        from .books import TITLES
        for slug, n in db.library_books():
            print(f"{slug:<28} {n:>5} chunks  {TITLES.get(slug, slug)}")
        return
    if args.cmd == "summarize":
        from .summarize import run
        print(run())
        return
    if args.cmd == "contextualize":
        from .contextualize import run
        print(run(args.chunking))
        return
    if args.cmd == "ingest":
        from . import db
        print(db.ingest(args.chunking))
        return

    if args.cmd == "grade":
        from .answer_eval import grade
        label = args.mode if args.chunking == "paragraph" else f"{args.mode}+{args.chunking}"
        label += f"+w{args.window}" if args.window else ""
        print(grade(args.step, label)["summary"])
        return

    library_mode = args.cmd in ("search", "ask") and not args.moby_only
    if library_mode:  # search and ask default to the whole library
        from . import db, search_pg
        fn, units = search_pg.library("r128", args.book), db.load_library("r128", args.book)
    else:
        fn, units = build(args.mode, args.chunking)
    search = lambda q: fn(q, units)

    if args.cmd == "ask":
        from .generate import chat, citations, expand, library_messages, messages_for, select_context
        context = expand(select_context(search(args.query)), units, args.window)
        answer = chat((library_messages if library_mode else messages_for)(args.query, context))
        print(answer, "\n")
        for i, p in enumerate(context, 1):
            mark = "*" if p in citations(answer, context) else " "
            print(f"{mark}[{i}] ch {p.chapter}: {p.text[:100]}...")
        return
    if args.cmd == "answer-eval":
        from .answer_eval import run
        label = args.mode if args.chunking == "paragraph" else f"{args.mode}+{args.chunking}"
        label += f"+w{args.window}" if args.window else ""
        out = run(search, args.step, label, units, args.window)
        for q in out["questions"]:
            print(f"{q['id']} ctx={str(q['in_context']):<5} cites_gold={str(q['cites_gold']):<5} "
                  f"abstain={str(q['abstained']):<5} {q['answer'][:110]!r}")
        print("\n", out["summary"])
        return
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
