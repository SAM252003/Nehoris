import csv
from typing import List
from .config import Settings
from .extract import MentionExtractor
from .sampler import run_batch
from .storage import Storage


def load_queries(path: str) -> List[str]:
    qs: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
    for row in r:
        if row.get("query"):
            qs.append(row["query"].strip())
    return qs


def run_campaign(config_path: str):
    cfg = Settings.load(config_path)
    cfg.ensure_dirs()

    queries = load_queries(cfg.campaign.queries_file)
    extractor = MentionExtractor(cfg.brand.variants, cfg.competitors, cfg.campaign.appear_lead_chars)
    store = Storage(cfg.io.out_dir)

    all_rows = []
    for model in cfg.campaign.models:
        rows = run_batch(
            model_spec=model,
            queries=queries,
            runs_per_query=cfg.campaign.runs_per_query,
            temperature=cfg.campaign.temperature,
            extractor=extractor,
        )
    all_rows.extend(rows)

    # Sauvegarde
    store.append_results([
        {k: v for k, v in r.items() if k != "_text"} for r in all_rows
    ])
    store.append_raw(all_rows)

    return len(all_rows)