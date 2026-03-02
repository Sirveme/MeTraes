"""
cocina_1.py — Router para servir la pantalla KDS.
Inyecta la configuración del restaurante en el template.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/cocina")
async def kds_screen(
    request: Request,
    restaurant_id: int = 1,
    station_id: int = None,
    db: Session = Depends(get_db),
):
    """
    Pantalla KDS para TV de cocina.
    URL: /cocina?restaurant_id=1&station_id=2
    En celular auto-redirige a /cocina/movil
    """
    # Auto-detectar celular → redirigir a vista móvil
    ua = (request.headers.get('user-agent', '') or '').lower()
    is_mobile = any(k in ua for k in ['mobile', 'android', 'iphone', 'ipod'])
    if is_mobile:
        params = f"?restaurant_id={restaurant_id}"
        if station_id:
            params += f"&station_id={station_id}"
        return RedirectResponse(url=f"/cocina/movil{params}", status_code=302)
    # Config que se inyecta al template (el JS la lee)
    # Detectar protocolo (Railway usa HTTPS)
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
            "kds_columns": 4,
            "kds_font_size_base": 24,
            "sound_new_order": True,
        },
    }

    return templates.TemplateResponse("cocina_1.html", {
        "request": request,
        "config": config,
        "restaurant_id": restaurant_id,
        "station_id": station_id,
    })