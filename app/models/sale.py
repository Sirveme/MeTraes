"""
Sale — Venta cerrada y facturada.
Se crea cuando el Order se paga. Se envía a Facturalo.pro API
para emitir boleta/factura electrónica ante SUNAT.
"""

from sqlalchemy import (
    Column, Integer, String, Numeric, Text,
    ForeignKey, DateTime, Boolean
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), unique=True, index=True)
    cash_register_id = Column(Integer, ForeignKey("cash_registers.id", ondelete="SET NULL"))
    
    # --- Correlativo ---
    sale_number = Column(Integer)                       # Correlativo de venta del día
    
    # --- Cliente (para factura) ---
    customer_doc_type = Column(String(2), default="0")  # 0=Sin doc, 1=DNI, 6=RUC
    customer_doc_number = Column(String(15))             # DNI o RUC
    customer_name = Column(String(200))
    customer_address = Column(String(500))               # Requerido para factura
    customer_email = Column(String(200))                 # Para envío digital
    
    # --- Totales ---
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax_amount = Column(Numeric(10, 2), default=0)       # IGV
    discount_amount = Column(Numeric(10, 2), default=0)
    tip_amount = Column(Numeric(10, 2), default=0)
    delivery_fee = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), nullable=False)
    
    # --- Pago ---
    payment_method = Column(String(30), nullable=False)  # efectivo, yape, plin, tarjeta, mixto
    payment_details = Column(JSONB, default={})
    paid_amount = Column(Numeric(10, 2), nullable=False)
    change_amount = Column(Numeric(10, 2), default=0)
    
    # --- Facturalo.pro (nuestro SaaS) ---
    comprobante_type = Column(String(2))                 # "03"=Boleta, "01"=Factura
    facturalo_comprobante_id = Column(Integer)            # ID retornado por Facturalo.pro
    facturalo_serie = Column(String(10))                  # "B001", "F001"
    facturalo_numero = Column(Integer)                    # Número correlativo
    facturalo_pdf_url = Column(String(500))               # URL del PDF
    facturalo_xml_url = Column(String(500))               # URL del XML
    facturalo_cdr_status = Column(String(50))             # Estado SUNAT
    facturalo_hash = Column(String(100))                  # Hash del comprobante
    facturalo_response = Column(JSONB, default={})        # Respuesta completa de la API
    
    # --- Estado ---
    status = Column(
        String(20), default="completed"
        # completed  → Venta normal
        # voided     → Anulada (nota de crédito)
        # refunded   → Devuelta
    )
    voided_at = Column(DateTime(timezone=True))
    void_reason = Column(String(300))
    credit_note_id = Column(Integer)                     # ID de nota de crédito en Facturalo.pro
    
    # --- Quién cerró la venta ---
    cashier_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # --- Turno ---
    shift_date = Column(DateTime(timezone=True))         # Fecha del turno (para cierre de caja)
    
    # --- Auditoría ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # --- Relationships ---
    restaurant = relationship("Restaurant", back_populates="sales")
    #order = relationship("Order", back_populates="sale")
    cashier = relationship("User", foreign_keys=[cashier_id])
    
    @property
    def comprobante_display(self):
        """'B001-00000123' o 'F001-00000045'"""
        if self.facturalo_serie and self.facturalo_numero:
            return f"{self.facturalo_serie}-{str(self.facturalo_numero).zfill(8)}"
        return "Sin comprobante"
    
    def __repr__(self):
        return f"<Sale {self.id}: S/{self.total} ({self.payment_method})>"