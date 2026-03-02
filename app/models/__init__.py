"""
Metraes.com — Schemas Pydantic
Validación de datos para API REST.
Organizados por módulo para la Fase 1 (KDS Demo).
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


# ============================================================
# RESTAURANT
# ============================================================

class RestaurantBase(BaseModel):
    name: str = Field(..., max_length=200)
    trade_name: Optional[str] = None
    ruc: str = Field(..., pattern=r"^\d{11}$")
    address: Optional[str] = None
    phone: Optional[str] = None

class RestaurantCreate(RestaurantBase):
    pass

class RestaurantOut(RestaurantBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    table_count: int = 0
    floor_count: int = 1
    is_active: bool = True


# ============================================================
# ZONE (Pisos / Salones)
# ============================================================

class ZoneBase(BaseModel):
    name: str = Field(..., max_length=100)
    short_name: Optional[str] = Field(None, max_length=20)
    floor_number: int = 1
    zone_type: str = "salon"
    capacity: Optional[int] = None
    color: str = "#3b82f6"
    sort_order: int = 0

class ZoneCreate(ZoneBase):
    pass

class ZoneOut(ZoneBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    table_count: int = 0
    is_active: bool = True


# ============================================================
# TABLE (Mesas)
# ============================================================

class TableBase(BaseModel):
    number: int
    zone_id: Optional[int] = None
    label: Optional[str] = None
    capacity: int = 4
    pos_x: int = 0
    pos_y: int = 0
    shape: str = "square"

class TableCreate(TableBase):
    pass

class TableOut(TableBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    status: str = "free"
    assigned_waiter_id: Optional[int] = None
    current_order_id: Optional[int] = None
    qr_code: Optional[str] = None
    zone_name: Optional[str] = None  # Desnormalizado para display

class TableStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(free|occupied|waiting|bill|reserved|cleaning|blocked)$")

class TableTransfer(BaseModel):
    new_waiter_id: int


# ============================================================
# KITCHEN STATION (Estaciones de cocina)
# ============================================================

class KitchenStationBase(BaseModel):
    name: str = Field(..., max_length=100)
    short_name: Optional[str] = None
    display_name: Optional[str] = None
    color: str = "#f97316"
    icon: Optional[str] = None
    target_time_minutes: int = 15
    alert_time_minutes: int = 25
    sort_order: int = 0

class KitchenStationCreate(KitchenStationBase):
    pass

class KitchenStationOut(KitchenStationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    is_active: bool = True
    is_accepting_orders: bool = True


# ============================================================
# CATEGORY
# ============================================================

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=100)
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    color: str = "#3b82f6"
    sort_order: int = 0

class CategoryCreate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    is_active: bool = True


# ============================================================
# PRODUCT (Platos / Bebidas)
# ============================================================

class ProductBase(BaseModel):
    name: str = Field(..., max_length=200)
    short_name: Optional[str] = None
    category_id: Optional[int] = None
    station_id: Optional[int] = None
    sale_price: Decimal = Field(..., ge=0)
    description: Optional[str] = None
    prep_time_minutes: int = 15
    image_url: Optional[str] = None
    sizes: list = []
    modifiers: list = []
    allergens: list[str] = []

class ProductCreate(ProductBase):
    pass

class ProductOut(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    is_active: bool = True
    is_available: bool = True
    category_name: Optional[str] = None
    station_name: Optional[str] = None


# ============================================================
# ORDER (Pedidos / Comandas)
# ============================================================

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(default=1, ge=0.001)
    size_name: Optional[str] = None
    modifiers: list = []
    notes: Optional[str] = None
    course: int = 1
    is_urgent: bool = False

class OrderCreate(BaseModel):
    table_id: Optional[int] = None
    order_type: str = "dine_in"         # dine_in, takeaway, delivery
    order_source: str = "pos"           # pos, virtual_menu, phone
    guest_count: int = 1
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    customer_notes: Optional[str] = None
    priority: str = "normal"
    notes: Optional[str] = None
    items: list[OrderItemCreate] = []

class OrderAddItems(BaseModel):
    """Agregar items a pedido abierto (sin cerrar y reabrir)."""
    items: list[OrderItemCreate]

class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: Optional[int]
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    size_name: Optional[str]
    modifiers: list
    notes: Optional[str]
    line_total: Decimal
    status: str
    station_id: Optional[int]
    station_name: Optional[str] = None
    course: int = 1
    is_urgent: bool = False
    sent_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    prep_wait_minutes: int = 0

class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    order_number: Optional[int]
    order_type: str
    order_source: str
    table_id: Optional[int]
    zone_id: Optional[int]
    waiter_id: Optional[int]
    status: str
    priority: str
    guest_count: int
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    tip_amount: Decimal
    total: Decimal
    payment_method: Optional[str]
    notes: Optional[str]
    items: list[OrderItemOut] = []
    # Display helpers
    table_display: Optional[str] = None     # "Mesa 15 - Piso 2"
    waiter_name: Optional[str] = None
    customer_name: Optional[str] = None
    # Timestamps
    opened_at: Optional[datetime]
    sent_to_kitchen_at: Optional[datetime]
    all_items_ready_at: Optional[datetime]
    paid_at: Optional[datetime]
    kitchen_wait_minutes: int = 0


# ============================================================
# KDS (Kitchen Display - schemas específicos)
# ============================================================

class KDSOrderItem(BaseModel):
    """Item como se muestra en el KDS — optimizado para pantalla grande."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_name: str
    short_name: Optional[str] = None
    quantity: Decimal
    size_name: Optional[str]
    modifiers_summary: str = ""         # "Mixto, Sin cebolla, Extra picante"
    notes: Optional[str]
    status: str
    is_urgent: bool = False
    is_fire: bool = False
    course: int = 1
    prep_wait_minutes: int = 0

class KDSOrder(BaseModel):
    """Pedido como se muestra en el KDS — card grande con timer."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: Optional[int]
    order_type: str
    table_display: str                  # "Mesa 15 - Piso 2"
    waiter_name: Optional[str]
    priority: str
    status: str
    items: list[KDSOrderItem] = []
    sent_to_kitchen_at: Optional[datetime]
    kitchen_wait_minutes: int = 0
    guest_count: int = 1

class KDSItemStatusUpdate(BaseModel):
    """Cambio de estado de un item desde el KDS."""
    status: str = Field(..., pattern=r"^(preparing|ready|cancelled)$")


# ============================================================
# PAYMENT (Cobro)
# ============================================================

class PaymentRequest(BaseModel):
    payment_method: str = Field(
        ...,
        pattern=r"^(efectivo|yape|plin|tarjeta_debito|tarjeta_credito|transferencia|mixto)$"
    )
    paid_amount: Decimal = Field(..., ge=0)
    payment_details: dict = {}          # Para mixto: {"efectivo": 20, "yape": 30}
    tip_amount: Decimal = Field(default=0, ge=0)
    # Cliente para factura (opcional)
    customer_doc_type: Optional[str] = None
    customer_doc_number: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    # Comprobante
    comprobante_type: str = "03"        # 03=Boleta, 01=Factura


# ============================================================
# VIRTUAL MENU (Carta Virtual - schemas públicos)
# ============================================================

class MenuCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    icon: Optional[str]
    image_url: Optional[str]

class MenuProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str]
    sale_price: Decimal
    image_url: Optional[str]
    sizes: list
    modifiers: list
    allergens: list[str]
    dietary_tags: list[str] = []
    prep_time_minutes: int
    is_available: bool
    is_featured: bool
    is_new: bool
    is_bestseller: bool
    is_spicy: bool
    spicy_level: int

class VirtualOrderCreate(BaseModel):
    """Pedido desde carta virtual (sin auth)."""
    table_id: Optional[int] = None      # Si es desde QR de mesa
    order_type: str = "dine_in"         # dine_in, takeaway, delivery
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None  # Para delivery
    customer_notes: Optional[str] = None
    customer_latitude: Optional[float] = None
    customer_longitude: Optional[float] = None
    items: list[OrderItemCreate]


# ============================================================
# AUTH
# ============================================================

class LoginPIN(BaseModel):
    """Login rápido con PIN (meseros/cocina en POS)."""
    pin: str = Field(..., pattern=r"^\d{4,6}$")
    restaurant_id: int

class LoginEmail(BaseModel):
    """Login con email/password (admin/owner)."""
    email: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict               # {id, name, role, restaurant_id, zone_id}


# ============================================================
# WEBSOCKET MESSAGES
# ============================================================

class WSMessage(BaseModel):
    """Mensaje genérico de WebSocket."""
    event: str              # "order_new", "item_status", "table_call", "message"
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sender_id: Optional[int] = None
    sender_type: Optional[str] = None  # "user", "customer", "system"