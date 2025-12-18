// Booking widget helpers, bookings loader, swap handler and loyalty form
// Migrated from frontend/index.html
(function(){
    function init(){
        // Lookup booking by reference (button exists in book panel)
        document.getElementById('lookupBookingBtn')?.addEventListener('click', ()=>{
            const ref = document.getElementById('bookingRefInput')?.value.trim();
            if(!ref){ alert('Enter a booking reference'); return; }
            window.location.href = 'lookup.html?ref=' + encodeURIComponent(ref);
        });

        // Load bookings (try API, fallback to localStorage sample)
        async function loadBookings(){
            const container = document.getElementById('bookingsList'); if(!container) return;
            container.innerHTML = '<p>Loading…</p>';
            try{
                const resp = await fetch('/api/bookings');
                if(!resp.ok) throw new Error('no-api');
                const data = await resp.json();
                renderBookings(data.bookings || data || []);
            }catch(e){
                const saved = localStorage.getItem('smartfly_bookings');
                if(saved){ try{ renderBookings(JSON.parse(saved)); return; }catch(err){} }
                container.innerHTML = '<p>No bookings available. Use <a href="lookup.html">Booking Lookup</a> or create a booking using the search above.</p>';
            }
        }

        function renderBookings(list){
            const container = document.getElementById('bookingsList'); if(!container) return;
            if(!list || !list.length){ container.innerHTML = '<p>No bookings found.</p>'; return; }
            const out = document.createElement('div'); out.className='data-grid'; out.style.gridTemplateColumns='repeat(auto-fit,minmax(260px,1fr))'; out.style.gap='12px';
            list.forEach(b => {
                const card = document.createElement('div'); card.className='card';
                const ref = b.ref||b.bookingRef||b.reference||'—';
                const flight = b.flight||b.flightNumber||'TBA';
                card.innerHTML = `<h4>Ref: ${ref}</h4><p>Flight: ${flight}</p><p>Date: ${b.date||b.departure||'TBA'}</p><div style="margin-top:8px"><a class="btn" href="lookup.html?ref=${encodeURIComponent(ref)}">Manage</a></div>`;
                out.appendChild(card);
            });
            container.innerHTML=''; container.appendChild(out);
        }

        document.getElementById('loadBookingsBtn')?.addEventListener('click', loadBookings);

        // Loyalty form
        document.getElementById('loyaltyForm')?.addEventListener('submit', (e)=>{
            e.preventDefault();
            const name = document.getElementById('lfName')?.value.trim();
            const email = document.getElementById('lfEmail')?.value.trim();
            if(!name||!email){ document.getElementById('loyaltyMsg').textContent = 'Please provide name and email.'; return; }
            const mem = {name,email,joined: new Date().toISOString()};
            const members = JSON.parse(localStorage.getItem('smartfly_members')||'[]'); members.push(mem); localStorage.setItem('smartfly_members', JSON.stringify(members));
            document.getElementById('loyaltyMsg').innerHTML = '<strong>Welcome to SmartFly Rewards — check your email for confirmation.</strong>';
            document.getElementById('loyaltyForm').reset();
        });

        // Swap handler
        try {
            const swapBtn = document.getElementById('swapAirports');
            const from = document.getElementById('airportFromInput');
            const to = document.getElementById('airportToInput');
            if (swapBtn && from && to){
                swapBtn.addEventListener('click', (e)=>{
                    swapBtn.classList.add('is-rotating');
                    setTimeout(()=> swapBtn.classList.remove('is-rotating'), 380);
                    const vFrom = from.value; const vTo = to.value; from.value = vTo; to.value = vFrom;
                    [from, to].forEach(i=>{ i.classList.add('swap-flash'); setTimeout(()=>i.classList.remove('swap-flash'), 520); });
                    setTimeout(()=>{ try{ to.focus(); } catch(e){} }, 180);
                });
            }
        } catch(e){ console.error('[swapAirports] init failed', e); }

        // Load flights for homepage widgets (public-facing)
        async function loadHomeFlights(){
            const container = document.getElementById('flightsList'); if(!container) return;
            container.innerHTML = '<p>Loading flights…</p>';
            function esc(s){ return String(s||'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'})[c]); }
            try{
                const res = await fetch('/api/flights');
                if(!res.ok) throw new Error('fetch-failed');
                const j = await res.json();
                const flights = j.flights || [];
                if(!flights.length){ container.innerHTML = '<div class="empty">No scheduled flights.</div>'; return; }
                const out = document.createElement('div'); out.className='data-grid'; out.style.gridTemplateColumns='repeat(auto-fit,minmax(260px,1fr))'; out.style.gap='12px';
                flights.forEach(f=>{
                    const flight = f.flight || '';
                    const time = f.time ? new Date(f.time).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : 'TBD';
                    const gate = f.gate || 'TBA';
                    const airline = f.airline || f.aircraft || '';
                    const bookings = f.bookings || 0;
                    const capacity = f.capacity || '—';
                    let routeHtml = '';
                    if (f.origin && f.destination){
                        const o = String(f.origin).toUpperCase();
                        const d = String(f.destination).toUpperCase();
                        const q = `from=${encodeURIComponent(o)}&to=${encodeURIComponent(d)}`;
                        routeHtml = `<div style="margin:6px 0"><a class="btn" href="/flight-results.html?${q}">${esc(o)} → ${esc(d)}</a> <button class="btn small open-in-booking" data-origin="${esc(o)}" data-destination="${esc(d)}">Open in Booking</button></div>`;
                    } else {
                        routeHtml = `<div style="margin:6px 0"><a class="btn" href="/flight-results.html?flight=${encodeURIComponent(flight)}">Details</a></div>`;
                    }
                    const card = document.createElement('div'); card.className='card';
                    card.innerHTML = `
                        <h4 style="margin:0 0 6px">${esc(flight)}</h4>
                        <p style="margin:0">${esc(airline)} • ${esc(time)} • Gate ${esc(gate)}</p>
                        <p style="margin:6px 0 0">Seats: ${bookings}/${esc(capacity)}</p>
                        ${routeHtml}
                    `;
                    out.appendChild(card);
                });
                container.innerHTML = ''; container.appendChild(out);

                // Wire open-in-booking buttons
                Array.from(container.querySelectorAll('button.open-in-booking')).forEach(btn=>{
                    btn.addEventListener('click', ()=>{
                        const o = btn.getAttribute('data-origin');
                        const d = btn.getAttribute('data-destination');
                        try{
                            const fromInput = document.getElementById('airportFromInput');
                            const toInput = document.getElementById('airportToInput');
                            const fromCode = document.getElementById('airportFromCode');
                            const toCode = document.getElementById('airportToCode');
                            if(fromInput) fromInput.value = o;
                            if(toInput) toInput.value = d;
                            if(fromCode) fromCode.value = o;
                            if(toCode) toCode.value = d;
                            try{ if (typeof updateDateSelectionVisibility === 'function') updateDateSelectionVisibility(); }catch(e){}
                            try{ if (typeof showPanel === 'function') showPanel('book'); else window.location.href = '/flight-results.html?from=' + encodeURIComponent(o) + '&to=' + encodeURIComponent(d); }catch(e){ window.location.href = '/flight-results.html?from=' + encodeURIComponent(o) + '&to=' + encodeURIComponent(d); }
                        }catch(e){ console.error('open-in-booking failed', e); }
                    });
                });
            }catch(err){
                console.debug('[home-widgets] loadHomeFlights failed', err);
                container.innerHTML = '<p class="empty">Unable to load flights.</p>';
            }
        }

        // Kick off home flights loader
        loadHomeFlights();

        // Mutation observer debug (keeps helpful dev info)
        try {
            const panels = new Set(); document.querySelectorAll('.action-panel').forEach(p=>panels.add(p));
            const obs = new MutationObserver((mutations)=>{
                mutations.forEach(m=>{
                    if (m.type === 'attributes' && m.target && m.target.classList && m.target.classList.contains('action-panel')){
                        console.debug('[mut-observer] attr change on', m.target.id, 'class=', m.target.className, 'style.display=', m.target.style.display);
                    }
                });
            });
            obs.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['class','style'], childList: true });
        } catch (e) { console.error('[mut-observer] failed', e); }
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
