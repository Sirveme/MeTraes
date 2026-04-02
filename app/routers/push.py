"""
push.py — Gestion de Push Subscriptions.
VAPID key publica, subscribe/unsubscribe, test push.
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.services import push_service

router = APIRouter()


# ============================================================
# SCHEMAS
# ============================================================

class SubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    device_name: Optional[str] = None


# ============================================================
# GET /api/v1/push/vapid-key — Publico
# ============================================================

@router.get("/api/v1/push/vapid-key")
async def get_vapid_key():
    """Devuelve VAPID public key para el cliente."""
    public_key = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not public_key:
        raise HTTPException(status_code=503, detail="Push notifications no configuradas")
    return {"public_key": public_key}


# ============================================================
# POST /api/v1/push/subscribe — Auth
# ============================================================

@router.post("/api/v1/push/subscribe")
async def subscribe(
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra subscription push para el dispositivo actual."""
    # Verificar si ya existe esta subscription (mismo endpoint)
    existing = db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint,
    ).first()

    if existing:
        # Reactivar si estaba inactiva
        existing.is_active = True
        existing.p256dh = body.p256dh
        existing.auth = body.auth
        existing.user_id = user.id
        existing.restaurant_id = user.restaurant_id
        existing.device_name = body.device_name
        db.commit()
        return {"status": "updated", "subscription_id": existing.id}

    sub = PushSubscription(
        restaurant_id=user.restaurant_id,
        user_id=user.id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        device_name=body.device_name,
    )
    db.add(sub)
    db.commit()

    return {"status": "subscribed", "subscription_id": sub.id}


# ============================================================
# DELETE /api/v1/push/unsubscribe — Auth
# ============================================================

@router.delete("/api/v1/push/unsubscribe")
async def unsubscribe(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Desactiva todas las subscriptions del usuario."""
    count = db.query(PushSubscription).filter(
        PushSubscription.user_id == user.id,
        PushSubscription.is_active == True,
    ).update({"is_active": False})
    db.commit()
    return {"status": "unsubscribed", "deactivated": count}


# ============================================================
# POST /api/v1/push/test — Auth
# ============================================================

@router.post("/api/v1/push/test")
async def test_push(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Envia push de prueba al usuario actual."""
    push_service.send_push(
        db,
        restaurant_id=user.restaurant_id,
        title="Notificacion de prueba",
        body="Las notificaciones push estan funcionando correctamente.",
        user_ids=[user.id],
    )
    return {"status": "sent", "message": "Push de prueba enviado"}
