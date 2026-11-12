from __future__ import annotations
import re
from html import unescape
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from email.utils import parsedate_to_datetime

UA = "SignalForge/0.1 (+local-first research tool)"

def fetch(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/atom+xml, application/rss+xml, text/html"})
    with urlopen(req, timeout=20) as response:
        return response.read(), response.headers.get_content_type()

def _text(element, names):
    for name in names:
        value = element.findtext(name)
        if value: return " ".join(value.split())
    return ""

def collect_feed(url: str, source_id: int, topics: list[str]) -> list[dict]:
    data, _ = fetch(url)
    root = ET.fromstring(data)
    tag = root.tag.rsplit("}", 1)[-1].lower()
    results = []
    if tag == "rss" or root.find("channel") is not None:
        entries = root.findall("./channel/item")
        for entry in entries:
            link = _text(entry, ["link"])
            if not link: continue
            date = _text(entry, ["pubDate", "date"])
            try: date = parsedate_to_datetime(date).isoformat() if date else None
            except (TypeError, ValueError): pass
            results.append({"source_id": source_id, "title": _text(entry, ["title"]) or link, "url": link, "published_at": date, "content": _text(entry, ["description", "content"]), "topics": topics})
    else:
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f"{ns}entry") + root.findall("entry"):
            link = next((e.attrib.get("href") for e in entry.findall(f"{ns}link") + entry.findall("link") if e.attrib.get("href")), None)
            if not link: continue
            results.append({"source_id": source_id, "title": _text(entry, [f"{ns}title", "title"]) or link, "url": link, "published_at": _text(entry, [f"{ns}published", f"{ns}updated", "published", "updated"]) or None, "content": _text(entry, [f"{ns}summary", f"{ns}content", "summary", "content"]), "topics": topics})
    return results

def ingest_url(url: str, source_id: int | None = None, topics: list[str] | None = None) -> dict:
    body, _ = fetch(url)
    html = body.decode("utf-8", errors="replace")
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", html, flags=re.I | re.S)
    return {"source_id": source_id, "title": unescape(title.group(1)).strip() if title else url, "url": url, "content": " ".join(unescape(text).split())[:100000], "topics": topics or []}
