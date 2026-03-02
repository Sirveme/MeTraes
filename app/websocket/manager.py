"""
WebSocket Manager — Gestiona conexiones en tiempo real.
Canales:
  kitchen:{restaurant_id}        → KDS recibe pedidos
  kitchen:{restaurant_id}:{station_id} → KDS por estación
  waiter:{user_id}               → Mesero recibe "plato listo"
  table:{table_id}               → Cliente ve estado de su pedido
  admin:{restaurant_id}          → Admin recibe alertas
  branch:{branch_id}             → Todos en una sucursal

Heartbeat cada 30s para mantener conexión en internet inestable (Iquitos).
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """Singleton que gestiona todas las conexiones WebSocket."""
    
    def __init__(self):
        # channel -> set of websockets
        self._channels: Dict[str, Set[WebSocket]] = {}
        self._heartbeat_interval = 30  # segundos
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Acepta conexión y la registra en un canal."""
        await websocket.accept()
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """Remueve conexión de un canal."""
        if channel in self._channels:
            self._channels[channel].discard(websocket)
            if not self._channels[channel]:
                del self._channels[channel]
    
    async def send_to_channel(self, channel: str, message: dict):
        """Envía mensaje a todos los conectados en un canal."""
        if channel not in self._channels:
            return
        
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(message, default=str)
        
        dead = set()
        for ws in self._channels[channel]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        
        # Limpiar conexiones muertas
        for ws in dead:
            self._channels[channel].discard(ws)
    
    async def send_to_user(self, user_id: int, message: dict):
        """Envía a un mesero/usuario específico."""
        await self.send_to_channel(f"waiter:{user_id}", message)
    
    async def send_to_kitchen(self, restaurant_id: int, message: dict, station_id: int = None):
        """Envía a cocina. Si station_id, SOLO al canal de la estación (no al general)."""
        if station_id:
            await self.send_to_channel(f"kitchen:{restaurant_id}:{station_id}", message)
        else:
            await self.send_to_channel(f"kitchen:{restaurant_id}", message)
    
    async def send_to_table(self, table_id: int, message: dict):
        """Envía al cliente en carta virtual."""
        await self.send_to_channel(f"table:{table_id}", message)
    
    async def send_to_admin(self, restaurant_id: int, message: dict):
        """Envía alerta al admin/manager."""
        await self.send_to_channel(f"admin:{restaurant_id}", message)
    
    async def broadcast_branch(self, branch_id: int, message: dict):
        """Envía a todos en una sucursal."""
        await self.send_to_channel(f"branch:{branch_id}", message)
    
    def get_connection_count(self, channel: str) -> int:
        return len(self._channels.get(channel, set()))
    
    def get_all_channels(self) -> list:
        return list(self._channels.keys())


# Singleton global
manager = ConnectionManager()