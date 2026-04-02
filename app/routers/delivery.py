"""
delivery.py — Pantalla de motorizado + API tracking GPS.
Sirve la pagina /delivery y los endpoints de gestion de entregas.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.order import Order
from app.models.user import User
from app.models.restaurant import Restaurant
from app.websocket.manager import manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# SCHEMAS
# ============================================================

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float


# ============================================================
# TEMPLATE: Pagina del motorizado
# GET /delivery?restaurant_id=N
# ============================================================

@router.get("/delivery")
async def delivery_page(
    request: Request,
    restaurant_id: int = Query(1),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")

    config = {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.trade_name or restaurant.name,
        "api_base": "/api/v1",
    }

    return templates.TemplateResponse("delivery.html", {
        "request": request,
        "config": config,
    })


# ============================================================
# API: Pedidos delivery pendientes
# GET /api/v1/delivery/orders
# ============================================================

@router.get("/api/v1/delivery/orders")
async def delivery_orders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pedidos delivery listos para despachar o en camino."""
    orders = db.query(Order).filter(
        Order.restaurant_id == user.restaurant_id,
        Order.order_type == "delivery",
        Order.status.in_(["ready", "dispatched"]),
    ).order_by(Order.all_items_ready_at.asc()).all()

    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "order_number": o.order_number,
            "status": o.status,
            "customer_name": o.customer_name or "Cliente",
            "customer_phone": o.customer_phone,
            "customer_address": o.customer_address or "Sin direccion",
            "customer_notes": o.customer_notes,
            "total": float(o.total or 0),
            "item_count": len(o.items) if o.items else 0,
            "ready_at": o.all_items_ready_at.isoformat() if o.all_items_ready_at else None,
            "dispatched_at": o.dispatched_at.isoformat() if o.dispatched_at else None,
            "delivery_driver_id": o.delivery_driver_id,
        })

    return {"orders": result}


# ============================================================
# API: Motorizado recoge pedido
# PUT /api/v1/delivery/{order_id}/pickup
# ============================================================

@router.put("/api/v1/delivery/{order_id}/pickup")
async def pickup_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Motorizado recoge el pedido — cambia status a dispatched."""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.restaurant_id == user.restaurant_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if order.status != "ready":
        raise HTTPException(status_code=400, detail=f"Pedido no esta listo (status: {order.status})")

    now = datetime.now(timezone.utc)
    order.status = "dispatched"
    order.dispatched_at = now
    order.delivery_driver_id = user.id
    db.commit()

    # Notificar admin via WebSocket
    await manager.send_to_admin(user.restaurant_id, {
        "event": "delivery_dispatched",
        "data": {
            "order_id": order.id,
            "order_number": order.order_number,
            "driver_name": user.short_name or user.name,
        }
    })

    # Push notification
    try:
        from app.services.push_service import notify_delivery_dispatched
        notify_delivery_dispatched(
            db, user.restaurant_id,
            order.order_number,
            user.short_name or user.name,
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "order_id": order.id,
        "order_status": order.status,
        "dispatched_at": now.isoformat(),
    }


# ============================================================
# API: Motorizado entrega pedido
# PUT /api/v1/delivery/{order_id}/deliver
# ============================================================

@router.put("/api/v1/delivery/{order_id}/deliver")
async def deliver_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Motorizado marca pedido como entregado."""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.restaurant_id == user.restaurant_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if order.status != "dispatched":
        raise HTTPException(status_code=400, detail=f"Pedido no esta despachado (status: {order.status})")

    now = datetime.now(timezone.utc)
    order.status = "delivered"
    order.delivered_at = now
    order.served_at = now
    db.commit()

    # Notificar admin
    await manager.send_to_admin(user.restaurant_id, {
        "event": "delivery_delivered",
        "data": {
            "order_id": order.id,
            "order_number": order.order_number,
            "driver_name": user.short_name or user.name,
        }
    })

    return {
        "status": "ok",
        "order_id": order.id,
        "order_status": order.status,
        "delivered_at": now.isoformat(),
    }


# ============================================================
# API: Actualizar GPS del motorizado
# POST /api/v1/delivery/{order_id}/location
# ============================================================

@router.post("/api/v1/delivery/{order_id}/location")
async def update_driver_location(
    order_id: int,
    body: LocationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Motorizado envia su ubicacion GPS."""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.restaurant_id == user.restaurant_id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    now = datetime.now(timezone.utc)
    order.delivery_driver_latitude = body.latitude
    order.delivery_driver_longitude = body.longitude
    order.delivery_driver_updated_at = now
    db.commit()

    return {"status": "ok", "updated_at": now.isoformat()}


# ============================================================
# API: Ver ubicacion del motorizado (publico, para el cliente)
# GET /api/v1/delivery/{order_id}/tracking
# ============================================================

@router.get("/api/v1/delivery/{order_id}/tracking")
async def get_driver_tracking(
    order_id: int,
    db: Session = Depends(get_db),
):
    """Ubicacion actual del motorizado — sin auth, para el cliente."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    driver_name = None
    if order.delivery_driver_id:
        driver = db.query(User).filter(User.id == order.delivery_driver_id).first()
        if driver:
            driver_name = driver.short_name or driver.name

    return {
        "order_id": order.id,
        "status": order.status,
        "driver_name": driver_name,
        "driver_latitude": float(order.delivery_driver_latitude) if order.delivery_driver_latitude else None,
        "driver_longitude": float(order.delivery_driver_longitude) if order.delivery_driver_longitude else None,
        "driver_updated_at": order.delivery_driver_updated_at.isoformat() if order.delivery_driver_updated_at else None,
        "customer_address": order.customer_address,
        "dispatched_at": order.dispatched_at.isoformat() if order.dispatched_at else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
    }
