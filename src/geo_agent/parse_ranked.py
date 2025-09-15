"""
Extraction de classements (Top N) depuis un texte libre.
Retourne un dict {brand_canon: rank}, où rank commence à 1.
Heuristiques:
- listes numérotées "1. ..." ou "1) ..." ou bullets "- • –"
- tableaux Markdown (1re colonne)
- fallback: ordre de première apparition dans le texte
"""

from __future__ import annotations
from typing import Dict, List
import re

NUM_RE = re.compile(r"^\s*(\d+[\.\)]\s+)(.+)$")
BULLET_RE = re.compile(r"^\s*([-*•–]\s+)(.+)$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")  # ligne markdown | a | b |
CELL_SPLIT_RE = re.compile(r"\s*\|\s*")

def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def _shorten(item: str) -> str:
    # garde le "nom" avant virgule/parenthèse/— pour réduire le bruit
    return re.split(r"[,(–—-]", item)[0].strip()

def _try_list_lines(lines: List[str], brand_map: Dict[str, str]) -> Dict[str, int]:
    ranks: Dict[str, int] = {}
    rank = 1
    for ln in lines:
        m = NUM_RE.match(ln) or BULLET_RE.match(ln)
        if not m:
            continue
        content = _shorten(_norm(m.group(2)))
        for variant, canon in brand_map.items():
            if variant in content and canon not in ranks:
                ranks[canon] = rank
                rank += 1
                break
    return ranks

def _try_table(lines: List[str], brand_map: Dict[str, str]) -> Dict[str, int]:
    # Détecte un tableau markdown, mappe la 1re colonne à un rang
    rows: List[List[str]] = []
    for ln in lines:
        m = TABLE_ROW_RE.match(ln)
        if not m:
            continue
        cells = [c.strip() for c in CELL_SPLIT_RE.split(m.group(1))]
        if cells:
            rows.append(cells)
    if len(rows) < 2:
        return {}
    # retirer séparateurs |---|
    rows = [r for r in rows if not all(set(ch) <= {"-", ":"} for ch in r)]
    ranks: Dict[str, int] = {}
    for i, r in enumerate(rows, start=1):
        head = _shorten(_norm(r[0]))
        for variant, canon in brand_map.items():
            if variant in head and canon not in ranks:
                ranks[canon] = i
                break
    return ranks

def parse_ranked(text: str, brand_map: Dict[str, str]) -> Dict[str, int]:
    """
    :param text: réponse LLM
    :param brand_map: {variant_normalisée: canon}
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # 1) listes
    ranks = _try_list_lines(lines, brand_map)
    if ranks:
        return ranks
    # 2) tableaux
    ranks = _try_table(lines, brand_map)
    if ranks:
        return ranks
    # 3) fallback: ordre de 1re apparition globale
    low = text.lower()
    first_pos: Dict[str, int] = {}
    for variant, canon in brand_map.items():
        idx = low.find(variant)
        if idx >= 0 and canon not in first_pos:
            first_pos[canon] = idx
    out: Dict[str, int] = {}
    for canon, _ in sorted(first_pos.items(), key=lambda kv: kv[1]):
        out[canon] = len(out) + 1
    return out
