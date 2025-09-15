import os, csv, json, typer
from .config import Settings
from .scoring import aggregate_per_query, share_of_voice

# --- helpers ---
def _as_bool(x) -> bool:
    return str(x).strip().lower() in {"true", "1", "yes", "y", "t"}

def _load_results_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        typer.echo(f"⚠️  Fichier introuvable : {path}")
        raise typer.Exit(code=1)
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            return rows


    elif action == "score":
    cfg = Settings.load(config)
    out = cfg.io.out_dir
    results_csv = os.path.join(out, "results.csv")
    rows_file = _load_results_csv(results_csv)

    # typer-compatible: cast les champs dont on a besoin
    rows = []
    for row in rows_file:
        rows.append({
            "query": row["query"],
            "appear_answer": _as_bool(row.get("appear_answer")),
            "appear_lead": _as_bool(row.get("appear_lead")),
            "first_pos": int(row.get("first_pos") or -1),
            "brand_hits": int(row.get("brand_hits") or 0),
            "comp_hits": json.loads(row.get("comp_hits") or "{}"),
            "sources": json.loads(row.get("sources") or "[]"),
        })

    per_q = aggregate_per_query(rows)
    sov = share_of_voice(rows)
    metrics_path = os.path.join(out, "metrics.csv")

    # écrit un CSV simple d'agrégats par prompt
    with open(metrics_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "Appear@Answer", "Appear@Lead", "AvgFirstPos", "AvgBrandHits"])
        for q, vals in per_q.items():
            w.writerow([
                q,
                vals["Appear@Answer"],
                vals["Appear@Lead"],
                vals["AvgFirstPos"],
                vals["AvgBrandHits"],
            ])

    typer.echo(f"Scores écrits dans {metrics_path}")
    typer.echo("SOV global :")
    typer.echo(json.dumps(sov, ensure_ascii=False, indent=2))

    elif action == "tally":
    cfg = Settings.load(config)
    out = cfg.io.out_dir
    results_csv = os.path.join(out, "results.csv")
    rows = _load_results_csv(results_csv)

    # --- Compte PAR RUN (tous les runs) ---
    total_runs = len(rows)
    mentions_runs = sum(1 for r in rows if _as_bool(r.get("appear_answer")))
    pct_runs = (mentions_runs / total_runs * 100) if total_runs else 0.0

    # --- Compte PAR PROMPT (1 vote par prompt) ---
    # utile si runs_per_query > 1 : un prompt compte s'il a AU MOINS une mention
    per_query_seen: dict[str, bool] = {}
    for r in rows:
        q = (r.get("query") or "").strip()
        hit = _as_bool(r.get("appear_answer"))
        per_query_seen[q] = per_query_seen.get(q, False) or hit

    total_prompts = len(per_query_seen)
    mentions_prompts = sum(1 for v in per_query_seen.values() if v)
    pct_prompts = (mentions_prompts / total_prompts * 100) if total_prompts else 0.0

    typer.echo(f"Par RUN    : {mentions_runs}/{total_runs} ({pct_runs:.1f}%)")
    typer.echo(f"Par PROMPT : {mentions_prompts}/{total_prompts} "
               f"({pct_prompts:.1f}%)  ← pour un 'X/100' exact")

    typer.echo("Astuce : pour avoir exactement 'X/100', mets runs_per_query=1 et 100 prompts.")

