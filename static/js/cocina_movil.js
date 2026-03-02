/* cocina_movil.js - KDS Movil Logic */
const CFG = window.KDS_CONFIG;
const KC = CFG.kitchen;

const APP = {
    orders: [],
    stations: [],
    activeStation: "all",
    soundOn: true,
    ws: null,
    _hb: null,
    _reconnectAttempts: 0,

    init() {
        this._setupSound();
        this._wsConnect();
        setTimeout(() => {
            if (this.orders.length === 0) this._loadREST();
        }, 5000);
    },

    // ====== WEBSOCKET ======
    _wsConnect() {
        const token = localStorage.getItem("access_token") || "";
        let url = CFG.ws_base + "/" + CFG.restaurant_id + "?token=" + token;
        if (CFG.station_id) url += "&station_id=" + CFG.station_id;

        this._setStatus(false);
        try { this.ws = new WebSocket(url); } catch(e) { this._reconnect(); return; }

        this.ws.onopen = () => {
            this._setStatus(true);
            this._reconnectAttempts = 0;
            this._hb = setInterval(() => { try { this.ws.send("ping"); } catch(e){} }, 30000);
        };
        this.ws.onclose = () => {
            this._setStatus(false);
            clearInterval(this._hb);
            this._reconnect();
        };
        this.ws.onerror = () => {};
        this.ws.onmessage = (e) => {
            if (e.data === "pong") return;
            try { this._onMsg(JSON.parse(e.data)); } catch(ex) {}
        };
    },

    _reconnect() {
        this._reconnectAttempts++;
        var delay = Math.min(3000 * this._reconnectAttempts, 30000);
        setTimeout(() => { if (!this.ws || this.ws.readyState !== WebSocket.OPEN) this._wsConnect(); }, delay);
    },

    _setStatus(on) {
        var el = document.getElementById("ws-status");
        el.className = on ? "status on" : "status off";
        el.textContent = on ? "\u2705" : "\u274c";
    },

    _onMsg(msg) {
        var d = msg.data;
        if (msg.event === "initial_state") {
            this.orders = d.orders || [];
            this.stations = d.stations || [];
            this._renderStations();
            this.render();
            return;
        }
        if (d && d.orders) {
            var prev = this.orders.length;
            this.orders = d.orders;
            if (d.orders.length > prev && !d.changed_item) this._alertNew(d);
            this.render();
        }
    },

    // ====== RENDER ======
    render() {
        var container = document.getElementById("orders");
        var empty = document.getElementById("empty");
        var filtered = this.orders;
        if (this.activeStation !== "all") {
            var sid = parseInt(this.activeStation);
            filtered = this.orders.filter(function(o) { return o.items.some(function(i) { return i.station_id === sid; }); });
        }
        filtered.sort(function(a, b) { return (b.kitchen_wait_minutes || 0) - (a.kitchen_wait_minutes || 0); });

        container.querySelectorAll(".card").forEach(function(c) { c.remove(); });

        if (filtered.length === 0) {
            empty.style.display = "flex";
        } else {
            empty.style.display = "none";
            var self = this;
            filtered.forEach(function(o) { container.appendChild(self._mkCard(o)); });
        }

        document.getElementById("order-count").textContent = this.orders.length;
        document.getElementById("n-all").textContent = this.orders.length;
        var self2 = this;
        this.stations.forEach(function(s) {
            var el = document.getElementById("n-s" + s.id);
            if (el) el.textContent = self2.orders.filter(function(o) { return o.items.some(function(i) { return i.station_id === s.id; }); }).length;
        });
    },

    _mkCard(o) {
        var card = document.createElement("div");
        card.className = "card";
        card.dataset.s = o.status;
        card.dataset.oid = o.id;
        var wm = Math.round(o.kitchen_wait_minutes || 0);
        if (wm >= KC.alert_time_minutes) card.classList.add("late");

        var timerCls = "ok";
        if (wm >= KC.alert_time_minutes) timerCls = "late";
        else if (wm >= KC.warning_time_minutes) timerCls = "warn";
        var timerTxt = wm < 60 ? wm + "m" : Math.floor(wm / 60) + "h" + (wm % 60) + "m";

        var typeBadge = "";
        if (o.order_type === "delivery") typeBadge = "<span class=\"badge-type dlv\">\ud83d\udef5 Delivery</span>";
        else if (o.order_type === "takeaway") typeBadge = "<span class=\"badge-type tkw\">\ud83d\udce6 P/Llevar</span>";

        var items = o.items;
        if (this.activeStation !== "all") {
            var sid2 = parseInt(this.activeStation);
            items = items.filter(function(i) { return i.station_id === sid2; });
        }

        var itemsHtml = "";
        var self = this;
        items.forEach(function(it) {
            var q = parseFloat(it.quantity);
            var qd = q === Math.floor(q) ? q.toString() : q.toFixed(1);
            var mods = it.modifiers_summary ? "<div class=\"item-mods\">" + self._esc(it.modifiers_summary) + "</div>" : "";
            var notes = it.notes ? "<div class=\"item-notes\">\ud83d\udcdd " + self._esc(it.notes) + "</div>" : "";
            var sz = it.size_name ? "[" + self._esc(it.size_name) + "] " : "";
            itemsHtml += "<div class=\"item\"><div class=\"item-dot " + it.status + "\"></div>" +
                "<div class=\"item-qty\">" + qd + "</div>" +
                "<div class=\"item-info\"><div class=\"item-name\">" + sz + self._esc(it.product_name) + "</div>" +
                mods + notes + "</div></div>";
        });

        var allSent = items.every(function(i) { return i.status === "sent"; });
        var allPrep = items.every(function(i) { return i.status === "preparing"; });
        var actHtml = "";
        if (allSent) {
            actHtml = "<div class=\"card-actions\"><button class=\"act-btn act-prep\" data-oid=\"" + o.id + "\" data-act=\"preparing\">\u25b6 PREPARAR</button></div>";
        } else if (allPrep) {
            actHtml = "<div class=\"card-actions\"><button class=\"act-btn act-done\" data-oid=\"" + o.id + "\" data-act=\"ready\">\u2705 TODO LISTO</button></div>";
        } else {
            actHtml = "<div class=\"card-actions\">" +
                "<button class=\"act-btn act-prep\" data-oid=\"" + o.id + "\" data-act=\"preparing\">\u25b6 PREP</button>" +
                "<button class=\"act-btn act-done\" data-oid=\"" + o.id + "\" data-act=\"ready\">\u2705 LISTO</button></div>";
        }

        var numStr = String(o.order_number).padStart(3, "0");
        card.innerHTML = "<div class=\"card-top\">" +
            "<span class=\"card-num\">#" + numStr + "</span>" +
            typeBadge +
            "<span class=\"card-table\">" + self._esc(o.table_display || "") + "</span>" +
            "<span class=\"card-timer " + timerCls + "\">" + timerTxt + "</span></div>" +
            "<div class=\"card-items\">" + itemsHtml + "</div>" + actHtml;

        var appRef = this;
        card.addEventListener("click", function(e) {
            var btn = e.target.closest("[data-act]");
            if (!btn) return;
            var act = btn.dataset.act;
            var oid = parseInt(btn.dataset.oid);
            var order = appRef.orders.find(function(x) { return x.id === oid; });
            if (!order) return;

            var its = order.items;
            if (appRef.activeStation !== "all") {
                var sid3 = parseInt(appRef.activeStation);
                its = its.filter(function(i) { return i.station_id === sid3; });
            }
            var toUpdate = its.filter(function(i) {
                if (act === "preparing") return i.status === "sent";
                if (act === "ready") return i.status === "preparing";
                return false;
            });
            toUpdate.forEach(function(i) { appRef._updateItem(i.id, act); });
            btn.style.opacity = "0.5";
            btn.textContent = "\u23f3";
            setTimeout(function() { btn.style.opacity = "1"; }, 1000);
        });

        return card;
    },

    // ====== API ======
    _updateItem(itemId, status) {
        var token = localStorage.getItem("access_token") || "";
        fetch(CFG.api_base + "/kitchen/items/" + itemId + "/status", {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
            body: JSON.stringify({ status: status }),
        }).catch(function(e) { console.error("[KDS] Error:", e); });
    },

    _loadREST() {
        var token = localStorage.getItem("access_token") || "";
        var self = this;
        fetch(CFG.api_base + "/kitchen/pending", { headers: { "Authorization": "Bearer " + token } })
            .then(function(r) { if (r.ok) return r.json(); }).then(function(d) { if (d) { self.orders = d; self.render(); } }).catch(function(){});
        fetch(CFG.api_base + "/kitchen/stations", { headers: { "Authorization": "Bearer " + token } })
            .then(function(r) { if (r.ok) return r.json(); }).then(function(d) { if (d) { self.stations = d; self._renderStations(); } }).catch(function(){});
    },

    // ====== STATIONS ======
    _renderStations() {
        var nav = document.getElementById("stations");
        nav.querySelectorAll("[data-sid]:not([data-sid=\"all\"])").forEach(function(b) { b.remove(); });
        var self = this;
        this.stations.forEach(function(s) {
            var btn = document.createElement("button");
            btn.className = "st-pill";
            btn.dataset.sid = s.id;
            btn.innerHTML = (s.icon || "") + " " + (s.short_name || s.name) + " <span class=\"st-n\" id=\"n-s" + s.id + "\">0</span>";
            btn.addEventListener("click", function() { self._selectStation(s.id); });
            nav.appendChild(btn);
        });
    },

    _selectStation(sid) {
        this.activeStation = sid === this.activeStation ? "all" : sid;
        document.querySelectorAll(".st-pill").forEach(function(p) {
            var match = p.dataset.sid === String(APP.activeStation) || (APP.activeStation === "all" && p.dataset.sid === "all");
            p.classList.toggle("active", match);
        });
        this.render();
    },

    // ====== ALERTS ======
    _alertNew(data) {
        if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 300]);
        if (this.soundOn) {
            var snd = document.getElementById("snd-new");
            if (snd) { snd.currentTime = 0; snd.play().catch(function(){}); }
        }
        var el = document.getElementById("alert");
        var det = document.getElementById("alert-detail");
        det.textContent = data.order_number ? "#" + String(data.order_number).padStart(3, "0") : "";
        el.classList.remove("hide");
        setTimeout(function() { el.classList.add("hide"); }, 2000);
    },

    _setupSound() {
        var self = this;
        document.getElementById("btn-sound").addEventListener("click", function() {
            self.soundOn = !self.soundOn;
            this.textContent = self.soundOn ? "\ud83d\udd0a" : "\ud83d\udd07";
            if (self.soundOn) {
                var s = document.getElementById("snd-new");
                if (s) s.play().then(function() { s.pause(); s.currentTime = 0; }).catch(function(){});
            }
        });
    },

    _esc(s) {
        if (!s) return "";
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },
};

document.addEventListener("DOMContentLoaded", function() { APP.init(); });