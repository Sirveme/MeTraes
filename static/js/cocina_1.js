/* ============================================
   cocina_1.js — Lógica principal del KDS
   Renderiza cards, maneja touch, timers, filtros.
   Lee config de window.KDS_CONFIG (inyectada por Jinja2).
   ============================================ */

const KDS = {
    config: null,
    orders: [],
    stations: [],
    activeStation: 'all',
    soundEnabled: true,
    timerInterval: null,

    /**
     * Inicializar KDS.
     */
    init() {
        this.config = window.KDS_CONFIG;
        this._setupClock();
        this._setupTimerUpdater();
        this._setupEventListeners();
        this._connectWebSocket();

        // Fallback: si WS no conecta en 5s, cargar via REST
        setTimeout(() => {
            if (!KDS_WS.isConnected && this.orders.length === 0) {
                this._loadViaREST();
            }
        }, 5000);
    },

    // ========================================
    // RENDERING
    // ========================================

    /**
     * Renderizar todos los pedidos en el grid.
     */
    render() {
        const grid = document.getElementById('kds-grid');
        const emptyState = document.getElementById('empty-state');

        // Filtrar por estación activa
        let filtered = this.orders;
        if (this.activeStation !== 'all') {
            const sid = parseInt(this.activeStation);
            filtered = this.orders.filter(o =>
                o.items.some(i => i.station_id === sid)
            );
        }

        // Ordenar: urgentes primero, luego por tiempo (más antiguo primero)
        filtered.sort((a, b) => {
            if (a.priority === 'urgent' && b.priority !== 'urgent') return -1;
            if (b.priority === 'urgent' && a.priority !== 'urgent') return 1;
            return (a.kitchen_wait_minutes || 0) - (b.kitchen_wait_minutes || 0);
        });
        // Invertir: más antiguo primero (más tiempo esperando)
        filtered.sort((a, b) => (b.kitchen_wait_minutes || 0) - (a.kitchen_wait_minutes || 0));

        // Limpiar grid (preservar empty-state)
        const cards = grid.querySelectorAll('.order-card');
        cards.forEach(c => c.remove());

        // Mostrar/ocultar empty state
        if (filtered.length === 0) {
            emptyState.classList.remove('hidden');
        } else {
            emptyState.classList.add('hidden');
            filtered.forEach(order => {
                const card = this._createCard(order);
                grid.appendChild(card);
            });
        }

        // Actualizar contadores
        this._updateCounts();
    },

    /**
     * Crear card HTML para un pedido.
     */
    _createCard(order) {
        const card = document.createElement('div');
        card.className = 'order-card';
        card.dataset.orderId = order.id;
        card.dataset.status = order.status;

        const kc = this.config.kitchen;
        const waitMin = order.kitchen_wait_minutes || 0;
        const isDelayed = waitMin >= kc.alert_time_minutes;
        const isUrgent = order.priority === 'urgent';

        if (isDelayed) card.classList.add('delayed');
        if (isUrgent) card.classList.add('urgent');

        // --- Header ---
        let tableHtml = `<span class="card-table-name">${this._escHtml(order.table_display)}</span>`;
        if (order.waiter_name) {
            tableHtml += `<span class="card-waiter">👤 ${this._escHtml(order.waiter_name)}</span>`;
        }

        let typeBadge = '';
        if (order.order_type === 'delivery') {
            typeBadge = '<span class="card-type-badge delivery">Delivery</span>';
        } else if (order.order_type === 'takeaway') {
            typeBadge = '<span class="card-type-badge takeaway">P/Llevar</span>';
        }

        // --- Timer ---
        const timerClass = this._getTimerClass(waitMin);
        const timerDisplay = this._formatMinutes(waitMin);

        // --- Items ---
        let items = order.items;
        if (this.activeStation !== 'all') {
            const sid = parseInt(this.activeStation);
            items = items.filter(i => i.station_id === sid);
        }

        let itemsHtml = '';
        let lastCourse = 0;
        items.forEach(item => {
            // Separador de curso
            if (item.course > lastCourse && lastCourse > 0) {
                const courseNames = { 1: 'Entrada', 2: 'Plato fuerte', 3: 'Postre' };
                itemsHtml += `<div class="course-separator">${courseNames[item.course] || `Curso ${item.course}`}</div>`;
            }
            lastCourse = item.course;

            const dotClass = item.status;
            const nameClass = item.is_fire ? ' fire' : '';
            const qty = parseFloat(item.quantity);
            const qtyDisplay = qty === Math.floor(qty) ? qty.toString() : qty.toFixed(1);

            // Botón de acción según estado
            let actionBtn = '';
            if (item.status === 'sent') {
                actionBtn = `<button class="item-action-btn btn-start" data-item-id="${item.id}" data-action="preparing">PREP</button>`;
            } else if (item.status === 'preparing') {
                actionBtn = `<button class="item-action-btn btn-done" data-item-id="${item.id}" data-action="ready">LISTO</button>`;
            }

            let modHtml = item.modifiers_summary
                ? `<div class="item-modifiers">${this._escHtml(item.modifiers_summary)}</div>` : '';
            let notesHtml = item.notes
                ? `<div class="item-notes">📝 ${this._escHtml(item.notes)}</div>` : '';
            let sizeHtml = item.size_name
                ? `<span class="item-size">[${this._escHtml(item.size_name)}]</span> ` : '';

            itemsHtml += `
                <div class="item-row" data-item-id="${item.id}">
                    <div class="item-status-dot ${dotClass}"></div>
                    <div class="item-qty">${qtyDisplay}</div>
                    <div class="item-details">
                        <div class="item-name${nameClass}">${sizeHtml}${this._escHtml(item.product_name)}</div>
                        ${modHtml}
                        ${notesHtml}
                    </div>
                    ${actionBtn}
                </div>
            `;
        });

        // --- Bulk action button ---
        const allSent = items.every(i => i.status === 'sent');
        const allPreparing = items.every(i => i.status === 'preparing');
        let bulkBtn = '';
        if (allSent) {
            bulkBtn = `<button class="card-action-all start-all" data-order-id="${order.id}" data-action="preparing">▶ PREPARAR TODO</button>`;
        } else if (allPreparing) {
            bulkBtn = `<button class="card-action-all done-all" data-order-id="${order.id}" data-action="ready">✅ TODO LISTO</button>`;
        }

        // --- Timer bar ---
        const targetMin = kc.target_time_minutes;
        const barPercent = Math.min((waitMin / (targetMin * 2)) * 100, 100);

        card.innerHTML = `
            <div class="card-header">
                <span class="card-order-number">#${String(order.order_number).padStart(3, '0')}</span>
                ${typeBadge}
                <div class="card-table-info">${tableHtml}</div>
            </div>
            <div class="card-items">${itemsHtml}</div>
            <div class="card-footer">
                <span class="card-guests">👥 ${order.guest_count}</span>
                <div class="timer ${timerClass}">
                    <span class="timer-icon">⏱</span>
                    <span class="timer-value">${timerDisplay}</span>
                </div>
                ${bulkBtn}
            </div>
            <div class="timer-bar">
                <div class="timer-bar-fill ${timerClass}" style="width: ${barPercent}%"></div>
            </div>
        `;

        // Event delegation para botones
        card.addEventListener('click', (e) => this._handleCardClick(e, order));

        return card;
    },

    // ========================================
    // ACTIONS
    // ========================================

    /**
     * Manejar clicks en cards (items y bulk actions).
     */
    _handleCardClick(e, order) {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;

        const action = btn.dataset.action;
        const itemId = btn.dataset.itemId;
        const orderId = btn.dataset.orderId;

        if (itemId) {
            // Acción en item individual
            this._updateItemStatus(parseInt(itemId), action);
        } else if (orderId) {
            // Acción bulk: todos los items del pedido
            const items = order.items.filter(i => {
                if (action === 'preparing') return i.status === 'sent';
                if (action === 'ready') return i.status === 'preparing';
                return false;
            });

            // Si hay filtro de estación, solo los de esa estación
            let filtered = items;
            if (this.activeStation !== 'all') {
                const sid = parseInt(this.activeStation);
                filtered = items.filter(i => i.station_id === sid);
            }

            filtered.forEach(item => {
                this._updateItemStatus(item.id, action);
            });
        }
    },

    /**
     * Llamar API para cambiar estado de un item.
     */
    async _updateItemStatus(itemId, newStatus) {
        const token = localStorage.getItem('access_token') || '';
        try {
            const resp = await fetch(`${this.config.api_base}/kitchen/items/${itemId}/status`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ status: newStatus }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                console.error('[KDS] Error al actualizar item:', err);
            }
            // La actualización real llega por WebSocket
        } catch (e) {
            console.error('[KDS] Error de red:', e);
        }
    },

    // ========================================
    // WEBSOCKET HANDLERS
    // ========================================

    _connectWebSocket() {
        KDS_WS.onInitialState = (data) => {
            this.orders = data.orders || [];
            this.stations = data.stations || [];
            this._renderStationFilters();
            this.render();
        };

        KDS_WS.onMessage = (event, data) => {
            if (data.orders) {
                const prevCount = this.orders.length;
                this.orders = data.orders;

                // Detectar pedido nuevo
                if (data.orders.length > prevCount || event === 'order_sent') {
                    this._onNewOrder(data);
                }

                this.render();
            }
        };

        KDS_WS.connect();
    },

    /**
     * Nuevo pedido: flash visual + sonido.
     */
    _onNewOrder(data) {
        // Flash
        const flash = document.getElementById('new-order-flash');
        const detail = document.getElementById('flash-detail');

        if (data.changed_item) {
            return; // Es un update, no pedido nuevo
        }

        let orderInfo = '';
        if (data.order_number) {
            orderInfo = `#${String(data.order_number).padStart(3, '0')}`;
        }
        detail.textContent = orderInfo;

        flash.classList.remove('hidden');
        setTimeout(() => flash.classList.add('hidden'), 2500);

        // Sonido
        if (this.soundEnabled) {
            this._playSound('sound-new-order');
        }
    },

    // ========================================
    // STATION FILTERS
    // ========================================

    _renderStationFilters() {
        const nav = document.getElementById('station-filters');
        // Mantener botón "TODAS"
        const allBtn = nav.querySelector('[data-station-id="all"]');

        // Limpiar estaciones existentes
        nav.querySelectorAll('[data-station-id]:not([data-station-id="all"])').forEach(b => b.remove());

        this.stations.forEach(s => {
            const btn = document.createElement('button');
            btn.className = 'station-btn';
            btn.dataset.stationId = s.id;
            btn.style.borderColor = s.color;
            btn.innerHTML = `
                ${s.icon || ''} ${s.short_name || s.name}
                <span class="station-count" id="count-station-${s.id}">${s.pending_count}</span>
            `;
            btn.addEventListener('click', () => this._selectStation(s.id));
            nav.appendChild(btn);
        });
    },

    _selectStation(stationId) {
        this.activeStation = stationId === this.activeStation ? 'all' : stationId;

        // Actualizar UI de botones
        document.querySelectorAll('.station-btn').forEach(btn => {
            const sid = btn.dataset.stationId;
            btn.classList.toggle('active',
                sid === String(this.activeStation) || (this.activeStation === 'all' && sid === 'all')
            );
        });

        this.render();
    },

    // ========================================
    // TIMERS
    // ========================================

    _setupTimerUpdater() {
        // Actualizar timers cada 30 segundos
        this.timerInterval = setInterval(() => {
            // Incrementar wait minutes localmente
            this.orders.forEach(o => {
                if (o.kitchen_wait_minutes !== undefined) {
                    o.kitchen_wait_minutes += 0.5;
                }
            });
            // Actualizar solo los timers, no re-renderizar todo
            this._updateTimerDisplays();
        }, 30000);
    },

    _updateTimerDisplays() {
        const kc = this.config.kitchen;
        document.querySelectorAll('.order-card').forEach(card => {
            const orderId = parseInt(card.dataset.orderId);
            const order = this.orders.find(o => o.id === orderId);
            if (!order) return;

            const waitMin = Math.round(order.kitchen_wait_minutes || 0);
            const timerEl = card.querySelector('.timer');
            const timerValue = card.querySelector('.timer-value');
            const barFill = card.querySelector('.timer-bar-fill');

            if (timerValue) {
                timerValue.textContent = this._formatMinutes(waitMin);
            }

            const timerClass = this._getTimerClass(waitMin);
            if (timerEl) {
                timerEl.className = `timer ${timerClass}`;
            }
            if (barFill) {
                const percent = Math.min((waitMin / (kc.target_time_minutes * 2)) * 100, 100);
                barFill.style.width = `${percent}%`;
                barFill.className = `timer-bar-fill ${timerClass}`;
            }

            // Delayed class on card
            if (waitMin >= kc.alert_time_minutes) {
                card.classList.add('delayed');
            }
        });
    },

    _getTimerClass(minutes) {
        const kc = this.config.kitchen;
        if (minutes >= kc.alert_time_minutes) return 'alert';
        if (minutes >= kc.warning_time_minutes) return 'warning';
        return 'normal';
    },

    _formatMinutes(min) {
        min = Math.round(min);
        if (min < 60) return `${min}m`;
        const h = Math.floor(min / 60);
        const m = min % 60;
        return `${h}h ${m}m`;
    },

    // ========================================
    // COUNTS
    // ========================================

    _updateCounts() {
        // Total
        const countAll = document.getElementById('count-all');
        const ordersCount = document.getElementById('orders-count');
        const total = this.orders.length;

        if (countAll) countAll.textContent = total;
        if (ordersCount) {
            ordersCount.textContent = `${total} pedido${total !== 1 ? 's' : ''}`;
        }

        // Por estación
        this.stations.forEach(s => {
            const el = document.getElementById(`count-station-${s.id}`);
            if (el) {
                const count = this.orders.filter(o =>
                    o.items.some(i => i.station_id === s.id)
                ).length;
                el.textContent = count;
            }
        });
    },

    // ========================================
    // CLOCK
    // ========================================

    _setupClock() {
        const update = () => {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const el = document.getElementById('clock');
            if (el) el.textContent = `${h}:${m}`;
        };
        update();
        setInterval(update, 30000);
    },

    // ========================================
    // EVENT LISTENERS
    // ========================================

    _setupEventListeners() {
        // Fullscreen
        document.getElementById('btn-fullscreen')?.addEventListener('click', () => {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        });

        // Sound toggle
        document.getElementById('btn-sound')?.addEventListener('click', (e) => {
            this.soundEnabled = !this.soundEnabled;
            const btn = e.currentTarget;
            btn.textContent = this.soundEnabled ? '🔊' : '🔇';
            btn.classList.toggle('sound-off', !this.soundEnabled);
        });

        // Station filter: "TODAS"
        document.querySelector('[data-station-id="all"]')?.addEventListener('click', () => {
            this._selectStation('all');
        });
    },

    // ========================================
    // UTILITIES
    // ========================================

    _audioCtx: null,

    _playSound(elementId) {
        // Web Audio API beep (no depende de .wav/.mp3)
        try {
            if (!this._audioCtx) this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const ctx = this._audioCtx;
            const isUrgent = elementId.includes('urgent');
            const freq = isUrgent ? 1200 : 880;
            const times = isUrgent ? 5 : 3;
            const dur = 0.2;
            for (let i = 0; i < times; i++) {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = freq;
                osc.type = 'square';
                gain.gain.value = 0.3;
                const start = ctx.currentTime + i * (dur + 0.1);
                osc.start(start);
                osc.stop(start + dur);
            }
        } catch(e) {}
    },

    _escHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /**
     * Fallback: cargar pedidos via REST si WS no conecta.
     */
    async _loadViaREST() {
        const token = localStorage.getItem('access_token') || '';
        try {
            const resp = await fetch(`${this.config.api_base}/kitchen/pending`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (resp.ok) {
                this.orders = await resp.json();
                this.render();
            }
        } catch (e) {
            console.error('[KDS] Error cargando via REST:', e);
        }

        // Cargar estaciones
        try {
            const resp = await fetch(`${this.config.api_base}/kitchen/stations`, {
                headers: { 'Authorization': `Bearer ${token}` },
            });
            if (resp.ok) {
                this.stations = await resp.json();
                this._renderStationFilters();
            }
        } catch (e) {
            console.error('[KDS] Error cargando estaciones:', e);
        }
    },
};

// --- Inicializar cuando el DOM esté listo ---
document.addEventListener('DOMContentLoaded', () => {
    // No iniciar si no hay token válido (la pantalla PIN se encarga)
    var token = localStorage.getItem('access_token');
    if (!token) return;
    try {
        var payload = JSON.parse(atob(token.split('.')[1]));
        var rid = window.KDS_CONFIG.restaurant_id;
        if (parseInt(payload.restaurant_id) !== rid) return;
    } catch(e) { return; }
    KDS.init();
});