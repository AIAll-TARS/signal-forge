"""Source-file import with JSON and a deliberately small YAML subset (no PyYAML needed)."""
from __future__ import annotations
import json
from pathlib import Path

from .store import canonical_url


def _value(raw: str):
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [x.strip().strip('"\'') for x in raw[1:-1].split(",") if x.strip()]
    return raw.strip('"\'')


def load_sources(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() == ".json" or text.lstrip().startswith(("{", "[")):
        data = json.loads(text)
        return data.get("sources", data) if isinstance(data, dict) else data
    sources, current, in_sources = [], None, False
    for original in text.splitlines():
        line = original.split("#", 1)[0].rstrip()
        if not line.strip(): continue
        stripped = line.strip()
        if stripped == "sources:": in_sources = True; continue
        if not in_sources: continue
        if stripped.startswith("- "):
            if current: sources.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if ":" in stripped:
                key, val = stripped.split(":", 1); current[key.strip()] = _value(val)
        elif current and ":" in stripped:
            key, val = stripped.split(":", 1); current[key.strip()] = _value(val)
    if current: sources.append(current)
    if not sources: raise ValueError("No sources found. Expected JSON or YAML with a sources: list.")
    for source in sources:
        missing = {"name", "url"} - set(source)
        if missing: raise ValueError(f"Source missing required field(s): {', '.join(sorted(missing))}")
    return sources


def is_active(source: dict) -> bool:
    value = source.get("active", True)
    if isinstance(value, bool): return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _yaml_scalar(value: str) -> str:
    if value == "" or any(char in value for char in "#[]{},\"'") or value != value.strip():
        return json.dumps(value, ensure_ascii=False)
    return value


def _topics(value) -> list:
    if isinstance(value, list): return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip().startswith("["): return json.loads(value)
    if not value: return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _normalise(source: dict) -> dict:
    return {"name": str(source["name"]).strip(), "url": canonical_url(source["url"]), "authority": source.get("authority") or "unknown", "topics": _topics(source.get("topics", [])), "scan_method": source.get("scan_method") or "rss", "active": is_active(source)}


def _block(source: dict) -> str:
    item = _normalise(source)
    lines = [f"  - name: {_yaml_scalar(item['name'])}", f"    url: {_yaml_scalar(item['url'])}", f"    authority: {_yaml_scalar(str(item['authority']))}", "    topics: [" + ", ".join(_yaml_scalar(topic) for topic in item["topics"]) + "]", f"    scan_method: {_yaml_scalar(str(item['scan_method']))}"]
    if not item["active"]: lines.append("    active: false")
    return "\n".join(lines) + "\n"


def dump_sources(path: str | Path, sources: list[dict]) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    body = "# Signal Forge source list.\n# Edit this file on its own. The collector reads it. The cockpit does not own it.\nversion: 1\nproject: Galia Green Power\nsources:\n" + "".join(_block(source) for source in sources)
    temporary = path.with_suffix(path.suffix + ".tmp"); temporary.write_text(body, encoding="utf-8"); temporary.replace(path)


def save_source(path: str | Path, source: dict) -> bool:
    """Write one source into the registry file. Returns True when the URL is new."""
    path = Path(path); item = _normalise(source)
    if not path.exists():
        dump_sources(path, [item]); return True
    current = load_sources(path)
    for existing in current:
        if canonical_url(existing["url"]) == item["url"]:
            existing.update(item); dump_sources(path, current); return False
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"): text += "\n"
    path.write_text(text + _block(item), encoding="utf-8"); return True


def ensure_registry(path: str | Path, seed: str | Path | None = None, store=None) -> Path:
    path = Path(path)
    if path.exists(): return path
    path.parent.mkdir(parents=True, exist_ok=True)
    if seed and Path(seed).exists(): path.write_text(Path(seed).read_text(encoding="utf-8"), encoding="utf-8")
    else: dump_sources(path, [])
    if store is None: return path
    known = {canonical_url(source["url"]) for source in load_sources(path)}
    extras = []
    for row in store.all_sources():
        if row["url"] in known: continue
        extras.append({"name": row["name"], "url": row["url"], "authority": row["authority"] or "unknown", "topics": _topics(row["topics"]), "scan_method": row["scan_method"], "active": bool(row["active"])})
    if extras: dump_sources(path, [_normalise(source) for source in load_sources(path)] + extras)
    return path


def sync_registry(store, path: str | Path) -> dict:
    """Make the vault source table match the registry file. The file stays the master."""
    loaded = load_sources(path); keep = set(); added = 0
    for source in loaded:
        item = _normalise(source); keep.add(item["url"]) if item["active"] else None
        _, created = store.upsert_source(item); added += int(created)
    return {"added": added, "present": len(loaded), "active": len(keep), "deactivated": store.deactivate_except(keep)}
