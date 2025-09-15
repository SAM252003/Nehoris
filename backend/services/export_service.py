import os, csv, datetime as dt
from sqlmodel import Session, select
from ..models import Run

EXPORT_DIR = os.getenv("EXPORT_DIR", "data/exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

def export_campaign_csv(session: Session, campaign_id: int) -> str:
    rows = session.exec(select(Run).where(Run.campaign_id == campaign_id)).all()
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(EXPORT_DIR, f"campaign_{campaign_id}_{ts}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
    w.writerow(
        ["campaign_id", "prompt_id", "run_index", "model", "appear_answer", "appear_lead", "first_pos", "brand_hits",
         "comp_hits", "sources", "rankings", "created_at"])
    for r in rows:
        w.writerow([
            r.campaign_id,
            r.prompt_id,
            r.run_index,
            r.model,
            r.appear_answer,
            r.appear_lead,
            r.first_pos,
            r.brand_hits,
            r.comp_hits,
            r.sources,
            r.rankings,
            r.created_at.isoformat(),
        ])
    return path

