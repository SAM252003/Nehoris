"""
Simple scheduler (MVP) pour lancer automatiquement des campagnes à intervalle régulier.

Configuration par variables d'environnement :

  # Fréquence
  GEO_SCHEDULE_EVERY_MINUTES=1440           # ex: 1440 = 1 fois par jour
  GEO_SCHEDULE_RUN_IMMEDIATELY=true         # (optionnel) lance une exécution dès le démarrage

  # Paramètres de la campagne
  GEO_SCHEDULE_COMPANY_ID=1
  GEO_SCHEDULE_MODEL=perplexity:sonar
  GEO_SCHEDULE_RUNS_PER_QUERY=1
  GEO_SCHEDULE_TEMPERATURE=0.1

  # Source des prompts (exactement l'un des deux)
  GEO_SCHEDULE_PROMPTS_FILE=data/queries/printing_paris.fr.txt   # 1 prompt par ligne
  # ou
  GEO_SCHEDULE_CLONE_CAMPAIGN_ID=123  # réutilise les prompts d'une campagne passée

Comportement :
- À chaque "tick", crée une nouvelle campagne avec ces paramètres puis enfile le job
  d'exécution via RQ (Redis Queue). Si Redis/RQ indisponible, exécute en mode direct.
"""

from __future__ import annotations
import os
import time
import traceback
from typing import List, Optional
from sqlmodel import Session, select

# Charger .env si présent (facultatif)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Imports locaux
from ..db import engine
from ..models import Company, CampaignPrompt, Prompt
from ..services.campaign_service import create_campaign
from . import tasks

# RQ (file d'attente) — fallback si indisponible
try:
    from .queue import q  # type: ignore
    _RQ_OK = True
except Exception:
    q = None  # type: ignore
    _RQ_OK = False


# --------------------------- Helpers ---------------------------

def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

def _get_env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default

def _get_env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

def _read_prompts_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [ln.strip() for ln in f.readlines() if ln.strip()]

def _clone_prompts_from_campaign(session: Session, campaign_id: int) -> List[str]:
    cps = session.exec(
        select(CampaignPrompt).where(CampaignPrompt.campaign_id == campaign_id).order_by(CampaignPrompt.order_index)
    ).all()
    if not cps:
        return []
    # Récupérer les textes (relation simple)
    prompts: List[str] = []
    for cp in cps:
        pr = session.get(Prompt, cp.prompt_id)
        if pr and pr.text:
            prompts.append(pr.text.strip())
    return prompts


# --------------------------- Job principal ---------------------------

def _create_and_enqueue_once(
    company_id: int,
    model: str,
    runs_per_query: int,
    temperature: float,
    prompts: List[str],
) -> None:
    if not prompts:
        raise ValueError("La liste de prompts est vide")

    # Vérifier la company
    with Session(engine) as session:
        company = session.get(Company, company_id)
        if not company:
            raise ValueError(f"Company id={company_id} introuvable")

        # Créer une campagne
        camp = create_campaign(
            session=session,
            company_id=company_id,
            model=model,
            runs_per_query=runs_per_query,
            temperature=temperature,
            prompts=prompts,
        )

        # Enfiler l'exécution
        if _RQ_OK and q is not None:
            q.enqueue(tasks.run_campaign_async, camp.id)  # type: ignore
            print(f"[scheduler] Campagne {camp.id} enfilée dans RQ (model={model}, prompts={len(prompts)})")
        else:
            # Fallback : exécution synchronisée dans ce process
            print("[scheduler] RQ indisponible — exécution directe")
            tasks.run_campaign_async(camp.id)  # type: ignore


def _build_prompts(session: Session) -> List[str]:
    """
    Détermine la source des prompts selon les variables d'env.
    Priorité :
      1) GEO_SCHEDULE_PROMPTS_FILE
      2) GEO_SCHEDULE_CLONE_CAMPAIGN_ID
    """
    path = os.getenv("GEO_SCHEDULE_PROMPTS_FILE")
    if path:
        return _read_prompts_from_file(path)

    clone_id = os.getenv("GEO_SCHEDULE_CLONE_CAMPAIGN_ID")
    if clone_id:
        try:
            cid = int(clone_id)
        except Exception:
            raise ValueError("GEO_SCHEDULE_CLONE_CAMPAIGN_ID doit être un entier")
        prompts = _clone_prompts_from_campaign(session, cid)
        if not prompts:
            raise ValueError(f"Aucun prompt trouvé en clonant la campagne {cid}")
        return prompts

    raise ValueError("Veuillez définir GEO_SCHEDULE_PROMPTS_FILE ou GEO_SCHEDULE_CLONE_CAMPAIGN_ID")


# --------------------------- Boucle du scheduler ---------------------------

def run_scheduler_forever() -> None:
    every_min = _get_env_int("GEO_SCHEDULE_EVERY_MINUTES", 1440)
    run_now = _get_env_bool("GEO_SCHEDULE_RUN_IMMEDIATELY", False)

    company_id = _get_env_int("GEO_SCHEDULE_COMPANY_ID", 1)
    model = os.getenv("GEO_SCHEDULE_MODEL", "perplexity:sonar")
    runs_per_query = _get_env_int("GEO_SCHEDULE_RUNS_PER_QUERY", 1)
    temperature = _get_env_float("GEO_SCHEDULE_TEMPERATURE", 0.1)

    print(
        "[scheduler] DÉMARRAGE — every=%d min, now=%s, company_id=%d, model=%s, runs=%d, temp=%.2f"
        % (every_min, run_now, company_id, model, runs_per_query, temperature)
    )

    def _execute_once():
        try:
            with Session(engine) as session:
                prompts = _build_prompts(session)
            _create_and_enqueue_once(
                company_id=company_id,
                model=model,
                runs_per_query=runs_per_query,
                temperature=temperature,
                prompts=prompts,
            )
        except Exception as e:
            print("[scheduler] ERREUR:", e)
            traceback.print_exc()

    # Option: run immédiat
    if run_now:
        _execute_once()

    # Boucle infinie (intervalle fixe)
    while True:
        time.sleep(max(1, every_min * 60))
        _execute_once()


# --------------------------- Entrée CLI ---------------------------

if __name__ == "__main__":
    try:
        run_scheduler_forever()
    except KeyboardInterrupt:
        print("\n[scheduler] Arrêt demandé (Ctrl+C). Bye.")
