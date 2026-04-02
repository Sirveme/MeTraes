/* dashboard.js v1 — Dashboard Gerencial */
var CFG = window.DASH_CONFIG;

var DASH = {
    token: null,
    period: "today",
    refreshTimer: null,

    // ====== LOGIN ======
    login: function() {
        var pin = document.getElementById("pin-input").value.trim();
        var errEl = document.getElementById("pin-error");
        if (!pin || pin.length < 4) { errEl.textContent = "PIN de 4+ dígitos"; return; }
        errEl.textContent = "";

        fetch(CFG.api_base + "/auth/login/pin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pin: pin, restaurant_id: CFG.restaurant_id }),
        })
        .then(function(r) {
            if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || "Error"); });
            return r.json();
        })
        .then(function(data) {
            var role = data.user && data.user.role;
            if (role !== "owner" && role !== "manager") {
                errEl.textContent = "Solo owner/manager pueden acceder";
                return;
            }
            DASH.token = data.access_token;
            localStorage.setItem("dash_token", data.access_token);
            DASH._show();
        })
        .catch(function(e) {
            errEl.textContent = e.message;
        });
    },

    _show: function() {
        document.getElementById("pin-overlay").classList.add("hide");
        document.getElementById("header").classList.remove("hide");
        document.getElementById("filters").classList.remove("hide");
        document.getElementById("content").classList.remove("hide");
        document.getElementById("h-rest").textContent = CFG.restaurant_name;
        DASH._clock();
        setInterval(DASH._clock, 1000);
        DASH.loadStats();
        DASH.refreshTimer = setInterval(function() { DASH.loadStats(); }, 15000);
    },

    _clock: function() {
        var now = new Date();
        var h = String(now.getHours()).padStart(2, "0");
        var m = String(now.getMinutes()).padStart(2, "0");
        var s = String(now.getSeconds()).padStart(2, "0");
        document.getElementById("h-clock").textContent = h + ":" + m + ":" + s;
    },

    // ====== FILTERS ======
    setPeriod: function(p) {
        this.period = p;
        document.querySelectorAll(".filter-btn").forEach(function(b) {
            b.classList.toggle("active", b.dataset.period === p);
        });
        this.loadStats();
    },

    // ====== LOAD STATS ======
    loadStats: function() {
        var self = this;
        fetch(CFG.api_base + "/dashboard/stats?restaurant_id=" + CFG.restaurant_id + "&period=" + this.period, {
            headers: { "Authorization": "Bearer " + this.token },
        })
        .then(function(r) {
            if (r.status === 401) {
                // Token expired
                localStorage.removeItem("dash_token");
                location.reload();
                return;
            }
            if (!r.ok) throw new Error("Error cargando datos");
            return r.json();
        })
        .then(function(data) {
            if (!data) return;
            self._renderSummary(data.summary);
            self._renderHourly(data.hourly);
            self._renderBranches(data.branches);
            self._renderTopProducts(data.top_products);
            self._renderWaiters(data.waiters);
        })
        .catch(function(e) { console.error("[Dashboard]", e); });
    },

    // ====== RENDER: Summary ======
    _renderSummary: function(s) {
        document.getElementById("s-total").textContent = "S/ " + DASH._fmt(s.sale_total);
        document.getElementById("s-count").textContent = s.sale_count;
        document.getElementById("s-ticket").textContent = "S/ " + DASH._fmt(s.ticket_avg);
        document.getElementById("s-profit").textContent = "S/ " + DASH._fmt(s.profit);
    },

    // ====== RENDER: Hourly chart (SVG) ======
    _renderHourly: function(data) {
        var wrap = document.getElementById("hourly-chart");
        if (!data || data.length === 0) {
            wrap.innerHTML = '<div class="chart-empty">Sin ventas en este periodo</div>';
            return;
        }

        var barW = 36, gap = 6, padL = 4, padT = 14, padB = 22;
        var chartW = padL + data.length * (barW + gap);
        var maxTotal = Math.max.apply(null, data.map(function(d) { return d.total; }));
        if (maxTotal === 0) maxTotal = 1;
        var maxBarH = 100;
        var svgH = padT + maxBarH + padB;

        var svg = '<svg width="' + chartW + '" height="' + svgH + '" xmlns="http://www.w3.org/2000/svg">';

        data.forEach(function(d, i) {
            var x = padL + i * (barW + gap);
            var barH = Math.max(4, (d.total / maxTotal) * maxBarH);
            var y = padT + maxBarH - barH;

            // Value above bar
            svg += '<text x="' + (x + barW / 2) + '" y="' + (y - 3) + '" text-anchor="middle" class="bar-value">' + DASH._fmtK(d.total) + '</text>';
            // Bar
            svg += '<rect class="bar-rect" x="' + x + '" y="' + y + '" width="' + barW + '" height="' + barH + '" rx="3"/>';
            // Hour label
            var label = String(d.hour).padStart(2, "0") + "h";
            svg += '<text x="' + (x + barW / 2) + '" y="' + (padT + maxBarH + 14) + '" text-anchor="middle" class="bar-label">' + label + '</text>';
        });

        svg += '</svg>';
        wrap.innerHTML = svg;
    },

    // ====== RENDER: Branches ======
    _renderBranches: function(data) {
        var section = document.getElementById("branch-section");
        if (!data || data.length <= 1) {
            section.classList.add("hide");
            return;
        }
        section.classList.remove("hide");
        var tbody = document.getElementById("branch-body");
        tbody.innerHTML = "";
        data.forEach(function(b) {
            var tr = document.createElement("tr");
            tr.innerHTML =
                '<td class="bt-name">' + DASH._esc(b.name) + '</td>' +
                '<td>' + b.count + '</td>' +
                '<td>S/ ' + DASH._fmt(b.total) + '</td>' +
                '<td>S/ ' + DASH._fmt(b.ticket_avg) + '</td>';
            tbody.appendChild(tr);
        });
    },

    // ====== RENDER: Top products ======
    _renderTopProducts: function(data) {
        var ul = document.getElementById("top-list");
        if (!data || data.length === 0) {
            ul.innerHTML = '<div class="empty-state">Sin datos</div>';
            return;
        }
        ul.innerHTML = "";
        data.forEach(function(p) {
            var rankClass = p.rank === 1 ? " gold" : p.rank === 2 ? " silver" : p.rank === 3 ? " bronze" : "";
            var li = document.createElement("li");
            li.className = "top-item";
            li.innerHTML =
                '<span class="top-rank' + rankClass + '">' + p.rank + '</span>' +
                '<span class="top-name">' + DASH._esc(p.name) + '</span>' +
                '<span class="top-qty">' + Math.round(p.qty) + '</span>' +
                '<span class="top-total">S/ ' + DASH._fmt(p.total) + '</span>';
            ul.appendChild(li);
        });
    },

    // ====== RENDER: Waiters ======
    _renderWaiters: function(data) {
        var ul = document.getElementById("waiter-list");
        if (!data || data.length === 0) {
            ul.innerHTML = '<div class="empty-state">Sin datos</div>';
            return;
        }
        ul.innerHTML = "";
        data.forEach(function(w) {
            var initials = w.name.split(" ").map(function(n) { return n[0]; }).join("").substring(0, 2).toUpperCase();
            var li = document.createElement("li");
            li.className = "waiter-item";
            li.innerHTML =
                '<span class="waiter-avatar">' + initials + '</span>' +
                '<span class="waiter-name">' + DASH._esc(w.name) + '</span>' +
                '<span class="waiter-orders">' + w.orders + ' ped.</span>' +
                '<span class="waiter-total">S/ ' + DASH._fmt(w.total) + '</span>';
            ul.appendChild(li);
        });
    },

    // ====== UTILITIES ======
    _fmt: function(n) {
        return Number(n || 0).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },

    _fmtK: function(n) {
        if (n >= 1000) return (n / 1000).toFixed(1) + "k";
        return Math.round(n).toString();
    },

    _esc: function(s) {
        if (!s) return "";
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },
};

document.addEventListener("DOMContentLoaded", function() {
    // Try saved token
    var saved = localStorage.getItem("dash_token");
    if (saved) {
        DASH.token = saved;
        DASH._show();
    }
});
window.DASH = DASH;
