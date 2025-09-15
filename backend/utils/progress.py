# backend/utils/progress.py
from __future__ import annotations
import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List, Set

# --- Pub/Sub en mémoire pour les SSE ---

# Un set de files par campagne (un subscriber = une file)
_subscribers: Dict[int, Set[asyncio.Queue]] = {}

# Mémoire des lignes exportables (si tu envoies des events type="row")
_rows: Dict[int, List[Dict[str, Any]]] = {}

# NEW: dernier event non-row par campagne (ex: status/progress/done)
_last_event: Dict[int, Dict[str, Any]] = {}


def _get_subscribers(campaign_id: int) -> Set[asyncio.Queue]:
    return _subscribers.setdefault(campaign_id, set())


def _format_sse(data: Dict[str, Any]) -> bytes:
    """Formate un event en SSE ('data: {...}\\n\\n')."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n".encode("utf-8")


async def publish(campaign_id: int, event: Dict[str, Any]) -> None:
    """
    Publie un événement pour une campagne.
    - Duplique l’event vers tous les abonnés (files asyncio.Queue).
    - Si event.type == "row", on le mémorise pour l’export CSV.
    - NEW: on mémorise aussi le *dernier* event "non-row" pour le rejouer à l’abonnement.
    """
    etype = event.get("type")

    if etype == "row":
        _rows.setdefault(campaign_id, []).append(event)
    else:
        # on garde le dernier event "utile" (status/progress/done/…)
        _last_event[campaign_id] = event

    # Diffusion aux abonnés courants
    queues = list(_get_subscribers(campaign_id))  # snapshot
    for q in queues:
        try:
            await q.put(event)
        except RuntimeError:
            # queue fermée : on l’enlève silencieusement
            _get_subscribers(campaign_id).discard(q)


async def sse_stream(
    campaign_id: int,
    heartbeat_interval: float = 15.0,
) -> AsyncGenerator[bytes, None]:
    """
    Async generator à brancher dans StreamingResponse.
    Yields des chunks SSE (bytes). Envoie aussi des heartbeats réguliers.
    NEW: envoie immédiatement le *dernier* event connu, s’il existe (replay).
    """
    queue: asyncio.Queue = asyncio.Queue()
    subs = _get_subscribers(campaign_id)
    subs.add(queue)

    # NEW: rejoue le dernier event si on l’a (utile si on se connecte après coup)
    initial = _last_event.get(campaign_id)
    if initial is not None:
        yield _format_sse(initial)

    last_beat = time.monotonic()

    try:
        while True:
            # On attend un event ou un timeout pour heartbeat
            timeout = max(0.0, heartbeat_interval - (time.monotonic() - last_beat))
            try:
                event = await asyncio.wait_for(queue.get(), timeout=timeout)
                yield _format_sse(event)
            except asyncio.TimeoutError:
                # Heartbeat (comment SSE) pour garder la connexion vivante
                yield b": ping\n\n"
                last_beat = time.monotonic()
    finally:
        # Nettoyage : on retire la queue de la liste des abonnés
        subs.discard(queue)


# --- Accès simple aux rows pour l’export (optionnel) ---

def snapshot_rows(campaign_id: int) -> List[Dict[str, Any]]:
    """Retourne une copie des rows accumulées pour cette campagne."""
    return list(_rows.get(campaign_id, []))


def clear_rows(campaign_id: int) -> None:
    """Efface les rows en mémoire pour cette campagne (si tu veux libérer la RAM après export)."""
    _rows.pop(campaign_id, None)
    _last_event.pop(campaign_id, None)  # on peut aussi oublier le dernier event


__all__ = ["publish", "sse_stream", "snapshot_rows", "clear_rows"]
