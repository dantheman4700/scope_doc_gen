"""Utilities for retrieving historical scope references."""

from __future__ import annotations

import statistics
from typing import List, Optional
from uuid import UUID

from ..services.vector_store import VectorStore
from .history_profiles import ProfileEmbedder


def _safe_median(values: List[float]) -> Optional[float]:
    data = [v for v in values if v is not None]
    if not data:
        return None
    return statistics.median(data)


def _safe_iqr(values: List[float]) -> Optional[tuple[float, float]]:
    data = sorted(v for v in values if v is not None)
    if len(data) < 2:
        return None
    q1 = statistics.quantiles(data, n=4)[0]
    q3 = statistics.quantiles(data, n=4)[-1]
    return (q1, q3)


def build_query_profile(instructions_doc: Optional[dict], context_pack: dict) -> str:
    parts: List[str] = []
    if instructions_doc and instructions_doc.get('content'):
        parts.append("Instructions:\n" + instructions_doc['content'][:800])
    pain_points = context_pack.get('pain_points') or []
    if pain_points:
        top_pp = ", ".join(pp.get('description', '') for pp in pain_points[:3])
        if top_pp:
            parts.append("Key pain points: " + top_pp)
    integration_notes = context_pack.get('integration_notes') or []
    if integration_notes:
        top_integ = ", ".join(note.get('note', '') for note in integration_notes[:3])
        if top_integ:
            parts.append("Integrations: " + top_integ)
    effort = context_pack.get('effort_multipliers') or []
    if effort:
        parts.append("Effort drivers: " + ", ".join(e.get('driver', '') for e in effort[:3]))
    return " | ".join(p for p in parts if p)


def format_reference_block(results: List[dict]) -> Optional[str]:
    if not results:
        return None

    hours_vals = [r.get('hours_total') for r in results if r.get('hours_total') is not None]
    weeks_vals = [r.get('timeline_weeks') for r in results if r.get('timeline_weeks') is not None]
    milestones_vals = [r.get('milestone_count') for r in results if r.get('milestone_count') is not None]
    setup_cost_vals = [r.get('total_setup_cost') for r in results if r.get('total_setup_cost') is not None]
    monthly_cost_vals = [r.get('monthly_operating_cost') for r in results if r.get('monthly_operating_cost') is not None]

    lines: List[str] = []
    lines.append(f"TOTAL_MATCHES: {len(results)}")

    if hours_vals:
        med = _safe_median(hours_vals)
        iqr = _safe_iqr(hours_vals)
        hours_line = f"Hours median: {med:.1f}" if med is not None else "Hours median: n/a"
        if iqr:
            hours_line += f" (IQR {iqr[0]:.1f}-{iqr[1]:.1f})"
        lines.append(hours_line)
    if weeks_vals:
        med = _safe_median(weeks_vals)
        iqr = _safe_iqr(weeks_vals)
        weeks_line = f"Timeline weeks median: {med:.1f}" if med is not None else "Timeline weeks median: n/a"
        if iqr:
            weeks_line += f" (IQR {iqr[0]:.1f}-{iqr[1]:.1f})"
        lines.append(weeks_line)
    if milestones_vals:
        med = _safe_median(milestones_vals)
        iqr = _safe_iqr(milestones_vals)
        milestones_line = (
            f"Milestones median: {med:.1f}" if med is not None else "Milestones median: n/a"
        )
        if iqr:
            milestones_line += f" (IQR {iqr[0]:.1f}-{iqr[1]:.1f})"
        lines.append(milestones_line)
    if setup_cost_vals:
        med = _safe_median(setup_cost_vals)
        setup_line = f"Setup cost median: ${med:,.0f}" if med is not None else "Setup cost median: n/a"
        lines.append(setup_line)
    if monthly_cost_vals:
        med = _safe_median(monthly_cost_vals)
        monthly_line = f"Monthly cost median: ${med:,.0f}" if med is not None else "Monthly cost median: n/a"
        lines.append(monthly_line)

    services_counter = {}
    for r in results:
        services = r.get('services') or []
        for svc in services:
            services_counter[svc] = services_counter.get(svc, 0) + 1
    if services_counter:
        top_services = sorted(services_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        lines.append("Common services: " + ", ".join(f"{svc} ({count})" for svc, count in top_services))

    sample_lines = []
    for ref in results[:3]:
        text = ref.get('profile_text') or ''
        similarity = ref.get('similarity')
        snippet = text[:200].replace('\n', ' ')
        if similarity is not None:
            sample_lines.append(f"- Similarity {similarity:.2f}: {snippet}")
        else:
            sample_lines.append(f"- {snippet}")
    if sample_lines:
        lines.append("Sample references:")
        lines.extend(sample_lines)

    return "REFERENCE_ESTIMATES:\n" + "\n".join(lines)


class HistoryRetriever:
    def __init__(
        self,
        dsn: str,
        model_name: str,
        top_n: int = 12,
        min_similarity: float = 0.2,
        extractor: Optional[object] = None,
    ) -> None:
        self.embedder = ProfileEmbedder(model_name)
        self.top_n = top_n
        self.min_similarity = min_similarity
        self.extractor = extractor
        # For OpenAI embeddings we know the dimensions
        embedding_dim = getattr(self.embedder, "dim", None) or 1536
        self.vector_store = VectorStore(dsn, embedding_dim=embedding_dim)
        self.vector_store.ensure_schema()

    def fetch_reference_block(
        self,
        context_pack: dict,
    ) -> Optional[str]:
        # Build a deterministic, token-only query phrase from context pack
        integrations = []
        for note in (context_pack.get('integration_notes') or []):
            val = (note.get('note') or '').strip()
            if val:
                integrations.append(val)
        services = []  # not present in context pack; left empty
        parts = []
        if integrations:
            parts.append("integrations:" + ",".join(integrations[:5]))
        # Optionally reflect effort focus
        parts.append("project_type:automation_scope")
        query_profile = " | ".join(parts) if parts else "project_type:automation_scope"
        if not query_profile:
            return None
        # Avoid backslashes in f-string expressions on Python 3.8
        _qp_preview = query_profile[:200].replace("\n", " ")
        print(f"[INFO] History query profile (first 200 chars): {_qp_preview}")
        embedding = self.embedder.embed(query_profile)
        
        # Search for historical scopes (project_id=None for global historical records)
        vector_results = self.vector_store.similarity_search(
            embedding=list(embedding),
            top_k=self.top_n,
            project_id=None,
        )
        
        # Convert VectorRecord results to the format expected by format_reference_block
        results = []
        for record in vector_results:
            metadata = record.metadata or {}
            # VectorStore uses cosine distance, convert to similarity
            similarity = 1 - record.similarity if record.similarity is not None else None
            results.append({
                "scope_id": str(record.id),
                "profile_text": metadata.get("profile_text"),
                "distance": record.similarity,
                "similarity": similarity,
                "hours_total": metadata.get("hours_total"),
                "timeline_weeks": metadata.get("timeline_weeks"),
                "milestone_count": metadata.get("milestone_count"),
                "services": metadata.get("services"),
                "tags": metadata.get("tags"),
                "dev_hours": metadata.get("dev_hours"),
                "training_hours": metadata.get("training_hours"),
                "pm_hours": metadata.get("pm_hours"),
                "total_setup_cost": metadata.get("total_setup_cost"),
                "monthly_operating_cost": metadata.get("monthly_operating_cost"),
                "automation_outputs": metadata.get("automation_outputs"),
                "client_name": metadata.get("client_name"),
                "project_name": metadata.get("project_name"),
                "industry": metadata.get("industry"),
                "project_type": metadata.get("project_type"),
                "title": metadata.get("title"),
            })
        
        print(f"[INFO] History raw matches: {len(results)}")
        if results:
            preview = ", ".join(
                [
                    f"d={r.get('distance'):.3f}|sim={r.get('similarity'):.3f}|title={(r.get('title') or 'n/a')[:40]}|services={','.join((r.get('services') or [])[:3])}"
                    for r in results[:3]
                    if r.get('distance') is not None
                ]
            )
            if preview:
                print(f"[INFO] Top distances: {preview}")
        survivors = [r for r in results if (r.get('similarity') or 0) >= self.min_similarity]
        print(f"[INFO] History survivors after min_sim {self.min_similarity}: {len(survivors)}")
        block = format_reference_block(survivors if survivors else results)
        if block:
            print("[OK] Loaded reference estimates from historical scopes")
        else:
            print("[WARN] No historical references available")
        return block

