/* ============================================
   cocina_1_ws.js — WebSocket para KDS
   Conexión con reconexión automática.
   Heartbeat cada 30s (internet Iquitos).
   ============================================ */

const KDS_WS = {
    socket: null,
    reconnectInterval: 3000,
    reconnectAttempts: 0,
    maxReconnectAttempts: 100,  // Intentar por horas
    heartbeatTimer: null,
    heartbeatInterval: 30000,   // 30 segundos
    isConnected: false,

    // Callbacks (se asignan desde cocina_1.js)
    onConnected: null,
    onDisconnected: null,
    onMessage: null,
    onInitialState: null,

    /**
     * Conectar al WebSocket del KDS.
     */
    connect() {
        const config = window.KDS_CONFIG;
        const restaurantId = config.restaurant_id;
        const stationId = config.station_id;
        const token = localStorage.getItem('access_token') || '';

        // Construir URL
        let wsUrl = `${config.ws_base}/${restaurantId}?token=${token}`;
        if (stationId) {
            wsUrl += `&station_id=${stationId}`;
        }

        // Ajustar protocolo
        if (window.location.protocol === 'https:') {
            wsUrl = wsUrl.replace('ws://', 'wss://');
        }

        console.log('[KDS-WS] Conectando a:', wsUrl);
        this._updateStatus('connecting');

        try {
            this.socket = new WebSocket(wsUrl);
        } catch (e) {
            console.error('[KDS-WS] Error al crear WebSocket:', e);
            this._scheduleReconnect();
            return;
        }

        this.socket.onopen = () => {
            console.log('[KDS-WS] ✅ Conectado');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this._updateStatus('connected');
            this._startHeartbeat();
            if (this.onConnected) this.onConnected();
        };

        this.socket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this._handleMessage(msg);
            } catch (e) {
                // Puede ser un "pong" text
                if (event.data === 'pong') return;
                console.warn('[KDS-WS] Mensaje no parseable:', event.data);
            }
        };

        this.socket.onclose = (event) => {
            console.log('[KDS-WS] ❌ Desconectado:', event.code, event.reason);
            this.isConnected = false;
            this._updateStatus('disconnected');
            this._stopHeartbeat();
            if (this.onDisconnected) this.onDisconnected();
            // Auth failed: token inválido o restaurant_id no coincide
            if (event.code === 4001 || event.code === 4003 || event.code === 403) {
                console.warn('[KDS-WS] Token inválido, forzando re-login');
                localStorage.removeItem('access_token');
                var pinEl = document.getElementById('pin-login');
                if (pinEl) { pinEl.style.display = 'flex'; }
                return; // No reconectar
            }
            this._scheduleReconnect();
        };

        this.socket.onerror = (error) => {
            console.error('[KDS-WS] Error:', error);
        };
    },

    /**
     * Enviar mensaje al servidor.
     */
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            if (typeof data === 'string') {
                this.socket.send(data);
            } else {
                this.socket.send(JSON.stringify(data));
            }
        }
    },

    /**
     * Procesar mensaje recibido.
     */
    _handleMessage(msg) {
        const event = msg.event;
        const data = msg.data;

        switch (event) {
            case 'initial_state':
                console.log('[KDS-WS] Estado inicial recibido:', data.orders?.length, 'pedidos');
                if (this.onInitialState) this.onInitialState(data);
                break;

            case 'order_sent':
            case 'kds_update':
                if (this.onMessage) this.onMessage(event, data);
                break;

            default:
                console.log('[KDS-WS] Evento:', event, data);
                if (this.onMessage) this.onMessage(event, data);
        }
    },

    /**
     * Heartbeat: ping cada 30s para mantener conexión.
     */
    _startHeartbeat() {
        this._stopHeartbeat();
        this.heartbeatTimer = setInterval(() => {
            this.send('ping');
        }, this.heartbeatInterval);
    },

    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    },

    /**
     * Reconexión automática con backoff.
     */
    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('[KDS-WS] Máximo de intentos alcanzado');
            return;
        }

        this.reconnectAttempts++;
        // Backoff: 3s, 6s, 9s... hasta max 30s
        const delay = Math.min(this.reconnectInterval * this.reconnectAttempts, 30000);
        console.log(`[KDS-WS] Reintentando en ${delay / 1000}s (intento ${this.reconnectAttempts})`);

        setTimeout(() => {
            if (!this.isConnected) {
                this.connect();
            }
        }, delay);
    },

    /**
     * Actualizar badge de estado en el header.
     */
    _updateStatus(status) {
        const el = document.getElementById('connection-status');
        if (!el) return;

        el.className = 'status-badge';
        switch (status) {
            case 'connecting':
                el.className += ' status-connecting';
                el.textContent = '⏳ Conectando...';
                break;
            case 'connected':
                el.className += ' status-connected';
                el.textContent = '✅ En línea';
                break;
            case 'disconnected':
                el.className += ' status-disconnected';
                el.textContent = '❌ Sin conexión';
                break;
        }
    },

    /**
     * Desconectar limpiamente.
     */
    disconnect() {
        this._stopHeartbeat();
        this.maxReconnectAttempts = 0;  // No reconectar
        if (this.socket) {
            this.socket.close();
        }
    }
};