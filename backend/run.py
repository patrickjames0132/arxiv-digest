#!/usr/bin/env python3
"""CLI entry point for arXiv Atlas.

Usage:
    uv run python backend/run.py serve      # start the API + Atlas frontend
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the package importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arxiv_digest import app as app_module  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="arXiv Atlas")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="Run the Flask API + Atlas frontend")

    # Phase 3d — bring-your-own sources (local semantic library).
    p_ingest = sub.add_parser("ingest", help="Ingest a PDF file or URL into the source library")
    p_ingest.add_argument("target", help="Path to a PDF, or an http(s) URL")
    p_ingest.add_argument("--title", help="Override the source title")

    sub.add_parser("sources", help="List sources in the library")

    p_search = sub.add_parser("search-sources", help="Semantic search over the library")
    p_search.add_argument("query")
    p_search.add_argument("--source", help="Restrict to one source id")
    p_search.add_argument("-k", type=int, default=None, help="Number of passages")

    p_forget = sub.add_parser("forget", help="Delete a source by id")
    p_forget.add_argument("source_id")

    args = parser.parse_args()
    if args.command == "serve":
        app_module.main()
    elif args.command == "ingest":
        _cmd_ingest(args)
    elif args.command == "sources":
        _cmd_sources()
    elif args.command == "search-sources":
        _cmd_search(args)
    elif args.command == "forget":
        _cmd_forget(args)


def _cmd_ingest(args) -> None:
    from arxiv_digest import sources
    if not sources.available():
        print("Embeddings/sqlite-vec unavailable — cannot ingest.", file=sys.stderr)
        sys.exit(1)
    target = args.target
    if target.startswith(("http://", "https://")):
        src = sources.ingest_url(target, title=args.title)
    else:
        src = sources.ingest_pdf(target, title=args.title)
    pages = f", {src['pages']} pages" if src.get("pages") else ""
    print(f"Ingested [{src['kind']}] “{src['title']}” — {src['n_chunks']} chunks{pages}")
    print(f"  id: {src['id']}")


def _cmd_sources() -> None:
    from arxiv_digest import sources
    rows = sources.list_sources()
    if not rows:
        print("No sources yet. Add one with:  ingest <pdf-or-url>")
        return
    for s in rows:
        pages = f"{s['pages']}p" if s.get("pages") else "—"
        print(f"{s['id']}  [{s['kind']:3}] {pages:>5} {s['n_chunks']:>5}ch  {s['title']}")


def _cmd_search(args) -> None:
    from arxiv_digest import sources
    hits = sources.search(args.query, k=args.k, source_id=args.source)
    if not hits:
        print("No matches (library empty, or embeddings unavailable).")
        return
    for i, h in enumerate(hits, 1):
        loc = f"p.{h['page']}" if h.get("page") else "web"
        snippet = " ".join(h["text"].split())[:280]
        print(f"\n[{i}] {h['source_title']} · {loc} · dist={h['distance']:.3f}")
        print(f"    {snippet}…")


def _cmd_forget(args) -> None:
    from arxiv_digest import sources
    print("Deleted." if sources.delete_source(args.source_id) else "No such source.")


if __name__ == "__main__":
    main()
