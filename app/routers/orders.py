"""
Orders Router — CRUD de pedidos + enviar a cocina.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.order_item import OrderItem
from app.schemas import OrderCreate, OrderAddItems, OrderOut
from app.services import order_service
from app.websocket.manager import manager

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Crea un pedido nuevo (desde POS mesero o caja)."""
    order = order_service.create_order(
        db=db,
        data=data,
        restaurant_id=user.restaurant_id,
        waiter_id=user.id,
        branch_id=user.branch_id,
    )
    return _order_to_dict(db, order)


@router.post("/{order_id}/items")
async def add_items_to_order(
    order_id: int,
    data: OrderAddItems,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Agrega items a un pedido abierto."""
    order = _get_order(db, order_id, user.restaurant_id)
    order = order_service.add_items(db, order, data)
    return _order_to_dict(db, order)


@router.put("/{order_id}/send-to-kitchen")
async def send_order_to_kitchen(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Envía pedido a cocina. Los items pending pasan a sent."""
    order = _get_order(db, order_id, user.restaurant_id)
    order = order_service.send_to_kitchen(db, order)
    
    # Notificar a cocina por WebSocket
    from app.services.kitchen_service import get_pending_orders
    kds_data = get_pending_orders(db, user.restaurant_id)
    
    # Enviar a canal general de cocina
    await manager.send_to_kitchen(user.restaurant_id, {
        "event": "order_sent",
        "data": {
            "order_id": order.id,
            "order_number": order.order_number,
            "orders": kds_data,
        }
    })
    
    # Enviar también a canales por estación
    station_ids = set(i.station_id for i in order.items if i.station_id and i.status == "sent")
    for sid in station_ids:
        station_data = get_pending_orders(db, user.restaurant_id, station_id=sid)
        await manager.send_to_kitchen(user.restaurant_id, {
            "event": "order_sent",
            "data": {"orders": station_data}
        }, station_id=sid)
    
    return _order_to_dict(db, order)


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Obtiene detalle de un pedido."""
    order = _get_order(db, order_id, user.restaurant_id)
    return _order_to_dict(db, order)


@router.get("")
async def list_orders(
    status_filter: str = None,
    table_id: int = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista pedidos activos del restaurante."""
    query = db.query(Order).filter(Order.restaurant_id == user.restaurant_id)
    
    if status_filter:
        statuses = status_filter.split(",")
        query = query.filter(Order.status.in_(statuses))
    else:
        # Por defecto: pedidos activos
        query = query.filter(Order.status.in_(["open", "sent", "preparing", "ready", "served"]))
    
    if table_id:
        query = query.filter(Order.table_id == table_id)
    
    orders = query.order_by(Order.created_at.desc()).limit(50).all()
    return [_order_to_dict(db, o) for o in orders]


# --- Helpers ---

def _get_order(db: Session, order_id: int, restaurant_id: int) -> Order:
    order = db.query(Order).options(
        joinedload(Order.items),
        joinedload(Order.table),
        joinedload(Order.waiter),
    ).filter(
        Order.id == order_id,
        Order.restaurant_id == restaurant_id,
    ).first()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
    return order


def _order_to_dict(db: Session, order: Order) -> dict:
    """Serializa Order con items y display helpers."""
    # Cargar relaciones si no están cargadas
    if not order.items:
        db.refresh(order, ["items", "table", "waiter"])
    
    table_display = None
    if order.table:
        table_display = order.table.display_name
    elif order.order_type == "delivery":
        table_display = f"🛵 {order.customer_name or 'Delivery'}"
    elif order.order_type == "takeaway":
        table_display = f"📦 {order.customer_name or 'Para llevar'}"
    
    waiter_name = None
    if order.waiter:
        waiter_name = order.waiter.short_name or order.waiter.name.split()[0]
    
    return {
        "id": order.id,
        "restaurant_id": order.restaurant_id,
        "order_number": order.order_number,
        "order_type": order.order_type,
        "order_source": order.order_source,
        "table_id": order.table_id,
        "zone_id": order.zone_id,
        "waiter_id": order.waiter_id,
        "status": order.status,
        "priority": order.priority,
        "guest_count": order.guest_count,
        "subtotal": float(order.subtotal or 0),
        "tax_amount": float(order.tax_amount or 0),
        "discount_amount": float(order.discount_amount or 0),
        "tip_amount": float(order.tip_amount or 0),
        "total": float(order.total or 0),
        "payment_method": order.payment_method,
        "notes": order.notes,
        "table_display": table_display,
        "waiter_name": waiter_name,
        "customer_name": order.customer_name,
        "opened_at": order.opened_at.isoformat() if order.opened_at else None,
        "sent_to_kitchen_at": order.sent_to_kitchen_at.isoformat() if order.sent_to_kitchen_at else None,
        "all_items_ready_at": order.all_items_ready_at.isoformat() if order.all_items_ready_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "kitchen_wait_minutes": order.kitchen_wait_minutes,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "product_name": i.product_name,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "size_name": i.size_name,
                "modifiers": i.modifiers or [],
                "notes": i.notes,
                "line_total": float(i.line_total),
                "status": i.status,
                "station_id": i.station_id,
                "course": i.course,
                "is_urgent": i.is_urgent,
                "sent_at": i.sent_at.isoformat() if i.sent_at else None,
                "ready_at": i.ready_at.isoformat() if i.ready_at else None,
                "prep_wait_minutes": i.prep_wait_minutes,
            }
            for i in order.items
        ],
    }