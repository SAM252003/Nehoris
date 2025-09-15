# src/server.py
import os, csv, json, gzip
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import requests

load_dotenv()

MAX_PROMPTS = int(os.getenv("MAX_PROMPTS", 20))
MAX_RUNS = int(os.getenv("MAX_RUNS_PER_PROMPT", 2))
MAX_EST_MB = int(os.getenv("MAX_EST_MB", 500))

EXPORTS_DIR = Path(__file__).resolve().parents[1] / "data" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

# --------- Modèle d'entrée de campagne ----------
class CampaignIn(BaseModel):
    company: str
    variants: list[str] = []
    competitors: list[str] = []
    prompts: list[str]
    runs: int = 1
    model: str

def estimate_mb(prompts_count: int, runs: int, per_run_per_prompt_mb: float = 5.0) -> float:
    return prompts_count * runs * per_run_per_prompt_mb

# --------- Écriture compressée (résultats bruts) ----------
def write_result_line(path_gz: Path, row: dict):
    path_gz.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path_gz, "at", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

# --------- Page HTML -----------
@app.get("/", response_class=HTMLResponse)
def page():
    html_path = Path(__file__).with_name("templates") / "index.html"
    return html_path.read_text(encoding="utf-8")

# --------- Lancement de campagne (avec limites) -----------
@app.post("/api/campaigns/run")
def run_campaign(body: CampaignIn):
    prompts = [p.strip() for p in body.prompts if p.strip()]
    if len(prompts) == 0:
        raise HTTPException(status_code=400, detail="Aucun prompt fourni.")
    if len(prompts) > MAX_PROMPTS:
        raise HTTPException(status_code=400, detail=f"Trop de prompts ({len(prompts)}). Max: {MAX_PROMPTS}.")
    if body.runs < 1 or body.runs > MAX_RUNS:
        raise HTTPException(status_code=400, detail=f"Runs par prompt invalide ({body.runs}). Max: {MAX_RUNS}.")

    est = estimate_mb(len(prompts), body.runs)
    if est > MAX_EST_MB:
        raise HTTPException(status_code=400, detail=f"Campagne estimée ~{int(est)} MB > limite {MAX_EST_MB} MB.")

    # --- TODO: ici place ton appel LLM réel / pipeline ---
    # Exemple: on simule un résultat minimal et on l'écrit en JSONL.GZ + un CSV résumé

    run_id = f"{body.company.replace(' ','_')}_runs{body.runs}.jsonl.gz"
    raw_path = EXPORTS_DIR / run_id

    summary_csv = EXPORTS_DIR / f"{body.company.replace(' ','_')}_summary.csv"
    write_header = not summary_csv.exists()
    with summary_csv.open("a", encoding="utf-8", newline="") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=["company","prompt","model","run","answer_preview"])
        if write_header:
            writer.writeheader()

        for i, p in enumerate(prompts, start=1):
            for r in range(1, body.runs+1):
                fake_answer = f"Réponse pour prompt #{i} (run {r})"
                write_result_line(raw_path, {
                    "company": body.company,
                    "prompt": p,
                    "model": body.model,
                    "run": r,
                    "answer": fake_answer
                })
                writer.writerow({
                    "company": body.company,
                    "prompt": p[:120],
                    "model": body.model,
                    "run": r,
                    "answer_preview": fake_answer[:120]
                })

    return {"ok": True, "prompts": len(prompts), "runs": body.runs, "raw": str(raw_path.name), "summary": summary_csv.name}

# --------- Liste des exports (pour éviter 'Load failed') ----------
@app.get("/api/exports/list")
def list_exports():
    items = []
    for p in EXPORTS_DIR.glob("*"):
        if p.is_file():
            items.append({"name": p.name, "size_mb": round(p.stat().st_size/1_000_000, 1)})
    items.sort(key=lambda x: x["name"])
    return {"items": items}

# --------- Aperçu d'un export CSV (lazy load) ----------
@app.get("/api/exports/preview")
def preview_export(name: str, limit: int = Query(50, le=200)):
    path = EXPORTS_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    if path.suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Seuls les CSV ont un aperçu ici.")
    rows = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, r in enumerate(reader):
            if i >= limit: break
            rows.append(r)
    return {"columns": list(rows[0].keys()) if rows else [], "rows": rows, "limit": limit}
