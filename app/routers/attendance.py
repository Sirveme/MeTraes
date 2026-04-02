"""
attendance.py — Marcaciones de personal (entrada/salida).
POST /check, GET /today, GET /report.
Tambien sirve la pagina /marcacion.
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, and_, case, extract

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.attendance import Attendance
from app.models.user import User
from app.models.branch import Branch
from app.models.restaurant import Restaurant

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# SCHEMAS
# ============================================================

class CheckRequest(BaseModel):
    check_type: str  # "in" o "out"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# ============================================================
# TEMPLATE: Pagina de marcacion
# GET /marcacion?restaurant_id=N
# ============================================================

@router.get("/marcacion")
async def marcacion_page(
    request: Request,
    restaurant_id: int = Query(1),
    db: Session = Depends(get_db),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurante no encontrado")

    branches = db.query(Branch).filter(
        Branch.restaurant_id == restaurant_id,
        Branch.is_active == True,
    ).all()

    config = {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.trade_name or restaurant.name,
        "api_base": "/api/v1",
        "branches": [{"id": b.id, "name": b.name} for b in branches],
    }

    return templates.TemplateResponse("marcacion.html", {
        "request": request,
        "config": config,
    })


# ============================================================
# API: Registrar marcacion
# POST /api/v1/attendance/check
# ============================================================

def _get_today_range():
    """Retorna (start, end) del dia actual UTC."""
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, now


@router.post("/api/v1/attendance/check")
async def check_attendance(
    body: CheckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.check_type not in ("in", "out"):
        raise HTTPException(status_code=400, detail="check_type debe ser 'in' o 'out'")

    start, now = _get_today_range()

    # Buscar ultima marcacion del dia para este usuario
    last = db.query(Attendance).filter(
        Attendance.user_id == user.id,
        Attendance.checked_at >= start,
    ).order_by(Attendance.checked_at.desc()).first()

    # Validar: no doble check-in sin check-out previo
    if body.check_type == "in" and last and last.check_type == "in":
        raise HTTPException(
            status_code=400,
            detail="Ya tienes una entrada registrada. Debes marcar salida primero."
        )

    if body.check_type == "out" and (not last or last.check_type == "out"):
        raise HTTPException(
            status_code=400,
            detail="No tienes entrada registrada hoy. Debes marcar entrada primero."
        )

    attendance = Attendance(
        restaurant_id=user.restaurant_id,
        branch_id=user.branch_id,
        user_id=user.id,
        check_type=body.check_type,
        checked_at=now,
        latitude=body.latitude,
        longitude=body.longitude,
        method="pin",
    )
    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    # Push: verificar asistencia completa despues de check-in
    if body.check_type == "in":
        try:
            from app.services.push_service import notify_attendance_complete, notify_attendance_missing
            from app.models.branch import Branch
            # Contar personal activo esperado vs presente
            expected = db.query(User).filter(
                User.restaurant_id == user.restaurant_id,
                User.branch_id == user.branch_id,
                User.is_active == True,
                User.role.in_(["waiter", "kitchen", "cashier", "delivery"]),
            ).count()
            # Contar quienes ya marcaron hoy
            present_ids = db.query(Attendance.user_id).filter(
                Attendance.restaurant_id == user.restaurant_id,
                Attendance.branch_id == user.branch_id,
                Attendance.checked_at >= start,
                Attendance.check_type == "in",
            ).distinct().all()
            present = len(present_ids)
            branch = db.query(Branch).filter(Branch.id == user.branch_id).first()
            branch_name = branch.name if branch else ""
            if present >= expected and expected > 0:
                notify_attendance_complete(db, user.restaurant_id, branch_name, present, expected)
        except Exception:
            pass

    return {
        "status": "ok",
        "id": attendance.id,
        "check_type": attendance.check_type,
        "checked_at": attendance.checked_at.isoformat(),
        "user_name": user.short_name or user.name,
    }


# ============================================================
# API: Marcaciones del dia por branch
# GET /api/v1/attendance/today?restaurant_id=N
# ============================================================

@router.get("/api/v1/attendance/today")
async def attendance_today(
    restaurant_id: int,
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    start, _ = _get_today_range()

    q = db.query(Attendance).join(User, Attendance.user_id == User.id).filter(
        Attendance.restaurant_id == restaurant_id,
        Attendance.checked_at >= start,
    )
    if branch_id:
        q = q.filter(Attendance.branch_id == branch_id)

    records = q.order_by(Attendance.checked_at.desc()).all()

    # Agrupar por usuario
    user_map = {}
    for r in records:
        if r.user_id not in user_map:
            u = db.query(User).filter(User.id == r.user_id).first()
            user_map[r.user_id] = {
                "user_id": r.user_id,
                "user_name": u.short_name or u.name if u else "?",
                "role": u.role if u else "?",
                "checks": [],
            }
        user_map[r.user_id]["checks"].append({
            "id": r.id,
            "check_type": r.check_type,
            "checked_at": r.checked_at.isoformat(),
            "method": r.method,
        })

    return {"date": start.strftime("%Y-%m-%d"), "records": list(user_map.values())}


# ============================================================
# API: Reporte resumido
# GET /api/v1/attendance/report?restaurant_id=N&period=today|week|month
# ============================================================

def _get_period_range(period: str):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "week":
        start = today_start - timedelta(days=today_start.weekday())
    elif period == "month":
        start = today_start.replace(day=1)
    else:
        start = today_start

    return start, now


@router.get("/api/v1/attendance/report")
async def attendance_report(
    restaurant_id: int,
    period: str = Query("today", regex="^(today|week|month)$"),
    branch_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    start, end = _get_period_range(period)

    q = db.query(Attendance).filter(
        Attendance.restaurant_id == restaurant_id,
        Attendance.checked_at >= start,
        Attendance.checked_at <= end,
    )
    if branch_id:
        q = q.filter(Attendance.branch_id == branch_id)

    records = q.order_by(Attendance.user_id, Attendance.checked_at).all()

    # Agrupar por usuario y por dia
    user_days = {}  # {user_id: {date_str: [records]}}
    user_info = {}
    for r in records:
        uid = r.user_id
        day = r.checked_at.strftime("%Y-%m-%d")
        if uid not in user_days:
            user_days[uid] = {}
            u = db.query(User).filter(User.id == uid).first()
            user_info[uid] = {
                "user_id": uid,
                "user_name": u.short_name or u.name if u else "?",
                "role": u.role if u else "?",
            }
        if day not in user_days[uid]:
            user_days[uid][day] = []
        user_days[uid][day].append(r)

    report = []
    for uid, days in user_days.items():
        total_hours = 0
        daily = []
        for day, checks in sorted(days.items()):
            check_in = None
            check_out = None
            hours = 0
            for c in checks:
                if c.check_type == "in" and check_in is None:
                    check_in = c.checked_at
                elif c.check_type == "out":
                    check_out = c.checked_at
            if check_in and check_out:
                delta = (check_out - check_in).total_seconds() / 3600
                hours = round(delta, 2)
                total_hours += hours

            daily.append({
                "date": day,
                "check_in": check_in.isoformat() if check_in else None,
                "check_out": check_out.isoformat() if check_out else None,
                "hours": hours,
            })

        report.append({
            **user_info[uid],
            "total_hours": round(total_hours, 2),
            "days": daily,
        })

    return {"period": period, "start": start.isoformat(), "end": end.isoformat(), "report": report}
