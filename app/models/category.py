"""
Category — Categorías del menú.
Organiza productos tanto en POS como en Carta Virtual.
Ej: "Entradas", "Sopas", "Chifa Especial", "Pollos", "Bebidas", "Postres"
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, SmallInteger,
    ForeignKey, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))  # Subcategorías
    
    # --- Identificación ---
    name = Column(String(100), nullable=False)          # "Chifa Especial"
    description = Column(String(300))
    icon = Column(String(50))                           # "🥡", "🍗", "🍺"
    image_url = Column(String(500))                     # Foto de la categoría
    
    # --- Display ---
    color = Column(String(7), default="#3b82f6")
    sort_order = Column(SmallInteger, default=0)
    
    # --- Visibilidad ---
    is_active = Column(Boolean, default=True)
    is_visible_pos = Column(Boolean, default=True)      # Visible en POS mesero
    is_visible_menu = Column(Boolean, default=True)     # Visible en carta virtual
    
    # --- Horario (algunas categorías solo en ciertas horas) ---
    available_from = Column(String(5))                  # "11:00"
    available_until = Column(String(5))                 # "15:00" (solo almuerzo)
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="categories")
    parent = relationship("Category", remote_side=[id])
    products = relationship("Product", back_populates="category")
    
    def __repr__(self):
        return f"<Category {self.id}: {self.name}>"