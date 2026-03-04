/**
 * caja.js — Lógica completa de Caja POS.
 * Apertura/cierre, venta rápida de menú, venta a la carta,
 * cobro, comprobante, resumen diario con márgenes.
 */

var CAJA = {
    config: window.CAJA_CONFIG || {},
    user: null,
    token: null,
    categories: [],
    products: [],
    cart: [],         // [{product_id, product_name, quantity, unit_price, cost_price, size_name, line_total}]
    cajaOpen: false,
    selectedCat: "all",

    // Quick menu presets (configurable per restaurant later)
    quickMenus: [
        {label: "Menú", price: 8, cost: 3.2},
        {label: "Menú Ejecutivo", price: 12, cost: 5},
        {label: "Menú Especial", price: 15, cost: 6},
    ],

    // ================================================
    // INIT
    // ================================================
    init: function() {
        this.config = window.CAJA_CONFIG || {};
        this.bindEvents();
        this.startClock();
        document.getElementById("h-rest").textContent = this.config.restaurant_name || "";
        this.checkAuth();
    },

    checkAuth: function() {
        var token = localStorage.getItem("caja_token");
        if (!token) {
            document.getElementById("pin-overlay").style.display = "flex";
            document.getElementById("main").style.display = "none";
            return;
        }
        try {
            var payload = JSON.parse(atob(token.split(".")[1]));
            if (parseInt(payload.restaurant_id) !== this.config.restaurant_id ||
                (payload.exp && payload.exp * 1000 < Date.now())) {
                localStorage.removeItem("caja_token");
                document.getElementById("pin-overlay").style.display = "flex";
                return;
            }
            this.token = token;
            this.user = JSON.parse(localStorage.getItem("caja_user") || "{}");
            this.onLoggedIn();
        } catch(e) {
            localStorage.removeItem("caja_token");
            document.getElementById("pin-overlay").style.display = "flex";
        }
    },

    doLogin: function() {
        var self = this;
        var pin = document.getElementById("pin-input").value;
        var rid = this.config.restaurant_id;
        var errEl = document.getElementById("pin-error");
        var btn = document.getElementById("pin-btn");
        if (!pin || pin.length < 4) { errEl.textContent = "PIN de 4-6 dígitos"; return; }
        btn.textContent = "Entrando..."; btn.disabled = true;
        this.api("POST", "/api/v1/auth/login/pin", {pin: pin, restaurant_id: rid}, true)
        .then(function(data) {
            self.token = data.access_token;
            self.user = data.user;
            localStorage.setItem("caja_token", data.access_token);
            localStorage.setItem("caja_user", JSON.stringify(data.user));
            document.getElementById("pin-overlay").style.display = "none";
            self.onLoggedIn();
        })
        .catch(function(e) {
            errEl.textContent = e.message || "PIN incorrecto";
            btn.textContent = "Entrar"; btn.disabled = false;
        });
    },

    onLoggedIn: function() {
        document.getElementById("pin-overlay").style.display = "none";
        document.getElementById("main").style.display = "block";
        // Check caja status
        var self = this;
        this.api("GET", "/api/v1/caja/estado")
        .then(function(data) {
            if (data.is_open) {
                self.cajaOpen = true;
                self.updateHeader(data);
                self.loadMenu();
            } else {
                document.getElementById("open-overlay").style.display = "flex";
            }
        });
    },

    openCaja: function() {
        var self = this;
        var monto = document.getElementById("open-amount").value || "0";
        this.api("POST", "/api/v1/caja/abrir", {monto_apertura: parseFloat(monto)})
        .then(function(data) {
            self.cajaOpen = true;
            document.getElementById("open-overlay").style.display = "none";
            self.updateHeader(data);
            self.loadMenu();
            self.toast("Caja abierta");
        });
    },

    loadMenu: function() {
        var self = this;
        this.api("GET", "/api/v1/caja/menu")
        .then(function(data) {
            self.categories = data.categories || [];
            self.products = data.products || [];
            self.renderCategories();
            self.renderProducts();
            self.renderQuickMenus();
            self.loadPendientes();
            // Auto-refresh pending every 10s
            setInterval(function() { self.loadPendientes(); }, 10000);
        });
    },

    // ================================================
    // PENDING ORDERS (from kitchen)
    // ================================================
    loadPendientes: function() {
        var self = this;
        this.api("GET", "/api/v1/caja/pendientes")
        .then(function(data) {
            self.renderPendientes(data.orders || []);
        })
        .catch(function() {});
    },

    renderPendientes: function(orders) {
        var section = document.getElementById("pending-section");
        var container = document.getElementById("pending-orders");
        if (!orders || orders.length === 0) {
            section.style.display = "none";
            return;
        }
        section.style.display = "block";
        var html = "";
        var self = this;
        orders.forEach(function(o) {
            var statusClass = o.status === "ready" ? "ready" : (o.status === "preparing" ? "preparing" : "sent");
            var statusLabel = o.status === "ready" ? "Listo" : (o.status === "preparing" ? "Preparando" : "Enviado");
            var loc = o.table_number ? "Mesa " + o.table_number : (o.order_type === "takeaway" ? "P/Llevar" : "Pedido");
            if (o.zone_name) loc += " - " + o.zone_name;
            var itemsText = o.items.map(function(i) { return i.qty + "x " + i.name; }).join(", ");
            if (itemsText.length > 40) itemsText = itemsText.substring(0, 40) + "...";

            html += '<div class="pend-card" onclick="CAJA.cobrarPendiente(' + o.order_id + ')" data-oid="' + o.order_id + '">' +
                '<div class="pk-head">' +
                    '<span class="pk-num">#' + String(o.order_number).padStart(3, "0") + '</span>' +
                    '<span class="pk-status ' + statusClass + '">' + statusLabel + '</span>' +
                '</div>' +
                '<div class="pk-loc">' + loc + (o.customer_name ? " — " + o.customer_name : "") + '</div>' +
                '<div class="pk-items">' + itemsText + '</div>' +
                '<div class="pk-total">S/ ' + o.total.toFixed(2) + '</div>' +
            '</div>';
        });
        container.innerHTML = html;
    },

    cobrarPendiente: function(orderId) {
        var self = this;
        // Load order into pay modal directly
        this.api("GET", "/api/v1/caja/pendientes").then(function(data) {
            var order = (data.orders || []).find(function(o) { return o.order_id === orderId; });
            if (!order) { self.toast("Pedido no encontrado"); return; }
            self._pendingOrderId = orderId;
            document.getElementById("pay-total").textContent = "S/ " + order.total.toFixed(2);
            document.getElementById("pay-amount").value = order.total.toFixed(2);
            document.getElementById("pay-change").textContent = "";
            document.getElementById("pay-overlay").style.display = "flex";
            document.getElementById("factura-fields").style.display = "none";
            document.querySelectorAll(".pay-m").forEach(function(b) { b.classList.remove("active"); });
            document.querySelector('.pay-m[data-method="efectivo"]').classList.add("active");
            document.querySelectorAll(".comp-b").forEach(function(b) { b.classList.remove("active"); });
            document.querySelector('.comp-b[data-comp="boleta"]').classList.add("active");
            document.getElementById("cash-input-wrap").style.display = "block";
        });
    },

    // ================================================
    // RENDER
    // ================================================
    renderQuickMenus: function() {
        var container = document.getElementById("quick-btns");
        container.innerHTML = "";
        var self = this;
        this.quickMenus.forEach(function(m) {
            var btn = document.createElement("button");
            btn.className = "quick-btn";
            btn.innerHTML = m.label + ' <span class="qb-price">S/' + m.price.toFixed(0) + "</span>";
            btn.onclick = function() { self.addQuickMenu(m); };
            container.appendChild(btn);
        });
    },

    renderCategories: function() {
        var container = document.getElementById("cat-tabs");
        container.innerHTML = '<button class="cat-tab active" data-cat="all">Todos</button>';
        var self = this;
        this.categories.forEach(function(c) {
            var btn = document.createElement("button");
            btn.className = "cat-tab";
            btn.dataset.cat = c.id;
            btn.textContent = (c.icon || "") + " " + c.name;
            btn.onclick = function() { self.selectCategory(c.id); };
            container.appendChild(btn);
        });
        container.querySelector('[data-cat="all"]').onclick = function() { self.selectCategory("all"); };
    },

    renderProducts: function() {
        var container = document.getElementById("prod-grid");
        container.innerHTML = "";
        var self = this;
        var filtered = this.selectedCat === "all"
            ? this.products
            : this.products.filter(function(p) { return p.category_id == self.selectedCat; });

        filtered.forEach(function(p) {
            var card = document.createElement("div");
            card.className = "prod-card" + (p.is_available ? "" : " unavailable");
            var costHtml = p.cost_price ? '<div class="pc-cost">Costo: S/' + p.cost_price.toFixed(2) + '</div>' : '';
            card.innerHTML = '<div class="pc-name">' + (p.short_name || p.name) + '</div>' +
                '<div class="pc-price">S/' + p.sale_price.toFixed(2) + '</div>' + costHtml;
            card.onclick = function() { self.addProduct(p); };
            container.appendChild(card);
        });
    },

    selectCategory: function(catId) {
        this.selectedCat = catId;
        document.querySelectorAll(".cat-tab").forEach(function(b) {
            b.classList.toggle("active", b.dataset.cat === String(catId));
        });
        this.renderProducts();
    },

    // ================================================
    // CART
    // ================================================
    addQuickMenu: function(menu) {
        // Find existing in cart
        var existing = this.cart.find(function(c) { return c.product_name === menu.label && !c.product_id; });
        if (existing) {
            existing.quantity++;
            existing.line_total = existing.quantity * existing.unit_price;
        } else {
            this.cart.push({
                product_id: null,
                product_name: menu.label,
                quantity: 1,
                unit_price: menu.price,
                cost_price: menu.cost,
                size_name: null,
                line_total: menu.price,
                is_menu: true,
            });
        }
        this.renderCart();
        this.toast("+ " + menu.label);
    },

    addProduct: function(p) {
        // If has sizes, use first size price
        var price = p.sale_price;
        var sizeName = null;
        if (p.sizes && p.sizes.length > 0) {
            price = p.sizes[0].price;
            sizeName = p.sizes[0].name;
        }
        var existing = this.cart.find(function(c) {
            return c.product_id === p.id && c.size_name === sizeName;
        });
        if (existing) {
            existing.quantity++;
            existing.line_total = existing.quantity * existing.unit_price;
        } else {
            this.cart.push({
                product_id: p.id,
                product_name: p.short_name || p.name,
                quantity: 1,
                unit_price: price,
                cost_price: p.cost_price || 0,
                size_name: sizeName,
                line_total: price,
            });
        }
        this.renderCart();
    },

    renderCart: function() {
        var container = document.getElementById("order-items");
        if (this.cart.length === 0) {
            container.innerHTML = '<div class="order-empty">Toca un producto para agregar</div>';
            document.getElementById("btn-cobrar").disabled = true;
            this.updateTotals();
            return;
        }
        document.getElementById("btn-cobrar").disabled = false;
        var html = "";
        var self = this;
        this.cart.forEach(function(item, idx) {
            var detail = item.size_name ? item.size_name : "";
            html += '<div class="oi">' +
                '<div class="oi-qty">' +
                    '<button onclick="CAJA.changeQty(' + idx + ',-1)">−</button>' +
                    '<span>' + item.quantity + '</span>' +
                    '<button onclick="CAJA.changeQty(' + idx + ',1)">+</button>' +
                '</div>' +
                '<div class="oi-info">' +
                    '<div class="oi-name">' + item.product_name + '</div>' +
                    (detail ? '<div class="oi-detail">' + detail + '</div>' : '') +
                '</div>' +
                '<div class="oi-total">S/' + item.line_total.toFixed(2) + '</div>' +
                '<button class="oi-del" onclick="CAJA.removeItem(' + idx + ')">✕</button>' +
            '</div>';
        });
        container.innerHTML = html;
        this.updateTotals();
    },

    changeQty: function(idx, delta) {
        var item = this.cart[idx];
        item.quantity += delta;
        if (item.quantity <= 0) {
            this.cart.splice(idx, 1);
        } else {
            item.line_total = item.quantity * item.unit_price;
        }
        this.renderCart();
    },

    removeItem: function(idx) {
        this.cart.splice(idx, 1);
        this.renderCart();
    },

    clearCart: function() {
        this.cart = [];
        this.renderCart();
    },

    updateTotals: function() {
        var total = 0, totalCost = 0;
        this.cart.forEach(function(item) {
            total += item.line_total;
            totalCost += (item.cost_price || 0) * item.quantity;
        });
        var igv = total / 1.18 * 0.18;
        var subtotal = total - igv;

        document.getElementById("t-subtotal").textContent = "S/ " + subtotal.toFixed(2);
        document.getElementById("t-igv").textContent = "S/ " + igv.toFixed(2);
        document.getElementById("t-total").textContent = "S/ " + total.toFixed(2);

        if (totalCost > 0) {
            document.getElementById("cost-row").style.display = "flex";
            document.getElementById("margin-row").style.display = "flex";
            document.getElementById("t-cost").textContent = "S/ " + totalCost.toFixed(2);
            var margin = total - totalCost;
            document.getElementById("t-margin").textContent = "S/ " + margin.toFixed(2) + " (" + (margin/total*100).toFixed(0) + "%)";
        } else {
            document.getElementById("cost-row").style.display = "none";
            document.getElementById("margin-row").style.display = "none";
        }
    },

    getTotal: function() {
        var total = 0;
        this.cart.forEach(function(item) { total += item.line_total; });
        return total;
    },

    // ================================================
    // PAYMENT
    // ================================================
    openPay: function() {
        var total = this.getTotal();
        document.getElementById("pay-total").textContent = "S/ " + total.toFixed(2);
        document.getElementById("pay-amount").value = total.toFixed(2);
        document.getElementById("pay-change").textContent = "";
        document.getElementById("pay-overlay").style.display = "flex";
        document.getElementById("factura-fields").style.display = "none";
        // Reset selections
        document.querySelectorAll(".pay-m").forEach(function(b) { b.classList.remove("active"); });
        document.querySelector('.pay-m[data-method="efectivo"]').classList.add("active");
        document.querySelectorAll(".comp-b").forEach(function(b) { b.classList.remove("active"); });
        document.querySelector('.comp-b[data-comp="boleta"]').classList.add("active");
        document.getElementById("cash-input-wrap").style.display = "block";
    },

    selectPayMethod: function(method) {
        document.querySelectorAll(".pay-m").forEach(function(b) {
            b.classList.toggle("active", b.dataset.method === method);
        });
        // Only show cash input for efectivo
        document.getElementById("cash-input-wrap").style.display = method === "efectivo" ? "block" : "none";
    },

    selectComprobante: function(comp) {
        document.querySelectorAll(".comp-b").forEach(function(b) {
            b.classList.toggle("active", b.dataset.comp === comp);
        });
        document.getElementById("factura-fields").style.display = comp === "factura" ? "block" : "none";
    },

    updateChange: function() {
        var total = this.getTotal();
        var paid = parseFloat(document.getElementById("pay-amount").value) || 0;
        var change = paid - total;
        if (change >= 0) {
            document.getElementById("pay-change").textContent = "Vuelto: S/ " + change.toFixed(2);
            document.getElementById("pay-change").style.color = "var(--green)";
        } else {
            document.getElementById("pay-change").textContent = "Falta: S/ " + Math.abs(change).toFixed(2);
            document.getElementById("pay-change").style.color = "var(--red)";
        }
    },

    confirmPay: function() {
        var self = this;
        var total = this._pendingOrderId ? parseFloat(document.getElementById("pay-total").textContent.replace("S/ ", "")) : this.getTotal();
        var method = document.querySelector(".pay-m.active").dataset.method;
        var comp = document.querySelector(".comp-b.active").dataset.comp;
        var paid = method === "efectivo" ? parseFloat(document.getElementById("pay-amount").value) || 0 : total;

        if (method === "efectivo" && paid < total) {
            this.toast("Monto insuficiente");
            return;
        }

        var btn = document.getElementById("pay-confirm");
        btn.textContent = "Procesando..."; btn.disabled = true;

        // === COBRAR PEDIDO PENDIENTE (de cocina) ===
        if (this._pendingOrderId) {
            var body = {
                payment_method: method,
                paid_amount: paid,
                comprobante: comp || null,
            };
            if (comp === "factura") {
                body.customer_doc_type = "6";
                body.customer_doc_number = document.getElementById("cust-ruc").value;
                body.customer_name = document.getElementById("cust-name").value;
            }
            this.api("POST", "/api/v1/caja/cobrar/" + this._pendingOrderId, body)
            .then(function(data) {
                document.getElementById("pay-overlay").style.display = "none";
                btn.textContent = "Confirmar pago"; btn.disabled = false;
                var changeText = data.change > 0 ? " | Vuelto: S/" + data.change.toFixed(2) : "";
                self.toast("✅ Cobrado #" + String(data.order_number).padStart(3, "0") + " — S/" + data.total.toFixed(2) + changeText);
                self._pendingOrderId = null;
                self.loadPendientes();
                self.api("GET", "/api/v1/caja/estado").then(function(est) { self.updateHeader(est); });
            })
            .catch(function(e) {
                btn.textContent = "Confirmar pago"; btn.disabled = false;
                self.toast("Error: " + (e.message || "Error de red"));
            });
            return;
        }

        // === VENTA NUEVA (directa desde caja) ===
        var body = {
            items: this.cart.map(function(c) {
                return {
                    product_id: c.product_id,
                    product_name: c.product_name,
                    quantity: c.quantity,
                    unit_price: c.unit_price,
                    cost_price: c.cost_price,
                    size_name: c.size_name,
                };
            }),
            payment_method: method,
            paid_amount: paid,
            comprobante: comp || null,
            order_type: "dine_in",
        };

        if (comp === "factura") {
            body.customer_doc_type = "6";
            body.customer_doc_number = document.getElementById("cust-ruc").value;
            body.customer_name = document.getElementById("cust-name").value;
        }

        this.api("POST", "/api/v1/caja/venta", body)
        .then(function(data) {
            document.getElementById("pay-overlay").style.display = "none";
            btn.textContent = "Confirmar pago"; btn.disabled = false;
            self.cart = [];
            self.renderCart();
            var changeText = data.change > 0 ? " | Vuelto: S/" + data.change.toFixed(2) : "";
            self.toast("✅ Venta #" + String(data.order_number).padStart(3, "0") + " — S/" + data.total.toFixed(2) + changeText);
            self.api("GET", "/api/v1/caja/estado").then(function(est) { self.updateHeader(est); });
        })
        .catch(function(e) {
            btn.textContent = "Confirmar pago"; btn.disabled = false;
            self.toast("Error: " + (e.message || "Error de red"));
        });
    },

    // ================================================
    // CLOSE CAJA
    // ================================================
    openCloseCaja: function() {
        var self = this;
        this.api("GET", "/api/v1/caja/estado").then(function(data) {
            var html = '<div class="cs-row"><span>Apertura:</span><span>S/ ' + (data.opening_amount || 0).toFixed(2) + '</span></div>' +
                '<div class="cs-row"><span>Ventas:</span><span class="cs-big">' + (data.current_sales_count || 0) + ' — S/ ' + (data.current_sales_total || 0).toFixed(2) + '</span></div>' +
                '<div class="cs-row"><span>Efectivo esperado:</span><span>S/ ' + (data.current_cash || 0).toFixed(2) + '</span></div>';
            document.getElementById("close-summary").innerHTML = html;
            document.getElementById("close-amount").value = (data.current_cash || 0).toFixed(2);
            document.getElementById("close-overlay").style.display = "flex";
        });
    },

    doCloseCaja: function() {
        var self = this;
        var monto = parseFloat(document.getElementById("close-amount").value) || 0;
        this.api("POST", "/api/v1/caja/cerrar", {monto_cierre: monto})
        .then(function(data) {
            document.getElementById("close-overlay").style.display = "none";
            self.cajaOpen = false;
            var diff = data.difference;
            var diffText = diff === 0 ? "Cuadra perfecto" : (diff > 0 ? "Sobrante: S/" + diff.toFixed(2) : "Faltante: S/" + Math.abs(diff).toFixed(2));
            self.toast("Caja cerrada — " + data.sales_count + " ventas — " + diffText);
            self.updateHeader({is_open: false, current_sales_count: 0, current_sales_total: 0});
        });
    },

    // ================================================
    // RESUMEN
    // ================================================
    openResumen: function() {
        var self = this;
        this.api("GET", "/api/v1/caja/resumen").then(function(data) {
            var html = '<div class="res-big">S/ ' + data.total_ventas.toFixed(2) + '</div>' +
                '<div style="font-size:12px;color:var(--text3)">' + data.total_count + ' ventas hoy</div>' +
                '<div class="res-grid">' +
                    '<div class="res-card"><div class="rc-label">Costo est.</div><div class="rc-val">S/ ' + data.total_cost.toFixed(2) + '</div></div>' +
                    '<div class="res-card"><div class="rc-label">Ganancia</div><div class="rc-val rc-green">S/ ' + data.margin.toFixed(2) + ' (' + data.margin_pct + '%)</div></div>' +
                '</div>';

            // By payment method
            var pmHtml = '';
            for (var pm in data.by_payment) {
                pmHtml += '<tr><td>' + pm + '</td><td>' + data.by_payment[pm].count + '</td><td>S/ ' + data.by_payment[pm].total.toFixed(2) + '</td></tr>';
            }
            if (pmHtml) {
                html += '<table class="res-table"><thead><tr><th>Método</th><th>Qty</th><th>Total</th></tr></thead><tbody>' + pmHtml + '</tbody></table>';
            }

            // Top products
            if (data.top_products && data.top_products.length > 0) {
                var tpHtml = '';
                data.top_products.forEach(function(tp) {
                    tpHtml += '<tr><td>' + tp.name + '</td><td>' + tp.qty + '</td><td>S/ ' + tp.total.toFixed(2) + '</td></tr>';
                });
                html += '<div style="margin-top:12px;font-size:13px;font-weight:700;color:var(--text2)">Top productos</div>' +
                    '<table class="res-table"><thead><tr><th>Plato</th><th>Qty</th><th>Total</th></tr></thead><tbody>' + tpHtml + '</tbody></table>';
            }

            document.getElementById("resumen-content").innerHTML = html;
            document.getElementById("resumen-overlay").style.display = "flex";
        });
    },

    closeResumen: function() {
        document.getElementById("resumen-overlay").style.display = "none";
    },

    // ================================================
    // UI HELPERS
    // ================================================
    updateHeader: function(data) {
        var badge = document.getElementById("h-status");
        if (data.is_open !== false && (data.status === "opened" || data.status === "already_open" || data.is_open)) {
            badge.textContent = "Abierta";
            badge.className = "h-badge open";
        } else {
            badge.textContent = "Cerrada";
            badge.className = "h-badge";
        }
        document.getElementById("h-count").textContent = (data.current_sales_count || data.sales_count || 0) + " ventas";
        document.getElementById("h-total").textContent = "S/ " + (data.current_sales_total || data.total_sales || 0).toFixed(2);
    },

    startClock: function() {
        var el = document.getElementById("h-clock");
        setInterval(function() {
            var now = new Date();
            el.textContent = String(now.getHours()).padStart(2,"0") + ":" + String(now.getMinutes()).padStart(2,"0");
        }, 1000);
    },

    toast: function(msg) {
        var t = document.getElementById("toast");
        t.textContent = msg;
        t.classList.add("show");
        setTimeout(function() { t.classList.remove("show"); }, 3000);
    },

    // ================================================
    // API
    // ================================================
    api: function(method, url, body, noAuth) {
        var headers = {"Content-Type": "application/json"};
        if (!noAuth && this.token) {
            headers["Authorization"] = "Bearer " + this.token;
        }
        var opts = {method: method, headers: headers};
        if (body) opts.body = JSON.stringify(body);
        return fetch(url, opts).then(function(r) {
            if (!r.ok) {
                return r.text().then(function(text) {
                    try {
                        var err = JSON.parse(text);
                        throw new Error(err.detail || "Error " + r.status);
                    } catch(e) {
                        if (e.message && e.message !== text) throw e;
                        throw new Error("Error " + r.status + ": " + text.substring(0, 100));
                    }
                });
            }
            return r.json();
        });
    },

    // ================================================
    // EVENTS
    // ================================================
    bindEvents: function() {
        var self = this;
        document.getElementById("pin-btn").onclick = function() { self.doLogin(); };
        document.getElementById("pin-input").onkeydown = function(e) { if (e.key === "Enter") self.doLogin(); };
        document.getElementById("open-btn").onclick = function() { self.openCaja(); };
        document.getElementById("open-amount").onkeydown = function(e) { if (e.key === "Enter") self.openCaja(); };
        document.getElementById("btn-cobrar").onclick = function() { self.openPay(); };
        document.getElementById("btn-clear").onclick = function() { self.clearCart(); };
        document.getElementById("btn-cerrar").onclick = function() { self.openCloseCaja(); };
        document.getElementById("btn-resumen").onclick = function() { self.openResumen(); };
        document.getElementById("pay-cancel").onclick = function() { document.getElementById("pay-overlay").style.display = "none"; self._pendingOrderId = null; };
        document.getElementById("pay-confirm").onclick = function() { self.confirmPay(); };
        document.getElementById("pay-amount").oninput = function() { self.updateChange(); };
        document.getElementById("close-cancel").onclick = function() { document.getElementById("close-overlay").style.display = "none"; };
        document.getElementById("close-btn").onclick = function() { self.doCloseCaja(); };

        // Payment method buttons
        document.querySelectorAll(".pay-m").forEach(function(btn) {
            btn.onclick = function() { self.selectPayMethod(btn.dataset.method); };
        });
        // Comprobante buttons
        document.querySelectorAll(".comp-b").forEach(function(btn) {
            btn.onclick = function() { self.selectComprobante(btn.dataset.comp); };
        });
    },
};

document.addEventListener("DOMContentLoaded", function() { CAJA.init(); });