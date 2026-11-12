from __future__ import annotations
import json

def records(rows):
    return [dict(row) for row in rows]

def markdown(rows, date: str | None = None) -> str:
    label = date or "all available items"
    lines = [f"# Signal Forge briefing: {label}", ""]
    if not rows: return "\n".join(lines + ["No findings for this period."])
    for row in rows:
        r = dict(row)
        lines += [f"## [{r.get('priority') or 'unscored'}] {r['title']}", f"- Score: {r.get('score', 'unscored')} | Confidence: {r.get('confidence', 'unscored')} | Impact: {r.get('impact', 'pending analysis')}", f"- Source: {r.get('source_name') or 'direct ingest'} | {r['url']}"]
        if r.get("why_it_matters"): lines.append(f"- Why it matters: {r['why_it_matters']}")
        if r.get("recommendation"): lines.append(f"- Recommended action: {r['recommendation']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def as_json(rows): return json.dumps(records(rows), ensure_ascii=False, indent=2, default=str)
