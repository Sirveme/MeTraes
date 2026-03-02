"""
Kitchen Service — Lógica del KDS.
Cambio de estado de items, detección de retrasos, datos para pantalla.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.kitchen_station import KitchenStation
from app.models.table import Table
from app.models.user import User
from app.schemas import KDSOrder, KDSOrderItem


def get_pending_orders(db: Session, restaurant_id: int, station_id: int = None) -> list[dict]:
    """
    Pedidos activos para el KDS.
    Si station_id, filtra items de esa estación solamente.
    """
    query = db.query(Order).options(
        joinedload(Order.items).joinedload(OrderItem.station),
        joinedload(Order.table),
        joinedload(Order.zone),
        joinedload(Order.waiter),
    ).filter(
        Order.restaurant_id == restaurant_id,
        Order.status.in_(["sent", "preparing"]),
    ).order_by(Order.sent_to_kitchen_at.asc())
    
    orders = query.all()
    result = []
    
    for order in orders:
        # Filtrar items por estación si aplica
        if station_id:
            items = [i for i in order.items if i.station_id == station_id and i.status in ("sent", "preparing")]
        else:
            items = [i for i in order.items if i.status in ("sent", "preparing")]
        
        if not items:
            continue
        
        # Construir display de mesa
        table_display = "Sin mesa"
        if order.table:
            table_display = order.table.display_name
        elif order.order_type == "delivery":
            table_display = f"🛵 Delivery - {order.customer_name or 'Cliente'}"
        elif order.order_type == "takeaway":
            table_display = f"📦 Para llevar - {order.customer_name or 'Cliente'}"
        
        waiter_name = None
        if order.waiter:
            waiter_name = order.waiter.short_name or order.waiter.name.split()[0]
        
        kds_items = []
        for item in items:
            kds_items.append({
                "id": item.id,
                "product_name": item.product_name,
                "quantity": float(item.quantity),
                "size_name": item.size_name,
                "modifiers_summary": item.modifier_summary,
                "notes": item.notes,
                "status": item.status,
                "is_urgent": item.is_urgent,
                "is_fire": item.is_fire,
                "course": item.course,
                "prep_wait_minutes": item.prep_wait_minutes,
            })
        
        result.append({
            "id": order.id,
            "order_number": order.order_number,
            "order_type": order.order_type,
            "table_display": table_display,
            "waiter_name": waiter_name,
            "priority": order.priority,
            "status": order.status,
            "items": kds_items,
            "sent_to_kitchen_at": order.sent_to_kitchen_at.isoformat() if order.sent_to_kitchen_at else None,
            "kitchen_wait_minutes": order.kitchen_wait_minutes,
            "guest_count": order.guest_count,
        })
    
    return result


def update_item_status(db: Session, item_id: int, new_status: str, user_id: int = None) -> dict:
    """
    Cambia estado de un item en el KDS.
    sent → preparing → ready (o cancelled)
    Retorna datos para broadcast por WebSocket.
    """
    item = db.query(OrderItem).options(
        joinedload(OrderItem.order).joinedload(Order.table),
        joinedload(OrderItem.order).joinedload(Order.waiter),
    ).filter(OrderItem.id == item_id).first()
    
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item no encontrado")
    
    now = datetime.now(timezone.utc)
    order = item.order
    
    # Validar transición de estado
    valid_transitions = {
        "sent": ["preparing", "cancelled"],
        "preparing": ["ready", "cancelled"],
    }
    if item.status not in valid_transitions or new_status not in valid_transitions.get(item.status, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede cambiar de '{item.status}' a '{new_status}'"
        )
    
    # Aplicar cambio
    item.status = new_status
    
    if new_status == "preparing":
        item.started_at = now
        if user_id:
            item.prepared_by_id = user_id
        # Actualizar estado del pedido
        if order.status == "sent":
            order.status = "preparing"
    
    elif new_status == "ready":
        item.ready_at = now
        # ¿Todos los items del pedido están listos?
        if not order.first_item_ready_at:
            order.first_item_ready_at = now
        
        active_items = [i for i in order.items if i.status not in ("cancelled", "ready")]
        if not active_items:
            order.status = "ready"
            order.all_items_ready_at = now
            # Actualizar mesa
            if order.table:
                order.table.status = "occupied"
    
    elif new_status == "cancelled":
        item.cancelled_at = now
        if user_id:
            item.cancelled_by_id = user_id
    
    db.commit()
    
    # Datos para WebSocket
    table_display = "Sin mesa"
    if order.table:
        table_display = order.table.display_name
    
    waiter_id = order.waiter_id
    
    return {
        "item_id": item.id,
        "item_name": item.product_name,
        "item_status": new_status,
        "order_id": order.id,
        "order_number": order.order_number,
        "order_status": order.status,
        "table_display": table_display,
        "station_id": item.station_id,
        "waiter_id": waiter_id,
        "restaurant_id": order.restaurant_id,
        "table_id": order.table_id,
    }


def get_stations(db: Session, restaurant_id: int) -> list[dict]:
    """Estaciones de cocina activas con conteo de items pendientes."""
    stations = db.query(KitchenStation).filter(
        KitchenStation.restaurant_id == restaurant_id,
        KitchenStation.is_active == True,
    ).order_by(KitchenStation.sort_order).all()
    
    result = []
    for s in stations:
        pending_count = db.query(OrderItem).filter(
            OrderItem.station_id == s.id,
            OrderItem.status.in_(["sent", "preparing"]),
        ).count()
        
        result.append({
            "id": s.id,
            "name": s.name,
            "short_name": s.short_name,
            "display_name": s.display_name or s.name,
            "color": s.color,
            "icon": s.icon,
            "target_time_minutes": s.target_time_minutes,
            "alert_time_minutes": s.alert_time_minutes,
            "pending_count": pending_count,
            "is_accepting_orders": s.is_accepting_orders,
        })
    
    return result