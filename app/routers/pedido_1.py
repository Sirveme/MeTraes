"""
pedido_1.py — Router para POS Mesero.
Pantalla principal del mesero: login, mapa de mesas, toma de pedido.
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/pos")
async def pos_mesero(request: Request, restaurant_id: int = 1):
    """
    POS Mesero — Pantalla principal.
    URL: /pos?restaurant_id=1
    """
    is_https = request.headers.get('x-forwarded-proto', 'http') == 'https' or \
               request.url.scheme == 'https'
    ws_proto = 'wss' if is_https else 'ws'
    host = request.headers.get('host', 'localhost:8000')

    config = {
        "restaurant_id": restaurant_id,
        "api_base": "/api/v1",
        "ws_base": f"{ws_proto}://{host}/api/v1/kitchen/ws",
    }
    return templates.TemplateResponse("pedido_1.html", {
        "request": request,
        "config": config,
    })