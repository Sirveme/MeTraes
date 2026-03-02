"""
RestaurantConfig — Configuración parametrizable del negocio.
Se almacena como JSONB en Restaurant.config.
Cada Branch puede hacer override parcial en Branch.config_overrides.

Resolución: branch.config_overrides > restaurant.config > DEFAULTS

Mientras no haya panel de configuración, se edita vía API o directo en DB.
Todas las plantillas y scripts leen de aquí, NUNCA hardcodean valores.
"""

# Valores por defecto. Se copian al crear un restaurant nuevo.
# El panel de admin (futuro) editará estos valores por restaurant/branch.

RESTAURANT_CONFIG_DEFAULTS = {
    
    # =============================================
    # COCINA / KDS
    # =============================================
    "kitchen": {
        "target_time_minutes": 15,          # Tiempo objetivo de preparación
        "warning_time_minutes": 20,         # Timer se pone amarillo/naranja
        "alert_time_minutes": 25,           # Timer se pone rojo, alerta admin
        "critical_time_minutes": 35,        # Notificación push al owner/manager
        "auto_accept_orders": False,        # ¿Cocina acepta pedidos automáticamente?
        "sound_new_order": True,            # Sonido al recibir pedido nuevo
        "sound_file_new_order": "new_order.mp3",
        "kds_columns": 4,                  # Columnas en pantalla KDS
        "kds_font_size_base": 24,          # Fuente base en px (legible a 2m)
        "kds_show_waiter_name": True,       # Mostrar nombre del mesero en KDS
        "kds_show_table_zone": True,        # Mostrar zona/piso en KDS
        "kds_group_by": "order",            # "order" o "station"
    },

    # =============================================
    # MESAS / SERVICIO
    # =============================================
    "tables": {
        "auto_free_after_payment": True,    # Liberar mesa al pagar
        "cleaning_time_minutes": 5,         # Tiempo estimado de limpieza
        "reservation_hold_minutes": 15,     # Tiempo que se guarda reserva
        "allow_table_join": True,           # Permitir unir mesas
        "allow_table_transfer": True,       # Permitir transferir mesa entre meseros
        "require_guest_count": True,        # Obligar a ingresar cantidad de comensales
    },

    # =============================================
    # PERSONAL / TURNOS
    # =============================================
    "staff": {
        "clock_in_tolerance_minutes": 10,   # Tolerancia para marcar entrada
        "clock_in_late_discount": True,     # Aplicar descuento por tardanza
        "late_discount_per_minute": 0.50,   # S/ por minuto de tardanza
        "max_late_minutes": 30,             # Más de esto = falta
        "require_pin_for_actions": True,    # PIN para descuentos, anulaciones
        "shift_change_alert": True,         # Alertar 15 min antes del cambio
        "shift_change_alert_minutes": 15,
    },

    # =============================================
    # PAGOS
    # =============================================
    "payments": {
        "methods_enabled": {
            "efectivo": True,
            "yape": True,
            "plin": True,
            "tarjeta_debito": True,
            "tarjeta_credito": False,
            "transferencia": False,
        },
        "allow_split_bill": True,           # Permitir dividir cuenta
        "max_split_count": 10,              # Máximo de divisiones
        "allow_tips": True,                 # Habilitar propinas
        "tip_suggestions": [10, 15, 20],    # % sugeridos de propina
        "require_payment_confirmation": True,  # Confirmar antes de cerrar
        "auto_print_ticket": True,          # Imprimir ticket al pagar
        "round_to": 0.10,                   # Redondear a S/0.10
    },

    # =============================================
    # FACTURACIÓN (Facturalo.pro)
    # =============================================
    "billing": {
        "default_comprobante": "03",        # 03=Boleta, 01=Factura
        "auto_emit": True,                  # Emitir comprobante automáticamente al pagar
        "include_igv": True,                # Precios incluyen IGV
        "igv_rate": 0.18,                   # 18% IGV
        "boleta_min_amount": 0,             # Monto mínimo para boleta
        "factura_requires_ruc": True,       # Factura requiere RUC del cliente
    },

    # =============================================
    # CARTA VIRTUAL
    # =============================================
    "virtual_menu": {
        "enabled": True,
        "languages": ["es"],                # ["es", "en"]
        "show_prices": True,
        "show_allergens": True,
        "show_prep_time": True,
        "show_photos": True,
        "allow_order": True,                # Permitir pedir desde carta virtual
        "allow_payment": False,             # Permitir pagar desde carta virtual (fase futura)
        "require_name": True,               # Pedir nombre del cliente
        "require_phone_delivery": True,     # Pedir teléfono para delivery
        "install_prompt": True,             # Sugerir instalar PWA
        "satisfaction_survey": True,        # Encuesta post-comida
    },

    # =============================================
    # DELIVERY
    # =============================================
    "delivery": {
        "enabled": False,
        "radius_km": 5,
        "min_order_amount": 20.00,
        "fee_type": "fixed",                # "fixed", "per_km", "free"
        "fee_amount": 5.00,                 # Monto fijo o por km
        "free_delivery_above": 50.00,       # Gratis si pedido > S/50
        "estimated_time_minutes": 40,
        "max_concurrent_deliveries": 5,
    },

    # =============================================
    # GEOLOCALIZACIÓN
    # =============================================
    "geo": {
        "in_store_radius_meters": 50,       # Radio para considerar "en local"
        "in_store_vertical_margin_meters": 15,  # Margen vertical (pisos, ~5m por piso)
        "require_geo_for_delivery": True,
        "require_geo_for_dine_in": False,
    },

    # =============================================
    # DESCUENTOS / BONOS / MERMAS
    # =============================================
    "discounts": {
        "allow_discounts": True,
        "max_discount_percent": 20,         # Máximo descuento sin autorización
        "require_auth_above_percent": 15,   # Pedir autorización del manager
        "allow_void_items": True,           # Permitir anular items
        "void_requires_reason": True,
        "track_waste": True,                # Registrar mermas
        "waste_categories": [               # Categorías de merma
            "vencido", "dañado", "preparación", "devolución", "cortesía"
        ],
    },

    # =============================================
    # COMPRAS / STOCK
    # =============================================
    "stock": {
        "enabled": False,                   # Fase posterior
        "low_stock_alert": True,
        "low_stock_threshold_percent": 20,  # Alertar al 20% del stock
        "supplier_portal_enabled": False,   # Acceso proveedores al stock
        "auto_reorder": False,
    },

    # =============================================
    # COMUNICACIONES
    # =============================================
    "notifications": {
        "websocket_heartbeat_seconds": 30,
        "push_enabled": True,
        "sound_enabled": True,
        "sound_volume": 0.8,                # 0.0 a 1.0
        "vibrate_on_notification": True,
        "alert_on_delay": True,
        "alert_on_stock_low": True,
        "alert_on_customer_call": True,
    },

    # =============================================
    # NEGOCIO / BRANDING
    # =============================================
    "business": {
        "slogan": "",                       # "El mejor chifa de Iquitos"
        "welcome_message": "",              # Mensaje en carta virtual
        "currency": "PEN",
        "currency_symbol": "S/",
        "timezone": "America/Lima",
        "language": "es",
        "receipt_footer": "¡Gracias por su preferencia!",
        "receipt_show_logo": True,
    },
}


def get_config(restaurant, branch=None) -> dict:
    """
    Resuelve la configuración efectiva.
    Prioridad: branch.config_overrides > restaurant.config > DEFAULTS
    
    Uso en cualquier parte del código:
        from app.models.restaurant_config import get_config
        config = get_config(restaurant, branch)
        target = config["kitchen"]["target_time_minutes"]
    """
    import copy
    
    # 1. Empezar con defaults
    config = copy.deepcopy(RESTAURANT_CONFIG_DEFAULTS)
    
    # 2. Aplicar config del restaurant (override parcial)
    if hasattr(restaurant, 'config') and restaurant.config:
        _deep_merge(config, restaurant.config)
    
    # 3. Aplicar overrides de la branch (si aplica)
    if branch and hasattr(branch, 'config_overrides') and branch.config_overrides:
        _deep_merge(config, branch.config_overrides)
    
    return config


def _deep_merge(base: dict, override: dict):
    """Merge recursivo. override sobreescribe base, key por key."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value