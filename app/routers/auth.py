"""
Auth Router — Login por PIN (meseros/cocina) y por email (admin).
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import verify_password, create_access_token
from app.models.user import User
from app.schemas import LoginPIN, LoginEmail, TokenOut

router = APIRouter()


@router.post("/login/pin", response_model=TokenOut)
async def login_pin(data: LoginPIN, db: Session = Depends(get_db)):
    """Login rápido con PIN de 4-6 dígitos (meseros, cocina, cajeros)."""
    user = db.query(User).filter(
        User.restaurant_id == data.restaurant_id,
        User.pin == data.pin,
        User.is_active == True,
    ).first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PIN incorrecto")
    
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    
    token = create_access_token(user)
    return TokenOut(
        access_token=token,
        user={
            "id": user.id,
            "name": user.name,
            "short_name": user.short_name or user.name.split()[0],
            "role": user.role,
            "restaurant_id": user.restaurant_id,
            "branch_id": user.branch_id,
            "assigned_zone_id": user.assigned_zone_id,
            "assigned_station_id": user.assigned_station_id,
        }
    )


@router.post("/login", response_model=TokenOut)
async def login_email(data: LoginEmail, db: Session = Depends(get_db)):
    """Login con email/password (owner, manager)."""
    user = db.query(User).filter(
        User.email == data.email,
        User.is_active == True,
    ).first()
    
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    
    token = create_access_token(user)
    return TokenOut(
        access_token=token,
        user={
            "id": user.id,
            "name": user.name,
            "short_name": user.short_name or user.name.split()[0],
            "role": user.role,
            "restaurant_id": user.restaurant_id,
            "branch_id": user.branch_id,
        }
    )