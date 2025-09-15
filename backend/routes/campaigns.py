# backend/routes/campaigns.py
from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any

from ..schema import CampaignIn, CampaignOut
from ..services.campaign_service import (
    create_campaign,
    get_campaign_by_id,
    start_campaign_async,
)
from ..utils.progress import sse_stream

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut)
async def create_and_start_campaign(payload: CampaignIn) -> CampaignOut:
    """
    Crée la campagne ET lance le worker tout de suite.
    """
    out = await create_campaign(payload)  # -> CampaignOut (status=queued)
    # Démarre le worker en tâche de fond
    # (start_campaign_async lance déjà un create_task en interne, donc "await" retourne tout de suite)
    await start_campaign_async(out.id, payload.prompts, payload.runs_per_prompt)
    return out


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(campaign_id: int) -> CampaignOut:
    """
    Récupère l'état courant de la campagne (queued/running/done + compteurs).
    """
    return await get_campaign_by_id(campaign_id)


@router.get("/{campaign_id}/events")
async def campaign_events(campaign_id: int):
    """
    Flux Server-Sent Events. Renvoie des `data: {...}` + heartbeat `: ping`.
    """
    # IMPORTANT : on renvoie directement le générateur sse_stream(...)
    # Pas de "async for" ici, sinon on consomme le flux côté serveur.
    return StreamingResponse(
        sse_stream(campaign_id),
        media_type="text/event-stream",
    )


# (Optionnel mais pratique pour debug) : endpoint pour (re)demarrer un worker manuellement
@router.post("/{campaign_id}/start")
async def manual_start(campaign_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Démarre ou redémarre une campagne en fournissant `prompts` et `runs_per_prompt` dans le body.
    Body attendu: {"prompts": [...], "runs_per_prompt": 1}
    """
    prompts = body.get("prompts") or []
    runs_per_prompt = int(body.get("runs_per_prompt") or 1)
    if not prompts:
        raise HTTPException(status_code=400, detail="prompts manquant")
    await start_campaign_async(campaign_id, prompts, runs_per_prompt)
    return {"ok": True}
