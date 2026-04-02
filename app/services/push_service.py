"""
push_service.py — Envio de Push Notifications via Web Push API.
Usa pywebpush con VAPID keys desde variables de entorno.
Todas las funciones son fire-and-forget: nunca bloquean la operacion principal.
"""

import os
import json
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.models.push_subscription import PushSubscription
from app.models.alert_config import AlertConfig
from app.models.user import User

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS_EMAIL = os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:duil@perusistemas.pro")


def send_push(
    db: Session,
    restaurant_id: int,
    title: str,
    body: str,
    url: Optional[str] = None,
    alert_type: Optional[str] = None,
    roles: Optional[list] = None,
    user_ids: Optional[list] = None,
):
    """
    Envia push notification a subscripciones activas.
    Filtra por roles o user_ids. Si alert_type se provee,
    verifica que el usuario tenga esa alerta habilitada.
    Nunca lanza excepcion — todo en try/except.
    """
    try:
        if not VAPID_PRIVATE_KEY:
            logger.warning("[push] VAPID_PRIVATE_KEY no configurada, skipping push")
            return

        from pywebpush import webpush, WebPushException

        # Buscar subscripciones activas
        query = db.query(PushSubscription).filter(
            PushSubscription.restaurant_id == restaurant_id,
            PushSubscription.is_active == True,
        )

        # Filtrar por user_ids directos
        if user_ids:
            query = query.filter(PushSubscription.user_id.in_(user_ids))
        elif roles:
            # Buscar user_ids por rol
            role_users = db.query(User.id).filter(
                User.restaurant_id == restaurant_id,
                User.role.in_(roles),
                User.is_active == True,
            ).all()
            role_user_ids = [u.id for u in role_users]
            if not role_user_ids:
                return
            query = query.filter(PushSubscription.user_id.in_(role_user_ids))

        subscriptions = query.all()
        if not subscriptions:
            return

        # Filtrar por alert_config si aplica
        if alert_type:
            enabled_user_ids = set()
            for sub in subscriptions:
                config = db.query(AlertConfig).filter(
                    AlertConfig.user_id == sub.user_id,
                    AlertConfig.restaurant_id == restaurant_id,
                    AlertConfig.alert_type == alert_type,
                ).first()
                # Si no hay config, usar default del tipo
                if config is None:
                    from app.models.alert_config import ALERT_TYPES
                    default = ALERT_TYPES.get(alert_type, {}).get("default", True)
                    if default:
                        enabled_user_ids.add(sub.user_id)
                elif config.is_enabled:
                    enabled_user_ids.add(sub.user_id)
            subscriptions = [s for s in subscriptions if s.user_id in enabled_user_ids]

        if not subscriptions:
            return

        payload = json.dumps({
            "title": title,
            "body": body,
            "url": url or f"/dashboard/{restaurant_id}",
            "restaurant_id": restaurant_id,
        })

        vapid_claims = {"sub": VAPID_CLAIMS_EMAIL}

        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {
                            "p256dh": sub.p256dh,
                            "auth": sub.auth,
                        },
                    },
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims,
                )
            except WebPushException as e:
                # 410 Gone = subscription expired, desactivar
                if hasattr(e, 'response') and e.response and e.response.status_code == 410:
                    sub.is_active = False
                    db.commit()
                    logger.info(f"[push] Subscription {sub.id} desactivada (410 Gone)")
                else:
                    logger.warning(f"[push] Error enviando a subscription {sub.id}: {e}")
            except Exception as e:
                logger.warning(f"[push] Error inesperado subscription {sub.id}: {e}")

    except Exception as e:
        logger.error(f"[push] Error general en send_push: {e}")


# ============================================================
# HELPERS — Notificaciones especificas
# ============================================================

def notify_sale(db: Session, rid: int, order_number: int, total: float, branch_name: str, payment_method: str):
    """Notifica venta completada a owner/manager."""
    send_push(
        db, rid,
        title=f"Venta #{order_number:03d}",
        body=f"S/ {total:.2f} — {payment_method} — {branch_name}",
        alert_type="sale_completed",
        roles=["owner", "manager"],
    )


def notify_caja_opened(db: Session, rid: int, user_name: str, branch_name: str):
    """Notifica apertura de caja."""
    send_push(
        db, rid,
        title="Caja abierta",
        body=f"{user_name} abrio caja en {branch_name}",
        alert_type="caja_opened",
        roles=["owner", "manager"],
    )


def notify_caja_closed(db: Session, rid: int, sales_count: int, total: float, branch_name: str):
    """Notifica cierre de caja con resumen."""
    send_push(
        db, rid,
        title="Caja cerrada",
        body=f"{sales_count} ventas — S/ {total:.2f} — {branch_name}",
        alert_type="caja_closed",
        roles=["owner", "manager"],
    )


def notify_attendance_complete(db: Session, rid: int, branch_name: str, present: int, expected: int):
    """Notifica que todo el personal esperado ya marco."""
    send_push(
        db, rid,
        title="Personal completo",
        body=f"{present}/{expected} presentes en {branch_name}",
        alert_type="attendance_complete",
        roles=["owner", "manager"],
    )


def notify_attendance_missing(db: Session, rid: int, branch_name: str, missing_names: list):
    """Notifica personal faltante."""
    names = ", ".join(missing_names[:5])
    if len(missing_names) > 5:
        names += f" (+{len(missing_names) - 5})"
    send_push(
        db, rid,
        title="Personal faltante",
        body=f"Faltan en {branch_name}: {names}",
        alert_type="attendance_missing",
        roles=["owner", "manager"],
    )


def notify_delivery_dispatched(db: Session, rid: int, order_number: int, driver_name: str):
    """Notifica que motorizado salio con pedido."""
    send_push(
        db, rid,
        title=f"Delivery #{order_number:03d} en camino",
        body=f"Motorizado: {driver_name}",
        alert_type="delivery_dispatched",
        roles=["owner", "manager"],
    )
