"""
Mentions & visibilité — détection robuste (exact + fuzzy).
Usage:
    det = MentionDetector(brand_variants=["\\bPizza del Mama\\b", "pizzadelmama.com"],
                          competitors=["Domino's", "Pizza Hut"])
    stats = det.analyze(text)  # -> MentionStats(...)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Iterable
import re

# Fuzzy matching (optionnel) — chute gracieuse si absent
try:
    from rapidfuzz.fuzz import partial_ratio  # type: ignore
    _FUZZY_AVAILABLE = True
except Exception:  # pragma: no cover
    partial_ratio = None  # type: ignore
    _FUZZY_AVAILABLE = False


@dataclass
class MentionStats:
    appear_answer: bool
    appear_lead: bool
    first_pos: int
    brand_hits: int
    comp_hits: Dict[str, int]


class MentionDetector:
    """
    Détecte les mentions de la marque cible et des concurrents dans un texte.
    - Match exact via regex (tu peux inclure \\b dans tes variantes pour limiter aux mots complets)
    - Fuzzy matching (RapidFuzz) pour tolérer fautes et petites variantes
    """

    def __init__(
        self,
        brand_variants: List[str],
        competitors: List[str],
        lead_chars: int = 300,
        fuzzy: bool = True,
        fuzzy_threshold: int = 88,
    ) -> None:
        if not brand_variants:
            raise ValueError("brand_variants ne peut pas être vide")
        self.brand_patterns = [re.compile(v, re.IGNORECASE) for v in brand_variants]
        self.comp_patterns = {c: re.compile(c, re.IGNORECASE) for c in competitors}
        self.lead = max(0, int(lead_chars))
        self.fuzzy = bool(fuzzy and _FUZZY_AVAILABLE)
        self.fuzzy_threshold = int(fuzzy_threshold)
        # terme “principal” pour fuzzy = première variante débarrassée des \\b
        self._brand_main = self._strip_tokens(self.brand_patterns[0].pattern)

    # ----------------- helpers internes -----------------

    @staticmethod
    def _strip_tokens(pat: str) -> str:
        return pat.replace("\\b", "").strip()

    @staticmethod
    def _words(text: str) -> Iterable[str]:
        # tokens alphanum + - .  (capture domaines et composés)
        return re.findall(r"[\w\-.]{3,}", text, flags=re.UNICODE)

    def _fuzzy_hits(self, text: str, term: str) -> int:
        if not self.fuzzy:
            return 0
        t = term.lower()
        return sum(1 for w in self._words(text) if partial_ratio(w.lower(), t) >= self.fuzzy_threshold)

    @staticmethod
    def _regex_hits(text: str, patterns: List[re.Pattern]) -> List[re.Match]:
        hits: List[re.Match] = []
        for p in patterns:
            hits.extend(p.finditer(text))
        return sorted(hits, key=lambda m: m.start())

    # ----------------- API publique -----------------

    def appear_in_answer(self, text: str) -> bool:
        """True si la marque apparaît (exact ou fuzzy) quelque part dans la réponse."""
        if self._regex_hits(text, self.brand_patterns):
            return True
        return self._fuzzy_hits(text, self._brand_main) > 0

    def appear_in_lead(self, text: str) -> bool:
        """True si la marque apparaît dans les X premiers caractères (lead)."""
        head = text[: self.lead]
        return self.appear_in_answer(head)

    def first_index(self, text: str) -> int:
        """Index caractère de la première mention (exacte), -1 si absente."""
        hits = self._regex_hits(text, self.brand_patterns)
        return hits[0].start() if hits else -1

    def count_brand_hits(self, text: str) -> int:
        """Nombre d’occurrences (exact + fuzzy principal)."""
        exact = len(self._regex_hits(text, self.brand_patterns))
        fuzzy_n = self._fuzzy_hits(text, self._brand_main)
        return exact + fuzzy_n

    def count_competitor_hits(self, text: str) -> Dict[str, int]:
        """Nombre d’occurrences par concurrent (exact + fuzzy)."""
        out: Dict[str, int] = {c: len(list(p.finditer(text))) for c, p in self.comp_patterns.items()}
        if self.fuzzy:
            for c in list(out.keys()):
                out[c] += self._fuzzy_hits(text, c)
        return out

    def analyze(self, text: str) -> MentionStats:
        """Retourne toutes les métriques de base pour un texte donné."""
        return MentionStats(
            appear_answer=self.appear_in_answer(text),
            appear_lead=self.appear_in_lead(text),
            first_pos=self.first_index(text),
            brand_hits=self.count_brand_hits(text),
            comp_hits=self.count_competitor_hits(text),
        )

    # -------- utilitaire pour le parser de classement --------
    def build_brand_map(self) -> Dict[str, str]:
        """
        Construit un dict {variant_normalisée: canon} à partir des variantes & concurrents.
        - canon = nom “principal” de la marque cible pour toutes ses variantes
        - les concurrents pointent vers eux-mêmes
        """
        canon = self._brand_main or "brand"
        m: Dict[str, str] = {}
        for p in self.brand_patterns:
            v = self._strip_tokens(p.pattern).lower()
            if v:
                m[v] = canon
        for c in self.comp_patterns.keys():
            m[c.lower()] = c
        return m
