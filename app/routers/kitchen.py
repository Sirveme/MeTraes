"""
Kitchen Router — Endpoints del KDS + WebSocket cocina.
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.auth import get_current_user, decode_token
from app.models.user import User
from app.schemas import KDSItemStatusUpdate
from app.services import kitchen_service
from app.websocket.manager import manager

router = APIRouter()


# ============================================================
# REST Endpoints
# ============================================================

@router.get("/pending")
async def get_pending_orders(
    station_id: int = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pedidos activos para el KDS. Opcional: filtrar por estación."""
    return kitchen_service.get_pending_orders(db, user.restaurant_id, station_id)


@router.get("/stations")
async def get_stations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Estaciones de cocina con conteo de items pendientes."""
    return kitchen_service.get_stations(db, user.restaurant_id)


@router.put("/items/{item_id}/status")
async def update_item_status(
    item_id: int,
    data: KDSItemStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Cambia estado de un item desde el KDS.
    sent → preparing → ready (o cancelled)
    Notifica por WebSocket al mesero y al admin.
    """
    result = kitchen_service.update_item_status(db, item_id, data.status, user.id)
    
    # --- WebSocket: notificar a todos ---
    
    # 1. Actualizar KDS (todas las pantallas de cocina)
    kds_data = kitchen_service.get_pending_orders(db, user.restaurant_id)
    await manager.send_to_kitchen(user.restaurant_id, {
        "event": "kds_update",
        "data": {"orders": kds_data, "changed_item": result}
    })
    
    # 2. Si estación específica, actualizar también esa pantalla
    if result.get("station_id"):
        station_data = kitchen_service.get_pending_orders(db, user.restaurant_id, result["station_id"])
        await manager.send_to_kitchen(user.restaurant_id, {
            "event": "kds_update",
            "data": {"orders": station_data, "changed_item": result}
        }, station_id=result["station_id"])
    
    # 3. Notificar al mesero cuando su item está listo
    if data.status == "ready" and result.get("waiter_id"):
        await manager.send_to_user(result["waiter_id"], {
            "event": "item_ready",
            "data": result,
        })
    
    # 4. Notificar al cliente en carta virtual
    if data.status == "ready" and result.get("table_id"):
        await manager.send_to_table(result["table_id"], {
            "event": "item_ready",
            "data": {
                "item_name": result["item_name"],
                "order_status": result["order_status"],
            },
        })
    
    # 5. Notificar admin si el pedido completo está listo
    if result.get("order_status") == "ready":
        await manager.send_to_admin(user.restaurant_id, {
            "event": "order_ready",
            "data": result,
        })
    
    return result


# ============================================================
# WebSocket — Conexión en tiempo real para KDS
# ============================================================

@router.websocket("/ws/{restaurant_id}")
async def kitchen_websocket(
    websocket: WebSocket,
    restaurant_id: int,
    token: str = Query(None),
    station_id: int = Query(None),
):
    """
    WebSocket para pantalla KDS.
    Conectar: ws://host/api/v1/kitchen/ws/{restaurant_id}?token=JWT&station_id=1
    
    Recibe:
    - order_sent: pedido nuevo enviado a cocina
    - kds_update: actualización de estado de items
    
    Envía:
    - ping: heartbeat
    """
    # Validar token
    if token:
        try:
            payload = decode_token(token)
            if int(payload.get("restaurant_id", 0)) != restaurant_id:
                await websocket.close(code=4003, reason="Restaurant no coincide")
                return
        except Exception:
            await websocket.close(code=4001, reason="Token inválido")
            return
    
    # Conectar a canales
    channel = f"kitchen:{restaurant_id}"
    await manager.connect(websocket, channel)
    
    station_channel = None
    if station_id:
        station_channel = f"kitchen:{restaurant_id}:{station_id}"
        await manager.connect(websocket, station_channel)
    
    # Enviar estado inicial
    db = SessionLocal()
    try:
        orders = kitchen_service.get_pending_orders(db, restaurant_id, station_id)
        stations = kitchen_service.get_stations(db, restaurant_id)
        await websocket.send_json({
            "event": "initial_state",
            "data": {"orders": orders, "stations": stations},
        })
    finally:
        db.close()
    
    # Mantener conexión
    try:
        while True:
            data = await websocket.receive_text()
            # El KDS principalmente recibe, pero puede enviar pings
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
        if station_channel:
            manager.disconnect(websocket, station_channel)


@router.websocket("/ws/waiter/{user_id}")
async def waiter_websocket(
    websocket: WebSocket,
    user_id: int,
    token: str = Query(None),
):
    """
    WebSocket para mesero. Recibe notificaciones de items listos.
    Conectar: ws://host/api/v1/kitchen/ws/waiter/{user_id}?token=JWT
    """
    if token:
        try:
            payload = decode_token(token)
            if int(payload.get("sub", 0)) != user_id:
                await websocket.close(code=4003, reason="User no coincide")
                return
        except Exception:
            await websocket.close(code=4001, reason="Token inválido")
            return
    
    channel = f"waiter:{user_id}"
    await manager.connect(websocket, channel)
    
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)