/* carta_virtual.js v1 — Carta Virtual (QR) */
var CFG = window.CARTA_CONFIG;

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

    init: function() {
        document.getElementById("rest-name").textContent = CFG.restaurant_name;
        document.getElementById("table-badge").textContent =
            (CFG.zone_name ? CFG.zone_name + " \u2022 " : "") + CFG.table_label;
        this.loadMenu();
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
            btn.textContent = (c.icon || "") + " " + c.name;
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
                var icon = (cat && cat.icon) ? cat.icon : "\ud83c\udf7d\ufe0f";
                imgHtml = '<div class="p-img-placeholder">' + icon + '</div>';
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
                '</div>';

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
            table_id: CFG.table_id,
            order_type: "dine_in",
            customer_notes: notes,
            items: items,
        };

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
            // Success
            CARTA.cart = [];
            CARTA._updateCartBtn();
            CARTA.toggleCart();

            var suc = document.getElementById("success");
            document.getElementById("success-detail").textContent =
                "Pedido #" + String(data.order_number).padStart(3, "0") +
                "\nTotal: S/ " + data.total.toFixed(2) +
                "\n\nEl mesero atender\u00e1 tu mesa en breve.";
            suc.classList.remove("hide");

            setTimeout(function() { suc.classList.add("hide"); }, 5000);
        })
        .catch(function(e) {
            alert("Error: " + e.message);
        })
        .finally(function() {
            btn.disabled = false;
            btn.textContent = "Enviar pedido";
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