from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session
from ..db import get_session
from ..services.export_service import export_campaign_csv
from ..schema import ExportOut

router = APIRouter(prefix="/exports", tags=["exports"])

@router.post("/campaign/{campaign_id}", response_model=ExportOut)
def export_campaign(campaign_id: int, session: Session = Depends(get_session)):
    path = export_campaign_csv(session, campaign_id)
    return ExportOut(path=path)

@router.get("/campaign/{campaign_id}.csv")
def download_campaign_csv(campaign_id: int, session: Session = Depends(get_session)):
    path = export_campaign_csv(session, campaign_id)
    try:
        return FileResponse(path, media_type="text/csv", filename=f"campaign_{campaign_id}.csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
