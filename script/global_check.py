# scripts/global_check.py
from __future__ import annotations
import os, argparse, json, csv, sys
from typing import List, Dict, Any

# ⚠️ Imports ABSOLUS (respectent ta structure)
from src.geo_agent.brand.brand_models import Brand
from src.geo_agent.brand.detector import detect

# On essaie OpenAI si clé dispo, sinon Ollama
def _choose_provider(args_provider: str | None) -> str:
    if args_provider and args_provider != "auto":
        return args_provider
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "ollama"

def _ask_openai(model: str | None, prompt: str, temperature: float) -> str:
    from src.geo_agent.models.openai_client import OpenAIClient
    cli = OpenAIClient()  # lit OPENAI_API_KEY
    # compat: ton client peut exposer answer(...) ou answer_with_meta(...)
    if hasattr(cli, "answer"):
        return cli.answer([{"role": "user", "content": prompt}], model=model, temperature=temperature)  # type: ignore
    return cli.answer_with_meta(prompt, temperature=temperature)["text"]  # type: ignore

def _ask_ollama(model: str | None, prompt: str, temperature: float) -> str:
    from src.geo_agent.models.ollama_client import OllamaClient
    cli = OllamaClient(model=model or os.getenv("OLLAMA_MODEL", "llama3.2:1b-instruct"))
    if hasattr(cli, "answer"):
        return cli.answer(prompt, temperature=temperature)  # type: ignore
    return cli.answer_with_meta(prompt, temperature=temperature)["text"]  # type: ignore

def _health_ollama() -> bool:
    import requests
    host = (os.getenv("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
    try:
        r = requests.get(f"{host}/api/tags", timeout=5)
        r.raise_for_status()
        return True
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="auto", help="auto|openai|ollama")
    ap.add_argument("--model", default="llama3.2:1b-instruct-fp16")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--prompt", default="Meilleur pizza a paris.")
    ap.add_argument("--csv", default="out/geo_demo_metrics.csv")
    args = ap.parse_args()

    provider = _choose_provider(args.provider)
    print(f"[provider] {provider}")

    if provider == "ollama" and not _health_ollama():
        print("❌ Ollama KO (vérifie OLLAMA_HOST et que le serveur tourne).")
        sys.exit(1)
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY manquante.")
        sys.exit(1)

    # 1) Pose le prompt
    if provider == "openai":
        answer_text = _ask_openai(args.model, args.prompt, args.temperature)
    else:
        answer_text = _ask_ollama(args.model, args.prompt, args.temperature)

    print("\n[answer]\n", answer_text[:500], "...\n")

    # 2) Détection de marques
    brands: List[Brand] = [
        Brand(name="Pizza Del Mama", variants=["PizzaDelMama", "PDM"]),
        Brand(name="Globex", variants=["Globex Pizza"]),
    ]
    matches = detect(answer_text, brands, fuzzy_threshold=85.0)

    # 3) Résumé simple (pour SOV / first mention)
    summary: Dict[str, Any] = {}
    for m in matches:
        s = summary.setdefault(m.brand, {"total": 0, "exact": 0, "fuzzy": 0, "first_mention_index": None})
        s["total"] += 1
        if m.method == "exact":
            s["exact"] += 1
        elif m.method == "fuzzy":
            s["fuzzy"] += 1
        if s["first_mention_index"] is None or m.start < s["first_mention_index"]:
            s["first_mention_index"] = m.start

    print("[summary]")
    print(json.dumps(summary, indent=2))

    # 4) (Option) export CSV
    os.makedirs(os.path.dirname(args.csv), exist_ok=True)
    rows = []
    for brand, s in summary.items():
        rows.append({
            "brand": brand,
            "total": s["total"],
            "exact": s["exact"],
            "fuzzy": s["fuzzy"],
            "first_mention_index": s["first_mention_index"],
        })
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["brand", "total", "exact", "fuzzy", "first_mention_index"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n[export] CSV écrit → {args.csv}")

if __name__ == "__main__":
    # Lancer avec: PYTHONPATH=. python scripts/global_check.py
    main()
