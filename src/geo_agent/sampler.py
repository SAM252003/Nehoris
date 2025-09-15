import time, uuid, datetime as dt
from typing import List, Dict
from .extract import MentionExtractor
from .prompts import build_user_prompt, GENERIC_SYSTEM
from .models.openai_client import OpenAIClient
from .models.ollama_client import OllamaClient
from .models.perplexity_client import PerplexityClient # NEW


def make_client(model_spec: str):
    prov, model = model_spec.split(":", 1)
    if prov == "openai":
        return OpenAIClient(model)
    if prov == "ollama":
        return OllamaClient(model)
    if prov == "perplexity":  # NEW (web-grounded)
        return PerplexityClient(model)
    raise ValueError(f"Fournisseur non supporté: {prov}")


def run_batch(model_spec: str, queries: List[str], runs_per_query: int, temperature: float,
extractor: MentionExtractor) -> List[Dict]:
    client = make_client(model_spec)
    rows: List[Dict] = []

    for q in queries:
        for _ in range(runs_per_query):
            run_id = str(uuid.uuid4())
    messages = [{"role": "system", "content": GENERIC_SYSTEM}] + build_user_prompt(q)
    text = client.answer(messages, temperature=temperature)

    row = {
        "model": client.name,
        "query": q,
        "run_id": run_id,
        "appear_answer": extractor.appear_at_answer(text),
        "appear_lead": extractor.appear_at_lead(text),
        "first_pos": extractor.first_pos(text),
        "brand_hits": extractor.brand_hits(text),
        "comp_hits": extractor.comp_hits(text),
        "created_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "_text": text,
    }
    rows.append(row)
    time.sleep(0.15)
    return rows

import time, uuid, datetime as dt
from typing import List, Dict
from .extracts import MentionExtractor
from .prompts import build_user_prompt, GENERIC_SYSTEM
from .models.openai_client import OpenAIClient
from .models.ollama_client import OllamaClient= # NEW
# (Anthropic/Perplexity clients peuvent être ajoutés ici)


def make_client(model_spec: str):
    prov, model = model_spec.split(":", 1)
    if prov == "openai":
        return OpenAIClient(model)
    if prov == "ollama":  # NEW
        return OllamaClient(model)
    raise ValueError(f"Fournisseur non supporté: {prov}")


def run_batch(model_spec: str, queries: List[str], runs_per_query: int, temperature: float,
extractor: MentionExtractor) -> List[Dict]:
    client = make_client(model_spec)
    rows: List[Dict] = []
    return rows