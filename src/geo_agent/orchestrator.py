import csv
from typing import List
from .config import Settings
from .extract import MentionExtractor
from .sampler import run_batch
from .storage import Storage


def load_queries(path: str) -> List[str]:
    qs: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
    for row in r:
        if row.get("query"):
            qs.append(row["query"].strip())
    return qs


def run_campaign(config_path: str):
    cfg = Settings.load(config_path)
    cfg.ensure_dirs()

    queries = load_queries(cfg.campaign.queries_file)
    extractor = MentionExtractor(cfg.brand.variants, cfg.competitors, cfg.campaign.appear_lead_chars)
    store = Storage(cfg.io.out_dir)

    all_rows = []
    for model in cfg.campaign.models:
        rows = run_batch(
            model_spec=model,
            queries=queries,
            runs_per_query=cfg.campaign.runs_per_query,
            temperature=cfg.campaign.temperature,
            extractor=extractor,
        )
    all_rows.extend(rows)

    # Sauvegarde
    store.append_results([
        {k: v for k, v in r.items() if k != "_text"} for r in all_rows
    ])
    store.append_raw(all_rows)

    return len(all_rows)

# === NEHORIS PATCH: GEO detection helper ======================================

from typing import Dict, List, Any, Optional
try:
    # si tu as ajouté le gateway
    from services.llm_gateway import LLMGateway  # type: ignore
    _GW_AVAILABLE = True
except Exception:
    _GW_AVAILABLE = False

from src.geo_agent.brand.brand_models import Brand
from src.geo_agent.brand.detector import detect

def run_prompt_with_brand_detection(
    provider: str,
    model: Optional[str],
    prompt_text: str,
    brands_raw: List[Dict[str, Any]],
    *,
    temperature: float = 0.2,
    fuzzy_threshold: float = 85.0,
) -> Dict[str, Any]:
    """
    1) Pose le prompt au LLM (gateway si dispo, sinon ton client Ollama/OpenAI direct)
    2) Détecte les marques dans la réponse
    3) Retourne un dict prêt pour scoring/storage
    """
    # 1) LLM answer
    if _GW_AVAILABLE:
        gw = LLMGateway()
        out = gw.ask(provider=provider, messages=prompt_text, model=model, temperature=temperature)
        answer_text = out["text"]
        used_model = out["model"]
    else:
        # Fallback: exemple avec OllamaClient (adapte si tu préfères OpenAI)
        from src.geo_agent.models.ollama_client import OllamaClient
        cli = OllamaClient(model=model or "llama3.1")
        answer_text = cli.answer_with_meta(prompt_text, temperature=temperature)["text"]
        used_model = model or cli.model

    # 2) Brand detection
    brands = [Brand(name=b.get("name", ""), variants=b.get("variants", []) or []) for b in brands_raw]
    matches = detect(answer_text, brands, fuzzy_threshold=fuzzy_threshold)

    # 3) Résumé simple (tu peux brancher sur scoring.py ensuite)
    by_brand: Dict[str, Any] = {}
    for m in matches:
        by_brand.setdefault(m.brand, {"total": 0, "exact": 0, "fuzzy": 0, "first_mention_index": None})
        by_brand[m.brand]["total"] += 1
        if m.method == "exact":
            by_brand[m.brand]["exact"] += 1
        if m.method == "fuzzy":
            by_brand[m.brand]["fuzzy"] += 1
        pos = m.start
        cur = by_brand[m.brand]["first_mention_index"]
        if cur is None or (isinstance(pos, int) and pos < cur):
            by_brand[m.brand]["first_mention_index"] = pos

    return {
        "provider": provider,
        "model": used_model,
        "prompt": prompt_text,
        "answer_text": answer_text,
        "matches": [m.model_dump() for m in matches],
        "brand_summary": by_brand,  # exploitable par scoring.py
    }


def run_batch_with_brand_detection(
    provider: str,
    model: Optional[str],
    prompts: List[str],
    brands_raw: List[Dict[str, Any]],
    *,
    temperature: float = 0.2,
    fuzzy_threshold: float = 85.0,
) -> List[Dict[str, Any]]:
    """
    Utilitaire batch: boucle sur une liste de prompts.
    """
    results: List[Dict[str, Any]] = []
    for p in prompts:
        results.append(
            run_prompt_with_brand_detection(
                provider=provider,
                model=model,
                prompt_text=p,
                brands_raw=brands_raw,
                temperature=temperature,
                fuzzy_threshold=fuzzy_threshold,
            )
        )
    return results
# === /NEHORIS PATCH ===========================================================

# === NEHORIS: GEO brand detection helper =====================================
from typing import Dict, List, Any, Optional
from src.geo_agent.brand.brand_models import Brand
from src.geo_agent.brand.detector import detect
from src.geo_agent.scoring import summarize_brand_matches

def run_prompt_with_brand_detection(
    provider: str,
    model: Optional[str],
    prompt_text: str,
    brands_raw: List[Dict[str, Any]],
    *,
    temperature: float = 0.2,
    fuzzy_threshold: float = 85.0,
) -> Dict[str, Any]:
    """
    1) Pose 'prompt_text' à TON client LLM (tu peux garder ta logique actuelle)
    2) Passe la réponse dans 'detect(...)'
    3) Retourne la réponse + matches + résumé pour scoring/export
    """
    # --- 1) LLM (exemple simple avec Ollama; remplace par ta logique si besoin)
    from src.geo_agent.models.ollama_client import OllamaClient
    cli = OllamaClient(model=model or "llama3.1")
    answer_text = cli.answer_with_meta(prompt_text, temperature=temperature)["text"]
    used_model = model or cli.model

    # --- 2) Détection
    brands = [Brand(name=b.get("name", ""), variants=b.get("variants", []) or []) for b in brands_raw]
    matches = detect(answer_text, brands, fuzzy_threshold=fuzzy_threshold)

    # --- 3) Résumé
    brand_summary = summarize_brand_matches(matches)

    return {
        "provider": provider,
        "model": used_model,
        "prompt": prompt_text,
        "answer_text": answer_text,
        "matches": [m.model_dump() for m in matches],
        "brand_summary": brand_summary,
    }
# === /NEHORIS =================================================================
