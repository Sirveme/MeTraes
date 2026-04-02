"""
PushSubscription — Suscripciones Web Push por dispositivo.
Cada usuario puede tener N dispositivos suscritos (celular + desktop).
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Text,
    ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Push API fields ---
    endpoint = Column(Text, nullable=False)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(200), nullable=False)

    # --- Device info ---
    device_name = Column(String(100))       # "Chrome Android", "Firefox Desktop"

    # --- Estado ---
    is_active = Column(Boolean, default=True)

    # --- Auditoria ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Relationships ---
    restaurant = relationship("Restaurant")
    user = relationship("User")

    def __repr__(self):
        return f"<PushSubscription {self.id}: user={self.user_id} active={self.is_active}>"
