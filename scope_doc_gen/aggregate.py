"""Aggregate per-file summaries into a global context pack with evidence."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def aggregate_summaries(summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge file-level summaries into a global context pack.

    Simple heuristic aggregation: concatenate lists, dedupe by text, rank by naive scores.
    This is intentionally lightweight to avoid more LLM calls in the hot path.
    """
    context: Dict[str, Any] = {
        "pain_points": [],
        "risks": [],
        "effort_multipliers": [],
        "integration_notes": [],
        "unknowns": [],
        "must_read_sections": [],
        "evidence_quotes": [],
        "files": [],
    }

    seen_pp = set()
    seen_risks = set()
    seen_effort = set()
    seen_unknowns = set()
    seen_sections = set()

    for s in summaries:
        fname = s.get("filename", "")
        context["files"].append(fname)

        # Pain points
        for pp in s.get("pain_points", []) or []:
            desc = (pp.get("description") or "").strip()
            if desc and desc.lower() not in seen_pp:
                context["pain_points"].append({
                    "description": desc,
                    "severity": pp.get("severity", ""),
                    "source": fname,
                })
                seen_pp.add(desc.lower())

        # Risks
        for r in s.get("risks", []) or []:
            r = (r or "").strip()
            if r and r.lower() not in seen_risks:
                context["risks"].append({"risk": r, "source": fname})
                seen_risks.add(r.lower())

        # Effort multipliers
        for em in s.get("effort_multipliers", []) or []:
            em = (em or "").strip()
            if em and em.lower() not in seen_effort:
                context["effort_multipliers"].append({"driver": em, "source": fname})
                seen_effort.add(em.lower())

        # Unknowns
        for u in s.get("unknowns", []) or []:
            u = (u or "").strip()
            if u and u.lower() not in seen_unknowns:
                context["unknowns"].append({"unknown": u, "source": fname})
                seen_unknowns.add(u.lower())

        # Must-read sections
        for m in s.get("must_read_sections", []) or []:
            m = (m or "").strip()
            if m and m.lower() not in seen_sections:
                context["must_read_sections"].append({"section": m, "source": fname})
                seen_sections.add(m.lower())

        # Integration notes
        integ = (s.get("integration_complexity") or "").strip()
        if integ:
            context["integration_notes"].append({"note": integ, "source": fname})

        # Evidence quotes
        for q in s.get("evidence_quotes", []) or []:
            quote = q.get("quote") or ""
            if quote:
                context["evidence_quotes"].append({
                    "quote": quote,
                    "rationale": q.get("rationale", ""),
                    "approx_location": q.get("approx_location", ""),
                    "source": fname,
                })

    # Simple ranking: push high severity pain points first
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    context["pain_points"].sort(key=lambda p: severity_rank.get((p.get("severity") or "").lower(), 3))

    return context


