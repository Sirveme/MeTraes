/**
 * alertas.js — Configuracion de alertas push.
 * PIN login, toggles on/off, umbrales, test push.
 */

var ALERTAS = {
    config: window.ALERTAS_CONFIG || {},
    user: null,
    token: null,
    alertConfigs: [],

    init: function() {
        this.config = window.ALERTAS_CONFIG || {};
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
        var token = localStorage.getItem("alertas_token");
        if (!token) { this.showLogin(); return; }
        try {
            var payload = JSON.parse(atob(token.split(".")[1]));
            if (parseInt(payload.restaurant_id) !== this.config.restaurant_id ||
                (payload.exp && payload.exp * 1000 < Date.now())) {
                localStorage.removeItem("alertas_token");
                this.showLogin(); return;
            }
            this.token = token;
            this.user = JSON.parse(localStorage.getItem("alertas_user") || "{}");
            this.onLoggedIn();
        } catch(e) {
            localStorage.removeItem("alertas_token");
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
            var role = data.user && data.user.role;
            if (role !== "owner" && role !== "manager") {
                errEl.textContent = "Solo owner/manager pueden acceder";
                btn.textContent = "Entrar"; btn.disabled = false;
                return;
            }
            self.token = data.access_token;
            self.user = data.user;
            localStorage.setItem("alertas_token", data.access_token);
            localStorage.setItem("alertas_user", JSON.stringify(data.user));
            self.onLoggedIn();
        })
        .catch(function(e) {
            errEl.textContent = e.message || "PIN incorrecto";
            btn.textContent = "Entrar"; btn.disabled = false;
        });
    },

    doLogout: function() {
        localStorage.removeItem("alertas_token");
        localStorage.removeItem("alertas_user");
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
        this.checkPushStatus();
        this.loadConfigs();
    },

    // ================================================
    // PUSH STATUS
    // ================================================
    checkPushStatus: function() {
        var banner = document.getElementById("push-banner");
        var btnPush = document.getElementById("btn-push");
        if (typeof isPushSubscribed === "function") {
            isPushSubscribed().then(function(subscribed) {
                if (subscribed) {
                    banner.className = "push-banner active";
                    banner.querySelector("span").textContent = "\u2705 Notificaciones activas";
                    btnPush.style.display = "none";
                }
            });
        }
    },

    enablePush: function() {
        var self = this;
        var btn = document.getElementById("btn-push");
        btn.textContent = "Activando...";
        btn.disabled = true;
        if (typeof initPush === "function") {
            initPush(this.token).then(function(ok) {
                if (ok) {
                    self.checkPushStatus();
                } else {
                    btn.textContent = "Error - Reintentar";
                    btn.disabled = false;
                }
            });
        } else {
            btn.textContent = "No disponible";
        }
    },

    // ================================================
    // LOAD CONFIGS
    // ================================================
    loadConfigs: function() {
        var self = this;
        this.api("GET", "/api/v1/alerts/config")
        .then(function(data) {
            self.alertConfigs = data.configs || [];
            self.renderConfigs();
        })
        .catch(function() {
            document.getElementById("alerts-list").innerHTML =
                '<p class="loading">Error cargando configuracion</p>';
        });
    },

    renderConfigs: function() {
        var list = document.getElementById("alerts-list");
        var html = "";
        var self = this;

        this.alertConfigs.forEach(function(c, idx) {
            var onClass = c.is_enabled ? " on" : "";
            html += '<div class="alert-row" data-type="' + c.alert_type + '">';
            html += '<div class="alert-info">';
            html += '<div class="alert-label">' + self.esc(c.label) + '</div>';

            if (c.has_threshold) {
                var val = c.threshold_value || "";
                html += '<div class="alert-threshold">';
                html += '<label>Meta S/</label>';
                html += '<input type="number" value="' + val + '" min="0" step="10" ';
                html += 'onchange="ALERTAS.updateThreshold(\'' + c.alert_type + '\', this.value)">';
                html += '</div>';
            }

            html += '</div>';
            html += '<div class="toggle' + onClass + '" onclick="ALERTAS.toggleAlert(\'' + c.alert_type + '\', ' + idx + ', this)">';
            html += '<div class="toggle-dot"></div>';
            html += '</div>';
            html += '</div>';
        });

        list.innerHTML = html;
    },

    toggleAlert: function(alertType, idx, el) {
        var isOn = el.classList.contains("on");
        var newState = !isOn;
        el.classList.toggle("on", newState);
        this.alertConfigs[idx].is_enabled = newState;
        this.saveConfig(alertType, newState, this.alertConfigs[idx].threshold_value);
    },

    updateThreshold: function(alertType, value) {
        var cfg = this.alertConfigs.find(function(c) { return c.alert_type === alertType; });
        if (cfg) {
            cfg.threshold_value = parseFloat(value) || null;
            this.saveConfig(alertType, cfg.is_enabled, cfg.threshold_value);
        }
    },

    saveConfig: function(alertType, isEnabled, thresholdValue) {
        this.api("PUT", "/api/v1/alerts/config", [{
            alert_type: alertType,
            is_enabled: isEnabled,
            threshold_value: thresholdValue,
        }]).catch(function() { /* silent */ });
    },

    // ================================================
    // TEST PUSH
    // ================================================
    testPush: function() {
        var btn = document.getElementById("btn-test");
        btn.disabled = true;
        btn.textContent = "Enviando...";
        this.api("POST", "/api/v1/push/test")
        .then(function() {
            btn.textContent = "\u2713 Enviado!";
            setTimeout(function() {
                btn.textContent = "\ud83d\udd14 Enviar notificacion de prueba";
                btn.disabled = false;
            }, 3000);
        })
        .catch(function(e) {
            btn.textContent = "Error: " + e.message;
            setTimeout(function() {
                btn.textContent = "\ud83d\udd14 Enviar notificacion de prueba";
                btn.disabled = false;
            }, 3000);
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

document.addEventListener("DOMContentLoaded", function() {
    ALERTAS.init();
});
window.ALERTAS = ALERTAS;
