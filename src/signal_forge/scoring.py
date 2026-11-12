"""Transparent deterministic analyst. Replace Analyst.analyze with an LLM implementation later."""
from __future__ import annotations

KEYWORDS = {
 "policy": ("regulation", "directive", "law", "permit", "permitting", "subsid", "support scheme", "red iii", "auction", "taryf", "ustaw", "rozporządzen"),
 "market": ("price", "pricing", "certificate", "gas market", "carbon", "feedstock", "econom", "revenue", "cost"),
 "project": ("project", "plant", "acquisition", "financing", "funding", "investment", "offtake", "tender", "partnership", "construction"),
 "grid": ("grid", "injection", "connection", "gaz-system", "pipeline", "network", "storage"),
 "core": ("biogas", "biomethane", "renewable gas", "anaerobic digestion", "upgrading"),
 "poland": ("poland", "polish", "polska", "polski", "warsaw", "warszaw"),
 "eu": ("european union", "eu ", "commission", "brussels", "europe"),
}

class Analyst:
    """Future interface: an LLM analyst can implement analyze(item) with this result shape."""
    def analyze(self, item: dict) -> dict:
        text = " ".join(str(item.get(k, "")) for k in ("title", "content", "topics", "geography")).lower()
        hits = {group: [word for word in words if word in text] for group, words in KEYWORDS.items()}
        score = 0
        score += 25 if hits["core"] else 0
        score += min(30, 10 * sum(bool(hits[g]) for g in ("policy", "market", "project", "grid")))
        score += 20 if hits["poland"] else (10 if hits["eu"] else 0)
        score += {"primary": 15, "industry": 10, "research": 10, "trade_press": 5}.get(item.get("authority"), 3)
        score = min(100, score)
        priority = "critical" if score >= 75 else "high" if score >= 50 else "watch" if score >= 25 else "background"
        confidence = "high" if item.get("authority") == "primary" and len(text) > 140 else "medium" if item.get("authority") in {"primary", "industry", "research"} else "low"
        domains = [g for g in ("policy", "market", "project", "grid") if hits[g]]
        impact = {"policy": "development timetable and eligibility", "market": "investment case", "project": "commercial strategy", "grid": "development timetable"}.get(domains[0], "market intelligence") if domains else "market intelligence"
        evidence = ", ".join(g for g in ("biomethane/biogas", "Poland", "EU", *domains) if (g != "biomethane/biogas" or hits["core"]) and (g != "Poland" or hits["poland"]) and (g != "EU" or hits["eu"])) or "limited direct investment signals"
        why = f"Signal touches {evidence}; it may affect {impact}."
        recommendation = "Review source evidence and assign an owner within one business day." if priority in {"critical", "high"} else "Track for confirmation and reassess if a concrete project, rule, or price impact emerges."
        rationale = f"score={score}; authority={item.get('authority','unknown')}; matched=" + (", ".join(domains + (["core sector"] if hits["core"] else [])) or "none")
        return {"score": score, "priority": priority, "confidence": confidence, "impact": impact, "why_it_matters": why, "recommendation": recommendation, "rationale": rationale}
