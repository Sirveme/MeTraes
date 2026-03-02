"""
Branch — Sucursal / Local / Establecimiento.
Un Restaurant (tenant) puede tener N branches.
Ej: "Chifa Fénix Dorado - Local Principal", "Chifa Fénix Dorado - San Juan"
Mesas, personal, cajas, zonas → pertenecen a una branch.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    SmallInteger, ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Branch(Base):
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Identificación ---
    name = Column(String(200), nullable=False)              # "Local Principal"
    code = Column(String(20))                               # "LP", "SJ" (código corto)
    address = Column(String(500))
    district = Column(String(100))
    phone = Column(String(20))
    
    # --- Geolocalización ---
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))
    geo_radius_meters = Column(Integer, default=50)         # Radio "en local" (vertical incluido)

    # --- Estructura física ---
    floor_count = Column(SmallInteger, default=1)
    table_count = Column(Integer, default=0)                # Auto-calculado

    # --- Facturación (series por sucursal) ---
    facturalo_serie_boleta = Column(String(10))             # "B001"
    facturalo_serie_factura = Column(String(10))            # "F001"
    
    # --- Configuración propia de esta sucursal ---
    # Hereda del restaurant si es NULL, override si tiene valor
    config_overrides = Column(JSONB, default={})
    
    # --- Horario (puede diferir del restaurant) ---
    schedule = Column(JSONB)                                # NULL = hereda del restaurant

    # --- Estado ---
    is_active = Column(Boolean, default=True)
    is_main = Column(Boolean, default=False)                # Sucursal principal
    sort_order = Column(Integer, default=0)

    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="branches")
    zones = relationship("Zone", back_populates="branch", cascade="all, delete-orphan")
    tables = relationship("Table", back_populates="branch", cascade="all, delete-orphan")
    cash_registers = relationship("CashRegister", back_populates="branch", cascade="all, delete-orphan")
    users = relationship("User", back_populates="branch")

    def __repr__(self):
        return f"<Branch {self.id}: {self.name}>"