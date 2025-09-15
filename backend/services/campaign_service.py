from __future__ import annotations

import asyncio
import inspect
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Imports "souples" (DB et modèles SQLAlchemy optionnels)
# ---------------------------------------------------------------------------
try:
    from ..db import get_session as _get_session
except Exception:
    _get_session = None

try:
    from ..models import Campaign  # Modèle SQLAlchemy éventuel
except Exception:
    Campaign = None

# ---------------------------------------------------------------------------
# Schémas Pydantic (on s’adapte à ta base de code : CampaignCreate ou CampaignIn)
# ---------------------------------------------------------------------------
try:
    # ex: schema.py définit CampaignCreate, CampaignOut
    from ..schema import CampaignCreate as CampaignIn
except Exception:
    try:
        from ..schema import CampaignIn  # fallback au nom classique
    except Exception:
        from pydantic import BaseModel

        class CampaignIn(BaseModel):  # dernier fallback
            company_id: int
            prompts: List[str]
            runs_per_prompt: int = 1
            model: str = "llama3.2:1b-instruct"

try:
    from ..schema import CampaignOut  # on réutilise ton CampaignOut
except Exception:
    from pydantic import BaseModel

    class CampaignOut(BaseModel):  # petit fallback
        id: int
        status: str = "queued"
        total_runs: int = 0
        completed_runs: int = 0
        visibility: float = 0.0


# ---------------------------------------------------------------------------
# Wrapper pour utiliser get_session() (générateur FastAPI) en context-manager
# ---------------------------------------------------------------------------
@contextmanager
def db_session():
    """
    Permet d'écrire :  with db_session() as s:
    même si get_session() est un générateur FastAPI.
    """
    if _get_session is None:
        yield None
        return
    gen = _get_session()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


# ---------------------------------------------------------------------------
# SSE : publish peut être sync OU async → on passe par _emit()
# ---------------------------------------------------------------------------
try:
    from ..utils.progress import publish  # peut être sync ou async, ou absent
except Exception:
    async def publish(campaign_id: int, event: Dict[str, Any]) -> None:
        # no-op si pas d'infra SSE
        return None


async def _emit(campaign_id: int, event: Dict[str, Any]) -> None:
    """
    Appelle publish() quelle que soit sa nature (sync/async).
    Évite le 'await publish(...)' direct qui plante si publish est sync.
    """
    try:
        result = publish(campaign_id, event)
        if inspect.isawaitable(result):
            await result
    except Exception:
        # on ignore les erreurs SSE pour ne pas casser le worker
        pass


# ---------------------------------------------------------------------------
# Mémoire (fallback) pour suivre l'état d'une campagne sans DB/colonnes dédiées
# ---------------------------------------------------------------------------
_mem: Dict[int, Dict[str, Any]] = {}
_mem_id_counter: int = 0


def _mem_next_id() -> int:
    global _mem_id_counter
    _mem_id_counter += 1
    return _mem_id_counter


# ---------------------------------------------------------------------------
# Worker simulé (remplace par ta queue si besoin)
# ---------------------------------------------------------------------------

import random



async def _simulate_worker(campaign_id: int, prompts: list[str], runs_per_prompt: int) -> None:
    total = len(prompts) * max(runs_per_prompt, 1)
    completed = 0
    hits = 0  # <= nombre de runs où la marque est détectée

    await publish(campaign_id, {"type": "status", "status": "running", "total": total, "completed": completed})

    for i, p in enumerate(prompts, start=1):
        for j in range(1, runs_per_prompt + 1):
            # Simule le temps de génération
            await asyncio.sleep(0.4)

            # --- ICI: logique de "détection de marque" (simulée) ---
            # Remplace ça par ta vraie logique (LLM + fuzzy matching).
            # Ici on simule une mention ~40% du temps.
            generated_text = f"Run {i}-{j} result"
            mentions_brand = random.random() < 0.4
            if mentions_brand:
                hits += 1

            # Émet une ligne exportable (utile pour le CSV/front)
            await publish(
                campaign_id,
                {
                    "type": "row",
                    "run": f"{i}-{j}",
                    "prompt": p,
                    "text": generated_text + (" (ACME mentionnée)" if mentions_brand else ""),
                    "mentions_brand": mentions_brand,
                },
            )

            completed += 1
            await publish(campaign_id, {"type": "progress", "completed": completed, "total": total})

    visibility = round((hits / total) * 100.0, 2) if total else 0.0
    await publish(
        campaign_id,
        {"type": "done", "completed": completed, "total": total, "hits": hits, "visibility": visibility},
    )


    # Optionnel : si tu veux aussi refléter l'état en DB (si colonnes présentes)
    if Campaign is not None and _get_session is not None:
        with db_session() as s:
            if s is None:
                return
            obj = s.get(Campaign, campaign_id)
            if obj is not None:
                if hasattr(Campaign, "status"):
                    setattr(obj, "status", "done")
                if hasattr(Campaign, "completed_runs"):
                    setattr(obj, "completed_runs", completed)
                if hasattr(Campaign, "visibility"):
                    setattr(obj, "visibility", visibility)
                s.add(obj)
                s.commit()


# ---------------------------------------------------------------------------
# Services : create, start_async, get_by_id
# ---------------------------------------------------------------------------
async def create_campaign(payload: CampaignIn) -> CampaignOut:
    """
    Crée la campagne. Utilise la DB si dispo, sinon fallback mémoire.
    Ne suppose PAS l'existence des colonnes (total_runs, completed_runs, visibility).
    """
    prompts = getattr(payload, "prompts", []) or []
    runs_per_prompt = int(getattr(payload, "runs_per_prompt", 1) or 1)
    model = getattr(payload, "model", "llama3.2:1b-instruct")
    company_id = int(getattr(payload, "company_id"))

    total_runs = len(prompts) * max(1, runs_per_prompt)

    # 1) Si DB dispo, on insère une ligne minimale (seulement colonnes existantes)
    if Campaign is not None and _get_session is not None:
        with db_session() as s:
            if s is not None:
                obj = Campaign(company_id=company_id)
                # on ne set que si la colonne existe côté modèle SQLAlchemy
                if hasattr(Campaign, "status"):
                    setattr(obj, "status", "queued")
                if hasattr(Campaign, "model"):
                    setattr(obj, "model", model)
                # ces colonnes ne sont peut-être PAS dans ton modèle → on vérifie
                if hasattr(Campaign, "total_runs"):
                    setattr(obj, "total_runs", total_runs)
                if hasattr(Campaign, "completed_runs"):
                    setattr(obj, "completed_runs", 0)
                if hasattr(Campaign, "visibility"):
                    setattr(obj, "visibility", 0.0)

                s.add(obj)
                s.commit()
                s.refresh(obj)
                cid = int(getattr(obj, "id"))
            else:
                cid = _mem_next_id()
    else:
        cid = _mem_next_id()

    # 2) Mémorise l'état initial en mémoire (toujours)
    _mem[cid] = {
        "status": "queued",
        "total_runs": total_runs,
        "completed_runs": 0,
        "visibility": 0.0,
        "model": model,
        "company_id": company_id,
        "prompts": list(prompts),
        "runs_per_prompt": runs_per_prompt,
    }

    return CampaignOut(
        id=cid,
        status="queued",
        total_runs=total_runs,
        completed_runs=0,
        visibility=0.0,
    )


async def start_campaign_async(campaign_id: int, prompts: List[str], runs_per_prompt: int) -> None:
    """
    Met la campagne à 'running' (DB si possible) puis lance le worker async.
    """
    # DB → passe en "running" si la colonne existe
    if Campaign is not None and _get_session is not None:
        with db_session() as s:
            if s is not None:
                obj = s.get(Campaign, campaign_id)
                if obj is not None and hasattr(Campaign, "status"):
                    setattr(obj, "status", "running")
                    s.add(obj)
                    s.commit()

    # mémoire
    _mem.setdefault(campaign_id, {})
    _mem[campaign_id].update({"status": "running"})
    # lance le worker simulé
    asyncio.create_task(_simulate_worker(campaign_id, prompts, runs_per_prompt))


async def get_campaign_by_id(campaign_id: int) -> CampaignOut:
    """
    Récupère l'état courant. Priorité à la mémoire pour les compteurs temps-réel.
    """
    state = _mem.get(campaign_id)
    if state:
        return CampaignOut(
            id=campaign_id,
            status=state.get("status", "queued"),
            total_runs=int(state.get("total_runs", 0) or 0),
            completed_runs=int(state.get("completed_runs", 0) or 0),
            visibility=float(state.get("visibility", 0.0) or 0.0),
        )

    # Si pas en mémoire, on tente la DB (au moins pour confirmer l'existence)
    if Campaign is not None and _get_session is not None:
        with db_session() as s:
            if s is None:
                return CampaignOut(id=campaign_id, status="queued", total_runs=0, completed_runs=0, visibility=0.0)
            obj = s.get(Campaign, campaign_id)
            if obj is None:
                return CampaignOut(id=campaign_id, status="not_found", total_runs=0, completed_runs=0, visibility=0.0)

            # on retourne ce qu'on peut lire ; le reste à 0
            status = getattr(obj, "status", "queued")
            total_runs = int(getattr(obj, "total_runs", 0) or 0) if hasattr(Campaign, "total_runs") else 0
            completed_runs = int(getattr(obj, "completed_runs", 0) or 0) if hasattr(Campaign, "completed_runs") else 0
            visibility = float(getattr(obj, "visibility", 0.0) or 0.0) if hasattr(Campaign, "visibility") else 0.0

            return CampaignOut(
                id=campaign_id,
                status=status,
                total_runs=total_runs,
                completed_runs=completed_runs,
                visibility=visibility,
            )

    # sinon : défaut
    return CampaignOut(id=campaign_id, status="queued", total_runs=0, completed_runs=0, visibility=0.0)


__all__ = ["create_campaign", "start_campaign_async", "get_campaign_by_id"]
