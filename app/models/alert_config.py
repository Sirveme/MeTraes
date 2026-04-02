"""
AlertConfig — Configuracion de alertas por usuario.
Cada usuario configura que alertas quiere recibir y sus umbrales.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric,
    ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


# Tipos de alerta predefinidos con defaults
ALERT_TYPES = {
    "sale_completed":       {"label": "Cada venta",                  "default": False, "has_threshold": False},
    "caja_opened":          {"label": "Apertura de caja",            "default": True,  "has_threshold": False},
    "caja_closed":          {"label": "Cierre de caja con resumen",  "default": True,  "has_threshold": False},
    "attendance_complete":  {"label": "Todo el personal marco",      "default": True,  "has_threshold": False},
    "attendance_missing":   {"label": "Personal faltante",           "default": True,  "has_threshold": False},
    "delivery_dispatched":  {"label": "Motorizado salio",            "default": True,  "has_threshold": False},
    "sales_milestone":      {"label": "Ventas alcanzaron meta",      "default": False, "has_threshold": True},
    "low_sales_alert":      {"label": "Ventas por debajo esperado",  "default": False, "has_threshold": True},
}


class AlertConfig(Base):
    __tablename__ = "alert_configs"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Tipo de alerta ---
    alert_type = Column(String(50), nullable=False)     # key de ALERT_TYPES

    # --- Config ---
    is_enabled = Column(Boolean, default=True)
    threshold_value = Column(Numeric(10, 2))            # Monto meta (ej: S/ 500)
    threshold_percent = Column(Integer)                  # % umbral
    schedule_time = Column(String(5))                    # "09:15" para alertas programadas

    # --- Auditoria ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # --- Relationships ---
    restaurant = relationship("Restaurant")
    user = relationship("User")

    def __repr__(self):
        return f"<AlertConfig {self.id}: {self.alert_type} user={self.user_id} enabled={self.is_enabled}>"
