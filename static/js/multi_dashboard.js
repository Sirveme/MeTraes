/**
 * multi_dashboard.js — Multi-Dashboard para contadores.
 * Login email/password, paneles por branch, auto-refresh.
 */

var CFG = window.MULTI_CONFIG || {};

var MULTI = {
    token: null,
    user: null,
    restaurantId: null,
    refreshTimer: null,

    init: function() {
        this.startClock();
        this.checkAuth();
    },

    // ================================================
    // AUTH (email/password)
    // ================================================
    checkAuth: function() {
        var token = localStorage.getItem("multi_token");
        if (!token) { this.showLogin(); return; }
        try {
            var payload = JSON.parse(atob(token.split(".")[1]));
            if (payload.exp && payload.exp * 1000 < Date.now()) {
                localStorage.removeItem("multi_token");
                this.showLogin(); return;
            }
            this.token = token;
            this.user = JSON.parse(localStorage.getItem("multi_user") || "{}");
            this.restaurantId = this.user.restaurant_id;
            this.onLoggedIn();
        } catch(e) {
            localStorage.removeItem("multi_token");
            this.showLogin();
        }
    },

    showLogin: function() {
        document.getElementById("login-overlay").style.display = "flex";
        document.getElementById("main").style.display = "none";
    },

    doLogin: function() {
        var email = document.getElementById("login-email").value.trim();
        var pass = document.getElementById("login-pass").value;
        var errEl = document.getElementById("login-error");
        var btn = document.getElementById("login-btn");

        if (!email || !pass) { errEl.textContent = "Ingresa email y contrasena"; return; }
        errEl.textContent = "";
        btn.textContent = "Ingresando..."; btn.disabled = true;

        var self = this;
        fetch(CFG.api_base + "/auth/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({email: email, password: pass}),
        })
        .then(function(r) {
            if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || "Error"); });
            return r.json();
        })
        .then(function(data) {
            var role = data.user && data.user.role;
            if (role !== "owner" && role !== "manager") {
                errEl.textContent = "Solo owner/manager pueden acceder";
                btn.textContent = "Ingresar"; btn.disabled = false;
                return;
            }
            self.token = data.access_token;
            self.user = data.user;
            self.restaurantId = data.user.restaurant_id;
            localStorage.setItem("multi_token", data.access_token);
            localStorage.setItem("multi_user", JSON.stringify(data.user));
            self.onLoggedIn();
        })
        .catch(function(e) {
            errEl.textContent = e.message || "Credenciales incorrectas";
            btn.textContent = "Ingresar"; btn.disabled = false;
        });
    },

    doLogout: function() {
        if (this.refreshTimer) clearInterval(this.refreshTimer);
        localStorage.removeItem("multi_token");
        localStorage.removeItem("multi_user");
        this.token = null;
        this.user = null;
        this.showLogin();
    },

    onLoggedIn: function() {
        document.getElementById("login-overlay").style.display = "none";
        document.getElementById("main").style.display = "block";
        this.loadStats();
        var self = this;
        this.refreshTimer = setInterval(function() { self.loadStats(); }, 20000);
    },

    // ================================================
    // LOAD STATS
    // ================================================
    loadStats: function() {
        if (!this.restaurantId) return;
        var self = this;
        fetch(CFG.api_base + "/dashboard/multi-stats?restaurant_id=" + this.restaurantId, {
            headers: {"Authorization": "Bearer " + this.token},
        })
        .then(function(r) {
            if (r.status === 401) {
                localStorage.removeItem("multi_token");
                location.reload();
                return;
            }
            if (!r.ok) throw new Error("Error");
            return r.json();
        })
        .then(function(data) {
            if (!data) return;
            document.getElementById("h-rest").textContent = data.restaurant_name || "Multi-Dashboard";
            self.renderPanels(data.panels || []);
        })
        .catch(function(e) { console.error("[Multi]", e); });
    },

    // ================================================
    // RENDER
    // ================================================
    renderPanels: function(panels) {
        var grid = document.getElementById("panels");
        var empty = document.getElementById("empty");

        if (panels.length === 0) {
            grid.innerHTML = "";
            empty.style.display = "block";
            return;
        }
        empty.style.display = "none";

        // Set grid columns class
        grid.className = "panels-grid cols-" + Math.min(panels.length, 6);

        var html = "";
        var self = this;
        panels.forEach(function(p) {
            var s = p.status; // green, yellow, red

            // Last sale text
            var lastSaleText = "Sin ventas";
            if (p.last_sale_minutes !== null) {
                if (p.last_sale_minutes < 1) lastSaleText = "Ahora";
                else if (p.last_sale_minutes < 60) lastSaleText = "Hace " + p.last_sale_minutes + " min";
                else lastSaleText = "Hace " + Math.round(p.last_sale_minutes / 60) + "h";
            }

            // Staff tag class
            var staffClass = "staff-ok";
            if (p.staff_expected > 0) {
                var ratio = p.staff_present / p.staff_expected;
                if (ratio < 0.3) staffClass = "staff-bad";
                else if (ratio < 0.8) staffClass = "staff-warn";
            }

            html += '<div class="panel s-' + s + '" onclick="MULTI.openBranch(' + p.branch_id + ')">';

            // Header
            html += '<div class="pn-head">';
            html += '<span class="pn-name">' + self.esc(p.branch_name) + '</span>';
            html += '<span class="pn-dot ' + s + '"></span>';
            html += '</div>';

            // Metrics
            html += '<div class="pn-metrics">';
            html += '<div class="pn-metric"><div class="pn-m-label">Ventas hoy</div>';
            html += '<div class="pn-m-value accent">S/ ' + self.fmt(p.sale_total) + '</div></div>';
            html += '<div class="pn-metric"><div class="pn-m-label">Cantidad</div>';
            html += '<div class="pn-m-value">' + p.sale_count + '</div></div>';
            html += '<div class="pn-metric"><div class="pn-m-label">Ticket prom.</div>';
            html += '<div class="pn-m-value small">S/ ' + self.fmt(p.ticket_avg) + '</div></div>';
            html += '<div class="pn-metric"><div class="pn-m-label">Ultima venta</div>';
            html += '<div class="pn-m-value small">' + lastSaleText + '</div></div>';
            html += '</div>';

            // Footer tags
            html += '<div class="pn-footer">';
            html += '<span class="pn-tag ' + (p.caja_open ? "caja-open" : "caja-closed") + '">';
            html += 'Caja ' + (p.caja_open ? "abierta" : "cerrada") + '</span>';
            html += '<span class="pn-tag ' + staffClass + '">';
            html += 'Personal ' + p.staff_present + '/' + p.staff_expected + '</span>';
            html += '</div>';

            html += '</div>';
        });

        grid.innerHTML = html;
    },

    openBranch: function(branchId) {
        // Open full dashboard in new tab
        window.open("/dashboard/" + this.restaurantId, "_blank");
    },

    // ================================================
    // HELPERS
    // ================================================
    startClock: function() {
        var el = document.getElementById("h-clock");
        function tick() {
            var now = new Date();
            var h = String(now.getHours()).padStart(2, "0");
            var m = String(now.getMinutes()).padStart(2, "0");
            var s = String(now.getSeconds()).padStart(2, "0");
            if (el) el.textContent = h + ":" + m + ":" + s;
        }
        tick();
        setInterval(tick, 1000);
    },

    fmt: function(n) {
        return Number(n || 0).toLocaleString("es-PE", {minimumFractionDigits: 2, maximumFractionDigits: 2});
    },

    esc: function(s) {
        if (!s) return "";
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },
};

document.addEventListener("DOMContentLoaded", function() { MULTI.init(); });
window.MULTI = MULTI;

// Enter key on login fields
document.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && document.getElementById("login-overlay").style.display !== "none") {
        MULTI.doLogin();
    }
});
