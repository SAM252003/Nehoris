import os, json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="GEO‑LLM Visibility", layout="wide")

OUT_DIR = "data/outputs"
results_csv = os.path.join(OUT_DIR, "results.csv")
metrics_csv = os.path.join(OUT_DIR, "metrics.csv")

st.title("GEO‑LLM Visibility — Dashboard")

if os.path.exists(results_csv):
    df = pd.read_csv(results_csv)
    st.metric("Total runs", len(df))
    st.dataframe(df.head(50))
else:
    st.warning("Run the campaign first to generate results.csv")

st.divider()
if os.path.exists(metrics_csv):
    dm = pd.read_csv(metrics_csv)
    st.subheader("Per‑Query Metrics")
    st.dataframe(dm)
else:
    st.info("Compute metrics with: python -m src.geo_agent.cli campaign score")