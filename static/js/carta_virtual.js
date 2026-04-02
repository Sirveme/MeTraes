/* carta_virtual.js v1 — Carta Virtual (QR) */
var CFG = window.CARTA_CONFIG;

var MAT_ICONS = {
    "ceviches":     { icon: "set_meal",     color: "#38bdf8" },
    "tiraditos":    { icon: "set_meal",     color: "#38bdf8" },
    "chicharrones": { icon: "skillet",      color: "#fb923c" },
    "frituras":     { icon: "skillet",      color: "#fb923c" },
    "arroces":      { icon: "rice_bowl",    color: "#fbbf24" },
    "sopas":        { icon: "soup_kitchen", color: "#f87171" },
    "caldos":       { icon: "soup_kitchen", color: "#f87171" },
    "bebidas":      { icon: "local_cafe",   color: "#a78bfa" },
    "postres":      { icon: "cake",         color: "#f472b6" },
    "especiales":   { icon: "star",         color: "#fbbf24" },
};
var MAT_DEFAULT = { icon: "restaurant", color: "#94a3b8" };

function _matIcon(catName, fontSize) {
    var key = (catName || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    var m = MAT_ICONS[key] || MAT_DEFAULT;
    var sz = fontSize || 28;
    return '<span class="material-symbols-rounded" style="color:' + m.color + ';font-size:' + sz + 'px">' + m.icon + '</span>';
}

var CARTA = {
    categories: [],
    products: [],
    cart: [],
    activeCat: null,
    modalProduct: null,
    modalQtyVal: 1,
    modalSize: null,
    modalMods: [],
    modalNotes: "",
    orderMode: "dine_in",       // "dine_in", "delivery", "takeaway"
    lastOrderId: null,          // for tracking
    lastOrderType: null,
    trackingTimer: null,

    init: function() {
        document.getElementById("rest-name").textContent = CFG.restaurant_name;
        this._updateBadge();
        this._initModeTabs();
        this.loadMenu();
    },

    _updateBadge: function() {
        var badge = document.getElementById("table-badge");
        if (this.orderMode === "dine_in") {
            badge.textContent = (CFG.zone_name ? CFG.zone_name + " \u2022 " : "") + CFG.table_label;
        } else if (this.orderMode === "delivery") {
            badge.textContent = "\ud83d\udef5 Delivery";
        } else {
            badge.textContent = "\ud83d\udce6 Para recoger";
        }
    },

    _initModeTabs: function() {
        var tabs = document.getElementById("mode-tabs");
        if (!tabs) return;
        // Hide delivery/takeaway tabs if not enabled
        var deliveryTab = tabs.querySelector('[data-mode="delivery"]');
        var takeawayTab = tabs.querySelector('[data-mode="takeaway"]');
        if (deliveryTab && !CFG.delivery_enabled) deliveryTab.style.display = "none";
        if (takeawayTab && !CFG.takeaway_enabled) takeawayTab.style.display = "none";
        // If only dine_in available, hide the entire tab bar
        if (!CFG.delivery_enabled && !CFG.takeaway_enabled) {
            tabs.style.display = "none";
        }
    },

    setMode: function(mode) {
        this.orderMode = mode;
        document.querySelectorAll(".mode-tab").forEach(function(t) {
            t.classList.toggle("active", t.dataset.mode === mode);
        });
        this._updateBadge();
        this._updateCustomerForm();
    },

    _updateCustomerForm: function() {
        var form = document.getElementById("customer-form");
        var addrWrap = document.getElementById("cf-address-wrap");
        var refWrap = document.getElementById("cf-reference-wrap");
        if (this.orderMode === "dine_in") {
            form.classList.add("hide");
        } else {
            form.classList.remove("hide");
            if (this.orderMode === "delivery") {
                addrWrap.classList.remove("hide");
                refWrap.classList.remove("hide");
            } else {
                addrWrap.classList.add("hide");
                refWrap.classList.add("hide");
            }
        }
    },

    // ====== LOAD MENU ======
    loadMenu: function() {
        var self = this;
        fetch(CFG.api_base + "/menu/" + CFG.restaurant_id)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                self.categories = data.categories || [];
                self.products = data.products || [];
                self.renderCategories();
                if (self.categories.length > 0) {
                    self.selectCategory(self.categories[0].id);
                }
            })
            .catch(function(e) { console.error("[Carta]", e); });
    },

    // ====== CATEGORIES ======
    renderCategories: function() {
        var nav = document.getElementById("cat-tabs");
        nav.innerHTML = "";
        // "Todos" tab
        var allBtn = document.createElement("button");
        allBtn.className = "cat-tab";
        allBtn.textContent = "Todos";
        allBtn.dataset.cid = "all";
        allBtn.addEventListener("click", function() { CARTA.selectCategory("all"); });
        nav.appendChild(allBtn);

        this.categories.forEach(function(c) {
            var btn = document.createElement("button");
            btn.className = "cat-tab";
            btn.dataset.cid = c.id;
            btn.innerHTML = _matIcon(c.name, 16) + " " + CARTA._esc(c.name);
            btn.addEventListener("click", function() { CARTA.selectCategory(c.id); });
            nav.appendChild(btn);
        });
    },

    selectCategory: function(catId) {
        this.activeCat = catId;
        document.querySelectorAll(".cat-tab").forEach(function(t) {
            t.classList.toggle("active", t.dataset.cid === String(catId));
        });
        this.renderProducts();
    },

    // ====== PRODUCTS ======
    renderProducts: function() {
        var grid = document.getElementById("products");
        var empty = document.getElementById("empty");
        grid.innerHTML = "";

        var prods = this.products;
        if (this.activeCat !== "all") {
            var cid = parseInt(this.activeCat);
            prods = prods.filter(function(p) { return p.category_id === cid; });
        }

        if (prods.length === 0) {
            empty.classList.remove("hide");
            return;
        }
        empty.classList.add("hide");

        prods.forEach(function(p) {
            var card = document.createElement("div");
            card.className = "p-card";
            card.addEventListener("click", function() { CARTA.openModal(p); });

            // Image or placeholder
            var imgHtml = "";
            if (p.image_url) {
                imgHtml = '<img class="p-img" src="' + p.image_url + '" alt="" loading="lazy">';
            } else {
                var cat = CARTA.categories.find(function(c) { return c.id === p.category_id; });
                var catName = (cat && cat.name) ? cat.name : "";
                imgHtml = '<div class="p-img-placeholder">' + _matIcon(catName, 28) + '</div>';
            }

            // Badge
            var badge = "";
            if (p.is_new) badge = '<span class="p-badge new">Nuevo</span>';
            else if (p.is_bestseller) badge = '<span class="p-badge best">\u2b50 Popular</span>';
            else if (p.is_spicy) badge = '<span class="p-badge spicy">\ud83c\udf36\ufe0f Picante</span>';

            // Sizes hint
            var sizesHint = "";
            if (p.sizes && p.sizes.length > 1) {
                var names = p.sizes.map(function(s) { return s.name; }).join(" \u2022 ");
                sizesHint = '<div class="p-sizes">' + names + '</div>';
            }

            // Price display
            var priceDisplay = "S/ " + p.price.toFixed(2);
            if (p.sizes && p.sizes.length > 0) {
                var minPrice = Math.min.apply(null, p.sizes.map(function(s) { return s.price; }));
                priceDisplay = "S/ " + minPrice.toFixed(2);
            }

            card.innerHTML = imgHtml +
                '<div class="p-info">' +
                    '<div class="p-name">' + CARTA._esc(p.name) + '</div>' +
                    sizesHint +
                    '<div class="p-bottom">' +
                        '<span class="p-price">' + priceDisplay + '</span>' +
                        badge +
                    '</div>' +
                '</div>' +
                '<button class="p-add-btn" data-pid="' + p.id + '">+</button>';

            // Quick-add button: if no sizes/modifiers, add directly; else open modal
            var addBtn = card.querySelector(".p-add-btn");
            addBtn.addEventListener("click", function(e) {
                e.stopPropagation();
                var hasMods = p.modifiers && p.modifiers.length > 0;
                var hasSizes = p.sizes && p.sizes.length > 1;
                if (hasMods || hasSizes) {
                    CARTA.openModal(p);
                } else {
                    CARTA.quickAdd(p);
                }
            });

            grid.appendChild(card);
        });
    },

    // ====== PRODUCT MODAL ======
    openModal: function(p) {
        this.modalProduct = p;
        this.modalQtyVal = 1;
        this.modalSize = null;
        this.modalMods = [];
        this.modalNotes = "";

        var body = document.getElementById("modal-body");
        var html = "";

        html += '<div class="m-name">' + CARTA._esc(p.name) + '</div>';
        if (p.description) html += '<div class="m-desc">' + CARTA._esc(p.description) + '</div>';

        var basePrice = p.price;

        // Sizes
        if (p.sizes && p.sizes.length > 0) {
            html += '<div class="m-section"><div class="m-section-title">Tamaño <span class="m-section-req">(requerido)</span></div><div class="m-sizes">';
            p.sizes.forEach(function(s, i) {
                var sel = i === 0 ? " selected" : "";
                if (i === 0) { CARTA.modalSize = s; basePrice = s.price; }
                html += '<button class="m-size' + sel + '" data-idx="' + i + '" onclick="CARTA.selectSize(' + i + ')">' +
                    CARTA._esc(s.name) +
                    '<span class="m-size-price">S/ ' + s.price.toFixed(2) + '</span>' +
                '</button>';
            });
            html += '</div></div>';
        }

        // Modifiers
        if (p.modifiers && p.modifiers.length > 0) {
            p.modifiers.forEach(function(grp, gi) {
                var req = grp.required ? ' <span class="m-section-req">(requerido)</span>' : '';
                html += '<div class="m-section"><div class="m-section-title">' + CARTA._esc(grp.group) + req + '</div><div class="m-opts">';
                grp.options.forEach(function(opt, oi) {
                    var priceStr = opt.price > 0 ? "+S/ " + opt.price.toFixed(2) : "";
                    html += '<div class="m-opt" data-gi="' + gi + '" data-oi="' + oi + '" onclick="CARTA.toggleMod(' + gi + ',' + oi + ')">' +
                        '<div class="m-opt-check">\u2713</div>' +
                        '<span class="m-opt-name">' + CARTA._esc(opt.name) + '</span>' +
                        '<span class="m-opt-price">' + priceStr + '</span>' +
                    '</div>';
                });
                html += '</div></div>';
            });
        }

        // Notes
        html += '<div class="m-section"><div class="m-section-title">Notas</div>' +
            '<textarea class="m-notes" id="modal-notes" placeholder="Sin cebolla, extra picante..." maxlength="200" oninput="CARTA.modalNotes=this.value"></textarea></div>';

        body.innerHTML = html;
        document.getElementById("modal-qty").textContent = "1";
        this._updateModalPrice();

        // Show
        document.getElementById("modal-overlay").classList.remove("hide");
        var modal = document.getElementById("modal");
        modal.classList.remove("hide");
        setTimeout(function() { modal.classList.add("open"); }, 10);
        document.body.style.overflow = "hidden";
    },

    closeModal: function() {
        var modal = document.getElementById("modal");
        modal.classList.remove("open");
        setTimeout(function() {
            modal.classList.add("hide");
            document.getElementById("modal-overlay").classList.add("hide");
            document.body.style.overflow = "";
        }, 300);
    },

    selectSize: function(idx) {
        this.modalSize = this.modalProduct.sizes[idx];
        document.querySelectorAll(".m-size").forEach(function(el) {
            el.classList.toggle("selected", parseInt(el.dataset.idx) === idx);
        });
        this._updateModalPrice();
    },

    toggleMod: function(gi, oi) {
        var grp = this.modalProduct.modifiers[gi];
        var opt = grp.options[oi];
        var key = gi + "-" + oi;

        var el = document.querySelector('.m-opt[data-gi="' + gi + '"][data-oi="' + oi + '"]');
        var isSelected = el.classList.contains("selected");

        if (grp.max === 1) {
            // Radio: deselect all in group, select this
            document.querySelectorAll('.m-opt[data-gi="' + gi + '"]').forEach(function(o) {
                o.classList.remove("selected");
            });
            // Remove all from this group
            this.modalMods = this.modalMods.filter(function(m) { return m.gi !== gi; });
            if (!isSelected) {
                el.classList.add("selected");
                this.modalMods.push({ gi: gi, oi: oi, name: opt.name, price: opt.price || 0 });
            }
        } else {
            // Checkbox: toggle
            if (isSelected) {
                el.classList.remove("selected");
                this.modalMods = this.modalMods.filter(function(m) { return !(m.gi === gi && m.oi === oi); });
            } else {
                // Check max
                var countInGroup = this.modalMods.filter(function(m) { return m.gi === gi; }).length;
                if (grp.max && countInGroup >= grp.max) return;
                el.classList.add("selected");
                this.modalMods.push({ gi: gi, oi: oi, name: opt.name, price: opt.price || 0 });
            }
        }
        this._updateModalPrice();
    },

    modalQty: function(delta) {
        this.modalQtyVal = Math.max(1, Math.min(20, this.modalQtyVal + delta));
        document.getElementById("modal-qty").textContent = this.modalQtyVal;
        this._updateModalPrice();
    },

    _updateModalPrice: function() {
        var p = this.modalProduct;
        var base = this.modalSize ? this.modalSize.price : p.price;
        var modTotal = 0;
        this.modalMods.forEach(function(m) { modTotal += m.price; });
        var total = (base + modTotal) * this.modalQtyVal;
        document.getElementById("modal-price-total").textContent = "S/ " + total.toFixed(2);
    },

    // ====== CART ======
    addToCart: function() {
        var p = this.modalProduct;
        // Check required modifiers
        if (p.modifiers) {
            for (var gi = 0; gi < p.modifiers.length; gi++) {
                if (p.modifiers[gi].required) {
                    var has = this.modalMods.some(function(m) { return m.gi === gi; });
                    if (!has) {
                        alert("Selecciona " + p.modifiers[gi].group);
                        return;
                    }
                }
            }
        }
        // Check required sizes
        if (p.sizes && p.sizes.length > 0 && !this.modalSize) {
            alert("Selecciona un tamaño");
            return;
        }

        var base = this.modalSize ? this.modalSize.price : p.price;
        var modTotal = 0;
        this.modalMods.forEach(function(m) { modTotal += m.price; });

        var item = {
            id: Date.now(),
            product_id: p.id,
            name: p.name,
            size_name: this.modalSize ? this.modalSize.name : null,
            modifiers: this.modalMods.map(function(m) { return { name: m.name, price: m.price }; }),
            notes: this.modalNotes || null,
            quantity: this.modalQtyVal,
            unit_price: base + modTotal,
            line_total: (base + modTotal) * this.modalQtyVal,
        };

        this.cart.push(item);
        this._updateCartBtn();
        this.closeModal();
    },

    quickAdd: function(p) {
        var price = (p.sizes && p.sizes.length === 1) ? p.sizes[0].price : p.price;
        var item = {
            id: Date.now(),
            product_id: p.id,
            name: p.name,
            size_name: (p.sizes && p.sizes.length === 1) ? p.sizes[0].name : null,
            modifiers: [],
            notes: null,
            quantity: 1,
            unit_price: price,
            line_total: price,
        };
        this.cart.push(item);
        this._updateCartBtn();
    },

    removeFromCart: function(itemId) {
        this.cart = this.cart.filter(function(i) { return i.id !== itemId; });
        this._updateCartBtn();
        this.renderCart();
        if (this.cart.length === 0) this.toggleCart();
    },

    updateCartQty: function(itemId, delta) {
        var item = this.cart.find(function(i) { return i.id === itemId; });
        if (!item) return;
        item.quantity = Math.max(1, item.quantity + delta);
        item.line_total = item.unit_price * item.quantity;
        this._updateCartBtn();
        this.renderCart();
    },

    _updateCartBtn: function() {
        var btn = document.getElementById("cart-btn");
        var countEl = document.getElementById("cart-count");
        var totalEl = document.getElementById("cart-total");

        if (this.cart.length === 0) {
            btn.classList.add("hide");
            return;
        }
        btn.classList.remove("hide");
        var count = 0;
        var total = 0;
        this.cart.forEach(function(i) { count += i.quantity; total += i.line_total; });
        countEl.textContent = count;
        totalEl.textContent = "S/ " + total.toFixed(2);
    },

    toggleCart: function() {
        var drawer = document.getElementById("cart-drawer");
        var overlay = document.getElementById("cart-overlay");
        var isOpen = drawer.classList.contains("open");
        if (isOpen) {
            drawer.classList.remove("open");
            overlay.classList.add("hide");
            document.body.style.overflow = "";
        } else {
            this.renderCart();
            this._updateCustomerForm();
            overlay.classList.remove("hide");
            drawer.classList.add("open");
            document.body.style.overflow = "hidden";
        }
    },

    renderCart: function() {
        var container = document.getElementById("cart-items");
        container.innerHTML = "";
        var total = 0;

        this.cart.forEach(function(item) {
            total += item.line_total;
            var detail = [];
            if (item.size_name) detail.push(item.size_name);
            if (item.modifiers.length > 0) detail.push(item.modifiers.map(function(m){return m.name;}).join(", "));
            if (item.notes) detail.push(item.notes);

            var div = document.createElement("div");
            div.className = "ci";
            div.innerHTML =
                '<div class="ci-info">' +
                    '<div class="ci-name">' + CARTA._esc(item.name) + '</div>' +
                    (detail.length ? '<div class="ci-detail">' + CARTA._esc(detail.join(" \u2022 ")) + '</div>' : '') +
                    '<div class="ci-price">S/ ' + item.line_total.toFixed(2) + '</div>' +
                '</div>' +
                '<div class="ci-qty">' +
                    '<button class="ci-qty-btn" onclick="CARTA.updateCartQty(' + item.id + ',-1)">\u2212</button>' +
                    '<span class="ci-qty-val">' + item.quantity + '</span>' +
                    '<button class="ci-qty-btn" onclick="CARTA.updateCartQty(' + item.id + ',1)">+</button>' +
                '</div>' +
                '<button class="ci-del" onclick="CARTA.removeFromCart(' + item.id + ')">\ud83d\uddd1</button>';
            container.appendChild(div);
        });

        document.getElementById("cart-subtotal").textContent = "S/ " + total.toFixed(2);
        document.getElementById("cart-total-final").textContent = "S/ " + total.toFixed(2);
    },

    // ====== SEND ORDER ======
    sendOrder: function() {
        if (this.cart.length === 0) return;

        // Validate customer form for delivery/takeaway
        if (this.orderMode !== "dine_in") {
            if (!this._validateCustomerForm()) return;
        }

        var btn = document.getElementById("btn-send");
        btn.disabled = true;
        btn.textContent = "Enviando...";

        var notes = document.getElementById("cart-notes").value || null;

        var items = this.cart.map(function(i) {
            return {
                product_id: i.product_id,
                quantity: i.quantity,
                size_name: i.size_name,
                modifiers: i.modifiers,
                notes: i.notes,
            };
        });

        var body = {
            table_id: this.orderMode === "dine_in" ? CFG.table_id : null,
            order_type: this.orderMode,
            customer_notes: notes,
            items: items,
        };

        // Add customer info for delivery/takeaway
        if (this.orderMode !== "dine_in") {
            body.customer_name = document.getElementById("cf-name").value.trim();
            body.customer_phone = document.getElementById("cf-phone").value.trim();
            if (this.orderMode === "delivery") {
                body.customer_address = document.getElementById("cf-address").value.trim();
                var ref = document.getElementById("cf-reference").value.trim();
                if (ref) body.customer_notes = (notes ? notes + " | " : "") + "Ref: " + ref;
            }
        }

        var self = this;
        fetch(CFG.api_base + "/order", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        })
        .then(function(r) {
            if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || "Error"); });
            return r.json();
        })
        .then(function(data) {
            self.cart = [];
            self._updateCartBtn();
            self.toggleCart();
            self.lastOrderId = data.order_id;
            self.lastOrderType = self.orderMode;

            if (self.orderMode === "dine_in") {
                // Show success + waiter button
                self._showDineInSuccess(data);
            } else {
                // Show tracking overlay
                self._showTracking(data);
            }
        })
        .catch(function(e) {
            alert("Error: " + e.message);
        })
        .finally(function() {
            btn.disabled = false;
            btn.textContent = "Enviar pedido";
        });
    },

    _validateCustomerForm: function() {
        var valid = true;
        var name = document.getElementById("cf-name");
        var phone = document.getElementById("cf-phone");
        var addr = document.getElementById("cf-address");

        // Reset
        name.classList.remove("error");
        phone.classList.remove("error");
        addr.classList.remove("error");

        if (!name.value.trim()) { name.classList.add("error"); valid = false; }
        if (!phone.value.trim()) { phone.classList.add("error"); valid = false; }
        if (this.orderMode === "delivery" && !addr.value.trim()) {
            addr.classList.add("error"); valid = false;
        }
        if (!valid) {
            alert("Completa los campos obligatorios");
        }
        return valid;
    },

    _showDineInSuccess: function(data) {
        var suc = document.getElementById("success");
        document.getElementById("success-detail").textContent =
            "Pedido #" + String(data.order_number).padStart(3, "0") +
            "\nTotal: S/ " + data.total.toFixed(2) +
            "\n\nEl mesero atendera tu mesa en breve.";
        document.getElementById("success-close").classList.add("hide");
        suc.classList.remove("hide");
        setTimeout(function() { suc.classList.add("hide"); }, 5000);

        // Show waiter request button
        var waiterBtn = document.getElementById("btn-waiter");
        waiterBtn.classList.remove("hide");
        // Hide cart button if visible
        document.getElementById("cart-btn").classList.add("hide");
    },

    // ====== ORDER TRACKING (delivery/takeaway) ======
    _showTracking: function(data) {
        this.lastOrderId = data.order_id;
        document.getElementById("tracking-number").textContent =
            "Pedido #" + String(data.order_number).padStart(3, "0") +
            " \u2022 S/ " + data.total.toFixed(2);

        this._renderTrackingSteps(data.status || "sent");

        if (this.lastOrderType === "takeaway") {
            document.getElementById("tracking-detail").textContent =
                "Te avisaremos cuando este listo para recoger.";
        } else {
            document.getElementById("tracking-detail").textContent =
                "Puedes seguir el estado de tu pedido aqui.";
        }

        document.getElementById("tracking").classList.remove("hide");

        // Start polling
        var self = this;
        this.trackingTimer = setInterval(function() {
            self._pollOrderStatus();
        }, 10000);
    },

    _pollOrderStatus: function() {
        if (!this.lastOrderId) return;
        var self = this;
        fetch(CFG.api_base + "/order/" + this.lastOrderId + "/status")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            self._renderTrackingSteps(data.status);
            var detail = document.getElementById("tracking-detail");

            if (data.status === "ready" || data.status === "served") {
                if (self.lastOrderType === "takeaway") {
                    detail.textContent = "Tu pedido esta listo! Acercate a recogerlo.";
                } else if (self.lastOrderType === "delivery") {
                    detail.textContent = "Tu pedido esta listo. Buscando motorizado...";
                }
            }

            // Poll driver location when dispatched
            if (data.status === "dispatched" && self.lastOrderType === "delivery") {
                self._pollDriverLocation();
            }

            if (data.status === "delivered") {
                detail.textContent = "Tu pedido ha sido entregado. Buen provecho!";
                clearInterval(self.trackingTimer);
                self.trackingTimer = null;
            }
            if (data.status === "paid") {
                clearInterval(self.trackingTimer);
                self.trackingTimer = null;
            }
        })
        .catch(function() { /* silently retry next interval */ });
    },

    _pollDriverLocation: function() {
        if (!this.lastOrderId) return;
        var apiBase = CFG.api_base.replace("/carta", "");
        fetch(apiBase + "/delivery/" + this.lastOrderId + "/tracking")
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var detail = document.getElementById("tracking-detail");
            var parts = [];
            if (data.driver_name) {
                parts.push("\ud83d\udef5 Motorizado: " + data.driver_name);
            }
            if (data.driver_latitude && data.driver_longitude) {
                parts.push("Ubicacion: " + data.driver_latitude.toFixed(5) + ", " + data.driver_longitude.toFixed(5));
                if (data.driver_updated_at) {
                    var d = new Date(data.driver_updated_at);
                    var h = String(d.getHours()).padStart(2, "0");
                    var m = String(d.getMinutes()).padStart(2, "0");
                    parts.push("Actualizado: " + h + ":" + m);
                }
            }
            if (parts.length > 0) {
                detail.textContent = parts.join("\n");
            } else {
                detail.textContent = "\ud83d\udef5 Tu motorizado esta en camino";
            }
        })
        .catch(function() {});
    },

    _renderTrackingSteps: function(currentStatus) {
        var isDelivery = this.lastOrderType === "delivery";
        var steps;
        if (isDelivery) {
            steps = [
                {key: "sent",      label: "Pedido recibido",    icon: "1"},
                {key: "preparing", label: "Preparando",          icon: "2"},
                {key: "ready",     label: "Listo",               icon: "3"},
                {key: "delivering",label: "Motorizado en camino",icon: "4"},
                {key: "delivered", label: "Entregado",           icon: "\u2713"},
            ];
        } else {
            steps = [
                {key: "sent",      label: "Pedido recibido", icon: "1"},
                {key: "preparing", label: "Preparando",       icon: "2"},
                {key: "ready",     label: "Listo para recoger",icon: "\u2713"},
            ];
        }

        // Map order status to step index
        var statusOrder = {
            "open": 0, "sent": 0, "pending_approval": 0,
            "preparing": 1,
            "ready": isDelivery ? 2 : 2, "served": isDelivery ? 2 : 2,
            "delivering": 3, "in_transit": 3,
            "delivered": 4, "paid": isDelivery ? 4 : 2,
        };
        var activeIdx = statusOrder[currentStatus] !== undefined ? statusOrder[currentStatus] : 0;

        var container = document.getElementById("tracking-steps");
        var html = "";
        for (var i = 0; i < steps.length; i++) {
            var s = steps[i];
            var cls = "tracking-step";
            if (i < activeIdx) cls += " done";
            else if (i === activeIdx) cls += " active";
            else cls += " pending";

            html += '<div class="' + cls + '">';
            html += '<div class="ts-dot">' + (i < activeIdx ? "\u2713" : s.icon) + '</div>';
            html += '<div class="ts-line"></div>';
            html += '<div class="ts-info">';
            html += '<div class="ts-label">' + s.label + '</div>';
            html += '</div></div>';
        }
        container.innerHTML = html;
    },

    closeTracking: function() {
        if (this.trackingTimer) {
            clearInterval(this.trackingTimer);
            this.trackingTimer = null;
        }
        document.getElementById("tracking").classList.add("hide");
        this.lastOrderId = null;
    },

    closeSuccess: function() {
        document.getElementById("success").classList.add("hide");
    },

    // ====== REQUEST WAITER ======
    requestWaiter: function() {
        if (!this.lastOrderId) return;
        var btn = document.getElementById("btn-waiter");
        btn.disabled = true;
        btn.textContent = "Llamando...";

        fetch(CFG.api_base.replace("/carta", "") + "/orders/" + this.lastOrderId + "/request-waiter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        })
        .then(function(r) {
            if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || "Error"); });
            return r.json();
        })
        .then(function() {
            btn.textContent = "\u2713 Mozo notificado";
            setTimeout(function() {
                btn.textContent = "\ud83d\ude4b Solicito Mozo";
                btn.disabled = false;
            }, 5000);
        })
        .catch(function(e) {
            alert("Error: " + e.message);
            btn.textContent = "\ud83d\ude4b Solicito Mozo";
            btn.disabled = false;
        });
    },

    _esc: function(s) {
        if (!s) return "";
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },
};

document.addEventListener("DOMContentLoaded", function() { CARTA.init(); });
// Expose globally for onclick handlers
window.CARTA = CARTA;