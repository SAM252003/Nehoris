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
    count: int = Body(20, description="Nombre de prompts à générer"),
    keywords: str = Body("", description="Mots-clés spécifiques séparés par virgules (ex: 'bio, local, artisanal')")
):
    """
    Génère automatiquement des prompts spécialisés par secteur d'activité
    """

    # Fonction pour gérer les prépositions françaises correctement
    def get_location_phrase(location: str, preposition_type: str = "à") -> str:
        if not location:
            return ""

        location_lower = location.lower()

        # Pays (utilisent "en" ou "au")
        pays_en = ["france", "italie", "espagne", "allemagne", "angleterre", "suisse", "belgique", "norvège", "suède", "finlande", "pologne", "hongrie", "autriche", "grèce", "turquie", "russie", "chine", "inde", "corée", "australie"]
        pays_au = ["canada", "japon", "brésil", "mexique", "maroc", "portugal", "danemark", "luxembourg", "royaume-uni", "pays-bas"]
        pays_aux = ["états-unis", "philippines", "émirats arabes unis", "pays-bas"]

        # Continents (utilisent "en")
        continents = ["europe", "asie", "afrique", "amérique", "océanie", "amérique du nord", "amérique du sud"]

        # Régions françaises (utilisent "en")
        regions = ["provence", "bretagne", "normandie", "alsace", "bourgogne", "champagne", "loire", "dordogne", "ardèche", "savoie", "haute-savoie", "ile-de-france", "nouvelle-aquitaine", "occitanie", "auvergne-rhône-alpes", "grand est", "hauts-de-france", "pays de la loire", "centre-val de loire", "bourgogne-franche-comté", "paca", "corse"]

        if preposition_type == "à":
            if location_lower in pays_en or location_lower in continents or location_lower in regions:
                return f"en {location}"
            elif location_lower in pays_au:
                return f"au {location}"
            elif location_lower in pays_aux:
                return f"aux {location}"
            elif location_lower == "monde":
                return "dans le monde"
            else:
                return f"à {location}"

        elif preposition_type == "dans":
            if location_lower in pays_en or location_lower in continents or location_lower in regions:
                return f"en {location}"
            elif location_lower in pays_au:
                return f"au {location}"
            elif location_lower in pays_aux:
                return f"aux {location}"
            elif location_lower == "monde":
                return "dans le monde"
            else:
                return f"dans {location}"

        elif preposition_type == "près":
            return f"près de {location}"

        return f"à {location}"

    # Préparation des différentes variantes de localisation
    location_phrase = get_location_phrase(location, "à")
    location_phrase_dans = get_location_phrase(location, "dans")
    location_phrase_pres = get_location_phrase(location, "près")

    # Templates spécialisés par secteur
    sector_templates = {
        "restaurant": [
            f"Meilleurs restaurants {location_phrase}",
            f"Où manger {location_phrase}",
            f"Restaurant gastronomique {location_phrase}",
            f"Bonne table {location_phrase}",
            f"Cuisine locale {location_phrase}",
            f"Restaurant traditionnel {location_phrase}",
            f"Dîner romantique {location_phrase}",
            f"Menu du jour {location_phrase}",
            f"Restaurant familial {location_phrase}",
            f"Spécialités culinaires {location_phrase}",
            f"Brunch {location_phrase}",
            f"Restaurant étoilé {location_phrase}",
            f"Bistrot authentique {location_phrase}",
            f"Cuisine du monde {location_phrase}",
            f"Restaurant végétarien {location_phrase}"
        ],
        "restaurant-vegan": [
            f"Restaurant vegan {location_phrase}",
            f"Cuisine végétalienne {location_phrase}",
            f"Restaurant végétarien {location_phrase}",
            f"Plats végétaux {location_phrase}",
            f"Menu vegan {location_phrase}",
            f"Repas sans viande {location_phrase}",
            f"Cuisine bio {location_phrase}",
            f"Healthy food {location_phrase}",
            f"Buddha bowl {location_phrase}",
            f"Smoothie bowl {location_phrase}",
            f"Tofu {location_phrase}",
            f"Quinoa {location_phrase}",
            f"Légumes bio {location_phrase}",
            f"Raw food {location_phrase}",
            f"Cuisine sans gluten {location_phrase}"
        ],
        "boulangerie": [
            f"Boulangerie artisanale {location_phrase}",
            f"Pain frais {location_phrase}",
            f"Croissants {location_phrase}",
            f"Pâtisserie {location_phrase}",
            f"Viennoiseries {location_phrase}",
            f"Baguette tradition {location_phrase}",
            f"Gâteaux sur mesure {location_phrase}",
            f"Pain bio {location_phrase}",
            f"Macarons {location_phrase}",
            f"Tarte aux fruits {location_phrase}",
            f"Petit déjeuner {location_phrase}",
            f"Sandwich frais {location_phrase}",
            f"Éclair au chocolat {location_phrase}",
            f"Paris-Brest {location_phrase}",
            f"Mille-feuille {location_phrase}"
        ],
        "coiffeur": [
            f"Coiffeur professionnel {location_phrase}",
            f"Salon de coiffure {location_phrase}",
            f"Coupe moderne {location_phrase}",
            f"Coloration cheveux {location_phrase}",
            f"Brushing {location_phrase}",
            f"Coiffure mariage {location_phrase}",
            f"Balayage {location_phrase}",
            f"Lissage brésilien {location_phrase}",
            f"Coiffeur homme {location_phrase}",
            f"Extensions cheveux {location_phrase}",
            f"Permanente {location_phrase}",
            f"Coiffure enfant {location_phrase}",
            f"Shampooing soin {location_phrase}",
            f"Mèches {location_phrase}",
            f"Relooking capillaire {location_phrase}"
        ],
        "garage": [
            f"Garage automobile {location_phrase}",
            f"Réparation voiture {location_phrase}",
            f"Mécanicien {location_phrase}",
            f"Entretien véhicule {location_phrase}",
            f"Contrôle technique {location_phrase}",
            f"Vidange {location_phrase}",
            f"Pneus {location_phrase}",
            f"Diagnostic auto {location_phrase}",
            f"Carrosserie {location_phrase}",
            f"Révision voiture {location_phrase}",
            f"Freins {location_phrase}",
            f"Embrayage {location_phrase}",
            f"Climatisation auto {location_phrase}",
            f"Batterie voiture {location_phrase}",
            f"Dépannage auto {location_phrase}"
        ],
        "dentiste": [
            f"Dentiste {location_phrase}",
            f"Cabinet dentaire {location_phrase}",
            f"Orthodontiste {location_phrase}",
            f"Implants dentaires {location_phrase}",
            f"Urgence dentaire {location_phrase}",
            f"Blanchiment dents {location_phrase}",
            f"Détartrage {location_phrase}",
            f"Prothèse dentaire {location_phrase}",
            f"Chirurgien dentiste {location_phrase}",
            f"Couronne dentaire {location_phrase}",
            f"Extraction dent {location_phrase}",
            f"Appareil dentaire {location_phrase}",
            f"Parodontologie {location_phrase}",
            f"Endodontie {location_phrase}",
            f"Stomatologue {location_phrase}"
        ],
        "avocat": [
            f"Avocat {location_phrase}",
            f"Cabinet d'avocats {location_phrase}",
            f"Conseil juridique {location_phrase}",
            f"Avocat divorce {location_phrase}",
            f"Droit du travail {location_phrase}",
            f"Avocat immobilier {location_phrase}",
            f"Contentieux {location_phrase}",
            f"Avocat pénal {location_phrase}",
            f"Droit de la famille {location_phrase}",
            f"Succession {location_phrase}",
            f"Avocat commercial {location_phrase}",
            f"Aide juridictionnelle {location_phrase}",
            f"Procédure {location_phrase}",
            f"Consultation juridique {location_phrase}",
            f"Avocat spécialisé {location_phrase}"
        ],
        "banque": [
            f"Banque {location_phrase}",
            f"Agence bancaire {location_phrase}",
            f"Crédit immobilier {location_phrase}",
            f"Prêt personnel {location_phrase}",
            f"Compte bancaire {location_phrase}",
            f"Conseiller financier {location_phrase}",
            f"Placement {location_phrase}",
            f"Assurance vie {location_phrase}",
            f"Crédit auto {location_phrase}",
            f"Livret épargne {location_phrase}",
            f"Carte bancaire {location_phrase}",
            f"Virement {location_phrase}",
            f"Découvert {location_phrase}",
            f"Investissement {location_phrase}",
            f"Banque en ligne {location_phrase}"
        ],
        "hotel": [
            f"Hôtel {location_phrase}",
            f"Hébergement {location_phrase}",
            f"Réservation hôtel {location_phrase}",
            f"Chambre d'hôtel {location_phrase}",
            f"Hôtel de luxe {location_phrase}",
            f"Nuit d'hôtel {location_phrase}",
            f"Hôtel spa {location_phrase}",
            f"Auberge {location_phrase}",
            f"Gîte {location_phrase}",
            f"Maison d'hôtes {location_phrase}",
            f"Hôtel restaurant {location_phrase}",
            f"Suite {location_phrase}",
            f"Petit déjeuner inclus {location_phrase}",
            f"Hôtel centre ville {location_phrase}",
            f"Escapade romantique {location_phrase}"
        ],
        "pharmacie": [
            f"Pharmacie {location_phrase}",
            f"Garde pharmacie {location_phrase}",
            f"Médicaments {location_phrase}",
            f"Ordonnance {location_phrase}",
            f"Parapharmacie {location_phrase}",
            f"Pharmacien {location_phrase}",
            f"Homéopathie {location_phrase}",
            f"Urgence pharmacie {location_phrase}",
            f"Conseil santé {location_phrase}",
            f"Vaccin {location_phrase}",
            f"Cosmétiques {location_phrase}",
            f"Matériel médical {location_phrase}",
            f"Automédication {location_phrase}",
            f"Pharmacie de nuit {location_phrase}",
            f"Phytothérapie {location_phrase}"
        ],
        "immobilier": [
            f"Agence immobilière {location_phrase}",
            f"Vente appartement {location_phrase}",
            f"Location maison {location_phrase}",
            f"Agent immobilier {location_phrase}",
            f"Estimation immobilière {location_phrase}",
            f"Achat maison {location_phrase}",
            f"Investissement locatif {location_phrase}",
            f"Négociateur {location_phrase}",
            f"Gestion locative {location_phrase}",
            f"Mandat vente {location_phrase}",
            f"Visite appartement {location_phrase}",
            f"Syndic {location_phrase}",
            f"Copropriété {location_phrase}",
            f"Notaire {location_phrase}",
            f"Crédit immobilier {location_phrase}"
        ],
        "artisan": [
            f"Artisan {location_phrase}",
            f"Travaux maison {location_phrase}",
            f"Plombier {location_phrase}",
            f"Électricien {location_phrase}",
            f"Maçon {location_phrase}",
            f"Peintre {location_phrase}",
            f"Menuisier {location_phrase}",
            f"Couvreur {location_phrase}",
            f"Chauffagiste {location_phrase}",
            f"Carreleur {location_phrase}",
            f"Serrurier {location_phrase}",
            f"Dépannage {location_phrase}",
            f"Rénovation {location_phrase}",
            f"Devis gratuit {location_phrase}",
            f"Artisan qualifié {location_phrase}"
        ],
        "commerce": [
            f"Magasin {location_phrase}",
            f"Boutique {location_phrase}",
            f"Commerce {location_phrase}",
            f"Shopping {location_phrase}",
            f"Vente {location_phrase}",
            f"Promotion {location_phrase}",
            f"Soldes {location_phrase}",
            f"Livraison {location_phrase}",
            f"Magasin spécialisé {location_phrase}",
            f"Centre commercial {location_phrase}",
            f"Achat local {location_phrase}",
            f"Produits {location_phrase}",
            f"Service client {location_phrase}",
            f"Retrait magasin {location_phrase}",
            f"Conseiller vente {location_phrase}"
        ],
        "service": [
            f"Service professionnel {location_phrase}",
            f"Prestation {location_phrase}",
            f"Consultant {location_phrase}",
            f"Expert {location_phrase}",
            f"Accompagnement {location_phrase}",
            f"Formation {location_phrase}",
            f"Audit {location_phrase}",
            f"Conseil {location_phrase}",
            f"Maintenance {location_phrase}",
            f"Support {location_phrase}",
            f"Assistance {location_phrase}",
            f"Diagnostic {location_phrase}",
            f"Intervention {location_phrase}",
            f"Dépannage {location_phrase}",
            f"Service à domicile {location_phrase}"
        ]
    }

    # Sélectionne les prompts spécialisés ou génériques
    if business_type in sector_templates:
        specialized_prompts = sector_templates[business_type]
    else:
        # Fallback générique pour les secteurs non listés
        specialized_prompts = [
            f"Meilleur {business_type} {location_phrase}",
            f"{business_type.capitalize()} professionnel {location_phrase}",
            f"Service {business_type} {location_phrase}",
            f"Expert {business_type} {location_phrase}",
            f"Spécialiste {business_type} {location_phrase}",
            f"{business_type.capitalize()} recommandé {location_phrase}",
            f"Bon {business_type} {location_phrase}",
            f"{business_type.capitalize()} de qualité {location_phrase}",
            f"Recherche {business_type} {location_phrase}",
            f"Trouvez un {business_type} {location_phrase}",
            f"Sélection {business_type} {location_phrase}",
            f"Guide {business_type} {location_phrase}",
            f"Annuaire {business_type} {location_phrase}",
            f"Comparatif {business_type} {location_phrase}",
            f"Avis {business_type} {location_phrase}"
        ]

    # Ajout de variations génériques pour compléter
    generic_variations = [
        f"Liste des meilleurs {business_type} {location_phrase}",
        f"Où trouver un {business_type} {location_phrase}",
        f"Recommandations {business_type} {location_phrase}",
        f"{business_type.capitalize()} proche {location}" if location else f"Proche {business_type}",
        f"Top {business_type} {location_phrase}",
        f"{business_type.capitalize()} local {location_phrase}",
        f"Adresse {business_type} {location_phrase}",
        f"Contact {business_type} {location_phrase}",
        f"{business_type.capitalize()} réputé {location_phrase}",
        f"{business_type.capitalize()} dans la région {location}" if location else f"{business_type.capitalize()} dans la région"
    ]

    # Combine spécialisés + génériques
    all_prompts = specialized_prompts + generic_variations

    # Traitement des mots-clés spécifiques
    if keywords.strip():
        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        keyword_prompts = []

        for keyword in keyword_list:
            # Génère des prompts enrichis avec chaque mot-clé
            keyword_prompts.extend([
                f"{business_type.capitalize()} {keyword} {location_phrase}",
                f"Meilleur {business_type} {keyword} {location_phrase}",
                f"Où trouver {business_type} {keyword} {location_phrase}",
                f"{keyword.capitalize()} {business_type} {location_phrase}",
                f"Restaurant {keyword} {location_phrase}" if business_type.startswith("restaurant") else f"{business_type} {keyword} {location_phrase}",
                f"Spécialiste {business_type} {keyword} {location_phrase}"
            ])

        # Priorité aux prompts avec mots-clés, puis compléter avec les autres
        all_prompts = keyword_prompts + all_prompts

    # Sélectionne et limite au nombre demandé
    generated_prompts = all_prompts[:count]

    # Si on n'a pas assez, on répète les meilleurs
    while len(generated_prompts) < count:
        remaining_needed = count - len(generated_prompts)
        generated_prompts.extend(specialized_prompts[:remaining_needed])

    return {
        "prompts": generated_prompts[:count],
        "business_type": business_type,
        "location": location,
        "count": len(generated_prompts[:count]),
        "sector_specialized": business_type in sector_templates
    }
