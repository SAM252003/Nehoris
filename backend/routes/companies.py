from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Company
from ..schema import CompanyIn, CompanyOut

router = APIRouter(prefix="/companies", tags=["companies"])

@router.post("", response_model=CompanyOut)
def create_company(body: CompanyIn, session: Session = Depends(get_session)):
    c = Company(name=body.name, variants=body.variants, competitors=body.competitors)
    session.add(c)
    session.commit()
    session.refresh(c)
    return CompanyOut(id=c.id, name=c.name, variants=c.variants, competitors=c.competitors)

@router.get("", response_model=list[CompanyOut])
def list_companies(session: Session = Depends(get_session)):
    rows = session.exec(select(Company)).all()
    return [CompanyOut(id=c.id, name=c.name, variants=c.variants, competitors=c.competitors) for c in rows]

@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, session: Session = Depends(get_session)):
    c = session.get(Company, company_id)
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyOut(id=c.id, name=c.name, variants=c.variants, competitors=c.competitors)

@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(company_id: int, body: CompanyIn, session: Session = Depends(get_session)):
    c = session.get(Company, company_id)
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    c.name = body.name
    c.variants = body.variants
    c.competitors = body.competitors
    session.add(c)
    session.commit()
    session.refresh(c)
    return CompanyOut(id=c.id, name=c.name, variants=c.variants, competitors=c.competitors)

@router.delete("/{company_id}", response_model=dict)
def delete_company(company_id: int, session: Session = Depends(get_session)):
    c = session.get(Company, company_id)
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    session.delete(c)
    session.commit()
    return {"ok": True}
