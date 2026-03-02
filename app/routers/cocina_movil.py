"""
cocina_movil.py — KDS Móvil para cocina sin TV.
Optimizado para celular: lista vertical, swipe, vibración.
Auto-detecta dispositivo en cocina_1.py y redirige aquí.
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/cocina/movil")
async def kds_mobile(
    request: Request,
    restaurant_id: int = 1,
    station_id: int = None,
):
    """
    KDS Móvil — Celular del cocinero.
    URL: /cocina/movil?restaurant_id=2
    """
    is_https = request.headers.get('x-forwarded-proto', 'http') == 'https' or \
               request.url.scheme == 'https'
    ws_proto = 'wss' if is_https else 'ws'
    host = request.headers.get('host', 'localhost:8000')

    config = {
        "restaurant_id": restaurant_id,
        "station_id": station_id,
        "api_base": "/api/v1",
        "ws_base": f"{ws_proto}://{host}/api/v1/kitchen/ws",
        "kitchen": {
            "target_time_minutes": 15,
            "warning_time_minutes": 20,
            "alert_time_minutes": 25,
        },
    }

    return templates.TemplateResponse("cocina_movil.html", {
        "request": request,
        "config": config,
    })