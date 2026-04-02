"""
demo_hub.py — Página de demostración para vendedor.
Muestra links de cada rol para que el dueño del restaurante
pueda abrir y compartir en tiempo real.
URL: /demo/{restaurant_id}
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models.restaurant import Restaurant
from app.models.branch import Branch
from app.models.zone import Zone
from app.models.table import Table
from app.models.user import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/demo/{restaurant_id}")
async def demo_hub_page(
    request: Request,
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    """Panel de demo — links de todos los roles."""
    restaurant = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id,
    ).first()

    if not restaurant:
        return templates.TemplateResponse("carta_404.html", {
            "request": request,
            "message": "Restaurante no encontrado.",
        })

    # Obtener branches
    branches = db.query(Branch).filter(
        Branch.restaurant_id == restaurant_id,
        Branch.is_active == True,
    ).order_by(Branch.sort_order).all()

    # Obtener zonas y mesas con QR
    zones = db.query(Zone).filter(
        Zone.restaurant_id == restaurant_id,
        Zone.is_active == True,
    ).order_by(Zone.sort_order).all()

    tables = db.query(Table).filter(
        Table.restaurant_id == restaurant_id,
    ).order_by(Table.number).all()

    users = db.query(User).filter(
        User.restaurant_id == restaurant_id,
        User.is_active == True,
    ).order_by(User.role).all()

    # Build host URL
    is_https = request.headers.get('x-forwarded-proto', 'http') == 'https' or \
               request.url.scheme == 'https'
    proto = 'https' if is_https else 'http'
    host = request.headers.get('host', 'localhost:8000')
    base_url = f"{proto}://{host}"

    config = {
        "restaurant_id": restaurant_id,
        "restaurant_name": restaurant.trade_name or restaurant.name,
        "base_url": base_url,
        "branches": [
            {"id": b.id, "name": b.name, "code": b.code, "is_main": b.is_main}
            for b in branches
        ],
        "zones": [
            {"id": z.id, "name": z.name, "short_name": z.short_name, "color": z.color, "branch_id": z.branch_id}
            for z in zones
        ],
        "tables": [
            {
                "id": t.id, "number": t.number, "zone_id": t.zone_id,
                "branch_id": t.branch_id,
                "qr_code": t.qr_code,
                "carta_url": f"{base_url}/carta/{t.qr_code}" if t.qr_code else None,
            }
            for t in tables
        ],
        "users": [
            {
                "name": u.name, "short_name": u.short_name,
                "role": u.role, "pin": u.pin, "branch_id": u.branch_id,
            }
            for u in users
        ],
    }

    return templates.TemplateResponse("demo_hub.html", {
        "request": request,
        "config": config,
    })