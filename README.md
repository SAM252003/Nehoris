# GEO‑LLM Visibility Agent

Mesure et prédit l’apparition d’une marque/entreprise dans les réponses des LLM sur un lot de 100–120 requêtes.

## Métriques
- **Appear@Answer**: % de réponses qui mentionnent la marque.
- **Appear@Lead**: % de réponses avec mention dans les 300 1ers caractères.
- **FirstMentionPos**: position de première occurrence (caractère).
- **BrandHits** / **CompHits**: nombre d’occurrences.
- **SOV-LLM**: part des mentions de la marque vs concurrents.

## Utilisation
1. Édite `config.yaml` (brand, variants, concurrents, modèle, fichier de requêtes).
2. Lancer une campagne:
```bash
python -m src.geo_agent.cli campaign run --config config.yaml