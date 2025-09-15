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

from __future__ import annotations
import os
import sys
from typing import List, Dict, Any
from urllib.parse import urlparse

from sqlmodel import Session, select
from src.geo_agent.models.ollama_client import OllamaClient
from src.geo_agent.config import Settings

cfg = Settings()
client = OllamaClient(model="llama3.1", host=cfg.ollama_host, timeout=cfg.ollama_timeout)


# S'assurer que le répertoire projet (parent) est dans sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# DB & modèles
from backend.db import engine
from backend.models import Company, Campaign, CampaignPrompt, Prompt, Run

# Progression SSE
from backend.utils.progress import publish

# Analyse (nouvelle implémentation fournie dans src/geo_agent/extracts.py)
from src.geo_agent.extracts import MentionDetector
from src.geo_agent.parse_ranked import parse_ranked as parse_ranked_list

# HTTP
import json
import time
import requests


# ------------------------- Clients LLM (minimaux) -------------------------

class _PerplexityClient:
    """
    Client minimal Perplexity (web-grounded).
    Nécessite PPLX_API_KEY. Route: POST /chat/completions
    """
    def __init__(self, model: str = "sonar"):
        self.model = model
        self.base = os.getenv("PPLX_BASE_URL", "https://api.perplexity.ai")
        self.key = os.getenv("PPLX_API_KEY")
        if not self.key:
            raise RuntimeError("PPLX_API_KEY manquant (Perplexity)")

    def answer_with_meta(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        url = f"{self.base}/chat/completions"
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "temperature": float(temperature)},
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        # Perplexity peut renvoyer "citations" ou "references"
        sources = data.get("citations") or data.get("references") or []
        return {"text": text, "sources": sources}


class _OllamaClient:
    """
    Client minimal Ollama (local).
    Démarrer Ollama puis `ollama pull llama3.1` par exemple.
    """
    def __init__(self, model: str = "llama3.1"):
        self.model = model
        self.base = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def answer_with_meta(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        url = f"{self.base}/api/chat"
        r = requests.post(
            url,
            json={"model": self.model, "messages": messages, "options": {"temperature": float(temperature)}, "stream": False},
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        text = (data.get("message") or {}).get("content", "") or ""
        return {"text": text, "sources": []}


class _OpenAIClient:
    """
    Client minimal OpenAI (Chat Completions).
    Nécessite OPENAI_API_KEY. Utilise model="gpt-5" par défaut si choisi.
    """
    def __init__(self, model: str = "gpt-5"):
        self.model = model
        self.key = os.getenv("OPENAI_API_KEY")
        if not self.key:
            raise RuntimeError("OPENAI_API_KEY manquant")
        # API v1 simple via HTTP (évite dépendance forte)
        self.base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def answer_with_meta(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        url = f"{self.base}/chat/completions"
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "temperature": float(temperature)},
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
        return {"text": text, "sources": []}


def _make_client(model_spec: str):
    """
    model_spec format: "provider:model"  ex: "perplexity:sonar", "ollama:llama3.1", "openai:gpt-5"
    """
    prov, model = model_spec.split(":", 1)
    if prov == "perplexity":
        return _PerplexityClient(model)
    if prov == "ollama":
        return _OllamaClient(model)
    if prov == "openai":
        return _OpenAIClient(model)
    raise ValueError(f"Fournisseur non supporté: {prov}")


# ------------------------- Utilitaires -------------------------

_SYSTEM_PROMPT = (
    "Tu es un assistant qui répond avec des listes claires et sourcées quand c'est possible. "
    "Quand la requête demande des recommandations / top listes, structure la réponse en éléments numérotés."
)

def _build_messages(query: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]


def _normalize_sources(sources: Any) -> List[str]:
    out: List[str] = []
    if not sources:
        return out
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except Exception:
            sources = [sources]
    for s in sources:
        try:
            u = urlparse(s)
            host = u.netloc or str(s)
            if host:
                out.append(host.lower())
        except Exception:
            out.append(str(s))
    return out


def _notify_progress(campaign_id: int, status: str, done: int, total: int) -> None:
    payload = {"campaign_id": campaign_id, "status": status, "completed_runs": done, "total_runs": total,
               "pct": round((done / total * 100) if total else 0.0, 1)}
    # publier même hors boucle async
    try:
        import asyncio
        asyncio.run(publish(campaign_id, payload))
    except RuntimeError:
        # si une boucle existe déjà
        try:
            import asyncio
            asyncio.get_event_loop().create_task(publish(campaign_id, payload))
        except Exception:
            pass
    except Exception:
        pass


# ------------------------- Tâche principale -------------------------

def run_campaign_async(campaign_id: int) -> None:
    """
    Exécute tous les runs de la campagne en base, met à jour la progression
    et persiste chaque réponse dans Run.
    """
    with Session(engine) as session:
        camp = session.get(Campaign, campaign_id)
        if not camp:
            return
        comp = session.get(Company, camp.company_id)
        if not comp:
            return

        cps = session.exec(
            select(CampaignPrompt).where(CampaignPrompt.campaign_id == campaign_id).order_by(CampaignPrompt.order_index)
        ).all()
        # protéger si pas de prompts
        if not cps:
            camp.status = "error"
            session.add(camp)
            session.commit()
            _notify_progress(campaign_id, camp.status, 0, 0)
            return

        client = _make_client(camp.model)
        det = MentionDetector(comp.variants, comp.competitors, lead_chars=300)

        # Dictionnaire {variant_normalisée: canon} pour parser classement
        brand_map = det.build_brand_map()

        total_runs = len(cps) * max(1, int(camp.runs_per_query or 1))
        done = 0

        camp.status = "running"
        session.add(camp)
        session.commit()
        _notify_progress(campaign_id, camp.status, done, total_runs)

        for cp in cps:
            pr: Prompt | None = session.get(Prompt, cp.prompt_id)
            if not pr:
                continue
            for run_idx in range(camp.runs_per_query or 1):
                # Appel modèle
                meta = client.answer_with_meta(_build_messages(pr.text), temperature=float(camp.temperature or 0.1))
                text: str = meta.get("text", "") or ""
                sources = _normalize_sources(meta.get("sources", []))

                # Analyse
                stats = det.analyze(text)
                rankings = parse_ranked_list(text, brand_map)

                # Persist
                row = Run(
                    campaign_id=camp.id,            # type: ignore
                    prompt_id=cp.prompt_id,
                    run_index=run_idx,
                    model=camp.model,
                    text=text,
                    appear_answer=stats.appear_answer,
                    appear_lead=stats.appear_lead,
                    first_pos=stats.first_pos,
                    brand_hits=stats.brand_hits,
                    comp_hits=stats.comp_hits,
                    sources=sources,
                    rankings=rankings,
                )
                session.add(row)

                # progression
                done += 1
                camp.completed_runs = done
                session.add(camp)
                session.commit()
                _notify_progress(campaign_id, camp.status, done, total_runs)

                # mini pause anti-throttle (facultatif)
                time.sleep(0.1)

        camp.status = "done"
        session.add(camp)
        session.commit()
        _notify_progress(campaign_id, camp.status, done, total_runs)
