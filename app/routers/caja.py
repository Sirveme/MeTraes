"""
caja.py — Router para Caja (POS Cobro + Facturación).
Pantalla principal del dueño/cajero de negocio pequeño.
Incluye: apertura/cierre de caja, venta rápida de menú,
venta a la carta, cobro, emisión de boleta/factura via Facturalo.pro,
y resumen diario con márgenes.
"""

from datetime import datetime, timezone, date
from decimal import Decimal
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.core.database import get_db
from app.core.auth import get_current_user, decode_token
from app.models.cash_register import CashRegister
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.category import Category
from app.models.sale import Sale
from app.models.user import User
from app.models.restaurant import Restaurant

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# TEMPLATE: Servir la página de Caja
# ============================================================

@router.get("/caja")
async def caja_page(
    request: Request,
    restaurant_id: int = 1,
    db: Session = Depends(get_db),
):
    """Pantalla de Caja."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        return templates.TemplateResponse("carta_404.html", {
            "request": request,
            "message": "Restaurante no encontrado.",
        })

    is_https = request.headers.get('x-forwarded-proto', 'http') == 'https' or \
               request.url.scheme == 'https'
    ws_proto = 'wss' if is_https else 'ws'
    host = request.headers.get('host', 'localhost:8000')

    config = {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.trade_name or restaurant.name,
        "ruc": restaurant.ruc,
        "api_base": "/api/v1",
        "ws_base": f"{ws_proto}://{host}/api/v1/kitchen/ws",
        "has_facturalo": bool(restaurant.facturalo_api_key),
    }

    return templates.TemplateResponse("caja.html", {
        "request": request,
        "config": config,
    })


# ============================================================
# API: Abrir Caja
# ============================================================

@router.post("/api/v1/caja/abrir")
async def abrir_caja(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Abrir turno de caja. Monto inicial opcional (default 0)."""
    body = await request.json()
    rid = current_user.restaurant_id
    monto = Decimal(str(body.get("monto_apertura", "0")))

    # Buscar caja del restaurante
    caja = db.query(CashRegister).filter(
        CashRegister.restaurant_id == rid,
        CashRegister.is_active == True,
    ).first()

    if not caja:
        raise HTTPException(status_code=404, detail="No hay caja configurada")

    if caja.is_open:
        # Ya está abierta, retornar info
        return {
            "status": "already_open",
            "caja_id": caja.id,
            "opened_at": caja.opened_at.isoformat() if caja.opened_at else None,
            "opened_by": caja.opened_by.name if caja.opened_by else None,
            "opening_amount": float(caja.opening_amount or 0),
        }

    caja.is_open = True
    caja.opened_by_id = current_user.id
    caja.opened_at = datetime.now(timezone.utc)
    caja.opening_amount = monto
    caja.current_cash = monto
    caja.current_sales_count = 0
    caja.current_sales_total = Decimal("0")
    db.commit()

    return {
        "status": "opened",
        "caja_id": caja.id,
        "opened_at": caja.opened_at.isoformat(),
        "opening_amount": float(monto),
    }


# ============================================================
# API: Estado de Caja
# ============================================================

@router.get("/api/v1/caja/estado")
async def estado_caja(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estado actual de la caja."""
    rid = current_user.restaurant_id
    caja = db.query(CashRegister).filter(
        CashRegister.restaurant_id == rid,
        CashRegister.is_active == True,
    ).first()

    if not caja:
        return {"is_open": False, "caja_id": None}

    return {
        "caja_id": caja.id,
        "is_open": caja.is_open,
        "opened_at": caja.opened_at.isoformat() if caja.opened_at else None,
        "opening_amount": float(caja.opening_amount or 0),
        "current_cash": float(caja.current_cash or 0),
        "current_sales_count": caja.current_sales_count or 0,
        "current_sales_total": float(caja.current_sales_total or 0),
    }


# ============================================================
# API: Cerrar Caja
# ============================================================

@router.post("/api/v1/caja/cerrar")
async def cerrar_caja(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cerrar turno de caja."""
    rid = current_user.restaurant_id
    body = await request.json()
    monto_cierre = Decimal(str(body.get("monto_cierre", "0")))

    caja = db.query(CashRegister).filter(
        CashRegister.restaurant_id == rid,
        CashRegister.is_active == True,
    ).first()

    if not caja or not caja.is_open:
        raise HTTPException(status_code=400, detail="Caja no está abierta")

    expected = caja.current_cash or Decimal("0")
    difference = monto_cierre - expected

    result = {
        "caja_id": caja.id,
        "opened_at": caja.opened_at.isoformat() if caja.opened_at else None,
        "closed_at": datetime.now(timezone.utc).isoformat(),
        "opening_amount": float(caja.opening_amount or 0),
        "total_sales": float(caja.current_sales_total or 0),
        "sales_count": caja.current_sales_count or 0,
        "expected_cash": float(expected),
        "actual_cash": float(monto_cierre),
        "difference": float(difference),
    }

    caja.is_open = False
    db.commit()

    return result


# ============================================================
# API: Productos + Categorías para Caja
# ============================================================

@router.get("/api/v1/caja/menu")
async def caja_menu(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Menú completo con costos para caja."""
    rid = current_user.restaurant_id

    categories = db.query(Category).filter(
        Category.restaurant_id == rid,
        Category.is_active == True,
    ).order_by(Category.sort_order).all()

    products = db.query(Product).filter(
        Product.restaurant_id == rid,
        Product.is_active == True,
    ).order_by(Product.sort_order, Product.name).all()

    return {
        "categories": [
            {
                "id": c.id, "name": c.name,
                "icon": c.icon, "sort_order": c.sort_order,
            }
            for c in categories
        ],
        "products": [
            {
                "id": p.id, "name": p.name, "short_name": p.short_name or p.name,
                "category_id": p.category_id,
                "sale_price": float(p.sale_price),
                "cost_price": float(p.cost_price) if p.cost_price else None,
                "sizes": p.sizes or [],
                "is_available": p.is_available,
                "is_instant": p.is_instant,
                "station_id": p.station_id,
            }
            for p in products
        ],
    }


# ============================================================
# API: Registrar Venta (Cobrar)
# ============================================================

@router.post("/api/v1/caja/venta")
async def registrar_venta(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registrar venta y opcionalmente emitir comprobante.
    Body: {
        items: [{product_id, quantity, unit_price, size_name?, cost_price?}],
        payment_method: "efectivo"|"yape"|"plin"|"tarjeta"|"mixto",
        paid_amount: 50.00,
        comprobante: "boleta"|"factura"|null,
        customer_doc_type: "1"|"6",  // DNI o RUC
        customer_doc_number: "12345678",
        customer_name: "Juan Pérez",
        order_type: "dine_in"|"takeaway"|"delivery",
        customer_notes: "",
        is_menu: false,
        menu_label: "Menú del día",
    }
    """
    body = await request.json()
    rid = current_user.restaurant_id
    items = body.get("items", [])
    payment_method = body.get("payment_method", "efectivo")
    paid_amount = Decimal(str(body.get("paid_amount", "0")))
    comprobante_type = body.get("comprobante")  # "boleta", "factura", or null
    order_type = body.get("order_type", "dine_in")

    if not items:
        raise HTTPException(status_code=400, detail="Sin items")

    # Buscar caja abierta
    caja = db.query(CashRegister).filter(
        CashRegister.restaurant_id == rid,
        CashRegister.is_active == True,
        CashRegister.is_open == True,
    ).first()

    if not caja:
        raise HTTPException(status_code=400, detail="Caja no está abierta")

    # Calcular totales
    subtotal = Decimal("0")
    total_cost = Decimal("0")
    order_items = []

    for item in items:
        qty = int(item.get("quantity", 1))
        unit_price = Decimal(str(item["unit_price"]))
        line_total = unit_price * qty
        subtotal += line_total

        cost = Decimal(str(item.get("cost_price", "0") or "0"))
        total_cost += cost * qty

        order_items.append({
            "product_id": item.get("product_id"),
            "product_name": item.get("product_name", "Item"),
            "quantity": qty,
            "unit_price": float(unit_price),
            "line_total": float(line_total),
            "cost_price": float(cost),
            "size_name": item.get("size_name"),
        })

    # IGV (incluido en precio para restaurantes)
    igv = (subtotal / Decimal("1.18") * Decimal("0.18")).quantize(Decimal("0.01"))
    total = subtotal
    change = paid_amount - total if paid_amount > total else Decimal("0")

    # Daily sequence
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    seq = db.query(sqlfunc.count(Order.id)).filter(
        Order.restaurant_id == rid,
        Order.created_at >= today_start,
    ).scalar() or 0
    seq += 1

    # Crear Order
    order = Order(
        restaurant_id=rid,
        branch_id=current_user.branch_id,
        order_type=order_type,
        order_source="pos",
        order_number=seq,
        daily_sequence=seq,
        waiter_id=current_user.id,
        cashier_id=current_user.id,
        cash_register_id=caja.id,
        subtotal=subtotal,
        tax_amount=igv,
        total=total,
        payment_method=payment_method,
        paid_amount=paid_amount,
        change_amount=change,
        status="paid",
        opened_at=datetime.now(timezone.utc),
        paid_at=datetime.now(timezone.utc),
        notes=body.get("customer_notes", ""),
        customer_name=body.get("customer_name", ""),
        customer_phone=body.get("customer_phone", ""),
    )
    db.add(order)
    db.flush()

    # Crear OrderItems
    for oi in order_items:
        db_item = OrderItem(
            order_id=order.id,
            product_id=oi["product_id"],
            product_name=oi["product_name"],
            quantity=oi["quantity"],
            unit_price=Decimal(str(oi["unit_price"])),
            line_total=Decimal(str(oi["line_total"])),
            size_name=oi.get("size_name"),
            status="served",
        )
        db.add(db_item)

    # Crear Sale
    sale = Sale(
        restaurant_id=rid,
        branch_id=current_user.branch_id,
        order_id=order.id,
        cash_register_id=caja.id,
        sale_number=seq,
        subtotal=subtotal,
        tax_amount=igv,
        total=total,
        payment_method=payment_method,
        paid_amount=paid_amount,
        change_amount=change,
        cashier_id=current_user.id,
        shift_date=datetime.now(timezone.utc),
        customer_doc_type=body.get("customer_doc_type", "0"),
        customer_doc_number=body.get("customer_doc_number"),
        customer_name=body.get("customer_name"),
    )

    # Comprobante via Facturalo.pro
    if comprobante_type in ("boleta", "factura"):
        sale.comprobante_type = "03" if comprobante_type == "boleta" else "01"
        # TODO: llamar Facturalo.pro API aquí
        # Por ahora guardamos el tipo, la integración real se activa
        # cuando el restaurante tenga facturalo_api_key configurado

    db.add(sale)

    # Actualizar caja
    caja.current_sales_count = (caja.current_sales_count or 0) + 1
    caja.current_sales_total = (caja.current_sales_total or Decimal("0")) + total
    if payment_method == "efectivo":
        caja.current_cash = (caja.current_cash or Decimal("0")) + total - change

    db.commit()

    return {
        "sale_id": sale.id,
        "order_id": order.id,
        "order_number": seq,
        "total": float(total),
        "igv": float(igv),
        "change": float(change),
        "payment_method": payment_method,
        "comprobante": sale.comprobante_type,
        "total_cost": float(total_cost),
        "margin": float(total - total_cost) if total_cost > 0 else None,
    }


# ============================================================
# API: Pedidos pendientes de cobro
# ============================================================

@router.get("/api/v1/caja/pendientes")
async def pedidos_pendientes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pedidos que pasaron por cocina y están listos para cobrar."""
    import traceback
    try:
        rid = current_user.restaurant_id

        orders = db.query(Order).filter(
            Order.restaurant_id == rid,
            Order.status.in_(["sent", "preparing", "ready", "served"]),
        ).order_by(Order.created_at.desc()).all()

        result = []
        for o in orders:
            # Load items safely
            items_list = []
            total_cost = 0
            try:
                for item in o.items:
                    items_list.append({
                        "name": item.product_name or "Item",
                        "qty": item.quantity or 1,
                        "price": float(item.unit_price or 0),
                        "total": float(item.line_total or 0),
                    })
                    if item.product_id:
                        prod = db.query(Product).filter(Product.id == item.product_id).first()
                        if prod and prod.cost_price:
                            total_cost += float(prod.cost_price) * (item.quantity or 1)
            except Exception as e:
                print(f"[CAJA] Error loading items for order {o.id}: {e}")

            # Safe field access
            table_num = None
            zone_name = None
            try:
                if o.table_id and o.table:
                    table_num = o.table.number
                if o.zone_id and o.zone:
                    zone_name = o.zone.name
            except Exception:
                pass

            result.append({
                "order_id": o.id,
                "order_number": o.order_number or 0,
                "status": o.status,
                "order_type": o.order_type or "dine_in",
                "table_number": table_num,
                "zone_name": zone_name,
                "customer_name": o.customer_name or "",
                "total": float(o.total or 0),
                "total_cost": total_cost,
                "items": items_list,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "minutes_ago": o.kitchen_wait_minutes if o.sent_to_kitchen_at else 0,
            })

        return {"orders": result}
    except Exception as e:
        print(f"[CAJA ERROR] pendientes: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# API: Cobrar pedido existente
# ============================================================

@router.post("/api/v1/caja/cobrar/{order_id}")
async def cobrar_pedido(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cobrar un pedido que ya pasó por cocina."""
    rid = current_user.restaurant_id
    body = await request.json()
    payment_method = body.get("payment_method", "efectivo")
    paid_amount = Decimal(str(body.get("paid_amount", "0")))
    comprobante_type = body.get("comprobante")

    order = db.query(Order).filter(
        Order.id == order_id,
        Order.restaurant_id == rid,
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Caja abierta
    caja = db.query(CashRegister).filter(
        CashRegister.restaurant_id == rid,
        CashRegister.is_active == True,
        CashRegister.is_open == True,
    ).first()
    if not caja:
        raise HTTPException(status_code=400, detail="Caja no está abierta")

    total = order.total or Decimal("0")
    if paid_amount == 0:
        paid_amount = total
    change = paid_amount - total if paid_amount > total else Decimal("0")
    igv = (total / Decimal("1.18") * Decimal("0.18")).quantize(Decimal("0.01"))

    # Update order
    order.status = "paid"
    order.payment_method = payment_method
    order.paid_amount = paid_amount
    order.change_amount = change
    order.cashier_id = current_user.id
    order.cash_register_id = caja.id
    order.paid_at = datetime.now(timezone.utc)

    # Daily sequence for sale
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    seq = db.query(sqlfunc.count(Sale.id)).filter(
        Sale.restaurant_id == rid,
        Sale.created_at >= today_start,
    ).scalar() or 0
    seq += 1

    # Create Sale
    sale = Sale(
        restaurant_id=rid,
        branch_id=current_user.branch_id,
        order_id=order.id,
        cash_register_id=caja.id,
        sale_number=seq,
        subtotal=total - igv,
        tax_amount=igv,
        total=total,
        payment_method=payment_method,
        paid_amount=paid_amount,
        change_amount=change,
        cashier_id=current_user.id,
        shift_date=datetime.now(timezone.utc),
        customer_doc_type=body.get("customer_doc_type", "0"),
        customer_doc_number=body.get("customer_doc_number"),
        customer_name=body.get("customer_name") or order.customer_name,
    )
    if comprobante_type in ("boleta", "factura"):
        sale.comprobante_type = "03" if comprobante_type == "boleta" else "01"

    db.add(sale)

    # Update caja
    caja.current_sales_count = (caja.current_sales_count or 0) + 1
    caja.current_sales_total = (caja.current_sales_total or Decimal("0")) + total
    if payment_method == "efectivo":
        caja.current_cash = (caja.current_cash or Decimal("0")) + total - change

    db.commit()

    return {
        "sale_id": sale.id,
        "order_id": order.id,
        "order_number": order.order_number,
        "total": float(total),
        "change": float(change),
        "payment_method": payment_method,
    }


# ============================================================
# API: Resumen del día
# ============================================================

@router.get("/api/v1/caja/resumen")
async def resumen_diario(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen de ventas del día con márgenes."""
    rid = current_user.restaurant_id
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Ventas del día
    sales = db.query(Sale).filter(
        Sale.restaurant_id == rid,
        Sale.created_at >= today_start,
        Sale.status == "completed",
    ).all()

    total_ventas = sum(float(s.total) for s in sales)
    total_count = len(sales)

    # Calcular costos de items vendidos hoy
    order_ids = [s.order_id for s in sales if s.order_id]
    total_cost = 0
    items_sold = {}

    if order_ids:
        oi_list = db.query(OrderItem).filter(
            OrderItem.order_id.in_(order_ids)
        ).all()
        for oi in oi_list:
            # Buscar costo del producto
            if oi.product_id:
                product = db.query(Product).filter(Product.id == oi.product_id).first()
                if product and product.cost_price:
                    total_cost += float(product.cost_price) * oi.quantity

            # Conteo de items vendidos
            name = oi.product_name or f"Producto {oi.product_id}"
            if name in items_sold:
                items_sold[name]["qty"] += oi.quantity
                items_sold[name]["total"] += float(oi.line_total)
            else:
                items_sold[name] = {"qty": oi.quantity, "total": float(oi.line_total)}

    # Top productos
    top_products = sorted(items_sold.items(), key=lambda x: x[1]["qty"], reverse=True)[:10]

    # Por método de pago
    by_payment = {}
    for s in sales:
        pm = s.payment_method or "otro"
        if pm not in by_payment:
            by_payment[pm] = {"count": 0, "total": 0}
        by_payment[pm]["count"] += 1
        by_payment[pm]["total"] += float(s.total)

    margin = total_ventas - total_cost
    margin_pct = (margin / total_ventas * 100) if total_ventas > 0 else 0

    return {
        "fecha": date.today().isoformat(),
        "total_ventas": round(total_ventas, 2),
        "total_count": total_count,
        "total_cost": round(total_cost, 2),
        "margin": round(margin, 2),
        "margin_pct": round(margin_pct, 1),
        "by_payment": by_payment,
        "top_products": [
            {"name": name, "qty": data["qty"], "total": round(data["total"], 2)}
            for name, data in top_products
        ],
    }