"""
KitchenStation — Estación de cocina.
Cada estación tiene su propia pantalla KDS (o sección de pantalla).
Los items del pedido se rutean automáticamente a la estación correcta.
Ej: "Parrilla", "Wok", "Freidora", "Bebidas", "Postres"
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, SmallInteger,
    ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class KitchenStation(Base):
    __tablename__ = "kitchen_stations"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # --- Identificación ---
    name = Column(String(100), nullable=False)          # "Parrilla", "Wok", "Freidora"
    short_name = Column(String(20))                     # "PAR", "WOK", "FRI" (para badges)
    display_name = Column(String(100))                  # "🔥 Parrilla" (con emoji para KDS)
    
    # --- Visual en KDS ---
    color = Column(String(7), default="#f97316")        # Color de la estación en KDS
    icon = Column(String(50))                           # Emoji o icono: "🔥", "🍳", "🥤"
    
    # --- Configuración ---
    target_time_minutes = Column(Integer, default=15)   # Tiempo objetivo de preparación
    alert_time_minutes = Column(Integer, default=25)    # Tiempo antes de alarma roja
    max_concurrent_orders = Column(Integer, default=10) # Capacidad simultánea
    printer_name = Column(String(100))                  # Impresora de comanda (si aplica)
    
    # --- Display ---
    sort_order = Column(SmallInteger, default=0)        # Orden en pantalla KDS
    
    # --- Estado ---
    is_active = Column(Boolean, default=True)
    is_accepting_orders = Column(Boolean, default=True) # Puede pausarse temporalmente
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="kitchen_stations")
    products = relationship("Product", back_populates="station")
    order_items = relationship("OrderItem", back_populates="station")
    
    def __repr__(self):
        return f"<KitchenStation {self.id}: {self.name}>"