from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserSession
from app.schemas import LoginIn, PasswordChangeIn, SessionOut
from app.security import (
    create_session,
    current_session,
    end_session,
    hash_password,
    login_throttle,
    needs_rehash,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["autenticazione"])


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=SessionOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    key = _client_key(request)
    if login_throttle.blocked(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Troppi tentativi falliti: riprova tra 15 minuti")
    user = db.scalars(select(User).where(User.username == data.username)).first()
    if user is None or not verify_password(user.password_hash, data.password):
        login_throttle.fail(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nome utente o password non corretti")
    login_throttle.reset(key)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(data.password)
    session = create_session(db, user, response)
    return SessionOut(username=user.username, csrf_token=session.csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, session: UserSession = Depends(current_session), db: Session = Depends(get_db)):
    end_session(db, session, response)


@router.get("/me", response_model=SessionOut)
def me(session: UserSession = Depends(current_session)):
    return SessionOut(username=session.user.username, csrf_token=session.csrf_token)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChangeIn, session: UserSession = Depends(current_session), db: Session = Depends(get_db)
):
    user = db.get(User, session.user_id)
    if not verify_password(user.password_hash, data.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La password attuale non è corretta")
    user.password_hash = hash_password(data.new_password)
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.id != session.id).delete()
    db.commit()
