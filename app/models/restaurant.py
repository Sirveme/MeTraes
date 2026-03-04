"""
Restaurant — Modelo principal del negocio.
Equivale a Store en QueVendi, pero con campos específicos de restaurante.
Cada restaurant es un tenant independiente en Metraes.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Numeric,
    Text, SmallInteger
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Restaurant(Base):
    __tablename__ = "restaurants"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # --- Datos del negocio ---
    name = Column(String(200), nullable=False)              # "Chifa Fénix Dorado"
    trade_name = Column(String(200))                        # Nombre comercial / marca
    ruc = Column(String(11), unique=True, nullable=False)   # RUC para SUNAT
    address = Column(String(500))
    district = Column(String(100))                          # Distrito en Iquitos
    city = Column(String(100), default="Iquitos")
    phone = Column(String(20))
    whatsapp = Column(String(20))                           # Para notif a clientes delivery
    email = Column(String(200))
    logo_url = Column(String(500))
    
    # --- Geolocalización del local ---
    latitude = Column(Numeric(10, 7))       # Para detectar pedido "en local" vs delivery
    longitude = Column(Numeric(10, 7))
    geo_radius_meters = Column(Integer, default=50)  # Radio para considerar "en local"
    
    # --- Configuración operativa ---
    table_count = Column(Integer, default=0)             # Total mesas (se actualiza auto)
    floor_count = Column(SmallInteger, default=1)        # Cantidad de pisos
    service_time_target_minutes = Column(Integer, default=15)  # Tiempo objetivo cocina
    service_time_alert_minutes = Column(Integer, default=25)   # Timer rojo
    currency = Column(String(3), default="PEN")
    tax_rate = Column(Numeric(5, 4), default=0.18)       # IGV 18%
    
    # --- Configuración Carta Virtual ---
    virtual_menu_enabled = Column(Boolean, default=True)
    virtual_menu_languages = Column(ARRAY(String), default=["es"])  # ["es", "en"]
    virtual_menu_banner_url = Column(String(500))
    delivery_enabled = Column(Boolean, default=False)
    takeaway_enabled = Column(Boolean, default=True)
    delivery_radius_km = Column(Numeric(5, 2))
    delivery_min_order = Column(Numeric(10, 2))
    
    # --- Métodos de pago habilitados ---
    payment_methods = Column(
        JSONB,
        default={
            "efectivo": True,
            "yape": True,
            "plin": True,
            "tarjeta_debito": True,
            "tarjeta_credito": False,
            "transferencia": False
        }
    )
    yape_phone = Column(String(20))     # Número Yape del negocio
    plin_phone = Column(String(20))     # Número Plin del negocio
    
    # --- Integración Facturalo.pro (nuestro SaaS) ---
    facturalo_api_key = Column(String(200))      # API key para emitir comprobantes
    facturalo_serie_boleta = Column(String(10))   # Ej: "B001"
    facturalo_serie_factura = Column(String(10))  # Ej: "F001"
    
    # --- Configuración parametrizable (ver restaurant_config.py) ---
    config = Column(JSONB, default={})  # Override parcial de RESTAURANT_CONFIG_DEFAULTS
    
    # --- Horario ---
    schedule = Column(
        JSONB,
        default={
            "lunes": {"open": "11:00", "close": "23:00"},
            "martes": {"open": "11:00", "close": "23:00"},
            "miercoles": {"open": "11:00", "close": "23:00"},
            "jueves": {"open": "11:00", "close": "23:00"},
            "viernes": {"open": "11:00", "close": "00:00"},
            "sabado": {"open": "11:00", "close": "00:00"},
            "domingo": {"open": "11:00", "close": "23:00"},
        }
    )
    
    # --- Estado ---
    is_active = Column(Boolean, default=True)
    subscription_plan = Column(String(50), default="basic")  # basic, pro, enterprise
    subscription_expires_at = Column(DateTime(timezone=True))
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    branches = relationship("Branch", back_populates="restaurant", cascade="all, delete-orphan")
    zones = relationship("Zone", back_populates="restaurant", cascade="all, delete-orphan")
    tables = relationship("Table", back_populates="restaurant", cascade="all, delete-orphan")
    users = relationship("User", back_populates="restaurant", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="restaurant", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="restaurant", cascade="all, delete-orphan")
    kitchen_stations = relationship("KitchenStation", back_populates="restaurant", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="restaurant", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="restaurant", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Restaurant {self.id}: {self.name} ({self.ruc})>"