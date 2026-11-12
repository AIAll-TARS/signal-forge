from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .brief import as_json, markdown
from .collect import collect_feed, ingest_url
from .scoring import Analyst
from .sources import load_sources
from .store import Store
from .server import serve


def parser():
    p = argparse.ArgumentParser(prog="signal-forge", description="Local-first biogas and biomethane intelligence")
    p.add_argument("--db", default="signal-forge.db", help="SQLite database path")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    imp = sub.add_parser("import-sources"); imp.add_argument("file")
    add = sub.add_parser("add-source"); add.add_argument("url"); add.add_argument("--name", required=True); add.add_argument("--authority", default="unknown"); add.add_argument("--topics", default=""); add.add_argument("--scan-method", default="rss")
    col = sub.add_parser("collect"); col.add_argument("--source-id", type=int); col.add_argument("--all", action="store_true")
    ing = sub.add_parser("ingest-url"); ing.add_argument("url"); ing.add_argument("--source-id", type=int); ing.add_argument("--topics", default="")
    score = sub.add_parser("score"); score.add_argument("--item-id", type=int)
    brief = sub.add_parser("brief"); brief.add_argument("--date"); brief.add_argument("--format", choices=("md", "json"), default="md")
    search = sub.add_parser("search"); search.add_argument("query"); search.add_argument("--format", choices=("md", "json"), default="md")
    serve_cmd = sub.add_parser("serve", help="Start the local Signal Forge browser cockpit")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", default=8765, type=int)
    serve_cmd.add_argument("--open", action="store_true", dest="open_browser")
    return p

def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "serve":
        serve(args.host, args.port, args.db, args.open_browser)
        return 0
    store = Store(args.db); store.init()
    try:
        if args.command == "init-db": print(f"Initialised {args.db}"); return 0
        if args.command == "import-sources":
            added = sum(store.add_source(s)[1] for s in load_sources(args.file)); store.log("import-sources", "ok", f"added={added}"); print(f"Imported {added} source(s)"); return 0
        if args.command == "add-source":
            sid, added = store.add_source({"name":args.name,"url":args.url,"authority":args.authority,"topics":[x.strip() for x in args.topics.split(",") if x.strip()],"scan_method":args.scan_method}); print(json.dumps({"id":sid,"created":added})); return 0
        if args.command == "collect":
            sources = [store.source(args.source_id)] if args.source_id else store.sources()
            if not args.all and not args.source_id: raise ValueError("Use --source-id ID or --all")
            total = 0
            for source in sources:
                if source is None: raise ValueError("Source not found")
                if source["scan_method"] not in {"rss", "atom", "feed"}:
                    print(f"Skipped source {source['id']}: unsupported scan_method={source['scan_method']}", file=sys.stderr); continue
                try:
                    for item in collect_feed(source["url"], source["id"], json.loads(source["topics"])): total += store.add_item(item)[1]
                except Exception as exc:
                    store.log("collect", "error", f"source={source['id']}: {exc}"); print(f"Source {source['id']} failed: {exc}", file=sys.stderr)
            store.log("collect", "ok", f"added={total}"); print(f"Collected {total} new item(s)"); return 0
        if args.command == "ingest-url":
            item = ingest_url(args.url, args.source_id, [x.strip() for x in args.topics.split(",") if x.strip()]); iid, added = store.add_item(item); print(json.dumps({"id":iid,"created":added})); return 0
        if args.command == "score":
            analyst, count = Analyst(), 0
            for item in store.unanalysed(args.item_id): store.save_analysis(item["id"], analyst.analyze(dict(item))); count += 1
            print(f"Scored {count} item(s)"); return 0
        rows = store.items(date=getattr(args, "date", None), query=getattr(args, "query", None))
        print(as_json(rows) if args.format == "json" else markdown(rows, getattr(args, "date", None))); return 0
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        store.log(args.command, "error", str(exc)); print(f"Error: {exc}", file=sys.stderr); return 2
    finally: store.close()

if __name__ == "__main__": raise SystemExit(main())
