import os, csv, json
from typing import List, Dict

class Storage:
def __init__(self, out_dir: str):
    self.out_dir = out_dir
    os.makedirs(out_dir, exist_ok=True)
    self.results_path = os.path.join(out_dir, "results.csv")
    self.raw_path = os.path.join(out_dir, "raw.ndjson")

def append_results(self, rows: List[Dict]):
    write_header = not os.path.exists(self.results_path)
    with open(self.results_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "model", "query", "run_id", "appear_answer", "appear_lead",
                "first_pos", "brand_hits", "comp_hits", "created_at"
            ],
        )
    if write_header:
        w.writeheader()
    for r in rows:
        r2 = dict(r)
    r2["comp_hits"] = json.dumps(r2["comp_hits"], ensure_ascii=False)
    w.writerow(r2)

def append_raw(self, rows: List[Dict]):
    with open(self.raw_path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")