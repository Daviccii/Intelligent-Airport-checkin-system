// Admin functions (modular)
(function(){
    // Admin login form
    const adminForm = document.getElementById('adminForm');
    if (adminForm){
        adminForm.addEventListener('submit', async (e)=>{
            e.preventDefault();
            const username = document.getElementById('adminUsername')?.value || '';
            const password = document.getElementById('adminPassword')?.value || '';
            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ role: 'admin', username, password })
                });
                if (res.ok){
                    const data = await res.json();
                    try { localStorage.setItem('session', data.token); } catch(e){}
                    document.cookie = 'session=' + encodeURIComponent(data.token) + ';path=/';
                    showToast('Login successful!');
                    try{ const af = document.getElementById('adminForm'); if (af){ af.hidden = true; af.setAttribute('aria-hidden','true'); } }catch(e){}
                    try{ const at = document.getElementById('adminTools'); if (at){ at.hidden = false; at.setAttribute('aria-hidden','false'); } }catch(e){}
                    if (typeof loadFlights === 'function') loadFlights();
                } else {
                    showToast('Invalid credentials', 'error');
                }
            } catch (err){
                showToast('Login failed', 'error');
            }
        });
    }

    // Load flights for admin dashboard
    async function loadFlights(){
        try {
            const res = await fetch('/api/flights', { headers: {'X-SESSION': localStorage.getItem('session')} });
            if (!res.ok) throw new Error('Failed');
            const data = await res.json();
            const list = document.getElementById('flightsList');
            if (!list) return;
            // Render each flight; if origin/destination exist, expose links to the route
            list.innerHTML = data.flights.map(f => {
                // safe values
                const flight = f.flight || '';
                const time = f.time || 'N/A';
                const gate = f.gate || 'TBA';
                const airline = f.airline || f.aircraft || '';
                const bookings = f.bookings || 0;
                const capacity = f.capacity || '—';

                // Build route/link if origin/destination provided
                let routeHtml = '';
                if (f.origin && f.destination) {
                    const o = String(f.origin).toUpperCase();
                    const d = String(f.destination).toUpperCase();
                    // link to flight-results with from/to
                    const q = `from=${encodeURIComponent(o)}&to=${encodeURIComponent(d)}`;
                    routeHtml = `<div style="margin:6px 0"><a class="btn" href="/flight-results.html?${q}">${o} → ${d}</a> <button class="btn small" data-origin="${o}" data-destination="${d}" data-flight="${flight}">Open in Booking</button></div>`;
                } else {
                    // fallback: link to flight details page by flight number
                    routeHtml = `<div style="margin:6px 0"><a class="btn" href="/flight-results.html?flight=${encodeURIComponent(flight)}">Details</a></div>`;
                }

                return `
                <div class="card">
                    <strong style="display:block;margin-bottom:6px">${escapeHtml(flight)}</strong>
                    <p style="margin:0">Time: ${escapeHtml(time)}</p>
                    <p style="margin:0">Gate: ${escapeHtml(gate)}</p>
                    <p style="margin:0">Airline: ${escapeHtml(airline)}</p>
                    <p style="margin:0">Seats: ${bookings}/${escapeHtml(capacity)}</p>
                    ${routeHtml}
                    <div style="margin-top:8px;display:flex;gap:8px;align-items:center">
                        <button class="btn small admin-toggle-checkin" data-flight="${escapeHtml(flight)}">${f.checkin_enabled ? 'Disable' : 'Enable'} Check-in</button>
                        <button class="btn small admin-edit-flight" data-flight="${escapeHtml(flight)}" data-origin="${escapeHtml(f.origin||'')}" data-destination="${escapeHtml(f.destination||'')}">Edit</button>
                    </div>
                </div>`;
            }).join('');

            // Wire 'Open in Booking' buttons to prefill the booking widget (if present)
            Array.from(list.querySelectorAll('button[data-origin][data-destination]')).forEach(btn => {
                btn.addEventListener('click', (ev) => {
                    const o = btn.getAttribute('data-origin');
                    const d = btn.getAttribute('data-destination');
                    try{
                        // Prefill booking widget fields if available
                        const fromInput = document.getElementById('airportFromInput');
                        const toInput = document.getElementById('airportToInput');
                        const fromCode = document.getElementById('airportFromCode');
                        const toCode = document.getElementById('airportToCode');
                        if (fromInput) { fromInput.value = o; }
                        if (toInput) { toInput.value = d; }
                        if (fromCode) { fromCode.value = o; }
                        if (toCode) { toCode.value = d; }
                        // Ensure date selection is shown and focus departure if booking widget logic exists
                        try { if (typeof updateDateSelectionVisibility === 'function') updateDateSelectionVisibility(); } catch(e){}
                        try { if (typeof showPanel === 'function') showPanel('book'); } catch(e){ window.location.href = '/flight-results.html?from=' + encodeURIComponent(o) + '&to=' + encodeURIComponent(d); }
                    }catch(e){ console.error('prefill booking failed', e); }
                });
            });
            // wire toggle buttons
            Array.from(document.querySelectorAll('.admin-toggle-checkin')).forEach(b => {
                b.addEventListener('click', ()=> toggleCheckin(b.dataset.flight));
            });
                // wire edit buttons for admin to update origin/destination
                Array.from(document.querySelectorAll('.admin-edit-flight')).forEach(b => {
                    b.addEventListener('click', async (ev) => {
                        const flight = b.getAttribute('data-flight');
                        const currentOrigin = b.getAttribute('data-origin') || '';
                        const currentDest = b.getAttribute('data-destination') || '';
                        try {
                            const origin = (window.prompt('Origin IATA code (e.g. JFK)', currentOrigin) || '').trim().toUpperCase();
                            if (!origin) return;
                            const destination = (window.prompt('Destination IATA code (e.g. LHR)', currentDest) || '').trim().toUpperCase();
                            if (!destination) return;
                            const payload = { origin: origin, destination: destination };
                            const res = await fetch('/api/flights/' + encodeURIComponent(flight), {
                                method: 'PUT',
                                headers: {'Content-Type': 'application/json','X-SESSION': localStorage.getItem('session')},
                                body: JSON.stringify(payload)
                            });
                            if (res.ok){ showToast('Flight updated'); loadFlights(); }
                            else { const txt = await res.text(); showToast('Failed to update flight: ' + txt, 'error'); }
                        } catch (err){ console.error('edit flight failed', err); showToast('Error updating flight', 'error'); }
                    });
                });
        } catch (err){ showToast('Error loading flights', 'error'); }
    }

    // show modal to add flight
    function showAddFlightForm(){
        const m = document.getElementById('addFlightModal');
        if (!m) return;
        try{ m.style.display = 'flex'; m.hidden = false; m.setAttribute('aria-hidden','false'); }catch(e){} try{ m.inert = false; }catch(e){}
        trapFocus(m);
    }

    function hideAddFlightModal(){
        const m = document.getElementById('addFlightModal'); if (!m) return;
        try{ m.hidden = true; m.setAttribute('aria-hidden','true'); }catch(e){} try{ m.inert = true; }catch(e){}
        if (typeof releaseFocus === 'function') releaseFocus(m);
    }

    const addFlightForm = document.getElementById('addFlightForm');
    if (addFlightForm){
        addFlightForm.addEventListener('submit', async (e)=>{
            e.preventDefault();
            const flight = document.getElementById('newFlightNumber')?.value || '';
            const time = document.getElementById('newFlightTime')?.value || '';
            const aircraft = document.getElementById('newFlightAircraft')?.value || '';
            const gate = document.getElementById('newFlightGate')?.value || '';
            try {
                const res = await fetch('/api/flights', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json','X-SESSION': localStorage.getItem('session')},
                    body: JSON.stringify({ flight, time, aircraft, gate })
                });
                if (res.ok){ showToast('Flight created successfully'); hideAddFlightModal(); loadFlights(); }
                else showToast('Failed to create flight', 'error');
            } catch (err){ showToast('Error creating flight', 'error'); }
        });
    }

    async function toggleCheckin(flight){
        try {
            const res = await fetch(`/api/flights/${flight}/checkin-toggle`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json','X-SESSION': localStorage.getItem('session')}
            });
            if (res.ok){ showToast('Check-in status updated'); loadFlights(); } else showToast('Failed to update check-in status', 'error');
        } catch (err){ showToast('Error updating check-in status', 'error'); }
    }

    // Passenger helpers (used by admin passenger section)
    async function fetchPassengers(){
        try {
            const res = await fetch('/api/passengers', { headers: {'X-SESSION': localStorage.getItem('session')} });
            return res.ok ? await res.json() : [];
        } catch (err){ showToast('Error fetching passengers', 'error'); return []; }
    }

    function renderPassengerTable(data){
        const container = document.getElementById('passengersList'); if (!container) return;
        container.innerHTML = '';
        if (!data || !data.length){ container.innerHTML = '<div class="empty">No passengers found.</div>'; return; }
        const table = document.createElement('table'); table.className = 'pass-table';
        table.innerHTML = `
            <thead><tr><th>#</th><th>Name</th><th>Email</th><th>Passport</th><th>Flight</th><th>Status</th></tr></thead>
            <tbody>${data.map((p,i)=>`<tr><td>${i+1}</td><td>${escapeHtml(p.name)}</td><td>${escapeHtml(p.email||'')}</td><td>${escapeHtml(p.passport)}</td><td>${escapeHtml(p.flight)}</td><td>${p.checked_in? 'Checked In' : 'Registered'}</td></tr>`).join('')}</tbody>
        `;
        container.appendChild(table);
    }

    function escapeHtml(s){ return String(s||'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'})[c]); }

    async function refreshPassengerList(){
        const passengers = await fetchPassengers();
        const filterEl = document.getElementById('filterFlight');
        const filter = filterEl ? filterEl.value.trim().toLowerCase() : '';
        const filtered = filter ? passengers.filter(p => p.flight && p.flight.toLowerCase().includes(filter)) : passengers;
        renderPassengerTable(filtered);
    }

    function adminLogout(){
        localStorage.removeItem('session');
        document.cookie = 'session=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        try{ const af = document.getElementById('adminForm'); if (af){ af.hidden = false; af.setAttribute('aria-hidden','false'); } }catch(e){}
        try{ const at = document.getElementById('adminTools'); if (at){ at.hidden = true; at.setAttribute('aria-hidden','true'); } }catch(e){}
        showToast('Logged out successfully');
    }

    // Focus trap helpers
    function trapFocus(modal){
        if (!modal) return;
        modal._previouslyFocused = document.activeElement;
        const selectors = 'a[href], area[href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), iframe, [tabindex]:not([tabindex="-1"])';
        const nodes = Array.from(modal.querySelectorAll(selectors)).filter(n=>n.offsetParent !== null || n === document.activeElement);
        const first = nodes[0] || modal; const last = nodes[nodes.length-1] || first;
        function keyHandler(e){
            if (e.key === 'Tab'){
                if (nodes.length === 0){ e.preventDefault(); return; }
                if (e.shiftKey){ if (document.activeElement === first){ e.preventDefault(); last.focus(); } }
                else { if (document.activeElement === last){ e.preventDefault(); first.focus(); } }
            }
            if (e.key === 'Escape'){ if (modal.id === 'addFlightModal') hideAddFlightModal(); }
        }
        modal._focusHandler = keyHandler; document.addEventListener('keydown', keyHandler); try{ first.focus(); } catch(e){}
    }

    function releaseFocus(modal){ if (!modal) return; if (modal._focusHandler) document.removeEventListener('keydown', modal._focusHandler); if (modal._previouslyFocused && typeof modal._previouslyFocused.focus === 'function'){ try{ modal._previouslyFocused.focus(); } catch(e){} } delete modal._focusHandler; delete modal._previouslyFocused; }

    // admin UI helpers
    function showAdminSection(section){
        try{
            try{ const f = document.getElementById('adminFlights'); if (f){ f.classList.toggle('active', section === 'flights'); f.hidden = section !== 'flights'; f.setAttribute('aria-hidden', String(section !== 'flights')); } }catch(e){}
            try{ const p = document.getElementById('adminPassengers'); if (p){ p.classList.toggle('active', section === 'passengers'); p.hidden = section !== 'passengers'; p.setAttribute('aria-hidden', String(section !== 'passengers')); } }catch(e){}
            try{ const b = document.getElementById('adminBookings'); if (b){ b.classList.toggle('active', section === 'bookings'); b.hidden = section !== 'bookings'; b.setAttribute('aria-hidden', String(section !== 'bookings')); } }catch(e){}
            if (section === 'passengers') refreshPassengerList();
        } catch(e){}
    }

    // expose some admin helpers globaly for existing inline code
    window.loadFlights = loadFlights;
    window.showAddFlightForm = showAddFlightForm;
    window.hideAddFlightModal = hideAddFlightModal;
    window.refreshPassengerList = refreshPassengerList;
    window.adminLogout = adminLogout;
    window.trapFocus = trapFocus;
    window.releaseFocus = releaseFocus;
    window.showAdminSection = showAdminSection;
    window.toggleCheckin = toggleCheckin;
    window.fetchPassengers = fetchPassengers;
    window.renderPassengerTable = renderPassengerTable;
    window.refreshFlights = loadFlights;

})();
