"""
alerts.py — Configuracion de alertas y pagina de gestion.
CRUD de AlertConfig + pagina /alertas.
"""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.alert_config import AlertConfig, ALERT_TYPES
from app.models.user import User
from app.models.restaurant import Restaurant

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# SCHEMAS
# ============================================================

class AlertConfigUpdate(BaseModel):
    alert_type: str
    is_enabled: bool
    threshold_value: Optional[float] = None
    threshold_percent: Optional[int] = None


# ============================================================
# TEMPLATE: Pagina de alertas
# GET /alertas?restaurant_id=N
# ============================================================

@router.get("/alertas")
async def alertas_page(
    request: Request,
    restaurant_id: int = Query(1),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    config = {
        "restaurant_id": restaurant_id,
        "restaurant_name": (restaurant.trade_name or restaurant.name) if restaurant else "",
        "api_base": "/api/v1",
        "alert_types": {k: {"label": v["label"], "has_threshold": v["has_threshold"], "default": v["default"]} for k, v in ALERT_TYPES.items()},
    }
    return templates.TemplateResponse("alertas.html", {
        "request": request,
        "config": config,
    })


# ============================================================
# API: Lista configuracion de alertas del usuario
# GET /api/v1/alerts/config
# ============================================================

@router.get("/api/v1/alerts/config")
async def get_alert_configs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna la configuracion de alertas del usuario actual."""
    configs = db.query(AlertConfig).filter(
        AlertConfig.user_id == user.id,
        AlertConfig.restaurant_id == user.restaurant_id,
    ).all()

    # Merge con defaults
    existing = {c.alert_type: c for c in configs}
    result = []
    for atype, info in ALERT_TYPES.items():
        if atype in existing:
            c = existing[atype]
            result.append({
                "alert_type": atype,
                "label": info["label"],
                "has_threshold": info["has_threshold"],
                "is_enabled": c.is_enabled,
                "threshold_value": float(c.threshold_value) if c.threshold_value else None,
                "threshold_percent": c.threshold_percent,
            })
        else:
            result.append({
                "alert_type": atype,
                "label": info["label"],
                "has_threshold": info["has_threshold"],
                "is_enabled": info["default"],
                "threshold_value": None,
                "threshold_percent": None,
            })

    return {"configs": result}


# ============================================================
# API: Actualizar configuracion
# PUT /api/v1/alerts/config
# ============================================================

@router.put("/api/v1/alerts/config")
async def update_alert_configs(
    updates: list[AlertConfigUpdate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza configuracion de alertas del usuario."""
    for u in updates:
        if u.alert_type not in ALERT_TYPES:
            continue

        existing = db.query(AlertConfig).filter(
            AlertConfig.user_id == user.id,
            AlertConfig.restaurant_id == user.restaurant_id,
            AlertConfig.alert_type == u.alert_type,
        ).first()

        if existing:
            existing.is_enabled = u.is_enabled
            if u.threshold_value is not None:
                existing.threshold_value = u.threshold_value
            if u.threshold_percent is not None:
                existing.threshold_percent = u.threshold_percent
        else:
            config = AlertConfig(
                restaurant_id=user.restaurant_id,
                user_id=user.id,
                alert_type=u.alert_type,
                is_enabled=u.is_enabled,
                threshold_value=u.threshold_value,
                threshold_percent=u.threshold_percent,
            )
            db.add(config)

    db.commit()
    return {"status": "ok", "updated": len(updates)}
