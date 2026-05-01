from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.models import User
from app.db.session import get_db
from app.auth import sessions


def get_current_user(
    session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status_code=401, detail="unauthorized")
    s = sessions.lookup_active_session(db, session_id=session)
    if s is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    user = db.get(User, s.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user
