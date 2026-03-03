"""
carta_virtual.py — Carta Virtual (QR en mesa).
Endpoints PÚBLICOS — sin autenticación.
El cliente escanea QR → ve menú → arma pedido → envía al mesero.

URL: metraes.com/carta/{qr_code}
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.models.zone import Zone
from app.models.category import Category
from app.models.product import Product
from app.models.user import User
from app.models.order import Order
from app.schemas import VirtualOrderCreate
from app.services import order_service
from app.websocket.manager import manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# PAGE: Servir la carta virtual
# ============================================================

@router.get("/carta/{qr_code}")
async def carta_virtual_page(
    request: Request,
    qr_code: str,
    db: Session = Depends(get_db),
):
    """
    Página de Carta Virtual.
    QR code identifica mesa → restaurante → menú.
    """
    # Buscar mesa por QR
    table = db.query(Table).options(
        joinedload(Table.zone),
        joinedload(Table.restaurant),
    ).filter(Table.qr_code == qr_code).first()

    if not table or not table.restaurant:
        return templates.TemplateResponse("carta_404.html", {
            "request": request,
            "message": "Mesa no encontrada. Pide al mesero un nuevo código QR.",
        })

    return _render_carta(request, table)


@router.get("/carta")
async def carta_virtual_by_number(
    request: Request,
    restaurant_id: int = None,
    mesa: int = None,
    db: Session = Depends(get_db),
):
    """
    Acceso alternativo sin QR: /carta?restaurant_id=3&mesa=5
    Para clientes sin cámara o para el dueño durante demos.
    """
    if not restaurant_id or not mesa:
        return templates.TemplateResponse("carta_404.html", {
            "request": request,
            "message": "Indica el número de mesa. Ejemplo: /carta?restaurant_id=3&mesa=5",
        })

    table = db.query(Table).options(
        joinedload(Table.zone),
        joinedload(Table.restaurant),
    ).filter(
        Table.restaurant_id == restaurant_id,
        Table.number == mesa,
    ).first()

    if not table or not table.restaurant:
        return templates.TemplateResponse("carta_404.html", {
            "request": request,
            "message": f"Mesa {mesa} no encontrada en este restaurante.",
        })

    return _render_carta(request, table)


def _render_carta(request: Request, table):
    """Helper: renderiza carta virtual para una mesa."""
    restaurant = table.restaurant

    if not restaurant.virtual_menu_enabled:
        return templates.TemplateResponse("carta_404.html", {
            "request": request,
            "message": f"{restaurant.name} no tiene carta virtual habilitada.",
        })

    is_https = request.headers.get('x-forwarded-proto', 'http') == 'https' or \
               request.url.scheme == 'https'
    ws_proto = 'wss' if is_https else 'ws'
    host = request.headers.get('host', 'localhost:8000')

    config = {
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.trade_name or restaurant.name,
        "logo_url": restaurant.logo_url,
        "table_id": table.id,
        "table_number": table.number,
        "table_label": table.label or f"Mesa {table.number}",
        "zone_name": table.zone.name if table.zone else None,
        "zone_color": table.zone.color if table.zone else "#3b82f6",
        "qr_code": table.qr_code,
        "currency": restaurant.currency or "PEN",
        "takeaway_enabled": restaurant.takeaway_enabled,
        "delivery_enabled": restaurant.delivery_enabled,
        "payment_methods": restaurant.payment_methods or {},
        "api_base": "/api/v1/carta",
        "ws_base": f"{ws_proto}://{host}/api/v1/carta/ws",
    }

    return templates.TemplateResponse("carta_virtual.html", {
        "request": request,
        "config": config,
    })


# ============================================================
# API: Menú público (sin auth)
# ============================================================

@router.get("/api/v1/carta/menu/{restaurant_id}")
async def get_public_menu(
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    """Menú público para carta virtual. Sin auth."""
    restaurant = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id,
        Restaurant.is_active == True,
    ).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")

    cats = db.query(Category).filter(
        Category.restaurant_id == restaurant_id,
        Category.is_active == True,
    ).order_by(Category.sort_order).all()

    prods = db.query(Product).filter(
        Product.restaurant_id == restaurant_id,
        Product.is_active == True,
        Product.is_available == True,
    ).order_by(Product.sort_order).all()

    return {
        "restaurant": {
            "name": restaurant.trade_name or restaurant.name,
            "logo_url": restaurant.logo_url,
            "banner_url": restaurant.virtual_menu_banner_url,
            "schedule": restaurant.schedule,
        },
        "categories": [
            {
                "id": c.id, "name": c.name, "icon": c.icon,
                "color": c.color, "image_url": c.image_url,
            }
            for c in cats
        ],
        "products": [
            {
                "id": p.id, "category_id": p.category_id,
                "name": p.name, "description": p.description,
                "price": float(p.sale_price),
                "image_url": p.image_url,
                "sizes": p.sizes or [],
                "modifiers": p.modifiers or [],
                "is_new": p.is_new, "is_bestseller": p.is_bestseller,
                "is_spicy": p.is_spicy, "is_featured": p.is_featured,
                "allergens": p.allergens or [],
                "prep_time_minutes": p.prep_time_minutes,
            }
            for p in prods
        ],
    }


# ============================================================
# API: Crear pedido desde carta virtual (sin auth)
# ============================================================

@router.post("/api/v1/carta/order", status_code=status.HTTP_201_CREATED)
async def create_virtual_order(
    data: VirtualOrderCreate,
    db: Session = Depends(get_db),
):
    """
    Cliente envía pedido desde carta virtual.
    No requiere auth. Identifica mesa por table_id.
    Asigna mesero automáticamente según zona.
    Estado: 'pending_approval' → mesero confirma → 'sent' a cocina.
    """
    if not data.table_id and not data.customer_name:
        raise HTTPException(400, "Se requiere mesa o nombre del cliente")

    if not data.items:
        raise HTTPException(400, "El pedido debe tener al menos un item")

    # Determinar restaurante y mesero
    restaurant_id = None
    waiter_id = None
    zone_id = None

    if data.table_id:
        table = db.query(Table).options(
            joinedload(Table.zone),
        ).filter(Table.id == data.table_id).first()
        if not table:
            raise HTTPException(404, "Mesa no encontrada")
        restaurant_id = table.restaurant_id
        zone_id = table.zone_id

        # Auto-asignar mesero de la zona (el que tenga menos mesas)
        if zone_id:
            waiter = db.query(User).filter(
                User.restaurant_id == restaurant_id,
                User.role == "waiter",
                User.assigned_zone_id == zone_id,
                User.is_active == True,
            ).first()
            if waiter:
                waiter_id = waiter.id
    else:
        # Takeaway/delivery sin mesa — necesitamos restaurant_id del primer producto
        if data.items:
            prod = db.query(Product).filter(Product.id == data.items[0].product_id).first()
            if prod:
                restaurant_id = prod.restaurant_id

    if not restaurant_id:
        raise HTTPException(400, "No se pudo determinar el restaurante")

    # Crear pedido con order_source="virtual_menu"
    from app.schemas import OrderCreate
    order_data = OrderCreate(
        table_id=data.table_id,
        order_type=data.order_type,
        order_source="virtual_menu",
        guest_count=1,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_address=data.customer_address,
        customer_notes=data.customer_notes,
        priority="normal",
        items=data.items,
    )

    order = order_service.create_order(
        db=db,
        data=order_data,
        restaurant_id=restaurant_id,
        waiter_id=waiter_id,
    )

    # Enviar directo a cocina (send_to_kitchen)
    order = order_service.send_to_kitchen(db, order)

    # Notificar cocina por WebSocket
    from app.services.kitchen_service import get_pending_orders
    kds_data = get_pending_orders(db, restaurant_id)

    await manager.send_to_kitchen(restaurant_id, {
        "event": "order_sent",
        "data": {
            "order_id": order.id,
            "order_number": order.order_number,
            "order_source": "virtual_menu",
            "table_display": f"Mesa {table.number}" if data.table_id else data.customer_name,
            "orders": kds_data,
        }
    })

    # Notificar mesero asignado (si existe)
    if waiter_id:
        await manager.send_to_user(waiter_id, {
            "event": "virtual_order_new",
            "data": {
                "order_id": order.id,
                "order_number": order.order_number,
                "table_number": table.number if data.table_id else None,
                "customer_name": data.customer_name,
                "item_count": len(data.items),
                "total": float(order.total),
            }
        })

    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "total": float(order.total),
        "message": "Pedido enviado. El mesero lo confirmará en breve.",
    }