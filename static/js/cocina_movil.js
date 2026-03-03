/* cocina_movil.js v2 - KDS Movil */
var CFG = window.KDS_CONFIG;
var KC = CFG.kitchen;

var APP = {
    orders: [],
    stations: [],
    activeStation: "all",
    soundOn: true,
    ws: null,
    _hb: null,
    _reconnectAttempts: 0,
    _audioCtx: null,

    init: function() {
        this._setupSound();
        this._setupStationAll();
        this._wsConnect();
        setTimeout(function() {
            if (APP.orders.length === 0) APP._loadREST();
        }, 5000);
    },

    // ====== AUDIO (Web Audio API, no .wav) ======
    _beep: function(freq, times, dur) {
        try {
            if (!this._audioCtx) this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            var ctx = this._audioCtx;
            for (var i = 0; i < times; i++) {
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = freq;
                osc.type = "square";
                gain.gain.value = 0.3;
                var start = ctx.currentTime + i * (dur + 0.1);
                osc.start(start);
                osc.stop(start + dur);
            }
        } catch(e) {}
    },

    // ====== WEBSOCKET ======
    _wsConnect: function() {
        var token = localStorage.getItem("access_token") || "";
        var url = CFG.ws_base + "/" + CFG.restaurant_id + "?token=" + token;
        if (CFG.station_id) url += "&station_id=" + CFG.station_id;

        this._setStatus(false);
        try { this.ws = new WebSocket(url); } catch(e) { this._reconnect(); return; }

        var self = this;
        this.ws.onopen = function() {
            self._setStatus(true);
            self._reconnectAttempts = 0;
            self._hb = setInterval(function() { try { self.ws.send("ping"); } catch(e){} }, 30000);
        };
        this.ws.onclose = function() {
            self._setStatus(false);
            clearInterval(self._hb);
            self._reconnect();
        };
        this.ws.onerror = function() {};
        this.ws.onmessage = function(e) {
            if (e.data === "pong") return;
            try { self._onMsg(JSON.parse(e.data)); } catch(ex) {}
        };
    },

    _reconnect: function() {
        this._reconnectAttempts++;
        var delay = Math.min(3000 * this._reconnectAttempts, 30000);
        setTimeout(function() { if (!APP.ws || APP.ws.readyState !== WebSocket.OPEN) APP._wsConnect(); }, delay);
    },

    _setStatus: function(on) {
        var el = document.getElementById("ws-status");
        el.className = on ? "status on" : "status off";
        el.textContent = on ? "\u2705" : "\u274c";
    },

    _onMsg: function(msg) {
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
    render: function() {
        var container = document.getElementById("orders");
        var empty = document.getElementById("empty");
        var filtered = this.orders.slice();

        if (this.activeStation !== "all") {
            var sid = parseInt(this.activeStation);
            filtered = this.orders.filter(function(o) {
                return o.items && o.items.some(function(i) { return i.station_id === sid; });
            });
        }

        filtered.sort(function(a, b) { return (b.kitchen_wait_minutes || 0) - (a.kitchen_wait_minutes || 0); });

        container.querySelectorAll(".card").forEach(function(c) { c.remove(); });

        if (filtered.length === 0) {
            empty.style.display = "flex";
        } else {
            empty.style.display = "none";
            for (var i = 0; i < filtered.length; i++) {
                container.appendChild(this._mkCard(filtered[i]));
            }
        }

        document.getElementById("order-count").textContent = this.orders.length;
        document.getElementById("n-all").textContent = this.orders.length;

        var self = this;
        this.stations.forEach(function(s) {
            var el = document.getElementById("n-s" + s.id);
            if (el) el.textContent = self.orders.filter(function(o) {
                return o.items && o.items.some(function(i) { return i.station_id === s.id; });
            }).length;
        });

        this._updateStationPills();
    },

    _mkCard: function(o) {
        var card = document.createElement("div");
        card.className = "card";
        card.dataset.s = o.status || "sent";
        card.dataset.oid = o.id;
        var wm = Math.round(o.kitchen_wait_minutes || 0);
        if (wm >= KC.alert_time_minutes) card.classList.add("late");

        var timerCls = "ok";
        if (wm >= KC.alert_time_minutes) timerCls = "late";
        else if (wm >= KC.warning_time_minutes) timerCls = "warn";
        var timerTxt = wm < 60 ? wm + "m" : Math.floor(wm / 60) + "h" + (wm % 60) + "m";

        var typeBadge = "";
        if (o.order_type === "delivery") typeBadge = "<span class=\"badge-type dlv\">\ud83d\udef5 DLV</span> ";
        else if (o.order_type === "takeaway") typeBadge = "<span class=\"badge-type tkw\">\ud83d\udce6 P/LL</span> ";

        var items = o.items || [];
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
            itemsHtml += "<div class=\"item\"><div class=\"item-dot " + (it.status || "sent") + "\"></div>" +
                "<div class=\"item-qty\">" + qd + "</div>" +
                "<div class=\"item-info\"><div class=\"item-name\">" + sz + self._esc(it.product_name) + "</div>" +
                mods + notes + "</div></div>";
        });

        var allSent = items.length > 0 && items.every(function(i) { return i.status === "sent"; });
        var allPrep = items.length > 0 && items.every(function(i) { return i.status === "preparing"; });
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

        var numStr = String(o.order_number || 0).padStart(3, "0");
        card.innerHTML = "<div class=\"card-top\">" +
            "<span class=\"card-num\">#" + numStr + "</span>" +
            typeBadge +
            "<span class=\"card-table\">" + self._esc(o.table_display || "") + "</span>" +
            "<span class=\"card-timer " + timerCls + "\">" + timerTxt + "</span></div>" +
            "<div class=\"card-items\">" + itemsHtml + "</div>" + actHtml;

        card.addEventListener("click", function(e) {
            var btn = e.target.closest("[data-act]");
            if (!btn) return;
            var act = btn.dataset.act;
            var oid = parseInt(btn.dataset.oid);
            var order = APP.orders.find(function(x) { return x.id === oid; });
            if (!order) return;

            var its = order.items || [];
            if (APP.activeStation !== "all") {
                var sid3 = parseInt(APP.activeStation);
                its = its.filter(function(i) { return i.station_id === sid3; });
            }
            var toUpdate = its.filter(function(i) {
                if (act === "preparing") return i.status === "sent";
                if (act === "ready") return i.status === "preparing";
                return false;
            });
            toUpdate.forEach(function(i) { APP._updateItem(i.id, act); });
            btn.style.opacity = "0.5";
            btn.textContent = "\u23f3";
            setTimeout(function() { btn.style.opacity = "1"; }, 1000);
        });

        return card;
    },

    // ====== API ======
    _updateItem: function(itemId, status) {
        var token = localStorage.getItem("access_token") || "";
        fetch(CFG.api_base + "/kitchen/items/" + itemId + "/status", {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
            body: JSON.stringify({ status: status }),
        }).catch(function(e) { console.error("[KDS]", e); });
    },

    _loadREST: function() {
        var token = localStorage.getItem("access_token") || "";
        fetch(CFG.api_base + "/kitchen/pending", { headers: { "Authorization": "Bearer " + token } })
            .then(function(r) { if (r.ok) return r.json(); })
            .then(function(d) { if (d) { APP.orders = d; APP.render(); } })
            .catch(function(){});
        fetch(CFG.api_base + "/kitchen/stations", { headers: { "Authorization": "Bearer " + token } })
            .then(function(r) { if (r.ok) return r.json(); })
            .then(function(d) { if (d) { APP.stations = d; APP._renderStations(); } })
            .catch(function(){});
    },

    // ====== STATIONS ======
    _setupStationAll: function() {
        var allBtn = document.querySelector("[data-sid=\"all\"]");
        if (allBtn) {
            allBtn.addEventListener("click", function() { APP._selectStation("all"); });
        }
    },

    _renderStations: function() {
        var nav = document.getElementById("stations");
        nav.querySelectorAll("[data-sid]:not([data-sid=\"all\"])").forEach(function(b) { b.remove(); });
        this.stations.forEach(function(s) {
            var btn = document.createElement("button");
            btn.className = "st-pill";
            btn.dataset.sid = s.id;
            btn.innerHTML = (s.icon || "") + " " + (s.short_name || s.name) + " <span class=\"st-n\" id=\"n-s" + s.id + "\">0</span>";
            btn.addEventListener("click", function() { APP._selectStation(s.id); });
            nav.appendChild(btn);
        });
    },

    _selectStation: function(sid) {
        if (sid === "all") {
            this.activeStation = "all";
        } else {
            this.activeStation = (this.activeStation === sid) ? "all" : sid;
        }
        this._updateStationPills();
        this.render();
    },

    _updateStationPills: function() {
        var as = this.activeStation;
        document.querySelectorAll(".st-pill").forEach(function(p) {
            var psid = p.dataset.sid;
            var isActive = false;
            if (as === "all") {
                isActive = (psid === "all");
            } else {
                isActive = (String(psid) === String(as));
            }
            p.classList.toggle("active", isActive);
        });
    },

    // ====== ALERTS ======
    _alertNew: function(data) {
        if (navigator.vibrate) navigator.vibrate([200, 100, 200, 100, 300]);
        if (this.soundOn) this._beep(880, 3, 0.2);

        var el = document.getElementById("alert");
        var det = document.getElementById("alert-detail");
        det.textContent = data.order_number ? "#" + String(data.order_number).padStart(3, "0") : "";
        el.classList.remove("hide");
        setTimeout(function() { el.classList.add("hide"); }, 2000);
    },

    _setupSound: function() {
        var self = this;
        document.getElementById("btn-sound").addEventListener("click", function() {
            self.soundOn = !self.soundOn;
            this.textContent = self.soundOn ? "\ud83d\udd0a" : "\ud83d\udd07";
            if (self.soundOn) self._beep(440, 1, 0.1);
        });
    },

    _esc: function(s) {
        if (!s) return "";
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },
};

document.addEventListener("DOMContentLoaded", function() { APP.init(); });