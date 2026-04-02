"""
dashboard.py — Dashboard Gerencial para dueños/contadores.
Muestra ventas en tiempo real, top platos, ranking mozos, comparativo por local.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, extract, and_

from app.core.database import get_db
from app.core.auth import decode_token
from app.models.sale import Sale
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.models.branch import Branch
from app.models.restaurant import Restaurant

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# TEMPLATE: Servir la página del Dashboard
# GET /dashboard/{restaurant_id}  (registrado sin prefix en main.py)
# ============================================================

@router.get("/dashboard/{restaurant_id}")
async def dashboard_page(
    request: Request,
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        return templates.TemplateResponse("carta_404.html", {
            "request": request,
            "message": "Restaurante no encontrado.",
        })

    config = {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.trade_name or restaurant.name,
        "api_base": "/api/v1",
    }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "config": config,
    })


# ============================================================
# API: Stats del Dashboard
# GET /api/v1/dashboard/stats  (prefix /api/v1 en main.py)
# ============================================================

def _get_date_range(period: str):
    """Retorna (start, end) según el periodo."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "week":
        start = today_start - timedelta(days=today_start.weekday())
    elif period == "month":
        start = today_start.replace(day=1)
    else:
        start = today_start

    return start, now


@router.get("/api/v1/dashboard/stats")
async def dashboard_stats(
    restaurant_id: int,
    period: str = Query("today", regex="^(today|week|month)$"),
    db: Session = Depends(get_db),
):
    start, end = _get_date_range(period)

    # --- A) RESUMEN ---
    summary = db.query(
        sqlfunc.count(Sale.id).label("count"),
        sqlfunc.coalesce(sqlfunc.sum(Sale.total), 0).label("total"),
    ).filter(
        Sale.restaurant_id == restaurant_id,
        Sale.status == "completed",
        Sale.created_at >= start,
        Sale.created_at <= end,
    ).first()

    sale_count = summary.count or 0
    sale_total = float(summary.total or 0)
    ticket_avg = round(sale_total / sale_count, 2) if sale_count > 0 else 0

    # Ganancia estimada: total vendido - costo de items
    # JOIN sales -> orders -> order_items -> products (cost_price)
    cost_query = db.query(
        sqlfunc.coalesce(
            sqlfunc.sum(OrderItem.quantity * Product.cost_price), 0
        )
    ).join(
        Order, OrderItem.order_id == Order.id
    ).join(
        Sale, Sale.order_id == Order.id
    ).outerjoin(
        Product, OrderItem.product_id == Product.id
    ).filter(
        Sale.restaurant_id == restaurant_id,
        Sale.status == "completed",
        Sale.created_at >= start,
        Sale.created_at <= end,
    ).scalar()

    total_cost = float(cost_query or 0)
    profit = round(sale_total - total_cost, 2)

    # --- B) VENTAS POR HORA ---
    hourly = db.query(
        extract("hour", Sale.created_at).label("hour"),
        sqlfunc.count(Sale.id).label("count"),
        sqlfunc.sum(Sale.total).label("total"),
    ).filter(
        Sale.restaurant_id == restaurant_id,
        Sale.status == "completed",
        Sale.created_at >= start,
        Sale.created_at <= end,
    ).group_by(
        extract("hour", Sale.created_at)
    ).order_by("hour").all()

    hourly_data = [{"hour": int(h.hour), "count": h.count, "total": float(h.total)} for h in hourly]

    # --- C) COMPARATIVO POR LOCAL ---
    branch_stats = db.query(
        Branch.id,
        Branch.name,
        sqlfunc.count(Sale.id).label("count"),
        sqlfunc.coalesce(sqlfunc.sum(Sale.total), 0).label("total"),
    ).outerjoin(
        Sale, and_(
            Sale.branch_id == Branch.id,
            Sale.status == "completed",
            Sale.created_at >= start,
            Sale.created_at <= end,
        )
    ).filter(
        Branch.restaurant_id == restaurant_id,
        Branch.is_active == True,
    ).group_by(Branch.id, Branch.name).all()

    branches_data = []
    for b in branch_stats:
        b_count = b.count or 0
        b_total = float(b.total or 0)
        branches_data.append({
            "id": b.id,
            "name": b.name,
            "count": b_count,
            "total": b_total,
            "ticket_avg": round(b_total / b_count, 2) if b_count > 0 else 0,
        })

    # --- D) TOP 10 PLATOS ---
    top_products = db.query(
        OrderItem.product_name,
        sqlfunc.sum(OrderItem.quantity).label("qty"),
        sqlfunc.sum(OrderItem.line_total).label("total"),
    ).join(
        Order, OrderItem.order_id == Order.id
    ).join(
        Sale, Sale.order_id == Order.id
    ).filter(
        Sale.restaurant_id == restaurant_id,
        Sale.status == "completed",
        Sale.created_at >= start,
        Sale.created_at <= end,
        OrderItem.status != "cancelled",
    ).group_by(
        OrderItem.product_name
    ).order_by(
        sqlfunc.sum(OrderItem.quantity).desc()
    ).limit(10).all()

    top_data = [
        {"rank": i + 1, "name": t.product_name, "qty": float(t.qty), "total": float(t.total)}
        for i, t in enumerate(top_products)
    ]

    # --- E) RANKING MOZOS ---
    waiter_stats = db.query(
        User.id,
        User.short_name,
        User.name,
        sqlfunc.count(Order.id).label("orders"),
        sqlfunc.coalesce(sqlfunc.sum(Order.total), 0).label("total"),
    ).join(
        Order, Order.waiter_id == User.id
    ).join(
        Sale, Sale.order_id == Order.id
    ).filter(
        User.restaurant_id == restaurant_id,
        User.role == "waiter",
        Sale.status == "completed",
        Sale.created_at >= start,
        Sale.created_at <= end,
    ).group_by(
        User.id, User.short_name, User.name
    ).order_by(
        sqlfunc.sum(Order.total).desc()
    ).all()

    waiters_data = [
        {
            "name": w.short_name or w.name,
            "orders": w.orders,
            "total": float(w.total),
        }
        for w in waiter_stats
    ]

    return {
        "period": period,
        "summary": {
            "sale_count": sale_count,
            "sale_total": sale_total,
            "ticket_avg": ticket_avg,
            "profit": profit,
            "total_cost": total_cost,
        },
        "hourly": hourly_data,
        "branches": branches_data,
        "top_products": top_data,
        "waiters": waiters_data,
    }
