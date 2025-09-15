from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login_stub():
    # À implémenter quand le modèle User/exigences JWT seront en place
    raise HTTPException(status_code=501, detail="Auth not implemented yet")

@router.post("/register")
def register_stub():
    raise HTTPException(status_code=501, detail="Auth not implemented yet")
