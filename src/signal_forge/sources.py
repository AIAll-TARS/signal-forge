"""Source-file import with JSON and a deliberately small YAML subset (no PyYAML needed)."""
from __future__ import annotations
import json
from pathlib import Path


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
