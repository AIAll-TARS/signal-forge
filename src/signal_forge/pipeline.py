"""One collect pass, and the collector loop that repeats it."""
from __future__ import annotations

import json
import sys
import time

from .collect import collect_feed
from .scoring import Analyst
from .sources import sync_registry

FEEDS = {"rss", "atom", "feed"}


def _topics(value) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    return json.loads(value)


def run_collect(store) -> dict:
    """Fetch active feeds once. Web pages are counted and skipped."""
    added = scored = skipped = 0
    errors = []
    analyst = Analyst()
    for source in store.sources():
        if source["scan_method"] not in FEEDS:
            skipped += 1
            continue
        try:
            for item in collect_feed(source["url"], source["id"], _topics(source["topics"])):
                item_id, is_new = store.add_item(item)
                added += is_new
                if is_new:
                    store.save_analysis(item_id, analyst.analyze({**item, "authority": source["authority"]}))
                    scored += 1
        except Exception as exc:
            errors.append(f"{source['name']}: {exc}")
    store.log("collect", "ok" if not errors else "error", f"added={added}; scored={scored}; skipped={skipped}; errors={len(errors)}")
    return {"added": added, "scored": scored, "skipped": skipped, "errors": errors}


def watch_once(store, path) -> dict:
    sync = sync_registry(store, path)
    result = run_collect(store)
    detail = f"sources={sync['active']}; added={result['added']}; scored={result['scored']}; skipped={result['skipped']}; errors={len(result['errors'])}"
    store.log("watch", "ok" if not result["errors"] else "error", detail)
    return {**result, "sync": sync}


def watch(store, path, interval: int) -> None:
    print(f"Collector reading {path} every {interval}s.", flush=True)
    try:
        while True:
            try:
                result = watch_once(store, path)
                print(f"Watch pass: added={result['added']} scored={result['scored']} skipped={result['skipped']} errors={len(result['errors'])}", flush=True)
            except Exception as exc:
                store.log("watch", "error", str(exc))
                print(f"Watch pass failed: {exc}", file=sys.stderr, flush=True)
            time.sleep(max(int(interval), 1))
    except KeyboardInterrupt:
        print("Collector stopped.", flush=True)
