"""
CashRegister — Caja registradora.
Una branch puede tener N cajas. Cada caja tiene su turno,
su cajero asignado, y su propio cierre de caja.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric,
    ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class CashRegister(Base):
    __tablename__ = "cash_registers"

    id = Column(Integer, primary_key=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Identificación ---
    name = Column(String(100), nullable=False)              # "Caja 1", "Caja Delivery"
    code = Column(String(20))                               # "C1", "CD"

    # --- Estado actual ---
    is_open = Column(Boolean, default=False)                # ¿Turno abierto?
    opened_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    opened_at = Column(DateTime(timezone=True))
    opening_amount = Column(Numeric(10, 2), default=0)      # Monto de apertura

    # --- Totales del turno actual ---
    current_cash = Column(Numeric(10, 2), default=0)        # Efectivo en caja
    current_sales_count = Column(Integer, default=0)
    current_sales_total = Column(Numeric(10, 2), default=0)

    # --- Configuración ---
    accepts_cash = Column(Boolean, default=True)
    accepts_card = Column(Boolean, default=True)
    accepts_yape = Column(Boolean, default=True)
    accepts_plin = Column(Boolean, default=True)
    printer_name = Column(String(100))                      # Impresora de tickets
    
    # --- Estado ---
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    branch = relationship("Branch", back_populates="cash_registers")
    restaurant = relationship("Restaurant")
    opened_by = relationship("User", foreign_keys=[opened_by_id])

    def __repr__(self):
        return f"<CashRegister {self.id}: {self.name} ({'abierta' if self.is_open else 'cerrada'})>"