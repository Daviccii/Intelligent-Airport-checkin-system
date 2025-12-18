// Booking widget behavior (modular)
(function(){
    const widget = document.querySelector('.booking-widget');
    if (!widget) return;

    const tripToggle = document.getElementById('tripTypeToggle');
    const tripOptions = document.getElementById('tripTypeOptions');
    const tripLabel = document.getElementById('tripTypeLabel');
    const optionButtons = tripOptions ? Array.from(tripOptions.querySelectorAll('.select__dropdown-option')) : [];
    // Prefer a native <select> when present
    const tripSelect = document.getElementById('tripTypeSelect');

    function ensureDefaultTripType(){
        // If a native select exists, it manages the trip type; nothing to do for the custom control.
        if (tripSelect) return;
        if (!optionButtons.length) return;
        let selected = optionButtons.find(b => b.getAttribute('aria-selected') === 'true');
        if (!selected) selected = optionButtons.find(b => b.dataset.value === 'return') || optionButtons[0];
        optionButtons.forEach(b => b.setAttribute('aria-selected', b === selected ? 'true' : 'false'));
        if (tripLabel && selected) tripLabel.textContent = selected.textContent.trim();
    }

    ensureDefaultTripType();

    // Ensure return date visibility follows trip type (hide/disable for one-way)
    function updateReturnVisibility(){
        try{
            let tripType = 'return';
            // Prefer native select value when available
            if (tripSelect && tripSelect.value) tripType = tripSelect.value;
            else if (tripToggle && tripToggle.getAttribute('data-value')) tripType = tripToggle.getAttribute('data-value');
            if (tripType === 'oneway'){
                if (returnDate){ returnDate.value = ''; returnDate.setAttribute('disabled','true'); returnDate.setAttribute('aria-hidden','true'); }
                if (returnDate && returnDate.parentElement) { try{ returnDate.parentElement.hidden = true; returnDate.parentElement.setAttribute('aria-hidden','true'); }catch(e){} }
            } else {
                if (returnDate){ returnDate.removeAttribute('disabled'); returnDate.removeAttribute('aria-hidden'); }
                if (returnDate && returnDate.parentElement) { try{ returnDate.parentElement.hidden = false; returnDate.parentElement.setAttribute('aria-hidden','false'); }catch(e){} }
            }
        }catch(e){ }
    }
    // Run once on init
    updateReturnVisibility();

    const fromInput = document.getElementById('airportFromInput');
    const toInput = document.getElementById('airportToInput');
    const swapBtn = document.getElementById('swapAirports');
    const searchBtn = document.getElementById('bookingSearchBtn');
    const dateSelection = document.getElementById('dateSelection');
    const departureDate = document.getElementById('departureDate');
    const returnDate = document.getElementById('returnDate');
    const searchFlightsBtn = document.getElementById('searchFlightsBtn');
    const adtInput = document.getElementById('passengerAdults');
    const chdInput = document.getElementById('passengerChildren');
    const infInput = document.getElementById('passengerInfants');
    const currencySelect = document.getElementById('currencySelect');
    // hidden fields to hold selected IATA codes (populated when a suggestion is chosen)
    const fromCodeInput = document.getElementById('airportFromCode');
    const toCodeInput = document.getElementById('airportToCode');
    const fareContainer = document.getElementById('fareRecommendations');

    function setSearchEnabled(enabled){
        if (!searchBtn) return;
        searchBtn.disabled = !enabled;
        if (enabled) searchBtn.removeAttribute('aria-disabled'); else searchBtn.setAttribute('aria-disabled','true');
    }

    function checkInputs(){
        const ok = fromInput && toInput && fromInput.value.trim() && toInput.value.trim();
        setSearchEnabled(!!ok);
    }

    // Show/hide the date selection after both origin and destination are provided.
    // We accept either typed values or selected IATA codes so the UX is responsive;
    // final validation still requires IATA codes when performing search.
    function updateDateSelectionVisibility(){
        try{
            const hasFromCode = fromCodeInput && (fromCodeInput.value || '').toString().trim() !== '';
            const hasToCode = toCodeInput && (toCodeInput.value || '').toString().trim() !== '';
            const hasFromText = fromInput && (fromInput.value || '').toString().trim() !== '';
            const hasToText = toInput && (toInput.value || '').toString().trim() !== '';
            const hasFrom = hasFromCode || hasFromText;
            const hasTo = hasToCode || hasToText;

            if (!dateSelection) return;

            if (hasFrom && hasTo){
                // reveal date selection
                try{ dateSelection.hidden = false; dateSelection.setAttribute('aria-hidden','false'); }catch(e){}
                // Respect trip type (hide return if one-way)
                try{ updateReturnVisibility(); }catch(e){}
                // enable the final search flights button
                if (searchFlightsBtn) { searchFlightsBtn.disabled = false; searchFlightsBtn.removeAttribute('aria-disabled'); }
                // focus the departure date for convenience (small timeout to let DOM settle)
                try{ setTimeout(()=>{ departureDate && departureDate.focus(); }, 30); }catch(e){}
            } else {
                try{ dateSelection.hidden = true; dateSelection.setAttribute('aria-hidden','true'); }catch(e){}
                if (searchFlightsBtn) { searchFlightsBtn.disabled = true; searchFlightsBtn.setAttribute('aria-disabled','true'); }
            }
        }catch(e){ console.debug('[booking-widget] updateDateSelectionVisibility error', e); }
    }

    // Initialize passenger and currency defaults from localStorage if present
    try{
        // Support two naming schemes for persisted passenger counts so the new dropdown
        // (which stores adults/children/infants) and the widget (which expects adt/chd/inf)
        const pAdt = localStorage.getItem('smartfly.passengers.adt');
        const pChd = localStorage.getItem('smartfly.passengers.chd');
        const pInf = localStorage.getItem('smartfly.passengers.inf');
        const pAdults = localStorage.getItem('smartfly.passengers.adults');
        const pChildren = localStorage.getItem('smartfly.passengers.children');
        const pInfants = localStorage.getItem('smartfly.passengers.infants');
        if (adtInput) adtInput.value = pAdt || pAdults || adtInput.value || '1';
        if (chdInput) chdInput.value = pChd || pChildren || chdInput.value || '0';
        if (infInput) infInput.value = pInf || pInfants || infInput.value || '0';
        if (currencySelect){ const cur = localStorage.getItem('smartfly.currency') || localStorage.getItem('currency'); if (cur) try{ currencySelect.value = cur; }catch(e){} }
    }catch(e){ }

    // Persist passenger/currency changes
    function persistPassengers(){
        try{ if (adtInput) { const v = String(Math.max(1, Number(adtInput.value||1))); localStorage.setItem('smartfly.passengers.adt', v); localStorage.setItem('smartfly.passengers.adults', v); } }catch(e){}
        try{ if (chdInput) { const v = String(Math.max(0, Number(chdInput.value||0))); localStorage.setItem('smartfly.passengers.chd', v); localStorage.setItem('smartfly.passengers.children', v); } }catch(e){}
        try{ if (infInput) { const v = String(Math.max(0, Number(infInput.value||0))); localStorage.setItem('smartfly.passengers.inf', v); localStorage.setItem('smartfly.passengers.infants', v); } }catch(e){}
    }
    if (adtInput) adtInput.addEventListener('change', ()=>{ persistPassengers(); });
    if (chdInput) chdInput.addEventListener('change', ()=>{ persistPassengers(); });
    if (infInput) infInput.addEventListener('change', ()=>{ persistPassengers(); });
    if (currencySelect) currencySelect.addEventListener('change', ()=>{ try{ localStorage.setItem('smartfly.currency', currencySelect.value); }catch(e){} });

    // Trip dropdown toggle (only for the custom dropdown; native select is wired below)
    if (!tripSelect && tripToggle){
        tripToggle.addEventListener('click', ()=>{
            const expanded = tripToggle.getAttribute('aria-expanded') === 'true';
            tripToggle.setAttribute('aria-expanded', String(!expanded));
            if (!expanded){
                tripOptions && tripOptions.setAttribute('aria-hidden','false');
                try{ tripOptions.inert = false; } catch(e){}
                tripOptions && tripOptions.querySelector('.select__dropdown-option')?.focus();
            } else {
                tripOptions && tripOptions.setAttribute('aria-hidden','true');
                try{ tripOptions.inert = true; } catch(e){}
            }
        });
        // close dropdown when clicking outside
        document.addEventListener('click', (ev)=>{
            if (!tripOptions) return;
            if (tripToggle.contains(ev.target) || tripOptions.contains(ev.target)) return;
            tripOptions.setAttribute('aria-hidden','true');
            try{ tripOptions.inert = true; } catch(e){}
            tripToggle.setAttribute('aria-expanded','false');
        });
    }

    // Option selection
    optionButtons.forEach(btn => {
        btn.addEventListener('click', (e)=>{
            optionButtons.forEach(b=>b.setAttribute('aria-selected','false'));
            btn.setAttribute('aria-selected','true');
            if (tripLabel) tripLabel.textContent = btn.textContent.trim();
            // store the selected trip type on the toggle for downstream use
            if (tripToggle && btn.dataset && btn.dataset.value) tripToggle.setAttribute('data-value', btn.dataset.value);
            if (tripToggle) tripToggle.setAttribute('aria-expanded','false');
            if (tripOptions) { tripOptions.setAttribute('aria-hidden','true'); try{tripOptions.inert=true;}catch(e){} }
            // update return date visibility after changing trip type
            updateReturnVisibility();
        });
    });

    // keyboard navigation
    if (tripOptions){
        tripOptions.addEventListener('keydown', (e)=>{
            if (!optionButtons.length) return;
            const current = optionButtons.findIndex(b=>b.getAttribute('aria-selected') === 'true');
            if (e.key === 'ArrowDown'){ e.preventDefault(); const next = optionButtons[(current + 1) % optionButtons.length]; next && next.click(); }
            if (e.key === 'ArrowUp'){ e.preventDefault(); const prev = optionButtons[(current - 1 + optionButtons.length) % optionButtons.length]; prev && prev.click(); }
            if (e.key === 'Escape'){ if (tripToggle) tripToggle.setAttribute('aria-expanded','false'); tripOptions.setAttribute('aria-hidden','true'); try{tripOptions.inert=true;}catch(e){} tripToggle && tripToggle.focus(); }
        });
    }

    // Wire native select if present
    if (tripSelect){
        tripSelect.addEventListener('change', ()=>{
            updateReturnVisibility();
        });
    }

    // swap inputs
    if (swapBtn){
        swapBtn.addEventListener('click', ()=>{
            const a = fromInput.value || '';
            fromInput.value = toInput.value || '';
            toInput.value = a;
            // swap stored IATA codes too, if present
            try {
                const aCode = fromCodeInput && fromCodeInput.value ? fromCodeInput.value : '';
                const bCode = toCodeInput && toCodeInput.value ? toCodeInput.value : '';
                if (fromCodeInput) fromCodeInput.value = bCode;
                if (toCodeInput) toCodeInput.value = aCode;
            } catch(e){}
            checkInputs();
            // update date visibility after swapping codes
            try{ updateDateSelectionVisibility(); } catch(e){}
            fromInput.focus();
        });
    }

    // mark session interaction when user types
    [fromInput, toInput].forEach(inp => {
        if (!inp) return;
        inp.addEventListener('input', ()=>{
            // If the user edits the text after selecting, clear the corresponding IATA code
            try{ if (inp === fromInput && fromCodeInput) fromCodeInput.value=''; if (inp === toInput && toCodeInput) toCodeInput.value=''; } catch(e){}
            checkInputs();
            try{ updateDateSelectionVisibility(); } catch(e){}
            try{ sessionStorage.setItem('smartfly.interacted','1'); } catch(e) {}
        });
    });

    if (searchBtn) searchBtn.addEventListener('click', ()=>{
        try{ sessionStorage.setItem('smartfly.interacted','1'); } catch(e){}
        try {
            // First click should reveal date selection only if both origin and destination IATA codes are set
            const hasFromCode = fromCodeInput && (fromCodeInput.value || '').toString().trim() !== '';
            const hasToCode = toCodeInput && (toCodeInput.value || '').toString().trim() !== '';
            if (dateSelection && dateSelection.hidden){
                if (!hasFromCode || !hasToCode){
                    if (fareContainer) fareContainer.innerHTML = '<div class="message error">Please select both origin and destination from the suggestions before choosing dates.</div>';
                    // focus the first missing field
                    try{ if (!hasFromCode) fromInput && fromInput.focus(); else toInput && toInput.focus(); } catch(e){}
                    return;
                }
                try{ dateSelection.hidden = false; dateSelection.setAttribute('aria-hidden','false'); }catch(e){}
                // focus the departure input for convenience
                try { departureDate && departureDate.focus(); } catch(e){}
                return;
            }
        } catch(e){}
        // if date selection already visible, do not perform preview fare recommendation here
        // Fare estimates are shown on the dedicated results page after the user clicks 'Search flights'.
    });
    checkInputs();
    // Ensure date selection hidden/shown correctly on init in case codes are prefilled
    try{ updateDateSelectionVisibility(); } catch(e){}
    
    // Auto-focus return date after departure chosen when trip type is return/multi
    function getTripType(){
        try{ if (tripSelect && tripSelect.value) return tripSelect.value; }catch(e){}
        try{ if (tripToggle && tripToggle.getAttribute('data-value')) return tripToggle.getAttribute('data-value'); }catch(e){}
        return 'return';
    }

    function maybeFocusReturn(){
        try{
            const tt = getTripType();
            if (tt === 'oneway') return;
            if (!returnDate) return;
            // If the return date's parent (wrapper) is hidden, do not focus
            const wrapper = returnDate.parentElement;
            if (wrapper && wrapper.hidden) return;
            // give the browser a moment to process the change UI
            setTimeout(()=>{ try{ returnDate.focus(); }catch(e){} }, 40);
        }catch(e){ /* noop */ }
    }

    if (departureDate){ departureDate.addEventListener('change', maybeFocusReturn); departureDate.addEventListener('input', maybeFocusReturn); }
    
    // --- Autocomplete for airport inputs ---
    // Small embedded airport dataset used as a fallback. We'll try to fetch a fuller dataset from a public source.
    const EMBED_AIRPORTS = [
        { code: 'LHR', name: 'Heathrow Airport', city: 'London', country: 'United Kingdom', lat: 51.4700, lon: -0.4543 },
        { code: 'LGW', name: 'Gatwick Airport', city: 'London', country: 'United Kingdom', lat: 51.1537, lon: -0.1821 },
        { code: 'JFK', name: 'John F. Kennedy International Airport', city: 'New York', country: 'USA', lat: 40.6413, lon: -73.7781 },
        { code: 'EWR', name: 'Newark Liberty International Airport', city: 'Newark', country: 'USA', lat: 40.6895, lon: -74.1745 },
        { code: 'LAX', name: 'Los Angeles International Airport', city: 'Los Angeles', country: 'USA', lat: 33.9416, lon: -118.4085 },
        { code: 'CDG', name: 'Charles de Gaulle Airport', city: 'Paris', country: 'France', lat: 49.0097, lon: 2.5479 },
        { code: 'ORY', name: 'Orly Airport', city: 'Paris', country: 'France', lat: 48.7262, lon: 2.3652 },
        { code: 'DXB', name: 'Dubai International', city: 'Dubai', country: 'UAE', lat: 25.2532, lon: 55.3657 },
        { code: 'SIN', name: 'Changi Airport', city: 'Singapore', country: 'Singapore', lat: 1.3644, lon: 103.9915 },
        { code: 'SYD', name: 'Sydney Kingsford Smith', city: 'Sydney', country: 'Australia', lat: -33.9399, lon: 151.1753 }
    ];

    // working airports array (starts as embedded fallback)
    let AIRPORTS = EMBED_AIRPORTS.slice();

    // Try to fetch a larger airports dataset (GitHub raw mirror of common airports JSON)
    async function loadLocalAirports(){
        // Try local preprocessed airports file first for offline reliability
        const localUrl = '/assets/data/airports.json';
        try {
            const res = await fetch(localUrl, { cache: 'no-store' });
            if (!res.ok) throw new Error('Local airports file not found');
            const data = await res.json();
            const mapped = [];
            if (Array.isArray(data)) {
                data.forEach(a => {
                    const code = (a.code && a.code.trim()) ? a.code.trim() : '';
                    const name = (a.name && a.name.trim()) ? a.name.trim() : '';
                    const city = (a.city && a.city.trim()) ? a.city.trim() : '';
                    const country = (a.country && a.country.trim()) ? a.country.trim() : '';
                    const lat = Number.isFinite(Number(a.lat)) ? Number(a.lat) : null;
                    const lon = Number.isFinite(Number(a.lon)) ? Number(a.lon) : null;
                    if (code && name) mapped.push({ code, name, city, country, lat, lon });
                });
            } else if (data && typeof data === 'object') {
                // support object keyed datasets as a fallback
                Object.keys(data).forEach(k => {
                    const a = data[k];
                    const code = (a.iata && a.iata.trim()) ? a.iata.trim() : (a.icao && a.icao.trim()) || k;
                    const city = (a.city && a.city.trim()) ? a.city.trim() : (a.name && a.name.split(',')[0]) || '';
                    const name = (a.name && a.name.trim()) ? a.name.trim() : '';
                    const country = (a.country && a.country.trim()) ? a.country.trim() : '';
                    let lat = null, lon = null;
                    try {
                        const parse = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
                        lat = parse(a.lat || a.latitude || a.latitude_deg || a.latitudeDegrees || a.latitude_deg);
                        lon = parse(a.lon || a.longitude || a.longitude_deg || a.longitudeDegrees || a.longitude_deg);
                        if ((lat === null || lon === null) && a.location && Array.isArray(a.location) && a.location.length >= 2){ lat = parse(a.location[0]); lon = parse(a.location[1]); }
                    } catch(e){}
                    if (code && name) mapped.push({ code, name, city, country, lat, lon });
                });
            }

            if (mapped.length) {
                const seen = new Map();
                mapped.forEach(m => { if (!seen.has(m.code)) seen.set(m.code, m); });
                AIRPORTS = Array.from(seen.values());
                console.debug('[booking-widget] loaded local airports, count=', AIRPORTS.length);
                return;
            }
        } catch (e) {
            console.debug('[booking-widget] local airports load failed, falling back', e);
        }

        // Fallback: try remote GitHub source if local not available
        try {
            const url = 'https://raw.githubusercontent.com/mwgg/airports/master/airports.json';
            const res2 = await fetch(url, { cache: 'no-store' });
            if (!res2.ok) throw new Error('Remote fetch failed');
            const data2 = await res2.json();
            const mapped2 = [];
            Object.keys(data2).forEach(k => {
                const a = data2[k];
                const code = (a.iata && a.iata.trim()) ? a.iata.trim() : (a.icao && a.icao.trim()) || k;
                const city = (a.city && a.city.trim()) ? a.city.trim() : (a.name && a.name.split(',')[0]) || '';
                const name = (a.name && a.name.trim()) ? a.name.trim() : '';
                const country = (a.country && a.country.trim()) ? a.country.trim() : '';
                let lat = null, lon = null;
                try {
                    const parse = v => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
                    lat = parse(a.lat || a.latitude || a.latitude_deg || a.latitudeDegrees || a.latitude_deg);
                    lon = parse(a.lon || a.longitude || a.longitude_deg || a.longitudeDegrees || a.longitude_deg);
                    if ((lat === null || lon === null) && a.location && Array.isArray(a.location) && a.location.length >= 2){ lat = parse(a.location[0]); lon = parse(a.location[1]); }
                } catch(e){}
                if (code && name) mapped2.push({ code, name, city, country, lat, lon });
            });
            if (mapped2.length) {
                const seen = new Map();
                mapped2.forEach(m => { if (!seen.has(m.code)) seen.set(m.code, m); });
                AIRPORTS = Array.from(seen.values());
                console.debug('[booking-widget] loaded remote airports, count=', AIRPORTS.length);
            }
        } catch (e) {
            console.debug('[booking-widget] remote airports load also failed, using embedded list', e);
        }
    }

    // load airports but do not block UI; fallback will be used if fetch fails
    loadLocalAirports();

    // Try to resolve user's geolocation (best-effort). If allowed we'll use it
    // to surface nearby airports on input focus (nearest → furthest).
    let userLat = null, userLon = null;
    function resolveUserLocation(timeoutMs = 4000){
        return new Promise((resolve) => {
            try{
                if (!navigator.geolocation) return resolve(null);
                let done = false;
                const success = (p) => { if (done) return; done = true; try{ userLat = p.coords.latitude; userLon = p.coords.longitude; }catch(e){} resolve({lat:userLat, lon:userLon}); };
                const failure = (e) => { if (done) return; done = true; resolve(null); };
                navigator.geolocation.getCurrentPosition(success, failure, { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: 600000 });
                // fallback timeout in case the API hangs
                setTimeout(()=>{ if (!done){ done = true; resolve(null); } }, timeoutMs + 200);
            }catch(e){ resolve(null); }
        });
    }
    // Start resolving location but don't block UI
    resolveUserLocation().then(()=>{ if (userLat && userLon) console.debug('[booking-widget] user location determined', userLat, userLon); });

    function nearestAirports(limit = 8){
        try{
            if (userLat != null && userLon != null){
                const copy = AIRPORTS.slice();
                copy.forEach(a => { a.__dist = (a.lat != null && a.lon != null) ? haversineDistance(userLat, userLon, a.lat, a.lon) : Number.MAX_VALUE; });
                copy.sort((x,y)=> (x.__dist || Number.MAX_VALUE) - (y.__dist || Number.MAX_VALUE));
                return copy.slice(0, limit).map(a=>{ delete a.__dist; return a; });
            }
            // fallback: return a curated/embedded subset (prefer big hubs)
            const prefer = ['LHR','LGW','JFK','LAX','CDG','DXB','SIN','SYD','EWR','ORY'];
            const seen = new Set();
            const out = [];
            prefer.forEach(code => { const f = AIRPORTS.find(x => (x.code||'').toUpperCase() === code); if (f && !seen.has(f.code)){ seen.add(f.code); out.push(f); } });
            // fill remaining with first entries
            for (let i=0;i<AIRPORTS.length && out.length<limit;i++){ const a=AIRPORTS[i]; if (!seen.has(a.code)){ seen.add(a.code); out.push(a); } }
            return out.slice(0,limit);
        }catch(e){ return AIRPORTS.slice(0, Math.min(limit, AIRPORTS.length)); }
    }

    function createSuggestionBox(input){
        const list = document.createElement('div');
        list.className = 'airport-suggestions';
        list.setAttribute('role','listbox');
        list.hidden = true; try{ list.setAttribute('aria-hidden','true'); }catch(e){}
        input.setAttribute('aria-haspopup','listbox');
        const id = input.id + '-list';
        list.id = id;
        input.setAttribute('aria-controls', id);
        input.parentNode.appendChild(list);
        return list;
    }

    function formatSuggestion(a){
        return `${a.city} — ${a.name} (${a.code})`;
    }

    function formatSuggestionHtml(a){
        // show code, name, city/country and include selected departure date/time to the right
        const city = a.city ? `${a.city}${a.country ? ', ' + a.country : ''}` : (a.country || '');
        // read selected departure date (if any) and format it
        const rawDepart = (typeof departureDate !== 'undefined' && departureDate && departureDate.value) ? departureDate.value : '';
        function fmtDate(iso){ try { if (!iso) return ''; const d = new Date(iso); return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }); } catch(e){ return iso; } }
        const departText = rawDepart ? fmtDate(rawDepart) : '';
        // time is not selectable in widget currently — show a placeholder
        const timeText = 'Any time';
        return `
            <div class="as-left">
                <div class="as-code">${(a.code||'').toUpperCase()}</div>
                <div class="as-info">
                    <div class="as-name">${escapeHtml(a.name || '')}</div>
                    <div class="as-city">${escapeHtml(city)}</div>
                </div>
            </div>
            <div class="as-right">
                <div class="as-datetime">
                    <div class="dt-date">${escapeHtml(departText || '')}</div>
                    <div class="dt-time">${escapeHtml(timeText)}</div>
                </div>
            </div>
        `;
    }

    function escapeHtml(str){
        return String(str).replace(/[&<>"]/g, s => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' })[s]);
    }

    function matchAirports(q){
        if (!q) return [];
        const s = q.trim().toLowerCase();
        try {
            return AIRPORTS.filter(a => {
                return (a.city || '').toLowerCase().includes(s) || (a.name || '').toLowerCase().includes(s) || (a.code || '').toLowerCase().startsWith(s);
            }).slice(0,8);
        } catch(e){ return []; }
    }

    function wireAutocomplete(inp, nextFocusEl){
        if (!inp) return;
        const box = createSuggestionBox(inp);
        let items = [];
        let idx = -1;

        function render(results){
            items = results;
            idx = -1;
            box.innerHTML = '';
            if (!results.length){ box.hidden = true; inp.setAttribute('aria-expanded','false'); return; }
            results.forEach((r, i)=>{
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'airport-suggestion';
                btn.setAttribute('role','option');
                btn.setAttribute('data-index', String(i));
                btn.setAttribute('aria-label', (r.city || '') + ' ' + (r.name || '') + ' ' + (r.code || ''));
                btn.innerHTML = formatSuggestionHtml(r);
                btn.addEventListener('click', ()=>{ selectIndex(i); });
                box.appendChild(btn);
            });
            box.hidden = false; box.setAttribute('aria-hidden','false');
            inp.setAttribute('aria-expanded','true');
        }

        function highlight(i){
            const children = Array.from(box.children);
            children.forEach((c,ci)=> c.classList.toggle('highlight', ci === i));
            idx = i;
        }

        function selectIndex(i){
            const a = items[i];
            if (!a) return;
            inp.value = `${a.city} — ${a.code}`;
            // populate hidden IATA code field for the input that was acted on
            try {
                if (inp === fromInput && fromCodeInput) fromCodeInput.value = a.code || '';
                if (inp === toInput && toCodeInput) toCodeInput.value = a.code || '';
            } catch(e){}
            box.hidden = true; inp.setAttribute('aria-expanded','false');
            checkInputs();
            // after a proper selection (IATA set) show the date inputs
            updateDateSelectionVisibility();
            // move focus
            try { sessionStorage.setItem('smartfly.interacted','1'); } catch(e){}
            if (nextFocusEl) { setTimeout(()=>{ try{ nextFocusEl.focus(); } catch(e){} }, 40); }
        }

        inp.addEventListener('input', (e)=>{
            const q = inp.value || '';
            const results = matchAirports(q);
            render(results);
        });

        // Show nearby airports only after a deliberate user click (nearest → furthest).
        // Use `pointerdown` to catch touch/mouse interactions and avoid showing
        // suggestions on programmatic focus (e.g. tab, script). Fall back to
        // `mousedown`/`click` for older browsers.
        function onUserShowNearby(e){
            try{
                // Only proceed for trusted user-initiated events
                if (!e || e.isTrusted === false) return;
                const q = (inp.value || '').trim();
                if (q) return; // user has typed — regular input handler will run
                const results = nearestAirports(8);
                render(results);
            }catch(err){ /* non-fatal */ }
        }
        inp.addEventListener('pointerdown', onUserShowNearby);
        inp.addEventListener('mousedown', onUserShowNearby);
        inp.addEventListener('click', onUserShowNearby);

        inp.addEventListener('keydown', (e)=>{
            if (box.hidden) {
                if (e.key === 'Enter') {
                    // if no suggestion but Enter pressed, move focus
                    e.preventDefault();
                    if (nextFocusEl) try{ nextFocusEl.focus(); } catch(e){}
                }
                return;
            }
            const max = box.children.length - 1;
            if (e.key === 'ArrowDown') { e.preventDefault(); const next = idx < max ? idx + 1 : 0; highlight(next); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); const prev = idx > 0 ? idx - 1 : max; highlight(prev); }
            else if (e.key === 'Enter') { e.preventDefault(); if (idx >= 0) selectIndex(idx); else if (box.children.length === 1) selectIndex(0); else { if (nextFocusEl) try{ nextFocusEl.focus(); } catch(e){} } }
            else if (e.key === 'Escape') { box.hidden = true; inp.setAttribute('aria-expanded','false'); }
        });

        // click outside closes
        document.addEventListener('click', (ev)=>{ if (!box.contains(ev.target) && ev.target !== inp) { box.hidden = true; inp.setAttribute('aria-expanded','false'); } });
    }

    // wire autocompletes: on from -> focus to, on to -> focus search button
    try {
        wireAutocomplete(fromInput, toInput || searchBtn);
        wireAutocomplete(toInput, searchBtn);
    } catch(e) { console.error('[booking-widget] autocomplete init failed', e); }

    // --- Fare estimation / recommendation logic ---
    // Fare configuration (tune these to match business rules)
    const FARE_CONFIG = {
        currency: 'USD',        // currency code for display
        locale: 'en-US',        // locale for number formatting
        baseFee: 30,            // fixed base fee in currency units
        perKm: 0.12,            // per-km rate in currency units
        multipliers: {
            oneway: 1.0,
            return: 1.9,
            multi: 2.6
        },
        classMultipliers: {
            flex: 1.30,   // Economy Flex multiplier vs Standard
            super: 1.60   // Economy Super Flex multiplier vs Standard
        }
    };

    // Haversine distance (km)
    function haversineDistance(lat1, lon1, lat2, lon2){
        if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) return null;
        const toRad = v => v * Math.PI / 180;
        const R = 6371; // km
        const dLat = toRad(lat2 - lat1);
        const dLon = toRad(lon2 - lon1);
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }

    function estimateBaseFare(codeA, codeB){
        if (!codeA || !codeB) return null;
        // look up airports by code (case-insensitive)
        const a = AIRPORTS.find(x => (x.code||'').toUpperCase() === (codeA||'').toUpperCase());
        const b = AIRPORTS.find(x => (x.code||'').toUpperCase() === (codeB||'').toUpperCase());
        if (a && b && a.lat != null && a.lon != null && b.lat != null && b.lon != null){
            const km = haversineDistance(a.lat, a.lon, b.lat, b.lon);
            if (km === null) return null;
            // pricing heuristic: base + per-km rate
            const base = Math.round(FARE_CONFIG.baseFee + km * FARE_CONFIG.perKm);
            return Math.max(30, base);
        }
        // fallback deterministic heuristic if lat/lon unavailable
        const A = (codeA||'').toUpperCase();
        const B = (codeB||'').toUpperCase();
        let dist = 0;
        const len = Math.max(A.length, B.length);
        for (let i=0;i<len;i++){
            const ca = A.charCodeAt(i) || 65;
            const cb = B.charCodeAt(i) || 65;
            dist += Math.abs(ca - cb);
        }
        const base = 50 + Math.round(dist * 2.5);
        return Math.max(30, base);
    }

    async function performSearchAndRecommend(){
        // determine selected codes (fall back to best guess from typed text)
        let fromCode = fromCodeInput && fromCodeInput.value ? fromCodeInput.value : '';
        let toCode = toCodeInput && toCodeInput.value ? toCodeInput.value : '';
        // try to guess codes if hidden fields empty
        if ((!fromCode || !toCode) && typeof matchAirports === 'function'){
            if (!fromCode && fromInput && fromInput.value) {
                const m = matchAirports(fromInput.value.trim()); if (m && m[0]) fromCode = m[0].code;
            }
            if (!toCode && toInput && toInput.value) {
                const m = matchAirports(toInput.value.trim()); if (m && m[0]) toCode = m[0].code;
            }
        }
        if (!fromCode || !toCode){
            if (fareContainer) fareContainer.innerHTML = '<div class="message error">Please select both origin and destination from the suggestions so IATA codes can be used.</div>';
            return null;
        }

        // determine trip type (prefer native select when present)
        let tripType = 'return';
        try { if (tripSelect && tripSelect.value) tripType = tripSelect.value; else if (tripToggle && tripToggle.getAttribute('data-value')) tripType = tripToggle.getAttribute('data-value'); } catch(e){}

        // Prefer server-side authoritative estimate; fall back to client-side if server not available
        let serverPrices = null;
        try {
            const q = new URLSearchParams({ from: fromCode.toUpperCase(), to: toCode.toUpperCase(), trip: tripType });
            const res = await fetch('/api/prices?' + q.toString(), { cache: 'no-store' });
            if (res && res.ok){
                serverPrices = await res.json();
            }
        } catch (e) {
            console.debug('[booking-widget] /api/prices fetch failed, falling back to local estimator', e);
            serverPrices = null;
        }

        let fareStandard, fareFlex, fareSuper, base;
        if (serverPrices && typeof serverPrices.fareStandard !== 'undefined'){
            fareStandard = Number(serverPrices.fareStandard);
            fareFlex = Number(serverPrices.fareFlex || Math.round(fareStandard * FARE_CONFIG.classMultipliers.flex));
            fareSuper = Number(serverPrices.fareSuper || Math.round(fareStandard * FARE_CONFIG.classMultipliers.super));
            base = Number(serverPrices.base || estimateBaseFare(fromCode, toCode) || 0);
        } else {
            const localBase = estimateBaseFare(fromCode, toCode);
            if (localBase === null){ if (fareContainer) fareContainer.innerHTML = '<div class="message error">Unable to estimate fare.</div>'; return null; }
            let typeMultiplier = FARE_CONFIG.multipliers.oneway;
            if (tripType === 'return') typeMultiplier = FARE_CONFIG.multipliers.return;
            else if (tripType === 'multi') typeMultiplier = FARE_CONFIG.multipliers.multi;
            const standardRaw = localBase * typeMultiplier;
            fareStandard = Math.round(standardRaw);
            fareFlex = Math.round(standardRaw * FARE_CONFIG.classMultipliers.flex);
            fareSuper = Math.round(standardRaw * FARE_CONFIG.classMultipliers.super);
            base = localBase;
        }

        // Do not render fares on the homepage — return computed fares so the caller
        // (e.g. the results page) can decide how and where to display them.

        return { fareStandard, fareFlex, fareSuper, base, tripType };
    }

    // When the user clicks the final Search flights button, validate and open the flight results page
    if (searchFlightsBtn){
        searchFlightsBtn.addEventListener('click', async ()=>{
            try{ sessionStorage.setItem('smartfly.interacted','1'); } catch(e){}

            // ensure we have IATA codes
            let fromCode = fromCodeInput && fromCodeInput.value ? fromCodeInput.value : '';
            let toCode = toCodeInput && toCodeInput.value ? toCodeInput.value : '';
            if ((!fromCode || !toCode) && typeof matchAirports === 'function'){
                if (!fromCode && fromInput && fromInput.value) { const m = matchAirports(fromInput.value.trim()); if (m && m[0]) fromCode = m[0].code; }
                if (!toCode && toInput && toInput.value) { const m = matchAirports(toInput.value.trim()); if (m && m[0]) toCode = m[0].code; }
            }
            if (!fromCode || !toCode){ if (fareContainer) fareContainer.innerHTML = '<div class="message error">Please select both origin and destination from the suggestions.</div>'; return; }

            // validate dates
            const depart = departureDate && departureDate.value ? departureDate.value : '';
            const ret = returnDate && returnDate.value ? returnDate.value : '';
            let tripType = 'return';
            try { if (tripSelect && tripSelect.value) tripType = tripSelect.value; else if (tripToggle && tripToggle.getAttribute('data-value')) tripType = tripToggle.getAttribute('data-value'); } catch(e){}
            if (!depart){ if (fareContainer) fareContainer.innerHTML = '<div class="message error">Please choose a departure date.</div>'; return; }
            if (tripType === 'return' && !ret){ if (fareContainer) fareContainer.innerHTML = '<div class="message error">Please choose a return date for a Return trip.</div>'; return; }

            // compute fares to pass along (and render locally). Await server-side estimator where available.
            const fares = await performSearchAndRecommend() || {};

            // build query params for flight-results page
            const params = new URLSearchParams();
            params.set('from', fromCode.toUpperCase());
            params.set('to', toCode.toUpperCase());
            params.set('depart', depart);
            if (ret) params.set('return', ret);
            params.set('trip', tripType);
            if (fares.fareStandard) params.set('fareStandard', String(fares.fareStandard));
            if (fares.fareFlex) params.set('fareFlex', String(fares.fareFlex));
            if (fares.fareSuper) params.set('fareSuper', String(fares.fareSuper));

            // Also include legacy/multi-leg style params used by some booking flows
            // (origin1/destination1/departure1, origin2/destination2/departure2)
            try{
                // passengers: read from widget inputs if present, fallback to 1/0/0
                // Read passenger counts from inputs with fallback to persisted values
                const readInt = (el, fallback) => { try{ if (el && el.value !== undefined && el.value !== null && String(el.value).trim() !== '') return Math.max(0, Number(el.value)); }catch(e){} try{ const v = localStorage.getItem(fallback); if (v !== null) return Math.max(0, Number(v)); }catch(e){} return 0; };
                const defaultAdt = Math.max(1, readInt(adtInput, 'smartfly.passengers.adults') || readInt(adtInput, 'smartfly.passengers.adt') || 1);
                const defaultChd = readInt(chdInput, 'smartfly.passengers.children') || readInt(chdInput, 'smartfly.passengers.chd') || 0;
                const defaultInf = readInt(infInput, 'smartfly.passengers.infants') || readInt(infInput, 'smartfly.passengers.inf') || 0;
                params.set('origin1', fromCode.toUpperCase());
                params.set('destination1', toCode.toUpperCase());
                params.set('departure1', depart || '');
                params.set('adt1', String(defaultAdt));
                params.set('chd1', String(defaultChd));
                params.set('inf1', String(defaultInf));

                if (ret){
                    params.set('origin2', toCode.toUpperCase());
                    params.set('destination2', fromCode.toUpperCase());
                    params.set('departure2', ret || '');
                    params.set('adt2', String(defaultAdt));
                    params.set('chd2', String(defaultChd));
                    params.set('inf2', String(defaultInf));
                }

                // currency: prefer the UI selection, fallback to stored preferences
                let cfgCurrency = null;
                try{ if (currencySelect && currencySelect.value) cfgCurrency = currencySelect.value; }catch(e){}
                if (!cfgCurrency) cfgCurrency = (localStorage.getItem('smartfly.currency') || localStorage.getItem('currency') || localStorage.getItem('preferredCurrency'));
                if (cfgCurrency) params.set('currency', cfgCurrency);
            }catch(e){ /* non-fatal */ }

            // navigate to flight results page where user can pick a price/class
            try { window.location.href = '/flight-results.html?' + params.toString(); } catch(e){ console.error('[booking-widget] redirect failed', e); }
        });
    }

    // Partner booking flow removed — all searches remain on SmartFly and open the
    // internal `flight-results.html` page in the same tab. External partner
    // integrations were intentionally removed to keep bookings on this system.
})();
