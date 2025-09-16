# src/geo_agent/brand/detector.py
from __future__ import annotations
from typing import List
import re
from rapidfuzz import fuzz
from src.geo_agent.brand.brand_models import Brand, BrandMatch
from src.geo_agent.brand.catalog import normalize, all_variants

def _compile_regex(variants: List[str]):
    patterns = []
    for v in variants:
        if re.search(r"[\\w]", v):
            pat = re.compile(rf"\\b{re.escape(v)}\\b", re.IGNORECASE)
        else:
            pat = re.compile(re.escape(v), re.IGNORECASE)
        patterns.append(pat)
    return patterns

def detect_exact(text: str, brand: Brand) -> List[BrandMatch]:
    matches: List[BrandMatch] = []
    variants = all_variants(brand.name, brand.variants)
    for rx in _compile_regex(variants):
        for m in rx.finditer(text):
            matches.append(
                BrandMatch(
                    brand=brand.name,
                    variant=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    score=100.0,
                    method="exact",
                    context=text[max(0, m.start()-30): m.end()+30],
                )
            )
    return matches

def detect_fuzzy(text: str, brand: Brand, threshold: float) -> List[BrandMatch]:
    matches: List[BrandMatch] = []
    ntext = normalize(text)
    variants = all_variants(brand.name, brand.variants)
    for v in variants:
        score = fuzz.token_set_ratio(ntext, v)
        if score >= threshold:
            token = v.split()[0]
            i = ntext.find(token)
            start = max(0, i) if i >= 0 else 0
            end = min(len(text), start + len(v))
            matches.append(
                BrandMatch(
                    brand=brand.name,
                    variant=v,
                    start=start,
                    end=end,
                    score=float(score),
                    method="fuzzy",
                    context=text[max(0, start-30): end+30],
                )
            )
    return matches

def detect(text: str, brands: List[Brand], fuzzy_threshold: float = 85.0) -> List[BrandMatch]:
    all_matches: List[BrandMatch] = []
    for b in brands:
        all_matches.extend(detect_exact(text, b))
        if fuzzy_threshold:
            all_matches.extend(detect_fuzzy(text, b, fuzzy_threshold))
    # de-dupe par (brand, start, end, method)
    uniq = {}
    for m in sorted(all_matches, key=lambda m: (-m.score, m.start)):
        key = (m.brand.lower(), m.start, m.end, m.method)
        if key not in uniq:
            uniq[key] = m
    return list(uniq.values())
