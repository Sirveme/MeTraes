"""
User — Personal del restaurante.
20-40 personas por turno. Login rápido con PIN de 4 dígitos.
Roles: owner, manager, waiter, cashier, kitchen, delivery.
Se asignan a zonas (pisos/salones) por turno.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    DateTime, Date, Numeric
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), index=True)
    
    # --- Identificación ---
    name = Column(String(200), nullable=False)          # Nombre completo
    short_name = Column(String(50))                     # "Carlos M." (para KDS/display)
    dni = Column(String(15))                            # DNI peruano
    phone = Column(String(20))
    email = Column(String(200))
    photo_url = Column(String(500))
    
    # --- Auth ---
    pin = Column(String(10))                            # PIN 4 dígitos para login rápido POS
    password_hash = Column(String(300))                 # Para acceso web/admin
    
    # --- Rol ---
    role = Column(
        String(20), nullable=False, default="waiter"
        # owner    → Dueño, acceso total
        # manager  → Administrador de turno
        # waiter   → Mesero/mozo
        # cashier  → Cajero
        # kitchen  → Cocinero (acceso KDS)
        # delivery → Repartidor
        # host     → Recepción / asigna mesas
    )
    
    # --- Asignación ---
    assigned_zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"))
    assigned_station_id = Column(Integer, ForeignKey("kitchen_stations.id", ondelete="SET NULL"))
    
    # --- Turno y horario ---
    shift = Column(String(20))                          # "mañana", "tarde", "noche"
    is_on_duty = Column(Boolean, default=False)         # ¿Está en turno ahora?
    clock_in_at = Column(DateTime(timezone=True))       # Hora de entrada
    clock_out_at = Column(DateTime(timezone=True))      # Hora de salida
    
    # --- Pago y compensación ---
    daily_rate = Column(Numeric(10, 2))                 # Jornal diario
    commission_rate = Column(Numeric(5, 4))             # % comisión sobre ventas
    tip_share_rate = Column(Numeric(5, 4))              # % del pool de propinas
    
    # --- Permisos granulares ---
    permissions = Column(
        JSONB,
        default={
            "can_discount": False,          # Puede aplicar descuentos
            "can_void": False,              # Puede anular items
            "can_transfer_table": True,     # Puede transferir mesa
            "can_split_bill": True,         # Puede dividir cuenta
            "can_view_reports": False,      # Puede ver reportes
            "can_manage_stock": False,      # Puede gestionar inventario
            "max_discount_percent": 0,      # Descuento máximo permitido
        }
    )
    
    # --- Estado ---
    is_active = Column(Boolean, default=True)
    hired_at = Column(Date)
    terminated_at = Column(Date)
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True))
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="users")
    branch = relationship("Branch", back_populates="users")
    assigned_zone = relationship("Zone", foreign_keys=[assigned_zone_id])
    assigned_station = relationship("KitchenStation", foreign_keys=[assigned_station_id])
    
    @property
    def display_role(self):
        roles = {
            "owner": "Dueño",
            "manager": "Administrador",
            "waiter": "Mesero",
            "cashier": "Cajero",
            "kitchen": "Cocina",
            "delivery": "Delivery",
            "host": "Recepción",
        }
        return roles.get(self.role, self.role)
    
    def __repr__(self):
        return f"<User {self.id}: {self.name} ({self.role})>"