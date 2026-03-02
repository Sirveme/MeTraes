"""
Table — Mesa del restaurante.
Pertenece a una Zone (piso/salón). El KDS muestra zona + mesa
para que el mozo sepa exactamente dónde llevar el plato.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, SmallInteger,
    ForeignKey, DateTime, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Table(Base):
    __tablename__ = "tables"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), index=True)
    zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"), index=True)
    
    # --- Identificación ---
    number = Column(Integer, nullable=False)            # Número de mesa (1, 2, 3...)
    label = Column(String(20))                          # Nombre alternativo: "VIP-1", "Barra-3"
    
    # --- Capacidad ---
    capacity = Column(SmallInteger, default=4)          # Personas que caben
    min_capacity = Column(SmallInteger, default=1)      # Mínimo para asignar
    
    # --- Estado en tiempo real ---
    status = Column(
        String(20), default="free"
        # free      → Mesa libre (verde)
        # occupied  → Ocupada, comiendo (azul)
        # waiting   → Esperando comida de cocina (amarillo)
        # bill      → Pidieron la cuenta (naranja)
        # reserved  → Reservada (morado)
        # cleaning  → Limpiándose (gris)
        # blocked   → No disponible (rojo oscuro)
    )
    
    # --- Asignación actual ---
    current_order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"))
    assigned_waiter_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # --- QR para Carta Virtual ---
    qr_code = Column(String(200), unique=True)          # UUID o código único para QR
    qr_url = Column(String(500))                        # URL completa del QR
    
    # --- Ubicación visual en mapa ---
    pos_x = Column(Integer, default=0)                  # Posición X en grid del mapa
    pos_y = Column(Integer, default=0)                  # Posición Y en grid del mapa
    shape = Column(String(20), default="square")        # square, round, rectangle
    
    # --- Config ---
    is_active = Column(Boolean, default=True)
    is_joinable = Column(Boolean, default=True)         # Puede unirse con otra mesa
    sort_order = Column(Integer, default=0)
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Constraints ---
    __table_args__ = (
        UniqueConstraint("restaurant_id", "number", name="uq_table_number_per_restaurant"),
    )
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="tables")
    branch = relationship("Branch", back_populates="tables")
    zone = relationship("Zone", back_populates="tables")
    current_order = relationship("Order", foreign_keys=[current_order_id])
    assigned_waiter = relationship("User", foreign_keys=[assigned_waiter_id])
    orders = relationship(
        "Order",
        back_populates="table",
        foreign_keys="Order.table_id",
        cascade="all, delete-orphan"
    )
    
    @property
    def display_name(self):
        """'Mesa 15 - Piso 2' o 'Mesa 3 - Terraza' para el KDS."""
        prefix = self.label or f"Mesa {self.number}"
        if self.zone:
            return f"{prefix} - {self.zone.short_name or self.zone.name}"
        return prefix
    
    def __repr__(self):
        return f"<Table {self.id}: Mesa {self.number} ({self.status})>"