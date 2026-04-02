/**
 * marcacion.js — Marcacion de personal (entrada/salida).
 * PIN login, geolocalizacion, boton grande, lista del dia.
 */

var MARCACION = {
    config: window.MARCACION_CONFIG || {},
    user: null,
    token: null,
    currentStatus: null,  // "in", "out", or null
    geoLat: null,
    geoLng: null,
    geoReady: false,

    // ================================================
    // INIT
    // ================================================
    init: function() {
        this.config = window.MARCACION_CONFIG || {};
        this.bindEvents();
        this.startClock();
        document.getElementById("h-rest").textContent = this.config.restaurant_name || "";
        this.checkAuth();
    },

    bindEvents: function() {
        var self = this;
        document.getElementById("pin-btn").onclick = function() { self.doLogin(); };
        document.getElementById("pin-input").addEventListener("keyup", function(e) {
            if (e.key === "Enter") self.doLogin();
        });
        document.getElementById("btn-check").onclick = function() { self.doCheck(); };
        document.getElementById("btn-logout").onclick = function() { self.doLogout(); };
    },

    startClock: function() {
        function tick() {
            var now = new Date();
            var h = String(now.getHours()).padStart(2, "0");
            var m = String(now.getMinutes()).padStart(2, "0");
            var s = String(now.getSeconds()).padStart(2, "0");
            var el = document.getElementById("h-clock");
            if (el) el.textContent = h + ":" + m + ":" + s;
        }
        tick();
        setInterval(tick, 1000);
    },

    // ================================================
    // AUTH
    // ================================================
    checkAuth: function() {
        var token = localStorage.getItem("marcacion_token");
        if (!token) {
            this.showLogin();
            return;
        }
        try {
            var payload = JSON.parse(atob(token.split(".")[1]));
            if (parseInt(payload.restaurant_id) !== this.config.restaurant_id ||
                (payload.exp && payload.exp * 1000 < Date.now())) {
                localStorage.removeItem("marcacion_token");
                this.showLogin();
                return;
            }
            this.token = token;
            this.user = JSON.parse(localStorage.getItem("marcacion_user") || "{}");
            this.onLoggedIn();
        } catch(e) {
            localStorage.removeItem("marcacion_token");
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
            localStorage.setItem("marcacion_token", data.access_token);
            localStorage.setItem("marcacion_user", JSON.stringify(data.user));
            self.onLoggedIn();
        })
        .catch(function(e) {
            errEl.textContent = e.message || "PIN incorrecto";
            btn.textContent = "Entrar"; btn.disabled = false;
        });
    },

    doLogout: function() {
        localStorage.removeItem("marcacion_token");
        localStorage.removeItem("marcacion_user");
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
        this.requestGeo();
        this.loadToday();
    },

    // ================================================
    // GEOLOCATION
    // ================================================
    requestGeo: function() {
        var self = this;
        var geoEl = document.getElementById("geo-status");
        if (!navigator.geolocation) {
            geoEl.textContent = "Geolocalizacion no disponible";
            self.geoReady = true;
            return;
        }
        geoEl.textContent = "Obteniendo ubicacion...";
        navigator.geolocation.getCurrentPosition(
            function(pos) {
                self.geoLat = pos.coords.latitude;
                self.geoLng = pos.coords.longitude;
                self.geoReady = true;
                geoEl.textContent = "Ubicacion OK (" +
                    pos.coords.latitude.toFixed(4) + ", " +
                    pos.coords.longitude.toFixed(4) + ")";
            },
            function(err) {
                self.geoReady = true;
                geoEl.textContent = "Sin ubicacion: " + err.message;
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    },

    // ================================================
    // LOAD TODAY
    // ================================================
    loadToday: function() {
        var self = this;
        var rid = this.config.restaurant_id;
        this.api("GET", "/api/v1/attendance/today?restaurant_id=" + rid, null, true)
        .then(function(data) {
            self.renderToday(data.records || []);
            self.detectStatus(data.records || []);
        })
        .catch(function() {
            self.updateButton(null);
        });
    },

    detectStatus: function(records) {
        // Encontrar el estado del usuario actual
        var uid = this.user ? this.user.id : null;
        var myRecord = null;
        for (var i = 0; i < records.length; i++) {
            if (records[i].user_id === uid) {
                myRecord = records[i];
                break;
            }
        }

        if (!myRecord || !myRecord.checks || myRecord.checks.length === 0) {
            this.currentStatus = null;
            this.updateStatusCard(null, null);
            this.updateButton(null);
            return;
        }

        var lastCheck = myRecord.checks[0]; // ya vienen desc
        this.currentStatus = lastCheck.check_type;
        this.updateStatusCard(lastCheck.check_type, lastCheck.checked_at);
        this.updateButton(lastCheck.check_type);
    },

    updateStatusCard: function(type, checkedAt) {
        var card = document.getElementById("status-card");
        var icon = document.getElementById("status-icon");
        var text = document.getElementById("status-text");
        var time = document.getElementById("status-time");

        card.className = "status-card";
        if (type === "in") {
            card.classList.add("checked-in");
            icon.innerHTML = "&#9989;";
            text.textContent = "Trabajando";
            if (checkedAt) {
                var d = new Date(checkedAt);
                var h = String(d.getHours()).padStart(2, "0");
                var m = String(d.getMinutes()).padStart(2, "0");
                time.textContent = "Entrada: " + h + ":" + m;
            }
        } else if (type === "out") {
            card.classList.add("checked-out");
            icon.innerHTML = "&#128308;";
            text.textContent = "Fuera de turno";
            if (checkedAt) {
                var d2 = new Date(checkedAt);
                var h2 = String(d2.getHours()).padStart(2, "0");
                var m2 = String(d2.getMinutes()).padStart(2, "0");
                time.textContent = "Salida: " + h2 + ":" + m2;
            }
        } else {
            icon.innerHTML = "&#9711;";
            text.textContent = "Sin marcar hoy";
            time.textContent = "";
        }
    },

    updateButton: function(lastType) {
        var btn = document.getElementById("btn-check");
        var iconEl = document.getElementById("btn-check-icon");
        var labelEl = document.getElementById("btn-check-label");
        btn.disabled = false;

        if (lastType === "in") {
            // Next action: salida
            btn.className = "btn-check salida";
            iconEl.innerHTML = "&#128308;";
            labelEl.textContent = "MARCAR SALIDA";
        } else {
            // Next action: entrada (null or "out")
            btn.className = "btn-check entrada";
            iconEl.innerHTML = "&#128994;";
            labelEl.textContent = "MARCAR ENTRADA";
        }
    },

    // ================================================
    // DO CHECK
    // ================================================
    doCheck: function() {
        var self = this;
        var btn = document.getElementById("btn-check");
        var errEl = document.getElementById("check-error");
        errEl.textContent = "";

        var checkType = (this.currentStatus === "in") ? "out" : "in";

        btn.disabled = true;
        var labelEl = document.getElementById("btn-check-label");
        labelEl.textContent = "Registrando...";

        this.api("POST", "/api/v1/attendance/check", {
            check_type: checkType,
            latitude: this.geoLat,
            longitude: this.geoLng,
        })
        .then(function(data) {
            self.currentStatus = data.check_type;
            self.updateStatusCard(data.check_type, data.checked_at);
            self.updateButton(data.check_type);
            self.loadToday();
        })
        .catch(function(e) {
            errEl.textContent = e.message || "Error al registrar";
            self.updateButton(self.currentStatus);
        });
    },

    // ================================================
    // RENDER TODAY
    // ================================================
    renderToday: function(records) {
        var list = document.getElementById("today-list");
        if (!records || records.length === 0) {
            list.innerHTML = '<p class="empty-msg">Sin marcaciones hoy</p>';
            return;
        }

        var html = "";
        for (var i = 0; i < records.length; i++) {
            var rec = records[i];
            var checks = rec.checks || [];
            for (var j = 0; j < checks.length; j++) {
                var c = checks[j];
                var dt = new Date(c.checked_at);
                var h = String(dt.getHours()).padStart(2, "0");
                var m = String(dt.getMinutes()).padStart(2, "0");
                var isIn = c.check_type === "in";
                html += '<div class="check-row">';
                html += '<div class="cr-icon">' + (isIn ? "&#9989;" : "&#128308;") + '</div>';
                html += '<div class="cr-info">';
                html += '<div class="cr-name">' + this.esc(rec.user_name) + '</div>';
                html += '<div class="cr-role">' + this.esc(rec.role) + '</div>';
                html += '</div>';
                html += '<span class="cr-type ' + c.check_type + '">' + (isIn ? "Entrada" : "Salida") + '</span>';
                html += '<div class="cr-time">' + h + ':' + m + '</div>';
                html += '</div>';
            }
        }
        list.innerHTML = html;
    },

    esc: function(s) {
        if (!s) return "";
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },

    // ================================================
    // API HELPER
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
};

// ====== BOOT ======
document.addEventListener("DOMContentLoaded", function() {
    MARCACION.init();
});
