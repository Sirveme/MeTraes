"""
Notification — Sistema de comunicación transversal.
Cualquier actor puede enviar a cualquier otro:
  Cliente → Caja/Cocina → Admin → Mozo
  Cocina → Mozo → Admin → Cliente
  Admin → Cocina/Mozo → Cliente

Se transmite via WebSocket en tiempo real + Push Notification
para cuando la app no está en primer plano.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Text,
    ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # --- Tipo de notificación ---
    notification_type = Column(
        String(30), nullable=False
        # order_new         → Pedido nuevo (→ cocina)
        # order_sent        → Pedido enviado a cocina (→ cocina)
        # item_preparing    → Item en preparación (→ mesero)
        # item_ready        → Item listo (→ mesero)
        # order_ready       → Todo el pedido listo (→ mesero, → cliente)
        # table_call        → Cliente llama mesero (→ mesero, → admin)
        # table_bill        → Cliente pide cuenta (→ cajero)
        # stock_low         → Stock bajo (→ admin)
        # stock_out         → Sin stock (→ admin, → cocina)
        # message           → Mensaje libre entre actores
        # alert             → Alerta del sistema
        # delay_warning     → Pedido retrasado (→ admin)
        # shift_change      → Cambio de turno (→ todos)
    )
    
    # --- Origen ---
    sender_type = Column(
        String(20)
        # user     → Personal del restaurante (mesero, cocina, admin, cajero)
        # customer → Cliente desde carta virtual
        # system   → Sistema automático
    )
    sender_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    sender_name = Column(String(100))                   # Para clientes sin user_id
    
    # --- Destino ---
    target_type = Column(
        String(20)
        # user      → Usuario específico
        # role      → Todos los de un rol (ej: todos los meseros)
        # zone      → Todos en una zona
        # station   → Estación de cocina
        # table     → Mesa (cliente en carta virtual)
        # broadcast → Todos
    )
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    target_role = Column(String(20))                    # "waiter", "kitchen", "cashier"
    target_zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"))
    target_station_id = Column(Integer, ForeignKey("kitchen_stations.id", ondelete="SET NULL"))
    target_table_id = Column(Integer, ForeignKey("tables.id", ondelete="SET NULL"))
    
    # --- Contenido ---
    title = Column(String(200))                         # "Mesa 15 - Plato listo"
    message = Column(Text)                              # Detalle
    data = Column(JSONB, default={})                    # Datos estructurados (order_id, item_id, etc.)
    
    # --- Referencia ---
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"))
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="SET NULL"))
    
    # --- Estado ---
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))
    is_pushed = Column(Boolean, default=False)          # Push notification enviada
    pushed_at = Column(DateTime(timezone=True))
    
    # --- Prioridad ---
    priority = Column(
        String(10), default="normal"
        # low, normal, high, urgent
    )
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))        # Auto-limpiar después de X tiempo
    
    def __repr__(self):
        return f"<Notification {self.id}: {self.notification_type} ({self.priority})>"