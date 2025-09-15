from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Prompt

router = APIRouter(prefix="/prompts", tags=["prompts"])

@router.post("", response_model=dict)
def upsert_prompts(body: dict, session: Session = Depends(get_session)):
    """
    body = {"prompts": ["...", "..."]}
    Crée si absent, renvoie les IDs.
    """
    created_ids: list[int] = []
    prompts = body.get("prompts", [])
    if not isinstance(prompts, list):
        raise HTTPException(status_code=400, detail="prompts must be a list")
    for p in prompts:
        text = (p or "").strip()
        if not text:
            continue
        row = session.exec(select(Prompt).where(Prompt.text == text)).first()
        if not row:
            row = Prompt(text=text)
            session.add(row)
            session.commit()
            session.refresh(row)
        created_ids.append(row.id)  # type: ignore
    return {"prompt_ids": created_ids}

@router.get("", response_model=list[dict])
def list_prompts(session: Session = Depends(get_session)):
    rows = session.exec(select(Prompt)).all()
    return [{"id": r.id, "text": r.text} for r in rows]

@router.delete("/{prompt_id}", response_model=dict)
def delete_prompt(prompt_id: int, session: Session = Depends(get_session)):
    row = session.get(Prompt, prompt_id)
    if not row:
        raise HTTPException(status_code=404, detail="Prompt not found")
    session.delete(row)
    session.commit()
    return {"ok": True}
