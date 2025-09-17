"""
Tâche d'exécution d'une campagne (RQ-friendly ou appel direct).

- Lit la campagne + prompts
- Appelle le LLM sélectionné
- Analyse (mentions, rangs Top-N, sources)
- Persiste chaque run en base
- Émet la progression via SSE (utils.progress.publish)

Usage (ex. sans RQ) :
    from backend.workers.tasks import run_campaign_async
    run_campaign_async(42)
"""
# backend/workers/tasks.py
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Campaign, CampaignPrompt, Run, RunResponse, Company
from ..utils.progress import publish_progress
from ..services.mentions import extract_mentions  # ta détection fuzzy existante

from geo_agent.models import get_llm_client
from geo_agent.config import settings


# ---------- Helpers LLM ----------
async def _call_llm_safe(prompt: str, model: Optional[str], temperature: float, retries: int) -> str:
    client = get_llm_client()  # choisi via env: LLM_PROVIDER=ollama|openai|...
    last_err: Optional[Exception] = None
    for _ in range(max(retries, 0) + 1):
        try:
            return await client.complete(
                prompt,
                model=model or settings.LLM_MODEL,
                temperature=temperature,
            )
        except Exception as e:
            last_err = e
            await asyncio.sleep(0.8)
    # Si toutes les tentatives échouent
    raise last_err if last_err else RuntimeError("LLM call failed")


def run_campaign_async(campaign_id: int) -> None:
    asyncio.run(_run_campaign(campaign_id))


# ---------- Orchestrateur principal ----------
async def _run_campaign(campaign_id: int) -> None:
    with get_session() as session:
        camp: Optional[Campaign] = session.query(Campaign).get(campaign_id)  # type: ignore
        if not camp:
            return

        camp.status = "running"
        session.commit()

        prompts: List[CampaignPrompt] = (
            session.query(CampaignPrompt).filter_by(campaign_id=campaign_id).all()
        )
        total_runs = sum(camp.runs_per_prompt for _ in prompts)
        completed = 0

        # Prépare les marques (principale + concurrents)
        brands_map = _companies_map(session, camp.company_id)  # {"ACME":[...], "Globex":[...]}
        primary = _primary_brand(session, camp.company_id)     # "ACME"

        run_level_vis: List[Dict[str, float]] = []

        for p in prompts:
            for i in range(camp.runs_per_prompt):
                # 1) Trace du run
                run = Run(campaign_id=camp.id, prompt_id=p.id, idx=i, status="running")
                session.add(run)
                session.commit()

                # 2) Appel LLM
                text = await _call_llm_safe(
                    p.text,
                    model=(camp.model or settings.LLM_MODEL),
                    temperature=(camp.temperature or settings.TEMPERATURE),
                    retries=settings.LLM_MAX_RETRIES,
                )

                # 3) Stocke la réponse brute
                session.add(RunResponse(run_id=run.id, raw_text=text))

                # 4) Détection de marques (fuzzy) -> compteur par marque
                hits = extract_mentions(text, brands_map, threshold=85)
                counter: Dict[str, int] = {b: 0 for b in brands_map.keys()}
                for brand, _score in hits:
                    counter[brand] = counter.get(brand, 0) + 1

                # 5) Visibilité pour CE run (dict brand -> ratio 0..1)
                rv = _run_visibility(counter)
                run_level_vis.append(rv)

                # 6) Progress SSE (live % pour la marque principale)
                completed += 1
                publish_progress(campaign_id, {
                    "type": "progress",
                    "completed": completed,
                    "total": total_runs,
                    "visibility_running_pct": round(100.0 * float(rv.get(primary, 0.0)), 1),
                    "last_run_visibility": {k: float(v) for k, v in rv.items()},
                })

                run.status = "done"
                session.commit()

        # 7) Visibilité finale de campagne (moyenne des parts par run)
        final_visibility = _campaign_visibility(run_level_vis)  # {"ACME":0.58,"Globex":0.42}

        camp.status = "done"
        session.commit()

        # 8) Event final SSE — clés simples pour le front
        primary_ratio = float(final_visibility.get(primary, 0.0))
        publish_progress(campaign_id, {
            "type": "done",
            "completed": completed,
            "total": total_runs,

            # --- clefs faciles à consommer côté front ---
            "visibility_ratio": primary_ratio,                          # 0..1 (marque principale)
            "visibility_pct": round(100.0 * primary_ratio, 1),          # 0..100
            "visibility": round(100.0 * primary_ratio, 1),              # rétro-compat éventuelle
            "visibility_breakdown": {k: float(v) for k, v in final_visibility.items()},  # toutes marques
        })


# ---------- Utilitaires locaux (marques & agrégations) ----------
def _companies_map(session: Session, company_id: int) -> Dict[str, List[str]]:
    """
    Construit la map des marques -> variantes pour le fuzzy.
    """
    c: Company = session.query(Company).get(company_id)  # type: ignore
    brands: Dict[str, List[str]] = {c.name: (c.variants or [])}
    for comp in (c.competitors or []):
        # concurrents: au minimum eux-mêmes comme variante
        brands.setdefault(comp, [comp])
    return brands


def _primary_brand(session: Session, company_id: int) -> str:
    c: Company = session.query(Company).get(company_id)  # type: ignore
    return c.name


def _run_visibility(counter: Dict[str, int]) -> Dict[str, float]:
    """
    Convertit un compteur de mentions en parts relatives (somme <= 1).
    """
    total = sum(counter.values())
    if total <= 0:
        return {b: 0.0 for b in counter.keys()}
    return {b: (v / total) for b, v in counter.items()}


def _campaign_visibility(rows: List[Dict[str, float]]) -> Dict[str, float]:
    """
    Agrège la visibilité campagne comme moyenne des parts par run.
    """
    if not rows:
        return {}
    agg = defaultdict(float)
    for rv in rows:
        for b, p in rv.items():
            agg[b] += p
    n = float(len(rows))
    return {b: (v / n) for b, v in agg.items()}

def run_campaign_async(campaign_id: int) -> None:
    try:
        asyncio.run(_run_campaign(campaign_id))
    except Exception as e:
        # Publie un event d’erreur pour l’UI
        from ..utils.progress import publish_progress
        publish_progress(campaign_id, {"type": "error", "message": str(e)})
        # (optionnel) log + mettre status=failed