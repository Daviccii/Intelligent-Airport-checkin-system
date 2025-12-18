// Panels, toasts, search and check-in handlers
// Migrated from frontend/index.html
(function(){
    // expose showPanel globally
    window.SMF_PANEL_PROTECTION_MS = window.SMF_PANEL_PROTECTION_MS || 2000;

    // Persistent panel-change trace storage (keeps last N entries in localStorage)
    window.SMF_PANEL_TRACE_KEY = window.SMF_PANEL_TRACE_KEY || 'smartfly.panelTraces';
    window.SMF_PANEL_TRACE_MAX = window.SMF_PANEL_TRACE_MAX || 25;

    function _getPanelTraces(){
        try{
            var raw = localStorage.getItem(window.SMF_PANEL_TRACE_KEY);
            if (!raw) return [];
            var parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) return [];
            return parsed;
        }catch(e){ return []; }
    }

    function _savePanelTraces(arr){
        try{ localStorage.setItem(window.SMF_PANEL_TRACE_KEY, JSON.stringify(arr)); } catch(e){}
    }

    function _recordPanelTrace(panelId, stackText){
        try{
            var traces = _getPanelTraces();
            var entry = {
                ts: (new Date()).toISOString(),
                panel: panelId || null,
                stack: (typeof stackText === 'string') ? stackText.split('\n').slice(0,12) : []
            };
            traces.push(entry);
            // keep only the last N entries
            if (traces.length > (window.SMF_PANEL_TRACE_MAX || 25)) traces = traces.slice(- (window.SMF_PANEL_TRACE_MAX || 25));
            _savePanelTraces(traces);
        }catch(e){ /* no-op */ }
    }

    // Console helpers for quick inspection
    window.getPanelTraces = function(){ return _getPanelTraces(); };
    window.printPanelTraces = function(){ try{ console.groupCollapsed('SmartFly panelTraces'); var t=_getPanelTraces(); t.forEach((e,i)=>{ console.log(i, e.ts, e.panel); console.log(e.stack.join('\n')); }); console.groupEnd(); return t; }catch(e){ console.error('[printPanelTraces] failed', e); return []; } };

    // Defensive: remove the tiny pre-hydration style as soon as this script runs
    // so that a later JS error cannot leave all panels hidden by the injected CSS.
    try {
        var __ph = document && document.querySelector && document.querySelector('style[data-panel-hydrate]');
        if (__ph && __ph.parentNode) __ph.parentNode.removeChild(__ph);
    } catch(e) { /* noop */ }

    // queued showPanel executor — process requests one-at-a-time with deduplication
    window.__smf_showPanel_queue = window.__smf_showPanel_queue || [];
    window.__smf_showPanel_busy = window.__smf_showPanel_busy || false;
    // lower default spacing but keep configurable: small value reduces perceived lag
    window.SMF_SHOWPANEL_LOCK_MS = window.SMF_SHOWPANEL_LOCK_MS || 250; // ms spacing between activations

    window.showPanel = function(id){
        try{
            id = (typeof id === 'string') ? id.trim() : String(id || '');
            if (!id) return;

            // If panel is already visible, no-op (dedupe at source)
            try{ var cp = document.getElementById(id + 'Panel'); if (cp && cp.classList && cp.classList.contains('active')) return; }catch(e){}

            // If a queued request for this id already exists, move it to the end (make it most-recent)
            var existing = window.__smf_showPanel_queue.findIndex(function(q){ return q && q.id === id; });
            if (existing !== -1){
                var it = window.__smf_showPanel_queue.splice(existing,1)[0];
                it.ts = Date.now();
                window.__smf_showPanel_queue.push(it);
            } else {
                window.__smf_showPanel_queue.push({ id: id, ts: Date.now() });
            }

            if (!window.__smf_showPanel_busy) processShowQueue();
        }catch(e){ console.error('[showPanel] enqueue failed', e); }
    };

    // Drain any early queued `showPanel` calls that were made before this
    // script loaded. Callers earlier in the page may have invoked the stub
    // `window.showPanel` which simply pushed names into
    // `window.__smf_boot_showPanel`. Consume that bootstrap queue now so all
    // panel activations go through the centralized, queued executor.
    try{
        var __bq = window.__smf_boot_showPanel || [];
        if (Array.isArray(__bq) && __bq.length){
            var _q = __bq.slice();
            try{ window.__smf_boot_showPanel = []; }catch(e){}
            _q.forEach(function(name, i){
                setTimeout(function(){ try{ showPanel(name); }catch(e){} }, i * 40);
            });
        }
    }catch(e){ /* noop */ }

    function processShowQueue(){
        if (window.__smf_showPanel_busy) return;
        var item = window.__smf_showPanel_queue.shift();
        if (!item) return;
        window.__smf_showPanel_busy = true;

        // record stack & persist a short trace for debugging
        try {
            var __stack = (new Error()).stack || '';
            var __lines = __stack.split('\n').slice(1,6).map(function(l){ return l.trim(); }).join('\n');
            console.debug('[showPanel-queue] processing ->', item.id, '\n', __lines);
            try{ _recordPanelTrace(item.id, __lines); }catch(e){}
        }catch(e){}

        var id = item.id;

        // Remove any subsequent queued identical requests (they are redundant)
        try{ window.__smf_showPanel_queue = window.__smf_showPanel_queue.filter(function(q){ return !q || q.id !== id; }); }catch(e){}

        const panel = document.getElementById((id || '') + 'Panel');
        if (!panel) {
            console.warn('[showPanel-queue] panel not found', id);
            // release and continue
            window.__smf_showPanel_busy = false;
            setTimeout(processShowQueue, 0);
            return;
        }

        try{
            if (panel.classList && panel.classList.contains('active')){
                try{ panel.setAttribute('aria-hidden','false'); }catch(e){}
                // very short pause before next request
                setTimeout(function(){ window.__smf_showPanel_busy = false; processShowQueue(); }, 30);
                return;
            }
        }catch(e){}

        document.querySelectorAll('.action-panel').forEach(function(p){
            try{ if (p.hasAttribute && p.hasAttribute('data-protected')) return; }catch(e){}
            try{ p.classList.remove('active'); p.setAttribute('aria-hidden','true'); }catch(e){}
        });

        try{ panel.classList.add('active'); panel.setAttribute('aria-hidden','false'); }catch(e){}
        if (id === 'home'){
            try{ panel.setAttribute('data-protected','1'); setTimeout(function(){ panel.removeAttribute('data-protected'); }, parseInt(window.SMF_PANEL_PROTECTION_MS,10)||2000); }catch(e){}
        }

        document.querySelectorAll('.header-tabs .tab-link').forEach(function(t){
            t.classList.remove('active');
            try{ t.setAttribute('aria-selected','false'); }catch(e){}
            try{ t.setAttribute('tabindex','-1'); }catch(e){}
        });
        const hdr = document.querySelector('.header-tabs .tab-link[data-key="' + (id||'') + '"]');
        if (hdr) {
            hdr.classList.add('active');
            try{ hdr.setAttribute('aria-selected','true'); }catch(e){}
            try{ hdr.setAttribute('tabindex','0'); }catch(e){}
        }
        try{ window.announcePanel && window.announcePanel(id); }catch(e){}

        // spacing window (smaller) to allow other scripts to enqueue safely
        setTimeout(function(){ window.__smf_showPanel_busy = false; processShowQueue(); }, parseInt(window.SMF_SHOWPANEL_LOCK_MS,10) || 250);
    }

    window.showToast = function(message, type = 'success'){
        const container = document.getElementById('toastContainer'); if (!container) return;
        const toast = document.createElement('div'); toast.className = `toast ${type}`;
        toast.innerHTML = `${message}<button onclick="this.parentElement.remove()" style="background:none;border:none;color:white;margin-left:10px">×</button>`;
        container.appendChild(toast); setTimeout(()=>toast.remove(), 3000);
    };

    window.announcePanel = function(key){
        if (!key) return;
        const names = {
            home: 'Home', explore: 'Explore', plan: 'Plan', book: 'Book and Manage', experience: 'Experience', loyalty: 'Loyalty Program', help: 'Help', flights: 'Flight Information', checkin: 'Check-in', admin: 'Admin'
        };
        const label = names[key] || key;
        try{
            const el = document.getElementById('panelAnnouncer'); if(!el) return; el.textContent = `${label} panel opened.`;
        }catch(e){}
    };

    // Flight Search handler (delegated)
    function initFlightSearch(){
        const searchForm = document.getElementById('searchForm');
        if (!searchForm) return;
        searchForm.addEventListener('submit', async (e)=>{
            e.preventDefault();
            const flight = document.getElementById('searchFlight')?.value || '';
            try {
                const res = await fetch('/api/flights');
                const data = await res.json();
                const found = (data && data.flights) ? data.flights.find(f => f.flight === flight) : null;
                const results = document.getElementById('searchResults');
                if (found && results) {
                    results.innerHTML = `<div class="card"><h4>${found.flight}</h4><p>Time: ${found.time||'N/A'}</p><p>Gate: ${found.gate||'TBA'}</p><p>Status: ${found.checkin_enabled ? 'Check-in Open' : 'Check-in Closed'}</p></div>`;
                } else if (results) {
                    results.innerHTML = '<p class="error">Flight not found</p>';
                }
            } catch(err){ window.showToast && window.showToast('Error searching flights','error'); }
        });
    }

    // Check-in handler
    function initCheckin(){
        const checkinForm = document.getElementById('checkinForm'); if (!checkinForm) return;
        checkinForm.addEventListener('submit', async (e)=>{
            e.preventDefault();
            const name = document.getElementById('name')?.value.trim() || '';
            const email = document.getElementById('email')?.value.trim() || '';
            const passport = document.getElementById('passport')?.value.trim() || '';
            const flight = document.getElementById('flight')?.value.trim() || '';
            try {
                const res = await fetch('/api/register', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name,email,passport,flight}) });
                const data = await res.json().catch(()=>({}));
                if (res.ok){ window.showToast && window.showToast('Check-in successful!'); window.location.href = `/api/boardingpass?passport=${encodeURIComponent(passport)}`; }
                else window.showToast && window.showToast(data.error||'Check-in failed','error');
            } catch(e){ window.showToast && window.showToast('Error during check-in','error'); }
        });
    }

    // Admin delegators
    window.showAdminSection = function(section){
        try{
            var f = document.getElementById('adminFlights'); var p = document.getElementById('adminPassengers'); var b = document.getElementById('adminBookings');
            if (f) { f.classList.toggle('active', section === 'flights'); f.setAttribute('aria-hidden', section === 'flights' ? 'false' : 'true'); }
            if (p) { p.classList.toggle('active', section === 'passengers'); p.setAttribute('aria-hidden', section === 'passengers' ? 'false' : 'true'); }
            if (b) { b.classList.toggle('active', section === 'bookings'); b.setAttribute('aria-hidden', section === 'bookings' ? 'false' : 'true'); }
            if (section==='passengers' && typeof window.refreshPassengerList === 'function') window.refreshPassengerList();
        }catch(e){}
    };
    window.refreshFlights = function(){ if (typeof window.loadFlights === 'function') return window.loadFlights(); };
    window.toggleCheckin = function(flight){ if (typeof window.toggleCheckin === 'function') return window.toggleCheckin(flight); };

    // Header / tabs behaviour (uses showPanel)
    function initHeaderTabs(){
        const headerTabs = Array.from(document.querySelectorAll('.header-tabs .tab-link'));
        if(!headerTabs.length) return;
        function activate(key, updateHash = true){
            const k = key || 'home';
            const panel = document.getElementById(k + 'Panel');
            if(!panel){ console.warn('[tabs] panel not found for', k); return; }
            document.querySelectorAll('.action-panel').forEach(p => { try { if (p.hasAttribute && p.hasAttribute('data-protected')) return; } catch(e){} try { p.classList.remove('active'); p.setAttribute('aria-hidden','true'); } catch(e){} });
            try { panel.classList.add('active'); panel.setAttribute('aria-hidden','false'); } catch(e){}
            headerTabs.forEach(t => { const is = (t.dataset.key === k); t.classList.toggle('active', is); try { t.setAttribute('aria-selected', is ? 'true' : 'false'); } catch(e){} try { t.setAttribute('tabindex', is ? '0' : '-1'); } catch(e){} });
            try { const focusable = panel.querySelector('input,button,a,select,textarea,[tabindex]:not([tabindex="-1"])'); if (focusable) focusable.focus(); } catch(e){}
            try { localStorage.setItem('smartfly.activeTab', k); } catch(e){}
            if (updateHash) { try { history.replaceState(null, '', '#' + k); } catch(e){} }
        }

        headerTabs.forEach((tab, i) => {
            tab.setAttribute('role','tab');
            if (!tab.hasAttribute('tabindex')) tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');
            if (!tab.hasAttribute('aria-selected')) tab.setAttribute('aria-selected', tab.classList.contains('active') ? 'true' : 'false');

            // If the tab is a plain anchor link to another page (no data-key), don't hijack clicks.
            const key = tab.dataset && tab.dataset.key ? tab.dataset.key : null;
            const isAnchorNav = (!key && tab.tagName === 'A' && tab.getAttribute('href') && !tab.getAttribute('href').startsWith('#'));
            if (!isAnchorNav) {
                tab.addEventListener('click', (e) => { try { e.preventDefault(); } catch(e){} const k = key || 'home'; try { sessionStorage.setItem('smartfly.interacted', '1'); } catch(e){} activate(k); });

                tab.addEventListener('keydown', (e) => {
                    if (e.key === 'ArrowRight') { e.preventDefault(); headerTabs[(i+1) % headerTabs.length].focus(); }
                    else if (e.key === 'ArrowLeft') { e.preventDefault(); headerTabs[(i-1 + headerTabs.length) % headerTabs.length].focus(); }
                    else if (e.key === 'Home') { e.preventDefault(); headerTabs[0].focus(); }
                    else if (e.key === 'End') { e.preventDefault(); headerTabs[headerTabs.length-1].focus(); }
                    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); tab.click(); }
                });
            }
        });

        let initial = (location.hash || '').replace('#','') || localStorage.getItem('smartfly.activeTab') || 'home';
        if (!document.getElementById(initial + 'Panel')) initial = 'home';
        try { const interacted = sessionStorage.getItem('smartfly.interacted'); if (!interacted && initial !== 'home') initial = 'home'; } catch(e){}
        activate(initial, false);
        window.addEventListener('hashchange', ()=>{ const k = (location.hash || '').replace('#','') || 'home'; activate(k, false); });
    }

    // Safety fallback: ensure visible panel after load
    function safetyFallback(){
        function isPanelVisible(el){ if(!el) return false; if (el.classList && el.classList.contains('active')) return true; try { const cs = window.getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity || '1') > 0; } catch(e){ return false; } }
        window.addEventListener('load', ()=>{ setTimeout(()=>{ const panels = Array.from(document.querySelectorAll('.action-panel')); const visible = panels.filter(isPanelVisible); if (visible.length === 0) { try { localStorage.removeItem('smartfly.activeTab'); } catch(e) {} if (typeof showPanel === 'function') { try { showPanel('home'); return; } catch(e){} } const hp = document.getElementById('homePanel'); if (hp) { try { hp.classList.add('active'); } catch(e){} } } }, 500); });
    }

    function init(){
        // Migration shim: clear inline display styles on panels and panes to avoid style races
        try{
            Array.from(document.querySelectorAll('.action-panel, .pane, .admin-section')).forEach(function(el){ try{ if (el && el.style && el.style.removeProperty) el.style.removeProperty('display'); }catch(e){} });
        }catch(e){}

        // Mutation observer: if other scripts attempt to set inline `style.display` on panels,
        // convert that intent to class toggles and remove the inline style to avoid race conditions.
        try{
            var _observer = new MutationObserver(function(mutations){
                mutations.forEach(function(m){
                    try{
                        if (m.type !== 'attributes' || m.attributeName !== 'style') return;
                        var el = m.target;
                        if (!el || !el.classList) return;
                        if (!el.classList.contains('action-panel')) return;
                        var inline = el.style.display;
                        if (inline && inline.length){
                            // capture intent then remove inline display
                            var val = inline.trim();
                            try{ el.style.removeProperty('display'); }catch(e){}
                            if (val === 'none') { el.classList.remove('active'); el.setAttribute('aria-hidden','true'); }
                            else { el.classList.add('active'); el.setAttribute('aria-hidden','false'); }
                        }
                    }catch(e){}
                });
            });
            _observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['style'] });
        }catch(e){}

        // Class-change observer: ensure only one .action-panel has the `active` class
        // This prevents other scripts that directly toggle classes from leaving multiple panels visible.
        try{
            var _classObserver = new MutationObserver(function(mutations){
                mutations.forEach(function(m){
                    try{
                        if (m.type !== 'attributes' || m.attributeName !== 'class') return;
                        var el = m.target;
                        if (!el || !el.classList) return;
                        if (!el.classList.contains('action-panel')) return;
                        // If this panel just became active, remove active from others (respecting data-protected)
                        if (el.classList.contains('active')){
                            // Capture a caller stack to help identify who activated this panel
                            var __stack = (new Error()).stack || '';
                            var __stackLines = __stack.split('\n').slice(1,12).map(function(l){ return l.trim(); }).join('\n');

                            // Find other active panels; if any exist, log a warning with stack trace
                            var others = Array.from(document.querySelectorAll('.action-panel.active')).filter(function(p){ return p !== el; });
                            if (others.length){
                                try{
                                    var ids = others.map(function(p){ try{ return p.id || p.getAttribute('id') || p.className; }catch(e){ return String(p); } });
                                    console.warn('[panels] conflicting activation: panel', (el.id||el.getAttribute('id')||el.className), 'became active while other panels were active:', ids, '\nCaller stack:\n' + __stackLines);
                                    try { _recordPanelTrace((el.id||el.getAttribute('id')||'unknown'), __stackLines); } catch(e){}
                                }catch(e){ /* noop */ }
                            }

                            document.querySelectorAll('.action-panel.active').forEach(function(p){
                                try{
                                    if (p === el) return;
                                    if (p.hasAttribute && p.hasAttribute('data-protected')) return;
                                    // record why this panel was removed
                                    try { _recordPanelTrace((p.id||p.getAttribute('id')||'unknown'), __stackLines); } catch(e){}
                                    p.classList.remove('active');
                                    p.setAttribute('aria-hidden','true');
                                }catch(e){}
                            });
                            try{ el.setAttribute('aria-hidden','false'); }catch(e){}
                        }
                    }catch(e){}
                });
            });
            _classObserver.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['class'] });
        }catch(e){}

        initFlightSearch(); initCheckin(); initHeaderTabs(); safetyFallback();
        // Remove pre-hydration style injected in <head> when present
        try {
            var ph = document.querySelector('style[data-panel-hydrate]');
            if (ph && ph.parentNode) ph.parentNode.removeChild(ph);
        } catch(e){}
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
