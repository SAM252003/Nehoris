from typing import List, Dict, Any
import statistics


def aggregate_per_query(rows: List[Dict[str, Any]]):
    by_q: Dict[str, List[Dict]] = {}
    for r in rows:
        by_q.setdefault(r["query"], []).append(r)
    per_q = {}
    for q, subset in by_q.items():
        n = len(subset)
        appear_answer = sum(1 for r in subset if r["appear_answer"]) / n
        appear_lead = sum(1 for r in subset if r["appear_lead"]) / n
        first_positions = [r["first_pos"] for r in subset if r["first_pos"] >= 0]
        avg_first_pos = statistics.mean(first_positions) if first_positions else None
        avg_brand_hits = statistics.mean([r["brand_hits"] for r in subset])

        # competitors avg
        comp_keys = subset[0]["comp_hits"].keys() if subset else []
        avg_comp = {k: statistics.mean([r["comp_hits"][k] for r in subset]) for k in comp_keys}

        per_q[q] = {
            "Appear@Answer": round(appear_answer, 4),
            "Appear@Lead": round(appear_lead, 4),
            "AvgFirstPos": None if avg_first_pos is None else round(avg_first_pos, 1),
            "AvgBrandHits": round(avg_brand_hits, 3),
            "AvgCompHits": {k: round(v, 3) for k, v in avg_comp.items()},
        }

    return per_q


def share_of_voice(rows: List[Dict[str, Any]]):
    total_brand = sum(r["brand_hits"] for r in rows)
    comp_totals: Dict[str, int] = {}
    for r in rows:
        for k, v in r["comp_hits"].items():
            comp_totals[k] = comp_totals.get(k, 0) + v
    denom = total_brand + sum(comp_totals.values())
    sov = (total_brand / denom) if denom > 0 else 0.0
    return {
        "total_brand_hits": total_brand,
        "competitors": comp_totals,
        "SOV": round(sov, 4),
    }

# --- GEO brand scoring helpers ---
from typing import List, Dict, Any
from src.geo_agent.brand.brand_models import BrandMatch

def summarize_brand_matches(matches: List[BrandMatch]) -> Dict[str, Any]:
    """
    Regroupe les matches par marque :
    - total, exact, fuzzy
    - first_mention_index (indice du 1er hit)
    """
    summary: Dict[str, Any] = {}
    for m in matches:
        s = summary.setdefault(m.brand, {"total": 0, "exact": 0, "fuzzy": 0, "first_mention_index": None})
        s["total"] += 1
        if m.method == "exact":
            s["exact"] += 1
        elif m.method == "fuzzy":
            s["fuzzy"] += 1
        # met à jour la première position si plus tôt
        if s["first_mention_index"] is None or (isinstance(m.start, int) and m.start < s["first_mention_index"]):
            s["first_mention_index"] = m.start
    return summary
# --- GEO brand scoring helpers (batch) ---
from __future__ import annotations
from typing import List, Dict, Any, Optional
from statistics import mean, median
from src.geo_agent.brand.brand_models import BrandMatch

def summarize_brand_matches(matches: List[BrandMatch]) -> Dict[str, Any]:
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

def aggregate_batch(per_prompt_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Agrège une liste de {brand: {total, exact, fuzzy, first_mention_index}}
    en métriques globales par marque:
      - total_mentions, exact_total, fuzzy_total
      - prompts_with_mention, mention_rate (0..1)
      - avg_first_index, median_first_index (sur les prompts où mentionnée)
    """
    brands = set()
    for s in per_prompt_summaries:
        brands.update(s.keys())

    out: Dict[str, Any] = {}
    n_prompts = len(per_prompt_summaries)

    for b in sorted(brands):
        totals = 0
        exacts = 0
        fuzzys = 0
        firsts: List[int] = []
        p_with = 0
        for s in per_prompt_summaries:
            if b in s:
                row = s[b]
                totals += int(row.get("total", 0))
                exacts += int(row.get("exact", 0))
                fuzzys += int(row.get("fuzzy", 0))
                idx = row.get("first_mention_index")
                if isinstance(idx, int):
                    firsts.append(idx)
                p_with += 1  # ce prompt a au moins 1 mention pour cette marque
        out[b] = {
            "total_mentions": totals,
            "exact_total": exacts,
            "fuzzy_total": fuzzys,
            "prompts_with_mention": p_with,
            "mention_rate": (p_with / n_prompts) if n_prompts else 0.0,
            "avg_first_index": (mean(firsts) if firsts else None),
            "median_first_index": (median(firsts) if firsts else None),
        }
    return {"n_prompts": n_prompts, "by_brand": out}
