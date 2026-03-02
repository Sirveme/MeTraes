"""
Order — Pedido / Comanda.
El corazón del sistema. Soporta:
- Pedido en mesa (dine_in) desde POS mesero
- Pedido desde carta virtual (QR en mesa o fuera del local)
- Para llevar (takeaway) desde caja
- Delivery desde carta virtual
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    SmallInteger, ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), index=True)
    
    # --- Origen del pedido ---
    order_type = Column(
        String(20), nullable=False, default="dine_in"
        # dine_in   → En mesa (mesero o carta virtual en local)
        # takeaway  → Para llevar (caja o carta virtual en local)
        # delivery  → Delivery (carta virtual fuera del local)
    )
    order_source = Column(
        String(20), default="pos"
        # pos           → Ingresado por mesero/cajero en POS
        # virtual_menu  → Carta virtual por cliente
        # phone         → Por teléfono (cajero ingresa)
    )
    
    # --- Número de orden (visible para cocina/cliente) ---
    order_number = Column(Integer)                      # Correlativo diario: 001, 002...
    daily_sequence = Column(Integer)                    # Reset diario
    
    # --- Mesa (si aplica) ---
    table_id = Column(Integer, ForeignKey("tables.id", ondelete="SET NULL"), index=True)
    zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"), index=True)
    
    # --- Personal asignado ---
    waiter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    cashier_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    cash_register_id = Column(Integer, ForeignKey("cash_registers.id", ondelete="SET NULL"))
    
    # --- Cliente (carta virtual / delivery) ---
    customer_name = Column(String(200))                 # Nombre del cliente
    customer_phone = Column(String(20))                 # Para delivery/takeaway
    customer_address = Column(String(500))              # Dirección delivery
    customer_notes = Column(Text)                       # "Tocar el timbre 2 veces"
    customer_latitude = Column(Numeric(10, 7))          # Geolocalización
    customer_longitude = Column(Numeric(10, 7))
    
    # --- Estado del pedido ---
    status = Column(
        String(20), default="open", index=True
        # open        → Abierto, agregando items
        # sent        → Enviado a cocina
        # preparing   → Al menos 1 item en preparación
        # ready       → Todos los items listos
        # served      → Entregado al cliente (en mesa)
        # dispatched  → Despachado (delivery/takeaway)
        # paid        → Pagado y cerrado
        # cancelled   → Cancelado
    )
    
    # --- Prioridad ---
    priority = Column(
        String(10), default="normal"
        # normal  → Orden normal
        # urgent  → Urgente (se destaca en KDS)
        # vip     → Cliente VIP
    )
    
    # --- Comensales ---
    guest_count = Column(SmallInteger, default=1)       # Número de personas
    
    # --- Totales ---
    subtotal = Column(Numeric(10, 2), default=0)
    tax_amount = Column(Numeric(10, 2), default=0)      # IGV
    discount_amount = Column(Numeric(10, 2), default=0)
    discount_reason = Column(String(200))
    tip_amount = Column(Numeric(10, 2), default=0)
    delivery_fee = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), default=0)
    
    # --- Pago ---
    payment_method = Column(String(30))                 # efectivo, yape, plin, tarjeta, mixto
    payment_details = Column(
        JSONB,
        default={}
        # Para pago mixto:
        # {"efectivo": 20.00, "yape": 30.00}
        # Para tarjeta:
        # {"tipo": "debito", "ultimos_4": "1234"}
    )
    paid_amount = Column(Numeric(10, 2), default=0)
    change_amount = Column(Numeric(10, 2), default=0)   # Vuelto
    split_count = Column(SmallInteger, default=1)       # División de cuenta
    
    # --- Notas ---
    notes = Column(Text)                                # Notas generales del pedido
    
    # --- Timestamps del ciclo de vida ---
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_to_kitchen_at = Column(DateTime(timezone=True))
    first_item_ready_at = Column(DateTime(timezone=True))
    all_items_ready_at = Column(DateTime(timezone=True))
    served_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    
    # --- Delivery ---
    estimated_delivery_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    delivery_driver_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # --- Satisfacción ---
    rating = Column(SmallInteger)                       # 1-5 estrellas
    feedback = Column(Text)                             # Comentario del cliente
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="orders")
    table = relationship("Table", back_populates="orders", foreign_keys=[table_id])
    zone = relationship("Zone", foreign_keys=[zone_id])
    waiter = relationship("User", foreign_keys=[waiter_id])
    cashier = relationship("User", foreign_keys=[cashier_id])
    delivery_driver = relationship("User", foreign_keys=[delivery_driver_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    #sale = relationship("Sale", back_populates="order", uselist=False)
    
    @property
    def display_location(self):
        """Ubicación legible para KDS: 'Mesa 5 - Piso 2' o 'Delivery - Jr. Próspero 234'"""
        if self.order_type == "delivery":
            return f"🛵 Delivery - {self.customer_name or 'Cliente'}"
        if self.order_type == "takeaway":
            return f"📦 Para llevar - {self.customer_name or 'Cliente'}"
        if self.table:
            return self.table.display_name
        return f"Pedido #{self.order_number}"
    
    @property
    def kitchen_wait_minutes(self):
        """Minutos desde que se envió a cocina."""
        if not self.sent_to_kitchen_at:
            return 0
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        delta = now - self.sent_to_kitchen_at
        return int(delta.total_seconds() / 60)
    
    def __repr__(self):
        return f"<Order {self.id}: #{self.order_number} ({self.status})>"