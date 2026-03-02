"""
Product — Plato, bebida o item del menú.
Con modificadores (sin cebolla, extra queso), alérgenos,
asignación a estación de cocina, y soporte para carta virtual.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    SmallInteger, ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    station_id = Column(Integer, ForeignKey("kitchen_stations.id", ondelete="SET NULL"), index=True)
    
    # --- Identificación ---
    name = Column(String(200), nullable=False)              # "Arroz Chaufa Especial"
    short_name = Column(String(50))                         # "Chaufa Esp." (para ticket/KDS)
    sku = Column(String(50))                                # Código interno
    description = Column(Text)                              # Descripción para carta virtual
    
    # --- Precios ---
    sale_price = Column(Numeric(10, 2), nullable=False)     # Precio de venta
    cost_price = Column(Numeric(10, 2))                     # Costo (para margen)
    has_igv = Column(Boolean, default=True)                 # Incluye IGV
    
    # --- Tamaños/Presentaciones ---
    sizes = Column(
        JSONB,
        default=[]
        # [
        #   {"name": "Personal", "price": 18.00},
        #   {"name": "Familiar", "price": 35.00},
        #   {"name": "Medio", "price": 25.00}
        # ]
    )
    
    # --- Modificadores disponibles ---
    modifiers = Column(
        JSONB,
        default=[]
        # [
        #   {"group": "Proteína", "required": true, "max": 1, "options": [
        #     {"name": "Pollo", "price": 0},
        #     {"name": "Chancho", "price": 0},
        #     {"name": "Mixto", "price": 5.00}
        #   ]},
        #   {"group": "Extras", "required": false, "max": 3, "options": [
        #     {"name": "Extra huevo", "price": 2.00},
        #     {"name": "Sin cebolla", "price": 0},
        #     {"name": "Extra picante", "price": 0}
        #   ]}
        # ]
    )
    
    # --- Alérgenos ---
    allergens = Column(
        ARRAY(String),
        default=[]
        # ["gluten", "lactosa", "maní", "mariscos", "soya", "huevo"]
    )
    dietary_tags = Column(
        ARRAY(String),
        default=[]
        # ["vegetariano", "vegano", "sin_gluten", "keto", "light"]
    )
    
    # --- Imágenes (carta virtual) ---
    image_url = Column(String(500))                         # Foto principal
    thumbnail_url = Column(String(500))                     # Thumbnail para lista
    gallery = Column(ARRAY(String), default=[])             # Galería de fotos
    
    # --- Cocina ---
    prep_time_minutes = Column(Integer, default=15)         # Tiempo de preparación estimado
    is_instant = Column(Boolean, default=False)             # No pasa por cocina (ej: bebida embotellada)
    
    # --- Disponibilidad ---
    is_active = Column(Boolean, default=True)               # Activo en el sistema
    is_available = Column(Boolean, default=True)            # Disponible ahora (se puede desactivar al vuelo)
    available_from = Column(String(5))                      # "11:00" (solo en cierto horario)
    available_until = Column(String(5))                     # "15:00"
    available_days = Column(ARRAY(String), default=[])      # ["lunes", "martes"] vacío = todos
    
    # --- Carta Virtual ---
    is_featured = Column(Boolean, default=False)            # Destacado en carta virtual
    is_new = Column(Boolean, default=False)                 # Badge "Nuevo"
    is_bestseller = Column(Boolean, default=False)          # Badge "Más pedido"
    is_spicy = Column(Boolean, default=False)               # Indicador picante 🌶️
    spicy_level = Column(SmallInteger, default=0)           # 0-3 nivel de picante
    
    # --- Orden ---
    sort_order = Column(Integer, default=0)
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="products")
    category = relationship("Category", back_populates="products")
    station = relationship("KitchenStation", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
    
    @property
    def effective_price(self):
        """Precio efectivo (considerando si tiene tamaños)."""
        return self.sale_price
    
    def __repr__(self):
        return f"<Product {self.id}: {self.name} (S/{self.sale_price})>"