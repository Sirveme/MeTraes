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
    config = {
        "restaurant_id": restaurant_id,
        "api_base": "/api/v1",
        "ws_base": f"ws://{request.headers.get('host', 'localhost:8000')}/api/v1/kitchen/ws",
    }
    return templates.TemplateResponse("pedido_1.html", {
        "request": request,
        "config": config,
    })