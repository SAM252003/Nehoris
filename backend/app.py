# backend/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routes import companies, prompts, campaigns, exports

app = FastAPI(title="GEO LLM Visibility API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/health")
def health():
    return {"ok": True}

# Routers
app.include_router(companies.router)
app.include_router(prompts.router)
app.include_router(campaigns.router)
app.include_router(exports.router)

