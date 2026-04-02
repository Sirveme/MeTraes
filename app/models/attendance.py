"""
Attendance — Marcaciones de personal (entrada/salida).
Cada check registra tipo (in/out), geolocation del browser,
y el metodo de marcacion (pin manual o geo automatico).
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Marcacion ---
    check_type = Column(String(10), nullable=False)        # "in" o "out"
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # --- Geolocation ---
    latitude = Column(Numeric(10, 7))
    longitude = Column(Numeric(10, 7))

    # --- Metodo ---
    method = Column(String(20), default="pin")             # "pin" (manual) o "geo" (automatico geofencing)

    # --- Extras ---
    photo_url = Column(String(500))                        # Selfie opcional (futuro)
    notes = Column(Text)

    # --- Auditoria ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Relationships ---
    restaurant = relationship("Restaurant")
    branch = relationship("Branch")
    user = relationship("User")

    def __repr__(self):
        return f"<Attendance {self.id}: user={self.user_id} {self.check_type} @ {self.checked_at}>"
