# backend/routes/geo.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
from statistics import mean, median

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

# --- Détection de marques (depuis src.geo_agent) ---
from src.geo_agent.brand.brand_models import Brand, BrandMatch
from src.geo_agent.brand.detector import detect

# --- Client LLM via factory ---
from src.geo_agent.models import get_llm_client

router = APIRouter(prefix="/geo", tags=["geo"])
router = APIRouter(prefix="/geo", tags=["geo"])

# =============== Helpers internes ===============

def _summarize_matches(matches: List[BrandMatch]) -> Dict[str, Any]:
    """Résumé par marque pour UNE réponse."""
    summary: Dict[str, Any] = {}
    for m in matches:
        s = summary.setdefault(m.brand, {"total": 0, "exact": 0, "fuzzy": 0, "first_mention_index": None})
        s["total"] += 1
        if m.method == "exact":
            s["exact"] += 1
        elif m.method == "fuzzy":
            s["fuzzy"] += 1
        if s["first_mention_index"] is None or (isinstance(m.start, int) and m.start < s["first_mention_index"]):
            s["first_mention_index"] = m.start
    return summary

def _aggregate_batch(per_prompt_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrège les résumés de plusieurs prompts en KPI GEO."""
    brands: set[str] = set()
    for s in per_prompt_summaries:
        brands.update(s.keys())

    out: Dict[str, Any] = {}
    n_prompts = len(per_prompt_summaries)

    for b in sorted(brands):
        totals = exacts = fuzzys = 0
        firsts: List[int] = []
        prompts_with = 0
        for s in per_prompt_summaries:
            if b in s:
                row = s[b]
                totals += int(row.get("total", 0))
                exacts += int(row.get("exact", 0))
                fuzzys += int(row.get("fuzzy", 0))
                idx = row.get("first_mention_index")
                if isinstance(idx, int):
                    firsts.append(idx)
                prompts_with += 1
        out[b] = {
            "total_mentions": totals,
            "exact_total": exacts,
            "fuzzy_total": fuzzys,
            "prompts_with_mention": prompts_with,
            "mention_rate": (prompts_with / n_prompts) if n_prompts else 0.0,  # = % de prompts où la marque apparaît
            "avg_first_index": (mean(firsts) if firsts else None),
            "median_first_index": (median(firsts) if firsts else None),
        }
    return {"n_prompts": n_prompts, "by_brand": out}

def _apply_match_mode(matches: List[BrandMatch], mode: str) -> List[BrandMatch]:
    """Filtrage optionnel des matches (pour des chiffres plus “propres”)."""
    if mode == "exact_only":
        return [m for m in matches if m.method == "exact"]
    return matches

def _ask_llm(provider: str, model: Optional[str], temperature: float, prompt: str) -> tuple[str, str]:
    """Appelle le LLM choisi et retourne (texte, modèle_utilisé). Supporte GPT-5 avec web search."""
    used_model = model or ("gpt-5-mini" if provider == "openai" else "llama3.2:3b-instruct-q4_K_M")
    client = get_llm_client(provider, used_model)

    if hasattr(client, "answer"):
        if provider == "openai" and used_model.startswith("gpt-5"):
            # Utilise GPT-5 avec recherche web pour du vrai GEO
            text = client.answer(prompt, model=used_model, temperature=temperature, web_search=True)
        elif provider == "openai":
            res = client.answer([{"role": "user", "content": prompt}], model=used_model, temperature=temperature)
            text = res if isinstance(res, str) else getattr(res, "text", "")
        else:
            text = client.answer(prompt, temperature=temperature)
    else:
        text = client.answer_with_meta(prompt, temperature=temperature)["text"]

    return text, used_model

# =============== Modèles d'entrée ===============

class AskDetectBody(BaseModel):
    provider: str = "ollama"          # "ollama" | "openai"
    model: Optional[str] = None
    temperature: float = 0.1
    prompt: str
    fuzzy_threshold: float = 85.0
    brands: List[Brand]
    match_mode: str = "all"           # "all" | "exact_only"

class AskDetectBatchBody(BaseModel):
    provider: str = "ollama"
    model: Optional[str] = None
    temperature: float = 0.1
    prompts: List[str]
    fuzzy_threshold: float = 85.0
    brands: List[Brand]
    match_mode: str = "exact_only"    # par défaut on est strict pour les stats

# =============== Endpoints ===============

@router.post("/ask-detect")
def ask_and_detect(body: AskDetectBody):
    """
    ➜ 1 prompt → 1 réponse + détection + résumé.
    Utile pour tester rapidement.
    """
    # 1) LLM
    answer_text, used_model = _ask_llm(body.provider, body.model, body.temperature, body.prompt)
    # 2) Détection
    matches = detect(answer_text, brands=body.brands, fuzzy_threshold=body.fuzzy_threshold)
    matches = _apply_match_mode(matches, body.match_mode)
    # 3) Résumé
    summary = _summarize_matches(matches)
    return {
        "provider": body.provider,
        "model": used_model,
        "answer_text": answer_text,
        "matches": [m.model_dump() for m in matches],
        "summary": summary,
    }

@router.post("/ask-detect-batch")
def ask_and_detect_batch(body: AskDetectBatchBody):
    """
    ➜ N prompts (ex. 20) → détail par prompt + KPI agrégés par marque.
    C’est l’endpoint à utiliser pour un audit GEO.
    """
    per_prompt: List[Dict[str, Any]] = []

    for prompt_text in body.prompts:
        answer_text, _used_model = _ask_llm(body.provider, body.model, body.temperature, prompt_text)
        matches = detect(answer_text, brands=body.brands, fuzzy_threshold=body.fuzzy_threshold)
        matches = _apply_match_mode(matches, body.match_mode)
        summary = _summarize_matches(matches)
        per_prompt.append({
            "prompt": prompt_text,
            "answer_text": answer_text,
            "summary": summary,
            "matches": [m.model_dump() for m in matches],
        })

    metrics = _aggregate_batch([item["summary"] for item in per_prompt])
    return {"per_prompt": per_prompt, "metrics": metrics}

@router.post("/generate-prompts")
def generate_prompts_for_sector(
    business_type: str = Body(..., description="Type d'activité (ex: 'restaurant', 'banque', 'artisan')"),
    location: str = Body("", description="Localisation (ex: 'Paris', 'Marseille')"),
    count: int = Body(20, description="Nombre de prompts à générer")
):
    """
    Génère automatiquement des prompts universels pour n'importe quel type d'entreprise
    """

    # Préparation de la localisation
    location_phrase = f"à {location}" if location else ""
    location_phrase_dans = f"dans {location}" if location else ""
    location_phrase_pres = f"près de {location}" if location else ""

    # Template de base universel
    base_prompt = f"Générer moi une liste de {business_type} {location_phrase}"

    # Variations du prompt de base
    prompt_variations = [
        f"Liste des meilleurs {business_type} {location_phrase}",
        f"Où trouver un bon {business_type} {location_phrase}",
        f"Recommandations {business_type} {location_phrase}",
        f"Meilleur {business_type} {location_phrase}",
        f"{business_type.capitalize()} recommandé {location_phrase}",
        f"Bon {business_type} {location_phrase}",
        f"{business_type.capitalize()} de qualité {location_phrase}",
        f"Recherche {business_type} {location_phrase}",
        f"{business_type.capitalize()} proche {location}" if location else f"Proche {business_type}",
        f"Sélection {business_type} {location_phrase}",
        f"Guide {business_type} {location_phrase}",
        f"Annuaire {business_type} {location_phrase}",
        f"Trouvez un {business_type} {location_phrase}",
        f"{business_type.capitalize()} dans la région {location}" if location else f"{business_type.capitalize()} dans la région",
        f"Comparatif {business_type} {location_phrase}",
        f"Avis {business_type} {location_phrase}",
        f"Top {business_type} {location_phrase}",
        f"{business_type.capitalize()} local {location_phrase}",
        f"Service {business_type} {location_phrase}",
        f"Professionnel {business_type} {location_phrase}"
    ]

    # Ajout de variations avec prépositions différentes
    additional_variations = [
        f"Liste de {business_type} {location_phrase_dans}",
        f"Meilleurs {business_type} {location_phrase_pres}",
        f"Où aller pour {business_type} {location_phrase}",
        f"Cherche {business_type} {location_phrase}",
        f"{business_type.capitalize()} réputé {location_phrase}",
        f"Adresse {business_type} {location_phrase}",
        f"Contact {business_type} {location_phrase}",
        f"Spécialiste {business_type} {location_phrase}",
        f"Expert {business_type} {location_phrase}",
        f"{business_type.capitalize()} professionnel {location_phrase}"
    ]

    # Combine toutes les variations
    all_prompts = prompt_variations + additional_variations

    # Sélectionne et limite au nombre demandé
    generated_prompts = all_prompts[:count]

    # Si on n'a pas assez, on répète les meilleurs
    while len(generated_prompts) < count:
        remaining_needed = count - len(generated_prompts)
        generated_prompts.extend(prompt_variations[:remaining_needed])

    return {
        "prompts": generated_prompts[:count],
        "business_type": business_type,
        "location": location,
        "count": len(generated_prompts[:count])
    }
