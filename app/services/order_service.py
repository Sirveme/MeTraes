"""
Order Service — Lógica de negocio para pedidos.
Crear, agregar items, enviar a cocina, calcular totales.
"""

from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.table import Table
from app.schemas import OrderCreate, OrderItemCreate, OrderAddItems


def get_next_order_number(db: Session, restaurant_id: int) -> int:
    """Correlativo diario. Resetea cada día."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    last = db.query(func.max(Order.daily_sequence)).filter(
        Order.restaurant_id == restaurant_id,
        Order.created_at >= today_start,
    ).scalar()
    return (last or 0) + 1


def create_order(db: Session, data: OrderCreate, restaurant_id: int, waiter_id: int = None, branch_id: int = None) -> Order:
    """Crea pedido con items."""
    seq = get_next_order_number(db, restaurant_id)
    
    order = Order(
        restaurant_id=restaurant_id,
        branch_id=branch_id,
        order_type=data.order_type,
        order_source=data.order_source,
        order_number=seq,
        daily_sequence=seq,
        table_id=data.table_id,
        waiter_id=waiter_id,
        guest_count=data.guest_count,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_address=data.customer_address,
        customer_notes=data.customer_notes,
        priority=data.priority,
        notes=data.notes,
        status="open",
    )
    db.add(order)
    db.flush()  # Obtener order.id
    
    # Agregar items
    if data.items:
        _add_items_to_order(db, order, data.items)
        db.flush()  # Flush items para que _recalculate_totals los encuentre (autoflush=False)

    # Actualizar mesa si aplica
    if data.table_id:
        table = db.query(Table).filter(Table.id == data.table_id).first()
        if table:
            table.status = "occupied"
            table.current_order_id = order.id
            table.assigned_waiter_id = waiter_id
    
    # Recalcular totales
    _recalculate_totals(db, order)
    
    db.commit()
    db.refresh(order)
    return order


def add_items(db: Session, order: Order, data: OrderAddItems) -> Order:
    """Agrega items a pedido abierto (sin cerrar y reabrir)."""
    if order.status in ("paid", "cancelled"):
        print(f"[add_items] RECHAZADO: order {order.id} status={order.status}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Pedido {order.status}, no se pueden agregar items")

    _add_items_to_order(db, order, data.items)
    db.flush()  # Flush nuevos items para que _recalculate_totals los encuentre (autoflush=False)
    _recalculate_totals(db, order)
    
    db.commit()
    db.refresh(order)
    return order


def send_to_kitchen(db: Session, order: Order) -> Order:
    """Envía pedido a cocina. Cambia estado de items pending → sent."""
    now = datetime.now(timezone.utc)
    
    pending_items = [i for i in order.items if i.status == "pending"]
    if not pending_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No hay items pendientes para enviar")
    
    for item in pending_items:
        item.status = "sent"
        item.sent_at = now
    
    # Actualizar estado del pedido
    if order.status == "open":
        order.status = "sent"
        order.sent_to_kitchen_at = now
    
    # Actualizar mesa
    if order.table_id:
        table = db.query(Table).filter(Table.id == order.table_id).first()
        if table:
            table.status = "waiting"
    
    db.commit()
    db.refresh(order)
    return order


def _add_items_to_order(db: Session, order: Order, items: list[OrderItemCreate]):
    """Helper interno: crea OrderItems a partir de los datos del request."""
    for item_data in items:
        product = db.query(Product).filter(Product.id == item_data.product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto {item_data.product_id} no encontrado"
            )
        
        # Calcular precio según size
        unit_price = product.sale_price
        if item_data.size_name and product.sizes:
            for size in product.sizes:
                if size.get("name") == item_data.size_name:
                    unit_price = Decimal(str(size.get("price", product.sale_price)))
                    break
        
        # Calcular total de modificadores
        modifier_total = Decimal("0")
        for mod in item_data.modifiers:
            modifier_total += Decimal(str(mod.get("price", 0)))
        
        # Line total
        qty = Decimal(str(item_data.quantity))
        line_total = (unit_price + modifier_total) * qty
        
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            station_id=product.station_id,
            product_name=product.short_name or product.name,
            quantity=item_data.quantity,
            unit_price=unit_price,
            size_name=item_data.size_name,
            modifiers=item_data.modifiers,
            notes=item_data.notes,
            modifier_total=modifier_total,
            line_total=line_total,
            course=item_data.course,
            is_urgent=item_data.is_urgent,
            status="pending",
        )
        db.add(order_item)


def _recalculate_totals(db: Session, order: Order):
    """Recalcula subtotal, IGV y total del pedido."""
    items = db.query(OrderItem).filter(
        OrderItem.order_id == order.id,
        OrderItem.status != "cancelled",
    ).all()
    
    subtotal = sum(i.line_total for i in items)
    # IGV incluido en precio (como es estándar en Perú)
    # subtotal = total con IGV, base = subtotal / 1.18
    tax_rate = Decimal("0.18")
    base = subtotal / (1 + tax_rate)
    tax_amount = subtotal - base
    
    order.subtotal = subtotal
    order.tax_amount = tax_amount.quantize(Decimal("0.01"))
    order.total = subtotal + (order.tip_amount or 0) + (order.delivery_fee or 0) - (order.discount_amount or 0)