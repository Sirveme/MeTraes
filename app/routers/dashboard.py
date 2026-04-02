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
from app.models.attendance import Attendance
from app.models.cash_register import CashRegister

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
    import traceback

    try:
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

        sale_count = (summary.count if summary else 0) or 0
        sale_total = float((summary.total if summary else 0) or 0)
        ticket_avg = round(sale_total / sale_count, 2) if sale_count > 0 else 0

        # Ganancia estimada
        total_cost = 0.0
        try:
            cost_query = db.query(
                sqlfunc.coalesce(
                    sqlfunc.sum(OrderItem.quantity * sqlfunc.coalesce(Product.cost_price, 0)), 0
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
        except Exception:
            traceback.print_exc()

        profit = round(sale_total - total_cost, 2)

        # --- B) VENTAS POR HORA ---
        hourly_data = []
        try:
            hourly = db.query(
                extract("hour", Sale.created_at).label("hour"),
                sqlfunc.count(Sale.id).label("count"),
                sqlfunc.coalesce(sqlfunc.sum(Sale.total), 0).label("total"),
            ).filter(
                Sale.restaurant_id == restaurant_id,
                Sale.status == "completed",
                Sale.created_at >= start,
                Sale.created_at <= end,
            ).group_by(
                extract("hour", Sale.created_at)
            ).order_by("hour").all()

            for h in hourly:
                hourly_data.append({
                    "hour": int(h.hour or 0),
                    "count": h.count or 0,
                    "total": float(h.total or 0),
                })
        except Exception:
            traceback.print_exc()

        # --- C) COMPARATIVO POR LOCAL ---
        branches_data = []
        try:
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
        except Exception:
            traceback.print_exc()

        # --- D) TOP 10 PLATOS ---
        top_data = []
        try:
            top_products = db.query(
                OrderItem.product_name,
                sqlfunc.coalesce(sqlfunc.sum(OrderItem.quantity), 0).label("qty"),
                sqlfunc.coalesce(sqlfunc.sum(OrderItem.line_total), 0).label("total"),
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

            for i, t in enumerate(top_products):
                top_data.append({
                    "rank": i + 1,
                    "name": t.product_name or "?",
                    "qty": float(t.qty or 0),
                    "total": float(t.total or 0),
                })
        except Exception:
            traceback.print_exc()

        # --- E) RANKING MOZOS ---
        waiters_data = []
        try:
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

            for w in waiter_stats:
                waiters_data.append({
                    "name": w.short_name or w.name,
                    "orders": w.orders or 0,
                    "total": float(w.total or 0),
                })
        except Exception:
            traceback.print_exc()

        # --- F) PERSONAL ACTIVO (marcados "in" sin "out" hoy) ---
        active_staff = []
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            today_now = datetime.now(timezone.utc)

            today_checks = db.query(Attendance).filter(
                Attendance.restaurant_id == restaurant_id,
                Attendance.checked_at >= today_start,
            ).order_by(Attendance.user_id, Attendance.checked_at.desc()).all()

            last_check_by_user = {}
            for chk in today_checks:
                if chk.user_id not in last_check_by_user:
                    last_check_by_user[chk.user_id] = chk

            for uid, chk in last_check_by_user.items():
                if chk.check_type == "in":
                    u = db.query(User).filter(User.id == uid).first()
                    if not u:
                        continue
                    delta_h = round((today_now - chk.checked_at).total_seconds() / 3600, 2)
                    active_staff.append({
                        "user_id": uid,
                        "name": u.short_name or u.name,
                        "role": u.role,
                        "check_in": chk.checked_at.isoformat(),
                        "hours_today": delta_h,
                    })
        except Exception:
            traceback.print_exc()

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
            "active_staff": active_staff,
        }

    except Exception:
        traceback.print_exc()
        # Return safe empty response instead of 500
        return {
            "period": period,
            "summary": {
                "sale_count": 0,
                "sale_total": 0,
                "ticket_avg": 0,
                "profit": 0,
                "total_cost": 0,
            },
            "hourly": [],
            "branches": [],
            "top_products": [],
            "waiters": [],
            "active_staff": [],
        }


# ============================================================
# TEMPLATE: Multi-Dashboard para contadores
# GET /multi-dashboard
# ============================================================

@router.get("/multi-dashboard")
async def multi_dashboard_page(request: Request):
    config = {
        "api_base": "/api/v1",
    }
    return templates.TemplateResponse("multi_dashboard.html", {
        "request": request,
        "config": config,
    })


# ============================================================
# API: Multi-stats por branch
# GET /api/v1/dashboard/multi-stats?restaurant_id=N
# ============================================================

@router.get("/api/v1/dashboard/multi-stats")
async def multi_dashboard_stats(
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    """Stats compactos por branch para el multi-dashboard."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        return {"restaurant_name": "?", "panels": []}

    branches = db.query(Branch).filter(
        Branch.restaurant_id == restaurant_id,
        Branch.is_active == True,
    ).order_by(Branch.sort_order).all()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    now = datetime.now(timezone.utc)

    panels = []
    for branch in branches:
        bid = branch.id

        # Ventas del dia
        sale_stats = db.query(
            sqlfunc.count(Sale.id).label("count"),
            sqlfunc.coalesce(sqlfunc.sum(Sale.total), 0).label("total"),
            sqlfunc.max(Sale.created_at).label("last_sale_at"),
        ).filter(
            Sale.restaurant_id == restaurant_id,
            Sale.branch_id == bid,
            Sale.status == "completed",
            Sale.created_at >= today_start,
        ).first()

        sale_count = sale_stats.count or 0
        sale_total = float(sale_stats.total or 0)
        ticket_avg = round(sale_total / sale_count, 2) if sale_count > 0 else 0

        # Ultima venta — minutos desde
        last_sale_minutes = None
        if sale_stats.last_sale_at:
            delta = (now - sale_stats.last_sale_at).total_seconds() / 60
            last_sale_minutes = round(delta)

        # Personal: esperado vs presente
        expected_staff = db.query(sqlfunc.count(User.id)).filter(
            User.restaurant_id == restaurant_id,
            User.branch_id == bid,
            User.is_active == True,
            User.role.in_(["waiter", "kitchen", "cashier", "delivery"]),
        ).scalar() or 0

        today_checkins = db.query(Attendance.user_id).filter(
            Attendance.restaurant_id == restaurant_id,
            Attendance.branch_id == bid,
            Attendance.checked_at >= today_start,
            Attendance.check_type == "in",
        ).distinct().all()
        present_staff = len(today_checkins)

        # Caja estado
        caja = db.query(CashRegister).filter(
            CashRegister.restaurant_id == restaurant_id,
            CashRegister.branch_id == bid,
            CashRegister.is_active == True,
        ).first()
        caja_open = caja.is_open if caja else False

        # Semaforo
        # Verde: caja abierta + ventas recientes (< 60 min) + personal >= 50%
        # Amarillo: alguna condicion falla
        # Rojo: caja cerrada + sin ventas + personal < 30%
        issues = 0
        if not caja_open:
            issues += 1
        if last_sale_minutes is not None and last_sale_minutes > 60:
            issues += 1
        if last_sale_minutes is None and sale_count == 0:
            issues += 1
        if expected_staff > 0 and present_staff < expected_staff * 0.5:
            issues += 1

        if issues == 0:
            status = "green"
        elif issues <= 1:
            status = "yellow"
        else:
            status = "red"

        panels.append({
            "branch_id": bid,
            "branch_name": branch.name,
            "status": status,
            "sale_count": sale_count,
            "sale_total": sale_total,
            "ticket_avg": ticket_avg,
            "last_sale_minutes": last_sale_minutes,
            "staff_present": present_staff,
            "staff_expected": expected_staff,
            "caja_open": caja_open,
        })

    return {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.trade_name or restaurant.name,
        "panels": panels,
    }
