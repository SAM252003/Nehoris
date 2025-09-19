# backend/app.py
from .db import init_db
from .routes import companies, prompts, campaigns, exports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import geo as geo_router
from backend.routes import llm as llm_routes

# --- bootstrap sys.path pour accéder à src/ ---
import os, sys
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
# ----------------------------------------------

app = FastAPI(title="Nehoris API")

# CORS pour le front en dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Routers
app.include_router(geo_router.router)
app.include_router(llm_routes.router)
app.include_router(companies.router)
app.include_router(prompts.router)
app.include_router(campaigns.router)
app.include_router(exports.router)

# WebSocket routes pour streaming
from backend import websocket_routes
app.include_router(websocket_routes.router)

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/health")
def health():
    return {"ok": True}

