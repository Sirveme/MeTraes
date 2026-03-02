"""
Zone — Pisos, salones, terrazas.
Restaurantes/chifas grandes tienen 2-3 pisos o múltiples salones.
El cocinero necesita saber "Mesa 15 - Piso 2" para que el mozo
lleve el plato al lugar correcto. El mozo se asigna a una zona.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, SmallInteger,
    ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Zone(Base):
    __tablename__ = "zones"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    
    # --- Identificación ---
    name = Column(String(100), nullable=False)          # "Piso 1", "Salón VIP", "Terraza"
    short_name = Column(String(20))                     # "P1", "VIP", "TRZ" (para KDS compacto)
    description = Column(String(300))                   # "Primer piso, salón principal con 20 mesas"
    
    # --- Ubicación ---
    floor_number = Column(SmallInteger, default=1)      # 1, 2, 3 (para ordenar por piso)
    zone_type = Column(
        String(20), default="salon"                     # salon, terraza, barra, privado, exterior
    )
    
    # --- Capacidad ---
    table_count = Column(Integer, default=0)            # Se actualiza automáticamente
    capacity = Column(Integer)                          # Aforo máximo de personas
    
    # --- Display ---
    color = Column(String(7), default="#3b82f6")        # Color en mapa de mesas
    sort_order = Column(Integer, default=0)             # Orden de visualización
    
    # --- Estado ---
    is_active = Column(Boolean, default=True)
    is_visible_in_menu = Column(Boolean, default=True)  # Mostrar en carta virtual
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="zones")
    branch = relationship("Branch", back_populates="zones")
    tables = relationship("Table", back_populates="zone", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Zone {self.id}: {self.name} (Piso {self.floor_number})>"