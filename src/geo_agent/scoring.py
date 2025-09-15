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