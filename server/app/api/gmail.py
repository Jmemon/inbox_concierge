from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.models import User
from app.db.session import get_db
from app.deps import get_current_user
from app.gmail.client import fetch_profile_summary


router = APIRouter(prefix="/api/gmail", tags=["gmail"])


@router.get("/profile")
def profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return fetch_profile_summary(db, user)
