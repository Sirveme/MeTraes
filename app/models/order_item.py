"""
OrderItem — Item individual del pedido.
Cada item tiene su propio estado y se rutea a una estación de cocina.
El KDS muestra items agrupados por pedido, coloreados por estado.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    SmallInteger, ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), index=True)
    station_id = Column(Integer, ForeignKey("kitchen_stations.id", ondelete="SET NULL"), index=True)
    
    # --- Detalle ---
    product_name = Column(String(200), nullable=False)  # Desnormalizado para historial
    quantity = Column(Numeric(10, 3), nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    size_name = Column(String(50))                      # "Personal", "Familiar"
    
    # --- Modificadores seleccionados ---
    modifiers = Column(
        JSONB,
        default=[]
        # [
        #   {"group": "Proteína", "name": "Mixto", "price": 5.00},
        #   {"group": "Extras", "name": "Sin cebolla", "price": 0},
        #   {"group": "Extras", "name": "Extra picante", "price": 0}
        # ]
    )
    
    # --- Notas del comensal / mesero ---
    notes = Column(Text)                                # "Bien cocido", "sin MSG"
    
    # --- Totales ---
    modifier_total = Column(Numeric(10, 2), default=0)  # Suma de precios de modificadores
    discount_amount = Column(Numeric(10, 2), default=0)
    line_total = Column(Numeric(10, 2), nullable=False)  # (unit_price + modifier_total) * qty - discount
    
    # --- Estado individual (para KDS) ---
    status = Column(
        String(20), default="pending", index=True
        # pending    → Agregado al pedido, no enviado
        # sent       → Enviado a cocina (aparece en KDS)
        # preparing  → Cocinero tocó "Preparando"
        # ready      → Listo para servir
        # delivered  → Entregado al cliente
        # cancelled  → Cancelado
    )
    
    # --- Prioridad ---
    is_urgent = Column(Boolean, default=False)          # Prioridad en KDS
    is_fire = Column(Boolean, default=False)            # "FIRE" = preparar YA (sincrono con otros items)
    
    # --- Secuencia (para servir en orden) ---
    course = Column(
        SmallInteger, default=1
        # 1 = Entrada, 2 = Plato principal, 3 = Postre
        # Permite que cocina prepare en el orden correcto
    )
    
    # --- Quién preparó ---
    prepared_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # --- Timestamps de lifecycle ---
    sent_at = Column(DateTime(timezone=True))           # Enviado a cocina
    started_at = Column(DateTime(timezone=True))        # Empezó a preparar
    ready_at = Column(DateTime(timezone=True))          # Listo
    delivered_at = Column(DateTime(timezone=True))      # Entregado
    cancelled_at = Column(DateTime(timezone=True))      # Cancelado
    
    # --- Motivo de cancelación ---
    cancel_reason = Column(String(200))
    cancelled_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    station = relationship("KitchenStation", back_populates="order_items")
    prepared_by = relationship("User", foreign_keys=[prepared_by_id])
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_id])
    
    @property
    def prep_wait_minutes(self):
        """Minutos desde que se envió a cocina."""
        if not self.sent_at:
            return 0
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        delta = now - self.sent_at
        return int(delta.total_seconds() / 60)
    
    @property
    def modifier_summary(self):
        """Resumen de modificadores para KDS: 'Mixto, Sin cebolla, Extra picante'"""
        if not self.modifiers:
            return ""
        return ", ".join(m.get("name", "") for m in self.modifiers)
    
    def __repr__(self):
        return f"<OrderItem {self.id}: {self.product_name} x{self.quantity} ({self.status})>"