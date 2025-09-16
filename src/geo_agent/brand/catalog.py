from __future__ import annotations
from typing import Iterable, List
from unidecode import unidecode

def normalize(s: str) -> str:
    return unidecode(s).lower().strip()

def all_variants(name: str, variants: Iterable[str]) -> List[str]:
    base = [name]
    outs = set(normalize(v) for v in (list(base) + list(variants)))
    more = set()
    for v in list(outs):
        more.add(v.replace("-", " "))
        more.add(v.replace(" ", ""))
    return sorted(outs | more)
