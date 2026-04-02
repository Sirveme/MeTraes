/**
 * delivery.js — Pantalla del motorizado.
 * PIN login, lista de pedidos, pickup/deliver, GPS tracking.
 */

var DELIVERY = {
    config: window.DELIVERY_CONFIG || {},
    user: null,
    token: null,
    orders: [],
    geoWatchId: null,
    geoLat: null,
    geoLng: null,
    locationTimers: {},  // order_id -> interval

    // ================================================
    // INIT
    // ================================================
    init: function() {
        this.config = window.DELIVERY_CONFIG || {};
        this.bindEvents();
        document.getElementById("h-rest").textContent = this.config.restaurant_name || "";
        this.checkAuth();
    },

    bindEvents: function() {
        var self = this;
        document.getElementById("pin-btn").onclick = function() { self.doLogin(); };
        document.getElementById("pin-input").addEventListener("keyup", function(e) {
            if (e.key === "Enter") self.doLogin();
        });
        document.getElementById("btn-logout").onclick = function() { self.doLogout(); };
    },

    // ================================================
    // AUTH
    // ================================================
    checkAuth: function() {
        var token = localStorage.getItem("delivery_token");
        if (!token) { this.showLogin(); return; }
        try {
            var payload = JSON.parse(atob(token.split(".")[1]));
            if (parseInt(payload.restaurant_id) !== this.config.restaurant_id ||
                (payload.exp && payload.exp * 1000 < Date.now())) {
                localStorage.removeItem("delivery_token");
                this.showLogin(); return;
            }
            this.token = token;
            this.user = JSON.parse(localStorage.getItem("delivery_user") || "{}");
            this.onLoggedIn();
        } catch(e) {
            localStorage.removeItem("delivery_token");
            this.showLogin();
        }
    },

    showLogin: function() {
        document.getElementById("pin-overlay").style.display = "flex";
        document.getElementById("main").style.display = "none";
    },

    doLogin: function() {
        var self = this;
        var pin = document.getElementById("pin-input").value;
        var rid = this.config.restaurant_id;
        var errEl = document.getElementById("pin-error");
        var btn = document.getElementById("pin-btn");
        if (!pin || pin.length < 4) { errEl.textContent = "PIN de 4-6 digitos"; return; }
        btn.textContent = "Entrando..."; btn.disabled = true;
        this.api("POST", "/api/v1/auth/login/pin", {pin: pin, restaurant_id: rid}, true)
        .then(function(data) {
            self.token = data.access_token;
            self.user = data.user;
            localStorage.setItem("delivery_token", data.access_token);
            localStorage.setItem("delivery_user", JSON.stringify(data.user));
            self.onLoggedIn();
        })
        .catch(function(e) {
            errEl.textContent = e.message || "PIN incorrecto";
            btn.textContent = "Entrar"; btn.disabled = false;
        });
    },

    doLogout: function() {
        this.stopGPS();
        localStorage.removeItem("delivery_token");
        localStorage.removeItem("delivery_user");
        this.token = null;
        this.user = null;
        document.getElementById("pin-input").value = "";
        document.getElementById("pin-error").textContent = "";
        document.getElementById("pin-btn").textContent = "Entrar";
        document.getElementById("pin-btn").disabled = false;
        this.showLogin();
    },

    onLoggedIn: function() {
        document.getElementById("pin-overlay").style.display = "none";
        document.getElementById("main").style.display = "block";
        document.getElementById("h-user").textContent = this.user.name || "";
        this.startGPS();
        this.loadOrders();
        // Auto-refresh every 15 seconds
        var self = this;
        setInterval(function() { self.loadOrders(); }, 15000);
    },

    // ================================================
    // GPS
    // ================================================
    startGPS: function() {
        var self = this;
        var gpsEl = document.getElementById("h-gps");
        if (!navigator.geolocation) {
            gpsEl.textContent = "GPS: No disponible";
            gpsEl.className = "h-gps off";
            return;
        }
        this.geoWatchId = navigator.geolocation.watchPosition(
            function(pos) {
                self.geoLat = pos.coords.latitude;
                self.geoLng = pos.coords.longitude;
                gpsEl.textContent = "GPS: OK";
                gpsEl.className = "h-gps";
            },
            function(err) {
                gpsEl.textContent = "GPS: " + err.message;
                gpsEl.className = "h-gps off";
            },
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 }
        );
    },

    stopGPS: function() {
        if (this.geoWatchId !== null) {
            navigator.geolocation.clearWatch(this.geoWatchId);
            this.geoWatchId = null;
        }
        // Stop all location timers
        for (var oid in this.locationTimers) {
            clearInterval(this.locationTimers[oid]);
        }
        this.locationTimers = {};
    },

    startLocationSending: function(orderId) {
        var self = this;
        // Send immediately
        this.sendLocation(orderId);
        // Then every 30 seconds
        if (this.locationTimers[orderId]) clearInterval(this.locationTimers[orderId]);
        this.locationTimers[orderId] = setInterval(function() {
            self.sendLocation(orderId);
        }, 30000);
    },

    stopLocationSending: function(orderId) {
        if (this.locationTimers[orderId]) {
            clearInterval(this.locationTimers[orderId]);
            delete this.locationTimers[orderId];
        }
    },

    sendLocation: function(orderId) {
        if (this.geoLat === null || this.geoLng === null) return;
        this.api("POST", "/api/v1/delivery/" + orderId + "/location", {
            latitude: this.geoLat,
            longitude: this.geoLng,
        }).catch(function() { /* silent */ });
    },

    // ================================================
    // LOAD ORDERS
    // ================================================
    loadOrders: function() {
        var self = this;
        this.api("GET", "/api/v1/delivery/orders")
        .then(function(data) {
            self.orders = data.orders || [];
            self.renderOrders();
            self.updateStats();
            // Start location sending for dispatched orders assigned to me
            self.orders.forEach(function(o) {
                if (o.status === "dispatched" && o.delivery_driver_id === self.user.id) {
                    if (!self.locationTimers[o.id]) {
                        self.startLocationSending(o.id);
                    }
                }
            });
        })
        .catch(function() {});
    },

    updateStats: function() {
        var pending = 0;
        var enroute = 0;
        this.orders.forEach(function(o) {
            if (o.status === "ready") pending++;
            else if (o.status === "dispatched") enroute++;
        });
        document.getElementById("stat-pending").textContent = pending;
        document.getElementById("stat-enroute").textContent = enroute;
    },

    // ================================================
    // RENDER
    // ================================================
    renderOrders: function() {
        var list = document.getElementById("orders-list");
        if (this.orders.length === 0) {
            list.innerHTML = '<p class="empty-msg">Sin pedidos delivery</p>';
            return;
        }

        var html = "";
        var self = this;
        this.orders.forEach(function(o) {
            var isDispatched = o.status === "dispatched";
            var num = "#" + String(o.order_number).padStart(3, "0");

            html += '<div class="order-card' + (isDispatched ? " dispatched" : "") + '">';

            // Top row
            html += '<div class="oc-top">';
            html += '<span class="oc-number">' + num + '</span>';
            html += '<span class="oc-badge ' + o.status + '">' + (isDispatched ? "En camino" : "Listo") + '</span>';
            html += '</div>';

            // Customer
            html += '<div class="oc-customer">';
            html += '<div class="oc-name">' + self.esc(o.customer_name) + '</div>';
            if (o.customer_phone) {
                html += '<div class="oc-phone"><a href="tel:' + o.customer_phone + '">' + o.customer_phone + '</a></div>';
            }
            html += '</div>';

            // Address
            html += '<div class="oc-address">';
            html += '<div class="oc-addr-label">Direccion</div>';
            html += '<div class="oc-addr-text">' + self.esc(o.customer_address) + '</div>';
            if (o.customer_notes) {
                html += '<div class="oc-notes">' + self.esc(o.customer_notes) + '</div>';
            }
            html += '</div>';

            // Meta
            html += '<div class="oc-meta">';
            html += '<span class="oc-meta-item"><strong>' + o.item_count + '</strong> items</span>';
            html += '<span class="oc-meta-item"><strong>S/ ' + o.total.toFixed(2) + '</strong></span>';
            if (o.ready_at) {
                var d = new Date(o.ready_at);
                html += '<span class="oc-meta-item">Listo ' + String(d.getHours()).padStart(2, "0") + ':' + String(d.getMinutes()).padStart(2, "0") + '</span>';
            }
            html += '</div>';

            // Actions
            html += '<div class="oc-actions">';
            if (isDispatched) {
                html += '<button class="oc-btn deliver" onclick="DELIVERY.deliverOrder(' + o.id + ', this)">&#9989; ENTREGADO</button>';
            } else {
                html += '<button class="oc-btn pickup" onclick="DELIVERY.pickupOrder(' + o.id + ', this)">&#128661; RECOGER PEDIDO</button>';
            }
            if (o.customer_phone) {
                html += '<a class="oc-btn call" href="tel:' + o.customer_phone + '">&#128222;</a>';
            }
            html += '</div>';

            html += '</div>';
        });
        list.innerHTML = html;
    },

    // ================================================
    // ACTIONS
    // ================================================
    pickupOrder: function(orderId, btn) {
        var self = this;
        btn.disabled = true;
        btn.textContent = "Recogiendo...";
        this.api("PUT", "/api/v1/delivery/" + orderId + "/pickup")
        .then(function() {
            self.startLocationSending(orderId);
            self.loadOrders();
        })
        .catch(function(e) {
            alert("Error: " + e.message);
            btn.disabled = false;
            btn.innerHTML = "&#128661; RECOGER PEDIDO";
        });
    },

    deliverOrder: function(orderId, btn) {
        var self = this;
        btn.disabled = true;
        btn.textContent = "Registrando...";
        this.api("PUT", "/api/v1/delivery/" + orderId + "/deliver")
        .then(function() {
            self.stopLocationSending(orderId);
            self.loadOrders();
        })
        .catch(function(e) {
            alert("Error: " + e.message);
            btn.disabled = false;
            btn.innerHTML = "&#9989; ENTREGADO";
        });
    },

    // ================================================
    // HELPERS
    // ================================================
    esc: function(s) {
        if (!s) return "";
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },

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
};

// ====== BOOT ======
document.addEventListener("DOMContentLoaded", function() {
    DELIVERY.init();
});
window.DELIVERY = DELIVERY;
