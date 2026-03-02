/* ============================================
   pedido_1.js — POS Mesero: Lógica completa
   Screens: Login PIN → Mapa Mesas → Toma Pedido
   Un solo archivo porque la lógica está entrelazada.
   ============================================ */

const POS = {
    config: null,
    token: null,
    user: null,

    // Data
    tables: [],
    zones: [],
    categories: [],
    products: [],
    currentZone: 'all',
    currentCategory: null,

    // Order state
    currentTable: null,
    currentOrder: null,
    cart: [],        // Items temporales antes de enviar
    cartIdSeq: 0,

    // Modal state
    modalProduct: null,
    modalQty: 1,
    modalSize: null,
    modalModifiers: {},  // group_index -> [option_indices]
    modalNotes: '',

    // ========================================
    // INIT
    // ========================================

    init() {
        this.config = window.POS_CONFIG;
        this._setupLoginListeners();
        this._setupTableListeners();
        this._setupOrderListeners();
        this._setupModalListeners();

        // Si hay token guardado, intentar restaurar sesión
        const saved = localStorage.getItem('access_token');
        if (saved) {
            this.token = saved;
            this.user = JSON.parse(localStorage.getItem('pos_user') || 'null');
            if (this.user) {
                this._goToTables();
                return;
            }
        }
    },

    // ========================================
    // NAVIGATION
    // ========================================

    _showScreen(id) {
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        document.getElementById(id)?.classList.add('active');
    },

    // ========================================
    // SCREEN 1: LOGIN
    // ========================================

    _pinValue: '',

    _setupLoginListeners() {
        document.querySelectorAll('.pin-key').forEach(btn => {
            btn.addEventListener('click', () => {
                const key = btn.dataset.key;
                if (key === 'clear') {
                    this._pinValue = '';
                } else if (key === 'enter') {
                    this._doLogin();
                    return;
                } else {
                    if (this._pinValue.length < 6) {
                        this._pinValue += key;
                    }
                }
                this._updatePinDots();

                // Auto-login al 4to dígito
                if (this._pinValue.length === 4) {
                    setTimeout(() => this._doLogin(), 200);
                }
            });
        });
    },

    _updatePinDots() {
        const dots = document.querySelectorAll('.pin-dot');
        dots.forEach((dot, i) => {
            dot.classList.toggle('filled', i < this._pinValue.length);
        });
    },

    async _doLogin() {
        if (this._pinValue.length < 4) return;

        const errorEl = document.getElementById('login-error');
        errorEl.classList.add('hidden');

        try {
            const resp = await fetch(`${this.config.api_base}/auth/login/pin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pin: this._pinValue,
                    restaurant_id: this.config.restaurant_id,
                }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                errorEl.textContent = err.detail || 'PIN incorrecto';
                errorEl.classList.remove('hidden');
                this._pinValue = '';
                this._updatePinDots();
                return;
            }

            const data = await resp.json();
            this.token = data.access_token;
            this.user = data.user;
            localStorage.setItem('access_token', this.token);
            localStorage.setItem('pos_user', JSON.stringify(this.user));

            // Rol cocina → redirigir a KDS
            if (this.user.role === 'kitchen') {
                window.location.href = `/cocina?restaurant_id=${this.config.restaurant_id}`;
                return;
            }

            this._goToTables();
        } catch (e) {
            errorEl.textContent = 'Error de conexión';
            errorEl.classList.remove('hidden');
            this._pinValue = '';
            this._updatePinDots();
        }
    },

    _logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('pos_user');
        this._pinValue = '';
        this._updatePinDots();
        this._showScreen('screen-login');
    },

    // ========================================
    // SCREEN 2: MAPA DE MESAS
    // ========================================

    async _goToTables() {
        document.getElementById('user-badge').textContent =
            `${this.user.short_name || this.user.name} · ${this.user.role}`;

        await this._loadTables();
        this._showScreen('screen-tables');
    },

    async _loadTables() {
        try {
            const resp = await this._fetch('/tables');
            if (resp.ok) {
                this.tables = await resp.json();
                this._extractZones();
                this._renderZoneTabs();
                this._renderTables();
            }
        } catch (e) {
            console.error('[POS] Error cargando mesas:', e);
        }
    },

    _extractZones() {
        const zoneMap = {};
        this.tables.forEach(t => {
            const zid = t.zone_id || 0;
            if (!zoneMap[zid]) {
                zoneMap[zid] = {
                    id: zid,
                    name: t.zone_name || 'General',
                    floor_number: t.floor_number || 1,
                    count: 0,
                };
            }
            zoneMap[zid].count++;
        });
        this.zones = Object.values(zoneMap).sort((a, b) => a.floor_number - b.floor_number);
    },

    _renderZoneTabs() {
        const container = document.getElementById('zone-tabs');
        container.innerHTML = '';

        // Tab "Todas"
        const allBtn = document.createElement('button');
        allBtn.className = 'zone-tab active';
        allBtn.dataset.zoneId = 'all';
        allBtn.innerHTML = `Todas <span class="zone-count">${this.tables.length}</span>`;
        allBtn.addEventListener('click', () => this._selectZone('all'));
        container.appendChild(allBtn);

        this.zones.forEach(z => {
            const btn = document.createElement('button');
            btn.className = 'zone-tab';
            btn.dataset.zoneId = z.id;
            btn.innerHTML = `${z.name} <span class="zone-count">${z.count}</span>`;
            btn.addEventListener('click', () => this._selectZone(z.id));
            container.appendChild(btn);
        });
    },

    _selectZone(zoneId) {
        this.currentZone = zoneId;
        document.querySelectorAll('.zone-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.zoneId === String(zoneId));
        });
        this._renderTables();
    },

    _renderTables() {
        const grid = document.getElementById('tables-grid');
        grid.innerHTML = '';

        let filtered = this.tables;
        if (this.currentZone !== 'all') {
            filtered = this.tables.filter(t => t.zone_id === this.currentZone);
        }

        filtered.forEach(t => {
            const card = document.createElement('div');
            const statusClass = t.status || 'free';
            const shapeClass = t.shape === 'round' ? ' round' : '';
            card.className = `table-card ${statusClass}${shapeClass}`;
            card.dataset.tableId = t.id;

            let waiterHtml = '';
            if (t.assigned_waiter_name) {
                waiterHtml = `<span class="table-waiter">👤 ${this._esc(t.assigned_waiter_name)}</span>`;
            }

            let orderDot = '';
            if (t.current_order_id) {
                orderDot = '<span class="table-order-badge"></span>';
            }

            card.innerHTML = `
                ${orderDot}
                <span class="table-number">${t.number}</span>
                <span class="table-zone-tag">${this._esc(t.zone_name || '')}</span>
                <span class="table-cap">👥 ${t.capacity}</span>
                ${waiterHtml}
            `;

            card.addEventListener('click', () => this._onTableClick(t));
            grid.appendChild(card);
        });
    },

    _onTableClick(table) {
        this.currentTable = table;
        this.cart = [];
        this.currentOrder = null;

        // Si la mesa tiene pedido abierto, cargar el pedido
        if (table.current_order_id) {
            this._loadExistingOrder(table.current_order_id);
        }

        this._goToOrder(table);
    },

    _setupTableListeners() {
        document.getElementById('btn-logout')?.addEventListener('click', () => this._logout());
        document.getElementById('btn-takeaway')?.addEventListener('click', () => {
            this.currentTable = { id: null, display_name: '📦 Para llevar', number: 0 };
            this.cart = [];
            this.currentOrder = null;
            this._goToOrder(this.currentTable, 'takeaway');
        });
    },

    // ========================================
    // SCREEN 3: TOMA DE PEDIDO
    // ========================================

    _orderType: 'dine_in',

    async _goToOrder(table, orderType = 'dine_in') {
        this._orderType = orderType;
        document.getElementById('order-table-name').textContent =
            table.display_name || `Mesa ${table.number}`;

        await this._loadMenu();
        this._renderCategories();
        this._renderCart();
        this._showScreen('screen-order');
    },

    async _loadMenu() {
        if (this.categories.length > 0) return; // Ya cargado

        try {
            // Cargar productos (incluye categoría)
            const resp = await this._fetch(`/orders?status_filter=none&table_id=-1`);
            // Mejor: cargar desde un endpoint de productos
            // Por ahora usamos seed data, así que cargamos directo
        } catch (e) {
            console.error('[POS] Error cargando menú:', e);
        }

        // Cargar categorías y productos via endpoints dedicados
        // Como aún no tenemos endpoint /products, cargar via un approach simplificado
        await this._loadMenuData();
    },

    async _loadMenuData() {
        // Cargar categorías
        try {
            const resp = await fetch(`${this.config.api_base}/menu/categories?restaurant_id=${this.config.restaurant_id}`);
            if (resp.ok) {
                this.categories = await resp.json();
            }
        } catch (e) {
            // Fallback: usar endpoint alternativo
        }

        // Cargar productos
        try {
            const resp = await fetch(`${this.config.api_base}/menu/products?restaurant_id=${this.config.restaurant_id}`);
            if (resp.ok) {
                this.products = await resp.json();
            }
        } catch (e) {
            // Fallback
        }

        // Si los endpoints de menú no existen aún, intentar cargar todo de una
        if (this.categories.length === 0 || this.products.length === 0) {
            try {
                const resp = await this._fetch('/menu/full');
                if (resp.ok) {
                    const data = await resp.json();
                    this.categories = data.categories || [];
                    this.products = data.products || [];
                }
            } catch (e) {
                console.error('[POS] No se pudo cargar el menú');
            }
        }
    },

    _renderCategories() {
        const container = document.getElementById('category-tabs');
        container.innerHTML = '';

        this.categories.forEach((cat, i) => {
            const btn = document.createElement('button');
            btn.className = `cat-tab${i === 0 ? ' active' : ''}`;
            btn.dataset.catId = cat.id;
            btn.innerHTML = `<span class="cat-icon">${cat.icon || '🍽️'}</span> ${this._esc(cat.name)}`;
            btn.addEventListener('click', () => this._selectCategory(cat.id));
            container.appendChild(btn);
        });

        if (this.categories.length > 0) {
            this._selectCategory(this.categories[0].id);
        }
    },

    _selectCategory(catId) {
        this.currentCategory = catId;
        document.querySelectorAll('.cat-tab').forEach(t => {
            t.classList.toggle('active', parseInt(t.dataset.catId) === catId);
        });
        this._renderProducts();
    },

    _renderProducts() {
        const grid = document.getElementById('products-grid');
        grid.innerHTML = '';

        const filtered = this.products.filter(p => p.category_id === this.currentCategory);

        filtered.forEach(p => {
            const card = document.createElement('div');
            card.className = `product-card${p.is_available === false ? ' unavailable' : ''}`;
            card.dataset.productId = p.id;

            let badges = '';
            if (p.is_new) badges += '<span class="product-badge badge-new">NUEVO</span>';
            if (p.is_bestseller) badges += '<span class="product-badge badge-best">⭐</span>';
            if (p.is_spicy) badges += '<span class="product-badge badge-hot">🌶️</span>';

            card.innerHTML = `
                <div class="product-name">${this._esc(p.short_name || p.name)}</div>
                <div class="product-price">S/ ${parseFloat(p.sale_price).toFixed(2)}</div>
                ${badges ? `<div class="product-badges">${badges}</div>` : ''}
            `;

            card.addEventListener('click', () => this._onProductClick(p));
            grid.appendChild(card);
        });
    },

    _onProductClick(product) {
        const hasSizes = product.sizes && product.sizes.length > 0;
        // Solo abrir modal si tiene modifiers REQUERIDOS o sizes
        const hasRequiredMods = product.modifiers && product.modifiers.some(m => m.required);

        if (!hasRequiredMods && !hasSizes) {
            // Sin modal: agregar directo o sumar cantidad si ya está en carrito
            const existing = this.cart.find(i =>
                i.product_id === product.id && !i.size_name && i.modifiers.length === 0
            );
            if (existing) {
                existing.quantity += 1;
                existing.line_total = existing.unit_price * existing.quantity;
                this._renderCart();
                this._toast(`${product.short_name || product.name} ×${existing.quantity}`, 'success');
            } else {
                this._addToCart(product, 1, null, [], '');
            }
            return;
        }

        // Abrir modal de modificadores
        this._openModifierModal(product);
    },

    async _loadExistingOrder(orderId) {
        try {
            const resp = await this._fetch(`/orders/${orderId}`);
            if (resp.ok) {
                this.currentOrder = await resp.json();
                // Los items existentes se muestran como "ya enviados"
            }
        } catch (e) {
            console.error('[POS] Error cargando pedido:', e);
        }
    },

    _setupOrderListeners() {
        document.getElementById('btn-back-tables')?.addEventListener('click', () => {
            this._goToTables();
        });

        document.getElementById('btn-send-kitchen')?.addEventListener('click', () => {
            this._sendToKitchen();
        });

        // Mobile: toggle cart
        const cartHeader = document.querySelector('.cart-header');
        if (cartHeader) {
            cartHeader.addEventListener('click', () => {
                document.querySelector('.cart-panel')?.classList.toggle('expanded');
            });
        }
    },

    // ========================================
    // CART
    // ========================================

    _addToCart(product, qty, sizeName, selectedMods, notes) {
        const unitPrice = sizeName
            ? (product.sizes.find(s => s.name === sizeName)?.price || product.sale_price)
            : product.sale_price;

        const modTotal = selectedMods.reduce((sum, m) => sum + (m.price || 0), 0);
        const lineTotal = (parseFloat(unitPrice) + modTotal) * qty;

        this.cart.push({
            _cartId: ++this.cartIdSeq,
            product_id: product.id,
            product_name: product.short_name || product.name,
            quantity: qty,
            unit_price: parseFloat(unitPrice),
            size_name: sizeName,
            modifiers: selectedMods,
            notes: notes,
            line_total: lineTotal,
            station_id: product.station_id,
        });

        this._renderCart();
        this._toast(`${product.short_name || product.name} agregado`, 'success');
    },

    _removeFromCart(cartId) {
        this.cart = this.cart.filter(i => i._cartId !== cartId);
        this._renderCart();
    },

    _changeCartQty(cartId, delta) {
        const item = this.cart.find(i => i._cartId === cartId);
        if (!item) return;
        item.quantity += delta;
        if (item.quantity <= 0) {
            this._removeFromCart(cartId);
            return;
        }
        const modTotal = item.modifiers.reduce((sum, m) => sum + (m.price || 0), 0);
        item.line_total = (item.unit_price + modTotal) * item.quantity;
        this._renderCart();
    },

    _renderCart() {
        const container = document.getElementById('cart-items');
        const emptyEl = document.getElementById('cart-empty');
        const countEl = document.getElementById('cart-count');
        const totalEl = document.getElementById('cart-total');
        const sendBtn = document.getElementById('btn-send-kitchen');

        // Existing order items (ya enviados)
        let existingHtml = '';
        if (this.currentOrder && this.currentOrder.items) {
            this.currentOrder.items.forEach(item => {
                existingHtml += `
                    <div class="cart-item" style="opacity:0.5">
                        <span class="cart-item-qty">${parseFloat(item.quantity)}</span>
                        <div class="cart-item-details">
                            <div class="cart-item-name">${this._esc(item.product_name)}</div>
                            <div class="cart-item-mods" style="color:var(--accent-green)">✓ ${item.status}</div>
                        </div>
                        <span class="cart-item-price">S/ ${parseFloat(item.line_total).toFixed(2)}</span>
                    </div>
                `;
            });
        }

        // New cart items
        let newHtml = '';
        this.cart.forEach(item => {
            let modsText = '';
            if (item.modifiers && item.modifiers.length > 0) {
                modsText = item.modifiers.map(m => m.name).join(', ');
            }
            let sizeText = item.size_name ? `[${item.size_name}] ` : '';

            newHtml += `
                <div class="cart-item" data-cart-id="${item._cartId}">
                    <div class="cart-item-qty-controls">
                        <button class="cart-qty-btn" onclick="POS._changeCartQty(${item._cartId}, -1)">−</button>
                        <span class="cart-item-qty">${item.quantity}</span>
                        <button class="cart-qty-btn" onclick="POS._changeCartQty(${item._cartId}, 1)">+</button>
                    </div>
                    <div class="cart-item-details">
                        <div class="cart-item-name">${sizeText}${this._esc(item.product_name)}</div>
                        ${modsText ? `<div class="cart-item-mods">${this._esc(modsText)}</div>` : ''}
                        ${item.notes ? `<div class="cart-item-notes">📝 ${this._esc(item.notes)}</div>` : ''}
                    </div>
                    <span class="cart-item-price">S/ ${item.line_total.toFixed(2)}</span>
                    <button class="cart-item-remove" onclick="POS._removeFromCart(${item._cartId})">✕</button>
                </div>
            `;
        });

        if (this.cart.length === 0 && !existingHtml) {
            container.innerHTML = '<div class="cart-empty"><span>Agrega platos del menú</span></div>';
        } else {
            container.innerHTML = existingHtml + newHtml;
        }

        // Totals
        const newTotal = this.cart.reduce((sum, i) => sum + i.line_total, 0);
        const existingTotal = this.currentOrder
            ? this.currentOrder.items.reduce((sum, i) => sum + parseFloat(i.line_total), 0) : 0;

        countEl.textContent = this.cart.length;
        totalEl.textContent = `S/ ${(newTotal + existingTotal).toFixed(2)}`;
        sendBtn.disabled = this.cart.length === 0;
    },

    // ========================================
    // SEND TO KITCHEN
    // ========================================

    async _sendToKitchen() {
        if (this.cart.length === 0) return;

        const sendBtn = document.getElementById('btn-send-kitchen');
        sendBtn.disabled = true;
        sendBtn.textContent = '⏳ Enviando...';

        try {
            let orderId;

            if (this.currentOrder) {
                // Agregar items a pedido existente
                const resp = await this._fetch(`/orders/${this.currentOrder.id}/items`, {
                    method: 'POST',
                    body: JSON.stringify({
                        items: this.cart.map(i => ({
                            product_id: i.product_id,
                            quantity: i.quantity,
                            size_name: i.size_name,
                            modifiers: i.modifiers,
                            notes: i.notes,
                            course: 1,
                            is_urgent: false,
                        })),
                    }),
                });

                if (!resp.ok) throw new Error('Error agregando items');
                const order = await resp.json();
                orderId = order.id;
            } else {
                // Crear pedido nuevo
                const resp = await this._fetch('/orders', {
                    method: 'POST',
                    body: JSON.stringify({
                        order_type: this._orderType,
                        order_source: 'pos',
                        table_id: this.currentTable?.id || null,
                        guest_count: 1,
                        priority: 'normal',
                        items: this.cart.map(i => ({
                            product_id: i.product_id,
                            quantity: i.quantity,
                            size_name: i.size_name,
                            modifiers: i.modifiers,
                            notes: i.notes,
                            course: 1,
                            is_urgent: false,
                        })),
                    }),
                });

                if (!resp.ok) throw new Error('Error creando pedido');
                const order = await resp.json();
                orderId = order.id;
            }

            // Enviar a cocina
            const sendResp = await this._fetch(`/orders/${orderId}/send-to-kitchen`, {
                method: 'PUT',
            });

            if (!sendResp.ok) throw new Error('Error enviando a cocina');

            this._toast('🔥 Pedido enviado a cocina', 'success');
            this.cart = [];
            this._renderCart();

            // Volver a mesas después de 1.5s
            setTimeout(() => this._goToTables(), 1500);

        } catch (e) {
            console.error('[POS] Error:', e);
            this._toast('Error al enviar pedido', 'error');
        } finally {
            sendBtn.textContent = '🔥 ENVIAR A COCINA';
            sendBtn.disabled = this.cart.length === 0;
        }
    },

    // ========================================
    // MODIFIER MODAL
    // ========================================

    _openModifierModal(product) {
        this.modalProduct = product;
        this.modalQty = 1;
        this.modalSize = null;
        this.modalModifiers = {};
        this.modalNotes = '';

        document.getElementById('modal-product-name').textContent = product.short_name || product.name;
        document.getElementById('modal-qty-value').textContent = '1';
        document.getElementById('modal-notes').value = '';

        const body = document.getElementById('modal-body');
        body.innerHTML = '';

        // Sizes
        if (product.sizes && product.sizes.length > 0) {
            const sizeHtml = `
                <div class="mod-group">
                    <div class="mod-group-label">Tamaño</div>
                    <div class="size-options">
                        ${product.sizes.map((s, i) => `
                            <button class="size-option${i === 0 ? ' selected' : ''}" data-size-index="${i}">
                                ${this._esc(s.name)}
                                <span class="size-price">S/ ${parseFloat(s.price).toFixed(2)}</span>
                            </button>
                        `).join('')}
                    </div>
                </div>
            `;
            body.innerHTML += sizeHtml;
            this.modalSize = product.sizes[0].name;

            // Listeners
            body.querySelectorAll('.size-option').forEach(btn => {
                btn.addEventListener('click', () => {
                    body.querySelectorAll('.size-option').forEach(b => b.classList.remove('selected'));
                    btn.classList.add('selected');
                    const idx = parseInt(btn.dataset.sizeIndex);
                    this.modalSize = product.sizes[idx].name;
                    this._updateModalPrice();
                });
            });
        }

        // Modifiers
        if (product.modifiers && product.modifiers.length > 0) {
            product.modifiers.forEach((group, gi) => {
                this.modalModifiers[gi] = [];
                const reqTag = group.required ? '<span class="required-tag">REQUERIDO</span>' : '';
                const maxSel = group.max || 99;

                let optionsHtml = group.options.map((opt, oi) => {
                    const priceTag = opt.price > 0 ? `<span class="mod-price">+S/${parseFloat(opt.price).toFixed(2)}</span>` : '';
                    return `<button class="mod-option" data-group="${gi}" data-option="${oi}">
                        ${this._esc(opt.name)}${priceTag}
                    </button>`;
                }).join('');

                body.innerHTML += `
                    <div class="mod-group">
                        <div class="mod-group-label">${this._esc(group.group)} ${reqTag}</div>
                        <div class="mod-options" data-group="${gi}" data-max="${maxSel}">${optionsHtml}</div>
                    </div>
                `;
            });

            // Listeners
            body.querySelectorAll('.mod-option').forEach(btn => {
                btn.addEventListener('click', () => {
                    const gi = parseInt(btn.dataset.group);
                    const oi = parseInt(btn.dataset.option);
                    const group = product.modifiers[gi];
                    const maxSel = group.max || 99;

                    if (btn.classList.contains('selected')) {
                        btn.classList.remove('selected');
                        this.modalModifiers[gi] = this.modalModifiers[gi].filter(x => x !== oi);
                    } else {
                        if (maxSel === 1) {
                            // Single select: deselect others
                            body.querySelectorAll(`.mod-option[data-group="${gi}"]`).forEach(b => b.classList.remove('selected'));
                            this.modalModifiers[gi] = [oi];
                        } else if (this.modalModifiers[gi].length < maxSel) {
                            this.modalModifiers[gi].push(oi);
                        } else {
                            return; // Max reached
                        }
                        btn.classList.add('selected');
                    }
                    this._updateModalPrice();
                });
            });
        }

        this._updateModalPrice();
        document.getElementById('modal-modifiers').classList.remove('hidden');
    },

    _updateModalPrice() {
        const p = this.modalProduct;
        let unitPrice = p.sale_price;

        if (this.modalSize && p.sizes) {
            const size = p.sizes.find(s => s.name === this.modalSize);
            if (size) unitPrice = size.price;
        }

        let modTotal = 0;
        if (p.modifiers) {
            Object.entries(this.modalModifiers).forEach(([gi, options]) => {
                options.forEach(oi => {
                    const opt = p.modifiers[parseInt(gi)].options[oi];
                    modTotal += opt.price || 0;
                });
            });
        }

        const total = (parseFloat(unitPrice) + modTotal) * this.modalQty;
        document.getElementById('modal-price').textContent = `S/ ${total.toFixed(2)}`;
    },

    _setupModalListeners() {
        document.getElementById('modal-close')?.addEventListener('click', () => {
            document.getElementById('modal-modifiers').classList.add('hidden');
        });
        document.querySelector('.modal-backdrop')?.addEventListener('click', () => {
            document.getElementById('modal-modifiers').classList.add('hidden');
        });

        document.getElementById('modal-qty-minus')?.addEventListener('click', () => {
            if (this.modalQty > 1) {
                this.modalQty--;
                document.getElementById('modal-qty-value').textContent = this.modalQty;
                this._updateModalPrice();
            }
        });
        document.getElementById('modal-qty-plus')?.addEventListener('click', () => {
            this.modalQty++;
            document.getElementById('modal-qty-value').textContent = this.modalQty;
            this._updateModalPrice();
        });

        document.getElementById('modal-add')?.addEventListener('click', () => {
            const p = this.modalProduct;
            const notes = document.getElementById('modal-notes').value.trim();

            // Collect selected modifiers as array of {name, price}
            const selectedMods = [];
            if (p.modifiers) {
                Object.entries(this.modalModifiers).forEach(([gi, options]) => {
                    options.forEach(oi => {
                        const opt = p.modifiers[parseInt(gi)].options[oi];
                        selectedMods.push({ name: opt.name, price: opt.price || 0 });
                    });
                });
            }

            // Validate required modifiers
            if (p.modifiers) {
                for (let gi = 0; gi < p.modifiers.length; gi++) {
                    const group = p.modifiers[gi];
                    if (group.required && (!this.modalModifiers[gi] || this.modalModifiers[gi].length === 0)) {
                        this._toast(`Selecciona: ${group.group}`, 'error');
                        return;
                    }
                }
            }

            this._addToCart(p, this.modalQty, this.modalSize, selectedMods, notes);
            document.getElementById('modal-modifiers').classList.add('hidden');
        });
    },

    // ========================================
    // UTILITIES
    // ========================================

    async _fetch(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(this.token ? { 'Authorization': `Bearer ${this.token}` } : {}),
            ...(options.headers || {}),
        };
        return fetch(`${this.config.api_base}${path}`, { ...options, headers });
    },

    _toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 2500);
    },

    _esc(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};

// --- Init ---
document.addEventListener('DOMContentLoaded', () => POS.init());