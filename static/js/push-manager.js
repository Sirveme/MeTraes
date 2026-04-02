/**
 * push-manager.js — Modulo reutilizable para Push Notifications.
 * Registra Service Worker, solicita permisos, subscribe al push server.
 * Usar: initPush(token) despues del login exitoso.
 */

function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; i++) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

async function initPush(token) {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.log('[push] Browser no soporta push');
        return false;
    }

    try {
        // Registrar Service Worker
        var reg = await navigator.serviceWorker.register('/service-worker.js');
        console.log('[push] SW registrado');

        // Solicitar permiso
        var perm = await Notification.requestPermission();
        if (perm !== 'granted') {
            console.log('[push] Permiso denegado');
            return false;
        }

        // Obtener VAPID public key del servidor
        var vapidRes = await fetch('/api/v1/push/vapid-key');
        if (!vapidRes.ok) {
            console.log('[push] No hay VAPID key configurada');
            return false;
        }
        var vapidData = await vapidRes.json();

        // Subscribir al push manager
        var sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidData.public_key)
        });

        // Extraer keys
        var p256dhKey = sub.getKey('p256dh');
        var authKey = sub.getKey('auth');

        var p256dh = btoa(String.fromCharCode.apply(null, new Uint8Array(p256dhKey)));
        var auth = btoa(String.fromCharCode.apply(null, new Uint8Array(authKey)));

        // Detectar dispositivo
        var ua = navigator.userAgent;
        var device = 'Navegador';
        if (/Android/i.test(ua)) device = 'Chrome Android';
        else if (/iPhone|iPad/i.test(ua)) device = 'Safari iOS';
        else if (/Firefox/i.test(ua)) device = 'Firefox Desktop';
        else if (/Chrome/i.test(ua)) device = 'Chrome Desktop';

        // Enviar subscription al servidor
        var res = await fetch('/api/v1/push/subscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token,
            },
            body: JSON.stringify({
                endpoint: sub.endpoint,
                p256dh: p256dh,
                auth: auth,
                device_name: device,
            })
        });

        if (res.ok) {
            console.log('[push] Subscription registrada');
            return true;
        } else {
            console.log('[push] Error registrando subscription');
            return false;
        }

    } catch(e) {
        console.error('[push] Error:', e);
        return false;
    }
}

async function isPushSubscribed() {
    if (!('serviceWorker' in navigator)) return false;
    try {
        var reg = await navigator.serviceWorker.getRegistration('/service-worker.js');
        if (!reg) return false;
        var sub = await reg.pushManager.getSubscription();
        return sub !== null;
    } catch(e) {
        return false;
    }
}
