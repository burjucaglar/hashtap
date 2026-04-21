/* HashTap KDS — polling-based live updates + touch action handlers.
   Tasarım notu: Odoo'nun OWL / asset bundle sistemine sokmadık; bu sayfa
   tamamen vanilla JS ve salt HashTap ürünü gibi hissettiriyor.
*/
(function () {
    "use strict";

    const POLL_MS = 3000;
    const WARN_AFTER_SEC = 10 * 60;   // 10 dk sonra sarı
    const DANGER_AFTER_SEC = 20 * 60; // 20 dk sonra kırmızı + pulse

    const els = {
        statusDot:  document.getElementById("kds-status-dot"),
        statusText: document.getElementById("kds-status-text"),
        clock:      document.getElementById("kds-clock"),
        cols: {
            new:        document.getElementById("col-new"),
            preparing:  document.getElementById("col-preparing"),
            ready:      document.getElementById("col-ready"),
        },
        counts: {
            new:        document.getElementById("count-new"),
            preparing:  document.getElementById("count-preparing"),
            ready:      document.getElementById("count-ready"),
        },
    };

    let pollTimer = null;
    let knownIds = new Set();
    let lastPayload = [];

    // ---------------------------------------------------------- utils --
    function jsonRpc(url, params) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0", method: "call", params: params || {},
            }),
        }).then((r) => r.json()).then((j) => j.result || {});
    }

    function pad2(n) { return String(n).padStart(2, "0"); }

    function tickClock() {
        const d = new Date();
        els.clock.textContent = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
    }
    setInterval(tickClock, 1000);
    tickClock();

    function elapsedSec(iso) {
        if (!iso) return 0;
        const t = new Date(iso).getTime();
        if (isNaN(t)) return 0;
        return Math.max(0, Math.floor((Date.now() - t) / 1000));
    }

    function formatElapsed(sec) {
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${pad2(m)}:${pad2(s)}`;
    }

    function setStatus(online, text) {
        els.statusDot.classList.toggle("online", !!online);
        els.statusDot.classList.toggle("offline", !online);
        els.statusText.textContent = text;
    }

    // ---------------------------------------------------------- render --
    function renderCard(order) {
        const card = document.createElement("article");
        card.className = "kds-card";
        card.dataset.id = order.id;
        card.dataset.state = order.state;

        const head = document.createElement("div");
        head.className = "kds-card-head";

        const table = document.createElement("span");
        table.className = "kds-table";
        table.textContent = order.table || "—";

        const ref = document.createElement("span");
        ref.className = "kds-ref";
        ref.textContent = order.reference || "";

        const elapsed = document.createElement("span");
        elapsed.className = "kds-elapsed";
        elapsed.dataset.fired = order.fired_at || "";
        head.appendChild(table);
        head.appendChild(ref);
        head.appendChild(elapsed);

        const lines = document.createElement("ul");
        lines.className = "kds-lines";
        (order.lines || []).forEach((ln) => {
            const li = document.createElement("li");
            const qty = document.createElement("span");
            qty.className = "kds-line-qty";
            qty.textContent = `${ln.quantity}×`;
            const name = document.createElement("span");
            name.className = "kds-line-name";
            name.textContent = ln.item_name;
            if (ln.modifier_names && ln.modifier_names.length) {
                const mods = document.createElement("span");
                mods.className = "kds-line-mods";
                mods.textContent = ln.modifier_names.join(", ");
                name.appendChild(mods);
            }
            if (ln.note) {
                const nt = document.createElement("span");
                nt.className = "kds-line-note";
                nt.textContent = `not: ${ln.note}`;
                name.appendChild(nt);
            }
            li.appendChild(qty);
            li.appendChild(name);
            lines.appendChild(li);
        });

        const note = document.createElement("div");
        note.className = "kds-note";
        if (order.customer_note) {
            note.textContent = `Müşteri notu: ${order.customer_note}`;
        }

        const actions = document.createElement("div");
        actions.className = "kds-actions";
        const recall = document.createElement("button");
        recall.className = "kds-btn kds-btn-secondary kds-recall";
        recall.textContent = "Geri Al";
        recall.addEventListener("click", () => recallOrder(order.id));
        const advance = document.createElement("button");
        advance.className = "kds-btn kds-btn-primary kds-advance";
        advance.addEventListener("click", () => advanceOrder(order.id));
        actions.appendChild(recall);
        actions.appendChild(advance);

        card.appendChild(head);
        card.appendChild(lines);
        card.appendChild(note);
        card.appendChild(actions);
        return card;
    }

    function paintElapsed() {
        document.querySelectorAll(".kds-elapsed").forEach((el) => {
            const iso = el.dataset.fired;
            if (!iso) { el.textContent = ""; return; }
            const sec = elapsedSec(iso);
            el.textContent = formatElapsed(sec);
            const card = el.closest(".kds-card");
            if (!card) return;
            card.classList.toggle("is-warn",
                sec >= WARN_AFTER_SEC && sec < DANGER_AFTER_SEC);
            card.classList.toggle("is-danger", sec >= DANGER_AFTER_SEC);
        });
    }
    setInterval(paintElapsed, 1000);

    function render(orders) {
        lastPayload = orders || [];
        const buckets = { new: [], preparing: [], ready: [] };
        (orders || []).forEach((o) => {
            const col = o.column || "new";
            if (buckets[col]) buckets[col].push(o);
        });

        Object.keys(buckets).forEach((key) => {
            const container = els.cols[key];
            container.innerHTML = "";
            buckets[key].forEach((o) => container.appendChild(renderCard(o)));
            els.counts[key].textContent = buckets[key].length;
        });
        paintElapsed();

        // Yeni sipariş sesli uyarı — basit beep (Opsiyonel).
        const nowIds = new Set((orders || []).map((o) => o.id));
        const fresh = [];
        nowIds.forEach((id) => { if (!knownIds.has(id)) fresh.push(id); });
        if (fresh.length && knownIds.size) beep();
        knownIds = nowIds;
    }

    // ---------------------------------------------------------- audio --
    let audioCtx = null;
    function beep() {
        try {
            if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.type = "sine"; osc.frequency.value = 880;
            gain.gain.value = 0.08;
            osc.start();
            setTimeout(() => osc.stop(), 180);
        } catch (e) { /* sessiz başarısızlık */ }
    }

    // ---------------------------------------------------------- actions --
    function advanceOrder(id) {
        jsonRpc(`/hashtap/kds/order/${id}/advance`, {}).then(() => poll());
    }
    function recallOrder(id) {
        jsonRpc(`/hashtap/kds/order/${id}/recall`, {}).then(() => poll());
    }

    // ---------------------------------------------------------- loop --
    function poll() {
        jsonRpc("/hashtap/kds/orders.json", {})
            .then((res) => {
                setStatus(true, "Canlı");
                render(res.orders || []);
            })
            .catch(() => setStatus(false, "Bağlantı yok"));
    }

    function start() {
        poll();
        pollTimer = setInterval(poll, POLL_MS);
    }

    // İlk dokunuşta AudioContext'i aktive et (Safari için gerekli).
    document.addEventListener("click", function initAudio() {
        try { if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) {}
        document.removeEventListener("click", initAudio);
    }, { once: true });

    start();
})();
