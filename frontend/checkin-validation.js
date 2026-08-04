/* ============================================================================
   SmartFly Online Check-In
   ----------------------------------------------------------------------------
   Data sources, in lookup order:
     1. sessionStorage['smartflyBookingSession'] — a booking made through this
        browser's own live search->payment flow just now (real "today" dates).
     2. GET /api/public/bookings and /api/public/passengers — the real,
        canonical data the backend actually writes to when a booking/payment
        is created. (Previously this fetched bookings.json/passengers.json as
        static files via a relative path, which resolved to a separate, stale
        copy under the frontend static folder that never got updated by real
        bookings — that's why newly paid bookings weren't found here.)

   IMPORTANT LIMITATION: there is no backend endpoint to persist a completed
   check-in back into bookings.json/passengers.json on disk. Completed
   check-ins are stored in localStorage (see OVERLAY_KEY) and merged back in
   on every load, so the flow behaves correctly in this browser, but it will
   not be visible to other users or survive a server-side data reset. Wiring
   a real PATCH/POST endpoint on the backend is the next step for that.
   ============================================================================ */

const BOOKINGS_URL = '/api/public/bookings';
const PASSENGERS_URL = '/api/public/passengers';
const OVERLAY_KEY = 'smartfly_checkin_overlay';

// Airports treated as domestic Kenya routes -- anything else is "international"
// and triggers the passport/travel-document step.
const KENYA_DOMESTIC = new Set(['NBO', 'MBA', 'KIS', 'EDL', 'MYD', 'LOK', 'WIL', 'UKA', 'MRE', 'LAU', 'GAS']);

const CHECKIN_OPENS_HOURS_BEFORE = 48; // matches this app's own check-in.html copy
const CHECKIN_CLOSES_HOURS_BEFORE = 2;

let DB = { bookings: [], passengers: [] };
let liveSession = null; // today's booking from sessionStorage, if any

const state = {
    step: 'search',
    intl: false,
    record: null,        // { pnr, name, lastName, flightNumber, origin, destination, departure, seatClass, source }
    passportOnFile: null,
    docs: {},             // { passportNumber, passportExpiry, country, visa }
    baggage: { wants: null, weight: null },
    dgAccepted: false,
    seat: null,
    special: [],
    boarding: null        // gate/boardingTime/terminal, computed on confirm
};

const STEP_ORDER = ['search', 'flight-info', 'documents', 'baggage', 'dangerous-goods', 'seat', 'special-requests', 'confirm', 'boarding-pass'];
const STEP_LABELS = { search: 'Find', 'flight-info': 'Details', documents: 'Docs', baggage: 'Baggage', 'dangerous-goods': 'Safety', seat: 'Seat', 'special-requests': 'Requests', confirm: 'Confirm', 'boarding-pass': 'Pass' };

function activeSteps() {
    return STEP_ORDER.filter(s => s !== 'documents' || state.intl);
}

/* ---------------------------------------------------------------------- */
/* Helpers                                                                */
/* ---------------------------------------------------------------------- */

const root = () => document.getElementById('wizard-root');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));

function seededRandom(seedStr) {
    let h = 0;
    const s = String(seedStr || 'seed');
    for (let i = 0; i < s.length; i++) { h = (Math.imul(31, h) + s.charCodeAt(i)) | 0; }
    return function () {
        h = Math.imul(h ^ (h >>> 15), 1 | h);
        h = (h + Math.imul(h ^ (h >>> 7), 61 | h)) ^ h;
        return ((h ^ (h >>> 14)) >>> 0) / 4294967296;
    };
}

function fmtDateTime(d) {
    if (!d) return 'Not available';
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' }) + ' \u00b7 ' +
        d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
function fmtDateOnly(d) {
    if (!d) return 'Not available';
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });
}
function fmtTimeOnly(d) {
    if (!d) return '--:--';
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/* ---------------------------------------------------------------------- */
/* Normalization -- the seed data has several inconsistent schema         */
/* generations mixed in the same array; these tolerate all of them.       */
/* ---------------------------------------------------------------------- */

function normalizeBooking(b) {
    const pnr = b.booking_reference || b.booking_ref || b.id || b.booking_id || '';
    const name = b.passenger_name || b.name || (Array.isArray(b.passengers) ? b.passengers[0] : '') || '';
    const paymentStatus = String(b.payment_status || b.status || '').toLowerCase();
    const bookingStatus = String(b.booking_status || '').toLowerCase();
    let departureRaw = b.departure_date || b.depart || null;
    let departure = null;
    if (departureRaw) {
        const d = new Date(departureRaw);
        if (!isNaN(d.getTime())) departure = d;
    }
    return {
        pnr: String(pnr).toUpperCase(),
        name,
        lastName: name.trim().split(/\s+/).pop() || '',
        flightNumber: b.flight_number || b.flight || '',
        origin: (b.origin || b.from || '').toUpperCase(),
        destination: (b.destination || b.to || '').toUpperCase(),
        departure,
        seatClass: b.seat_class || b.class || 'economy',
        seatOnFile: b.seat_assignment ?? b.seat ?? null,
        totalAmount: b.total_amount ?? b.amount ?? (b.fare ? Number(b.fare) : null),
        currency: b.currency || 'USD',
        paymentComplete: ['confirmed', 'completed', 'paid'].includes(paymentStatus),
        cancelled: bookingStatus === 'cancelled',
        baggageAllowance: typeof b.baggage_allowance === 'number' ? b.baggage_allowance : 1,
        passport: b.passport || null,
        email: b.email || null,
        phone: b.phone || null,
        checkedIn: b.checked_in === true,
        source: 'bookings.json',
        raw: b
    };
}

function normalizePassenger(p) {
    return {
        id: p.id || null,
        name: p.name || '',
        passport: p.passport || null,
        flightNumber: p.flight || '',
        seat: p.seat ?? null,
        email: p.email || null,
        phone: p.phone || null,
        dob: p.date_of_birth || null,
        nationality: p.nationality || null,
        checkedIn: !!p.checked_in,
        ticketNumber: p.ticket_number || null,
        raw: p
    };
}

async function loadDatabase() {
    const [bRes, pRes] = await Promise.allSettled([fetch(BOOKINGS_URL), fetch(PASSENGERS_URL)]);
    let bookings = [], passengers = [];
    let fetchError = null;

    if (bRes.status === 'fulfilled' && bRes.value.ok) {
        bookings = (await bRes.value.json()).map(normalizeBooking);
    } else {
        fetchError = `Could not load ${BOOKINGS_URL} (${bRes.status === 'fulfilled' ? bRes.value.status : bRes.reason}).`;
    }
    if (pRes.status === 'fulfilled' && pRes.value.ok) {
        passengers = (await pRes.value.json()).map(normalizePassenger);
    } else if (!fetchError) {
        fetchError = `Could not load ${PASSENGERS_URL} (${pRes.status === 'fulfilled' ? pRes.value.status : pRes.reason}).`;
    }

    DB.bookings = bookings;
    DB.passengers = passengers;

    const liveRaw = sessionStorage.getItem('smartflyBookingSession');
    if (liveRaw) {
        try {
            const s = JSON.parse(liveRaw);
            if (s.paymentStatus === 'Paid' && s.passengers && s.passengers[0]) {
                const p = s.passengers[0];
                liveSession = {
                    pnr: String(s.pnr || '').toUpperCase(),
                    name: `${p.firstName || ''} ${p.lastName || ''}`.trim(),
                    lastName: (p.lastName || '').trim(),
                    flightNumber: (s.selectedFlight && s.selectedFlight.flightNumber) || '',
                    origin: (s.searchParams && s.searchParams.origin || '').toUpperCase(),
                    destination: (s.searchParams && s.searchParams.destination || '').toUpperCase(),
                    departure: s.searchParams && s.searchParams.departure ? new Date(s.searchParams.departure) : null,
                    seatClass: (s.selectedFlight && s.selectedFlight.fareClass) || 'Economy',
                    seatOnFile: null,
                    totalAmount: s.selectedFlight ? s.selectedFlight.price : null,
                    currency: 'KES',
                    paymentComplete: true,
                    cancelled: false,
                    baggageAllowance: 1,
                    passport: p.passportNumber || null,
                    email: p.email || null,
                    phone: p.phone || null,
                    checkedIn: false,
                    source: 'live-session',
                    dob: p.dob || null,
                    nationality: p.nationality || null,
                    raw: s
                };
            }
        } catch (e) { /* ignore malformed session */ }
    }

    return fetchError;
}

function getOverlay(pnr) {
    try {
        const all = JSON.parse(localStorage.getItem(OVERLAY_KEY) || '{}');
        return all[pnr] || null;
    } catch (e) { return null; }
}
function setOverlay(pnr, patch) {
    let all = {};
    try { all = JSON.parse(localStorage.getItem(OVERLAY_KEY) || '{}'); } catch (e) { /* start fresh */ }
    all[pnr] = { ...(all[pnr] || {}), ...patch };
    localStorage.setItem(OVERLAY_KEY, JSON.stringify(all));
    return all[pnr];
}

function isInternational(origin, destination) {
    if (!origin || !destination) return true; // unknown -> ask for documents to be safe
    return !(KENYA_DOMESTIC.has(origin) && KENYA_DOMESTIC.has(destination));
}

/* ---------------------------------------------------------------------- */
/* Search + validation                                                    */
/* ---------------------------------------------------------------------- */

function enrichRecord(byRef) {
    // enrich with passengers.json (passport / DOB / nationality) when we can.
    // NOTE: the seed data reuses the same passport number across unrelated
    // passenger records in a few places, so passport alone isn't a safe key --
    // require it to agree with the flight too before falling back to passport-only.
    let pax = DB.passengers.find(p => byRef.passport && p.passport === byRef.passport && p.flightNumber === byRef.flightNumber);
    if (!pax) pax = DB.passengers.find(p => byRef.passport && p.passport === byRef.passport);
    if (!pax) pax = DB.passengers.find(p => p.flightNumber === byRef.flightNumber && p.name.trim().split(/\s+/).pop().toLowerCase() === byRef.lastName.toLowerCase());

    const record = {
        ...byRef,
        dob: byRef.dob || (pax ? pax.dob : null),
        nationality: byRef.nationality || (pax ? pax.nationality : null),
        passport: byRef.passport || (pax ? pax.passport : null),
        phone: byRef.phone || (pax ? pax.phone : null),
        checkedIn: byRef.checkedIn || (pax ? pax.checkedIn : false)
    };

    const overlay = getOverlay(record.pnr);
    if (overlay && overlay.checkedIn) record.checkedIn = true;

    return { record, overlay };
}

// reference is optional: a passenger who doesn't remember their PNR/e-ticket
// number can leave it blank and search by last name alone. If that turns up
// exactly one booking, it's treated the same as a normal exact match. If it
// turns up more than one (e.g. a family sharing a surname, or a passenger
// with several separate bookings), the caller shows a picker list instead of
// guessing -- the passenger clicks the correct one, then goes through the
// exact same classify() business rules (payment pending / too early / etc.)
// as any other match. A reference that's typed in but doesn't match is NOT
// silently downgraded to a name-only search -- that would leak more possible
// matches than the passenger asked for and defeats the point of entering a
// reference at all.
function findRecord(reference, lastName) {
    const ref = reference.trim().toUpperCase();
    const ln = lastName.trim().toLowerCase();
    if (!ln) return { outcome: 'not_found' };

    const candidates = [];
    if (liveSession) candidates.push(liveSession);
    candidates.push(...DB.bookings);

    if (!ref) {
        const rawMatches = candidates.filter(b => b.lastName.toLowerCase() === ln);
        if (rawMatches.length === 0) return { outcome: 'not_found' };

        const enriched = rawMatches.map(enrichRecord);
        if (enriched.length === 1) {
            const { record, overlay } = enriched[0];
            return classify(record, overlay);
        }
        return { outcome: 'multiple_matches', options: enriched };
    }

    let byRef = candidates.find(b => b.pnr === ref);

    if (!byRef) {
        // Fall back to matching an e-ticket number in passengers.json -- but this
        // must still resolve to a genuine, existing record in bookings.json.
        // SECURITY: a ticket_number that only matches a manifest-only test entry
        // with no real booking behind it (this data has several, e.g. ticket
        // "SF0456" / flight "FL001" -- zero matching bookings.json record) is
        // NOT a valid check-in path. Only a real booking proves someone actually
        // booked and paid, so if none is found here, byRef stays undefined and
        // this correctly falls through to "Booking not found" below -- we never
        // synthesize a booking out of passenger-manifest data alone.
        const pax = DB.passengers.find(p => (p.ticketNumber || '').toUpperCase() === ref);
        if (pax) {
            byRef = DB.bookings.find(b =>
                (pax.passport && b.passport && b.passport === pax.passport && b.flightNumber === pax.flightNumber) ||
                (pax.passport && b.passport && b.passport === pax.passport) ||
                (b.flightNumber && b.flightNumber === pax.flightNumber && b.lastName.toLowerCase() === pax.name.trim().split(/\s+/).pop().toLowerCase())
            );
        }
    }

    if (!byRef) return { outcome: 'not_found' };
    if (byRef.lastName.toLowerCase() !== ln) return { outcome: 'not_found' }; // same message either way -- don't leak which part failed

    const { record, overlay } = enrichRecord(byRef);
    return classify(record, overlay);
}

function classify(record, overlay) {
    if (record.cancelled) return { outcome: 'cancelled', record };
    if (!record.paymentComplete) return { outcome: 'payment_pending', record };
    if (record.checkedIn) return { outcome: 'already_checked_in', record, overlay };

    const now = new Date();
    if (record.departure) {
        const opens = new Date(record.departure.getTime() - CHECKIN_OPENS_HOURS_BEFORE * 3600 * 1000);
        const closes = new Date(record.departure.getTime() - CHECKIN_CLOSES_HOURS_BEFORE * 3600 * 1000);
        if (now > record.departure) return { outcome: 'departed', record };
        if (now > closes) return { outcome: 'too_late', record };
        if (now < opens) return { outcome: 'too_early', record, opensAt: opens };
    }
    return { outcome: 'ok', record };
}

/* ---------------------------------------------------------------------- */
/* Rail                                                                    */
/* ---------------------------------------------------------------------- */

function renderRail() {
    const steps = activeSteps();
    const idx = steps.indexOf(state.step);
    const rail = document.getElementById('rail');
    if (!rail) return;
    if (state.step === 'search' || idx === -1) { rail.innerHTML = ''; return; }
    rail.innerHTML = steps.map((s, i) => {
        const cls = i < idx ? 'done' : (i === idx ? 'current' : '');
        const dot = i < idx ? '<i class="fa-solid fa-check"></i>' : (i + 1);
        const line = i < steps.length - 1 ? '<div class="rail-line"></div>' : '';
        return `<div class="rail-step ${cls}" title="${esc(STEP_LABELS[s])}"><div class="rail-dot">${dot}</div></div>${line}`;
    }).join('');
}

function goStep(name) {
    state.step = name;
    renderRail();
    RENDERERS[name]();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ---------------------------------------------------------------------- */
/* Step: Search                                                           */
/* ---------------------------------------------------------------------- */

function renderSearch() {
    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Online check-in</div>
      <div class="card-title">Find your booking</div>
      <div class="card-sub">Enter your booking reference (PNR) or e-ticket number, along with the last name on the booking.</div>
      <form id="search-form" novalidate>
        <div class="form-group" id="g-ref">
          <label for="ref-input">Booking Reference (PNR) or E-Ticket Number</label>
          <input type="text" id="ref-input" class="form-input" placeholder="e.g. SF-808878">
          <div class="field-error">Enter your booking reference or e-ticket number.</div>
        </div>
        <div class="form-group" id="g-lastname">
          <label for="lastname-input">Last Name</label>
          <input type="text" id="lastname-input" class="form-input mono-off" placeholder="e.g. Kebiro">
          <div class="field-error">Enter the last name on the booking.</div>
        </div>
        <button type="submit" class="btn btn-primary" id="search-btn"><i class="fa-solid fa-magnifying-glass"></i> Find Booking</button>
      </form>
    </div>`;

    document.getElementById('search-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const refInput = document.getElementById('ref-input');
        const lnInput = document.getElementById('lastname-input');
        const gRef = document.getElementById('g-ref');
        const gLn = document.getElementById('g-lastname');
        gRef.classList.toggle('invalid', refInput.value.trim() === '');
        gLn.classList.toggle('invalid', lnInput.value.trim() === '');
        if (refInput.value.trim() === '' || lnInput.value.trim() === '') return;

        const btn = document.getElementById('search-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Searching…';

        setTimeout(() => {
            const result = findRecord(refInput.value, lnInput.value);
            handleSearchResult(result);
        }, 500);
    });
}

function handleSearchResult(result) {
    switch (result.outcome) {
        case 'not_found':
            return renderOutcomeScreen({
                tone: 'error', icon: 'fa-circle-exclamation',
                title: 'Booking not found.',
                body: 'Please check your booking reference and last name and try again.',
                primary: { label: 'Try Again', action: () => goStep('search') }
            });
        case 'payment_pending':
            return renderOutcomeScreen({
                tone: 'warning', icon: 'fa-credit-card',
                title: 'Your booking has not been paid.',
                body: 'Please complete payment before check-in.',
                primary: { label: 'Go to Payment', action: () => window.location.href = 'payment.html' },
                secondary: { label: 'Back', action: () => goStep('search') }
            });
        case 'cancelled':
            return renderOutcomeScreen({
                tone: 'error', icon: 'fa-ban',
                title: 'This booking has been cancelled.',
                body: 'Cancelled bookings are not eligible for check-in. Contact SmartFly support if you believe this is a mistake.',
                primary: { label: 'Back', action: () => goStep('search') }
            });
        case 'departed':
            return renderOutcomeScreen({
                tone: 'error', icon: 'fa-plane-departure',
                title: 'This flight has already departed.',
                body: 'Online check-in is no longer available for this booking.',
                primary: { label: 'Back', action: () => goStep('search') }
            });
        case 'too_late':
            return renderOutcomeScreen({
                tone: 'warning', icon: 'fa-clock',
                title: 'Online check-in has closed.',
                body: `Check-in closes ${CHECKIN_CLOSES_HOURS_BEFORE} hours before departure. Please visit the airport check-in desk.`,
                primary: { label: 'Back', action: () => goStep('search') }
            });
        case 'too_early': {
            state.record = result.record;
            return renderCountdown(result.opensAt);
        }
        case 'already_checked_in':
            state.record = result.record;
            return renderOutcomeScreen({
                tone: 'success', icon: 'fa-circle-check',
                title: 'You have already completed check-in.',
                body: 'Your boarding pass is ready below.',
                primary: { label: 'View Boarding Pass', action: () => showExistingBoardingPass(result.record, result.overlay) }
            });
        case 'ok':
            state.record = result.record;
            state.intl = isInternational(result.record.origin, result.record.destination);
            return goStep('flight-info');
    }
}

function renderOutcomeScreen({ tone, icon, title, body, primary, secondary }) {
    root().innerHTML = `
    <div class="card">
      <div class="outcome ${tone}">
        <i class="fa-solid ${icon} big"></i>
        <h3>${esc(title)}</h3>
        <p>${esc(body)}</p>
      </div>
      <div class="btn-row">
        ${secondary ? `<button class="btn btn-ghost" id="outcome-secondary">${esc(secondary.label)}</button>` : ''}
        <button class="btn btn-primary" id="outcome-primary">${esc(primary.label)}</button>
      </div>
    </div>`;
    document.getElementById('outcome-primary').addEventListener('click', primary.action);
    if (secondary) document.getElementById('outcome-secondary').addEventListener('click', secondary.action);
}

function renderCountdown(opensAt) {
    root().innerHTML = `
    <div class="card">
      <div class="outcome warning">
        <i class="fa-solid fa-hourglass-half big"></i>
        <h3>Check-in opens in</h3>
        <div class="countdown" id="countdown-readout">--</div>
        <p>Check-in for this flight opens ${CHECKIN_OPENS_HOURS_BEFORE} hours before departure (${esc(fmtDateTime(opensAt))}). Come back then.</p>
      </div>
      <div class="btn-row"><button class="btn btn-primary" id="countdown-back">Back</button></div>
    </div>`;
    document.getElementById('countdown-back').addEventListener('click', () => { clearInterval(window.__ciTimer); goStep('search'); });

    const tick = () => {
        const ms = opensAt.getTime() - Date.now();
        const el = document.getElementById('countdown-readout');
        if (!el) return clearInterval(window.__ciTimer);
        if (ms <= 0) { el.textContent = 'Now open'; clearInterval(window.__ciTimer); return; }
        const h = Math.floor(ms / 3600000);
        const m = Math.floor((ms % 3600000) / 60000);
        el.textContent = `${h} Hours ${m} Minutes`;
    };
    tick();
    window.__ciTimer = setInterval(tick, 30000);
}

/* ---------------------------------------------------------------------- */
/* Step: Flight info + verify details                                     */
/* ---------------------------------------------------------------------- */

function renderFlightInfo() {
    const r = state.record;
    const verifyRows = [
        ['Passport', r.passport],
        ['Date of Birth', r.dob ? fmtDateOnly(new Date(r.dob)) : null],
        ['Nationality', r.nationality],
        ['Phone Number', r.phone]
    ];
    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Step ${activeSteps().indexOf('flight-info') + 1} of ${activeSteps().length}</div>
      <div class="card-title">Passenger &amp; flight details</div>
      <div class="card-sub">Confirm this is you before continuing.</div>

      <div class="info-grid">
        <div class="info-item"><div class="k">Passenger</div><div class="v">${esc(r.name)}</div></div>
        <div class="info-item"><div class="k">Flight</div><div class="v route">${esc(r.flightNumber || '—')}</div></div>
        <div class="info-item"><div class="k">From</div><div class="v">${esc(r.origin || 'Not on file')}</div></div>
        <div class="info-item"><div class="k">To</div><div class="v">${esc(r.destination || 'Not on file')}</div></div>
        <div class="info-item"><div class="k">Departure</div><div class="v">${r.departure ? esc(fmtDateTime(r.departure)) : 'Not available'}</div></div>
        <div class="info-item"><div class="k">Seat</div><div class="v">${r.seatOnFile ? esc(String(r.seatOnFile)) : 'Not Assigned'}</div></div>
      </div>

      <div class="divider"></div>

      <div class="card-sub" style="margin-bottom:0.25rem;">On file for this passenger:</div>
      <ul class="verify-list">
        ${verifyRows.map(([k, v]) => `<li><i class="fa-solid ${v ? 'fa-circle-check' : 'fa-circle-minus'}" style="${v ? '' : 'color:var(--text-muted)'}"></i> ${esc(k)} <span class="val">${v ? esc(v) : 'Not on file'}</span></li>`).join('')}
      </ul>

      <div class="notice-box"><i class="fa-solid fa-circle-info"></i> Passenger details can't be edited during check-in. If anything above is incorrect, contact the airline before continuing.</div>

      <div class="btn-row">
        <button class="btn btn-ghost" id="fi-back">Back</button>
        <button class="btn btn-primary" id="fi-continue">These details are correct — Continue</button>
      </div>
    </div>`;
    document.getElementById('fi-back').addEventListener('click', () => goStep('search'));
    document.getElementById('fi-continue').addEventListener('click', () => goStep(state.intl ? 'documents' : 'baggage'));
}

/* ---------------------------------------------------------------------- */
/* Step: Travel documents (international only)                            */
/* ---------------------------------------------------------------------- */

function renderDocuments() {
    const r = state.record;
    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Step ${activeSteps().indexOf('documents') + 1} of ${activeSteps().length}</div>
      <div class="card-title">Travel document validation</div>
      <div class="card-sub">This is an international flight (${esc(r.origin || '?')} \u2192 ${esc(r.destination || '?')}). Confirm your travel documents.</div>
      <form id="doc-form" novalidate>
        <div class="form-group" id="g-passport">
          <label for="doc-passport">Passport Number</label>
          <input type="text" id="doc-passport" class="form-input" value="${esc(r.passport || '')}" placeholder="e.g. A12345678">
          <div class="field-error">Enter a valid passport number (6-9 letters/digits).</div>
        </div>
        <div class="form-group" id="g-expiry">
          <label for="doc-expiry">Passport Expiry</label>
          <input type="date" id="doc-expiry" class="form-input mono-off">
          <div class="field-error">Passport expired. Please update your travel document.</div>
        </div>
        <div class="form-group" id="g-country">
          <label for="doc-country">Country</label>
          <input type="text" id="doc-country" class="form-input mono-off" placeholder="e.g. Kenya">
          <div class="field-error">Enter the issuing country.</div>
        </div>
        <div class="form-group">
          <label for="doc-visa">Visa Number <span style="font-weight:400; color:var(--text-muted);">(if applicable)</span></label>
          <input type="text" id="doc-visa" class="form-input mono-off" placeholder="Optional">
        </div>
        <div class="btn-row">
          <button type="button" class="btn btn-ghost" id="doc-back">Back</button>
          <button type="submit" class="btn btn-primary">Continue</button>
        </div>
      </form>
    </div>`;

    document.getElementById('doc-back').addEventListener('click', () => goStep('flight-info'));
    document.getElementById('doc-form').addEventListener('submit', (e) => {
        e.preventDefault();
        const passport = document.getElementById('doc-passport').value.trim().toUpperCase();
        const expiryVal = document.getElementById('doc-expiry').value;
        const country = document.getElementById('doc-country').value.trim();
        const visa = document.getElementById('doc-visa').value.trim();

        let ok = true;
        const gP = document.getElementById('g-passport'), gE = document.getElementById('g-expiry'), gC = document.getElementById('g-country');
        gP.classList.remove('invalid'); gE.classList.remove('invalid'); gC.classList.remove('invalid');

        if (!/^[A-Z0-9]{6,9}$/.test(passport)) { gP.classList.add('invalid'); ok = false; }

        if (!expiryVal) { gE.classList.add('invalid'); gE.querySelector('.field-error').textContent = 'Passport expiry date is required.'; ok = false; }
        else {
            const expiry = new Date(expiryVal);
            const reference = r.departure || new Date();
            if (expiry <= reference) {
                gE.classList.add('invalid');
                gE.querySelector('.field-error').textContent = 'Passport expired. Please update your travel document.';
                ok = false;
            }
        }
        if (country === '') { gC.classList.add('invalid'); ok = false; }

        if (!ok) return;
        state.docs = { passportNumber: passport, passportExpiry: expiryVal, country, visa };
        goStep('baggage');
    });
}

/* ---------------------------------------------------------------------- */
/* Step: Baggage                                                          */
/* ---------------------------------------------------------------------- */

function renderBaggage() {
    const r = state.record;
    const entitledKg = (r.baggageAllowance || 1) * 20;
    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Step ${activeSteps().indexOf('baggage') + 1} of ${activeSteps().length}</div>
      <div class="card-title">Baggage declaration</div>
      <div class="card-sub">Your fare includes ${r.baggageAllowance || 1} checked bag(s), up to ${entitledKg}kg total.</div>

      <div class="card-sub" style="margin-bottom:0.75rem; font-weight:700; color:var(--text-main);">Will you check baggage?</div>
      <div class="choice-row" id="bag-yesno">
        <div class="choice-tile" data-val="no">No<span class="sub">Carry-on only</span></div>
        <div class="choice-tile" data-val="yes">Yes<span class="sub">Check a bag</span></div>
      </div>

      <div id="bag-weight-wrap" class="hidden" style="margin-top:1.25rem;">
        <div class="card-sub" style="margin-bottom:0.75rem; font-weight:700; color:var(--text-main);">Choose weight</div>
        <div class="choice-row" id="bag-weight">
          <div class="choice-tile" data-val="20">20kg</div>
          <div class="choice-tile" data-val="30">30kg</div>
          <div class="choice-tile" data-val="40">40kg</div>
        </div>
        <div id="bag-extra-notice" class="notice-box hidden" style="background:var(--warning-light); border-color:#FDE68A; color:#B45309;"><i class="fa-solid fa-triangle-exclamation"></i> Extra baggage charges apply — your fare covers up to ${entitledKg}kg.</div>
      </div>

      <div class="btn-row">
        <button class="btn btn-ghost" id="bag-back">Back</button>
        <button class="btn btn-primary" id="bag-continue" disabled>Continue</button>
      </div>
    </div>`;

    const continueBtn = document.getElementById('bag-continue');
    document.getElementById('bag-back').addEventListener('click', () => goStep(state.intl ? 'documents' : 'flight-info'));

    document.querySelectorAll('#bag-yesno .choice-tile').forEach(tile => {
        tile.addEventListener('click', () => {
            document.querySelectorAll('#bag-yesno .choice-tile').forEach(t => t.classList.remove('selected'));
            tile.classList.add('selected');
            state.baggage.wants = tile.dataset.val;
            const weightWrap = document.getElementById('bag-weight-wrap');
            if (tile.dataset.val === 'yes') {
                weightWrap.classList.remove('hidden');
                continueBtn.disabled = !state.baggage.weight;
            } else {
                weightWrap.classList.add('hidden');
                state.baggage.weight = null;
                continueBtn.disabled = false;
            }
        });
    });
    document.querySelectorAll('#bag-weight .choice-tile').forEach(tile => {
        tile.addEventListener('click', () => {
            document.querySelectorAll('#bag-weight .choice-tile').forEach(t => t.classList.remove('selected'));
            tile.classList.add('selected');
            const kg = parseInt(tile.dataset.val, 10);
            state.baggage.weight = kg;
            document.getElementById('bag-extra-notice').classList.toggle('hidden', kg <= entitledKg);
            continueBtn.disabled = false;
        });
    });

    continueBtn.addEventListener('click', () => goStep('dangerous-goods'));
}

/* ---------------------------------------------------------------------- */
/* Step: Dangerous goods                                                  */
/* ---------------------------------------------------------------------- */

function renderDangerousGoods() {
    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Step ${activeSteps().indexOf('dangerous-goods') + 1} of ${activeSteps().length}</div>
      <div class="card-title">Dangerous goods declaration</div>
      <div class="card-sub">Required by aviation safety regulations for every passenger.</div>

      <ul class="dg-list">
        <li><i class="fa-solid fa-explosion"></i> Explosives</li>
        <li><i class="fa-solid fa-battery-full"></i> Batteries beyond the permitted limit</li>
        <li><i class="fa-solid fa-flask"></i> Dangerous chemicals</li>
        <li><i class="fa-solid fa-gun"></i> Firearms</li>
      </ul>

      <label class="checkbox-row" for="dg-check">
        <input type="checkbox" id="dg-check">
        <span>I confirm that I am <strong>not</strong> carrying any of the items listed above.</span>
      </label>

      <div class="btn-row">
        <button class="btn btn-ghost" id="dg-back">Back</button>
        <button class="btn btn-primary" id="dg-continue" disabled>Continue</button>
      </div>
    </div>`;
    document.getElementById('dg-back').addEventListener('click', () => goStep('baggage'));
    document.getElementById('dg-check').addEventListener('change', (e) => {
        state.dgAccepted = e.target.checked;
        document.getElementById('dg-continue').disabled = !e.target.checked;
    });
    document.getElementById('dg-continue').addEventListener('click', () => goStep('seat'));
}

/* ---------------------------------------------------------------------- */
/* Step: Seat map                                                         */
/* ---------------------------------------------------------------------- */

function renderSeat() {
    const r = state.record;
    const rand = seededRandom(r.flightNumber || r.pnr);
    const rows = 12, cols = ['A', 'B', 'C', 'D', 'E', 'F'];
    const occupied = new Set();
    for (let row = 1; row <= rows; row++) {
        for (const c of cols) {
            if (rand() < 0.32) occupied.add(`${row}${c}`);
        }
    }
    state.__occupied = occupied;

    let rowsHtml = '';
    for (let row = 1; row <= rows; row++) {
        let cells = `<span class="row-label">${row}</span>`;
        cols.forEach((c, i) => {
            const id = `${row}${c}`;
            const isOcc = occupied.has(id);
            cells += `<button type="button" class="seat ${isOcc ? 'occupied' : ''}" data-seat="${id}" ${isOcc ? 'disabled' : ''}>${id}</button>`;
            if (i === 2) cells += '<span class="aisle-gap"></span>';
        });
        rowsHtml += `<div class="seat-row">${cells}</div>`;
    }

    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Step ${activeSteps().indexOf('seat') + 1} of ${activeSteps().length}</div>
      <div class="card-title">Select your seat</div>
      <div class="card-sub">Flight ${esc(r.flightNumber || '—')} \u00b7 ${esc((r.seatClass || 'economy').toString())}</div>

      <div class="seat-legend">
        <span><span class="legend-swatch" style="background:#D1FAE5;"></span> Available</span>
        <span><span class="legend-swatch" style="background:#E2E8F0;"></span> Occupied</span>
        <span><span class="legend-swatch" style="background:var(--primary-blue);"></span> Selected</span>
      </div>

      <div class="seat-selected-readout" id="seat-readout">No seat selected</div>
      <div class="seat-map">${rowsHtml}</div>
      <div id="seat-toast" class="notice-box hidden" style="background:var(--error-light); border-color:#FCA5A5; color:var(--error); justify-content:center;"><i class="fa-solid fa-circle-exclamation"></i> Seat unavailable.</div>

      <div class="btn-row">
        <button class="btn btn-ghost" id="seat-back">Back</button>
        <button class="btn btn-primary" id="seat-continue" disabled>Continue</button>
      </div>
    </div>`;

    document.getElementById('seat-back').addEventListener('click', () => goStep('dangerous-goods'));
    const continueBtn = document.getElementById('seat-continue');
    const readout = document.getElementById('seat-readout');
    const toast = document.getElementById('seat-toast');

    document.querySelectorAll('.seat').forEach(btn => {
        btn.addEventListener('click', () => {
            if (btn.classList.contains('occupied')) {
                toast.classList.remove('hidden');
                setTimeout(() => toast.classList.add('hidden'), 2000);
                return;
            }
            document.querySelectorAll('.seat.selected').forEach(s => s.classList.remove('selected'));
            btn.classList.add('selected');
            state.seat = btn.dataset.seat;
            readout.innerHTML = `Selected seat: <b>${esc(state.seat)}</b>`;
            continueBtn.disabled = false;
        });
    });
    continueBtn.addEventListener('click', () => goStep('special-requests'));
}

/* ---------------------------------------------------------------------- */
/* Step: Special requests                                                 */
/* ---------------------------------------------------------------------- */

const SPECIAL_OPTIONS = [
    { id: 'wheelchair', label: 'Wheelchair assistance', icon: 'fa-wheelchair-move' },
    { id: 'infant', label: 'Traveling with an infant', icon: 'fa-baby' },
    { id: 'legroom', label: 'Extra legroom', icon: 'fa-ruler-vertical' },
    { id: 'medical', label: 'Medical assistance', icon: 'fa-suitcase-medical' }
];

function renderSpecialRequests() {
    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Step ${activeSteps().indexOf('special-requests') + 1} of ${activeSteps().length}</div>
      <div class="card-title">Special requests</div>
      <div class="card-sub">Optional — select anything that applies.</div>

      ${SPECIAL_OPTIONS.map(o => `
        <label class="checkbox-row" for="sr-${o.id}">
          <input type="checkbox" id="sr-${o.id}" value="${o.id}">
          <span><i class="fa-solid ${o.icon}" style="width:18px; color:var(--primary-blue);"></i> ${esc(o.label)}</span>
        </label>`).join('')}

      <div class="btn-row">
        <button class="btn btn-ghost" id="sr-back">Back</button>
        <button class="btn btn-primary" id="sr-continue">Continue</button>
      </div>
    </div>`;
    document.getElementById('sr-back').addEventListener('click', () => goStep('seat'));
    document.getElementById('sr-continue').addEventListener('click', () => {
        state.special = SPECIAL_OPTIONS.filter(o => document.getElementById(`sr-${o.id}`).checked).map(o => o.label);
        goStep('confirm');
    });
}

/* ---------------------------------------------------------------------- */
/* Step: Confirm                                                          */
/* ---------------------------------------------------------------------- */

function renderConfirm() {
    const r = state.record;
    root().innerHTML = `
    <div class="card">
      <div class="card-eyebrow">Step ${activeSteps().indexOf('confirm') + 1} of ${activeSteps().length}</div>
      <div class="card-title">Ready to check in?</div>
      <div class="card-sub">Review your details before confirming.</div>

      <div class="summary-row"><span class="k">Passenger</span><span class="v">${esc(r.name)}</span></div>
      <div class="summary-row"><span class="k">Flight</span><span class="v">${esc(r.flightNumber || '—')}</span></div>
      <div class="summary-row"><span class="k">Route</span><span class="v">${esc(r.origin || '?')} \u2192 ${esc(r.destination || '?')}</span></div>
      <div class="summary-row"><span class="k">Seat</span><span class="v">${esc(state.seat)}</span></div>
      <div class="summary-row"><span class="k">Baggage</span><span class="v">${state.baggage.wants === 'yes' ? state.baggage.weight + 'kg checked' : 'Carry-on only'}</span></div>
      <div class="summary-row"><span class="k">Special requests</span><span class="v">${state.special.length ? esc(state.special.join(', ')) : 'None'}</span></div>
      <div class="summary-row"><span class="k">Safety declaration</span><span class="v"><i class="fa-solid fa-circle-check" style="color:var(--success);"></i> Accepted</span></div>
      ${state.intl ? `<div class="summary-row"><span class="k">Passport</span><span class="v">${esc(state.docs.passportNumber)}</span></div>` : ''}

      <div class="btn-row">
        <button class="btn btn-ghost" id="confirm-back">Back</button>
        <button class="btn btn-primary" id="confirm-submit"><i class="fa-solid fa-lock"></i> Confirm Check-in</button>
      </div>
    </div>`;
    document.getElementById('confirm-back').addEventListener('click', () => goStep('special-requests'));
    document.getElementById('confirm-submit').addEventListener('click', submitCheckin);
}

function submitCheckin() {
    const r = state.record;
    const rand = seededRandom(r.flightNumber || r.pnr);
    const gates = ['A1', 'A2', 'A3', 'B4', 'B5', 'B6', 'C1', 'C2', 'C7'];
    const terminals = ['1A', '1B', 'Terminal 2'];
    const gate = gates[Math.floor(rand() * gates.length)];
    const terminal = terminals[Math.floor(rand() * terminals.length)];
    const boardingTime = r.departure ? new Date(r.departure.getTime() - 45 * 60000) : null;

    const now = new Date();
    const checkinTimeStr = now.toISOString().slice(0, 19).replace('T', ' ');

    const boarding = {
        gate, terminal,
        boardingTime: boardingTime ? fmtTimeOnly(boardingTime) : '—',
        departureTime: r.departure ? fmtTimeOnly(r.departure) : '—',
        seat: state.seat
    };
    state.boarding = boarding;

    setOverlay(r.pnr, {
        checkedIn: true,
        seat: state.seat,
        checkinTime: checkinTimeStr,
        baggage: state.baggage,
        special: state.special,
        boarding
    });

    // Keep the live (today's) booking session consistent too, if that's what this was
    if (r.source === 'live-session') {
        try {
            const s = JSON.parse(sessionStorage.getItem('smartflyBookingSession') || '{}');
            s.checkedIn = true;
            s.seat = state.seat;
            sessionStorage.setItem('smartflyBookingSession', JSON.stringify(s));
        } catch (e) { /* non-fatal */ }
    }

    // Best-effort sync to the real backend so this check-in shows up in the
    // admin dashboard's Check-Ins panel. Previously this flow only ever wrote
    // to localStorage in this browser and never called the backend at all --
    // that's why admin never saw new check-ins. Fire-and-forget: a network
    // hiccup here shouldn't block the passenger from getting their boarding
    // pass, since the localStorage overlay above already makes check-in work
    // correctly in this browser regardless of whether the sync succeeds.
    syncCheckinToBackend(r, state.seat);

    goStep('boarding-pass');
}

function syncCheckinToBackend(r, seat) {
    if (!r.passport) {
        console.warn('No passport on file for this booking — skipping backend check-in sync (it will not appear on the admin dashboard).');
        return;
    }
    fetch('/api/checkin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            flight: r.flightNumber || '',
            passengers: [{
                name: r.name,
                passport: r.passport,
                seat: String(seat)
            }]
        })
    })
        .then((res) => res.json().catch(() => ({})).then((body) => ({ ok: res.ok, body })))
        .then(({ ok, body }) => {
            if (!ok) { console.warn('Backend check-in sync failed:', body); return; }
            const result = (body.results && body.results[0]) || {};
            if (result.status !== 'ok') console.warn('Backend check-in sync returned an error:', result);
        })
        .catch((err) => console.warn('Backend check-in sync failed (network):', err));
}

/* ---------------------------------------------------------------------- */
/* Step: Boarding pass + completion                                       */
/* ---------------------------------------------------------------------- */

function showExistingBoardingPass(record, overlay) {
    state.record = record;
    state.seat = (overlay && overlay.seat) || (record.seatOnFile ? String(record.seatOnFile) : 'Not Assigned');
    state.boarding = (overlay && overlay.boarding) || (() => {
        const rand = seededRandom(record.flightNumber || record.pnr);
        const gates = ['A1', 'A2', 'A3', 'B4', 'B5', 'B6', 'C1', 'C2', 'C7'];
        const terminals = ['1A', '1B', 'Terminal 2'];
        return {
            gate: gates[Math.floor(rand() * gates.length)],
            terminal: terminals[Math.floor(rand() * terminals.length)],
            boardingTime: record.departure ? fmtTimeOnly(new Date(record.departure.getTime() - 45 * 60000)) : '—',
            departureTime: record.departure ? fmtTimeOnly(record.departure) : '—',
            seat: state.seat
        };
    })();
    state.step = 'boarding-pass';
    renderRail();
    renderBoardingPass();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderBoardingPass() {
    const r = state.record;
    const b = state.boarding;
    root().innerHTML = `
    <div class="card">
      <div class="outcome success" style="margin-bottom:1.5rem;">
        <i class="fa-solid fa-circle-check big"></i>
        <h3>Check-in Complete</h3>
        <p>Have a pleasant journey! Boarding starts at ${esc(b.boardingTime)} \u00b7 Gate ${esc(b.gate)}</p>
      </div>

      <div class="pass-wrap">
        <div class="pass" id="pass-capture">
          <div class="pass-top">
            <div class="pass-brand">
              <div class="name">Smart<span>Fly</span> Airways</div>
              <div class="class-tag">${esc((r.seatClass || 'economy').toString())}</div>
            </div>
            <div class="pass-route">
              <div><div class="city">${esc(r.origin || '???')}</div><div class="city-name">Origin</div></div>
              <i class="fa-solid fa-plane plane-icon"></i>
              <div style="text-align:right;"><div class="city">${esc(r.destination || '???')}</div><div class="city-name">Destination</div></div>
            </div>
            <div class="pass-grid">
              <div><div class="k">Passenger</div><div class="v" style="font-size:0.85rem;">${esc(r.name)}</div></div>
              <div><div class="k">Flight</div><div class="v">${esc(r.flightNumber || '—')}</div></div>
              <div><div class="k">Seat</div><div class="v">${esc(state.seat)}</div></div>
              <div><div class="k">Gate</div><div class="v">${esc(b.gate)}</div></div>
              <div><div class="k">Boarding</div><div class="v">${esc(b.boardingTime)}</div></div>
              <div><div class="k">Departure</div><div class="v">${esc(b.departureTime)}</div></div>
              <div><div class="k">Terminal</div><div class="v">${esc(b.terminal)}</div></div>
              <div><div class="k">Date</div><div class="v" style="font-size:0.78rem;">${r.departure ? esc(fmtDateOnly(r.departure)) : '—'}</div></div>
            </div>
          </div>
          <div class="pass-tear"></div>
          <div class="pass-bottom">
            <div class="pass-qr" id="qr-holder"></div>
            <div class="pass-bottom-info">
              <div class="pnr">${esc(r.pnr)}</div>
              <div class="hint">Scan this code at the gate.<br>Please arrive by the boarding time shown.</div>
            </div>
          </div>
        </div>
      </div>

      <div class="download-row no-print">
        <button class="btn" id="dl-pdf"><i class="fa-solid fa-file-pdf"></i> Download PDF</button>
        <button class="btn" id="dl-print"><i class="fa-solid fa-print"></i> Print</button>
        <button class="btn" id="dl-email"><i class="fa-solid fa-envelope"></i> Email Boarding Pass</button>
      </div>

      <div class="btn-row no-print">
        <button class="btn btn-primary" id="dl-return" style="flex:1;">Return Home</button>
      </div>
    </div>`;

    if (window.QRCode) {
        new QRCode(document.getElementById('qr-holder'), {
            text: `SMARTFLY|${r.pnr}|${r.name}|${r.flightNumber}|${state.seat}`,
            width: 90, height: 90, colorDark: '#0F172A', colorLight: '#ffffff'
        });
    }

    document.getElementById('dl-print').addEventListener('click', () => window.print());
    document.getElementById('dl-return').addEventListener('click', () => { window.location.href = 'index.html'; });
    document.getElementById('dl-email').addEventListener('click', () => {
        const subject = encodeURIComponent(`Your SmartFly boarding pass — ${r.pnr}`);
        const body = encodeURIComponent(
            `SmartFly Airways — Boarding Pass\n\nPassenger: ${r.name}\nFlight: ${r.flightNumber}\nRoute: ${r.origin} -> ${r.destination}\nSeat: ${state.seat}\nGate: ${b.gate}\nBoarding: ${b.boardingTime}\nDeparture: ${b.departureTime}\nTerminal: ${b.terminal}\nBooking Ref: ${r.pnr}`
        );
        window.location.href = `mailto:${r.email || ''}?subject=${subject}&body=${body}`;
    });
    document.getElementById('dl-pdf').addEventListener('click', () => downloadPassPdf(r, b));
}

function downloadPassPdf(r, b) {
    if (!window.jspdf) { alert('PDF generation library did not load — check your connection and try again.'); return; }
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: 'mm', format: [100, 165] });
    const pageW = 100;

    // Grab the real QR code already rendered on screen (QRCode.js draws to a
    // <canvas> inside #qr-holder) so the PDF shows an actual scannable code
    // instead of a placeholder box.
    let qrDataUrl = null;
    try {
        const qrCanvas = document.querySelector('#qr-holder canvas');
        if (qrCanvas) qrDataUrl = qrCanvas.toDataURL('image/png');
    } catch (e) { qrDataUrl = null; }

    // ---- background ----
    doc.setFillColor(15, 23, 42);
    doc.rect(0, 0, pageW, 165, 'F');
    doc.setFillColor(37, 99, 235);
    doc.rect(0, 0, pageW, 1.6, 'F'); // top accent stripe, matches the site navbar

    // ---- brand row ----
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(14);
    doc.setTextColor(255, 255, 255);
    doc.text('Smart', 8, 14);
    const wSmart = doc.getTextWidth('Smart');
    doc.setTextColor(96, 165, 250);
    doc.text('Fly', 8 + wSmart, 14);
    const wFly = doc.getTextWidth('Fly');
    doc.setTextColor(255, 255, 255);
    doc.text(' Airways', 8 + wSmart + wFly, 14);

    // class badge, top-right
    const cls = (r.seatClass || 'Economy').toString().toUpperCase();
    doc.setFontSize(7);
    doc.setFont('helvetica', 'bold');
    const tagW = doc.getTextWidth(cls) + 6;
    const tagX = (pageW - 8) - tagW;
    doc.setFillColor(30, 58, 95);
    doc.roundedRect(tagX, 8.5, tagW, 6, 1.5, 1.5, 'F');
    doc.setTextColor(147, 197, 253);
    doc.text(cls, tagX + 3, 12.7);

    doc.setDrawColor(51, 65, 85);
    doc.setLineWidth(0.2);
    doc.line(8, 19, pageW - 8, 19);

    // ---- big route codes with a plane divider ----
    const originText = (r.origin || '???').toString();
    const destText = (r.destination || '???').toString();

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(26);
    doc.setTextColor(255, 255, 255);
    doc.text(originText, 8, 35);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(148, 163, 184);
    doc.text('ORIGIN', 8, 40);

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(26);
    doc.setTextColor(255, 255, 255);
    const destW = doc.getTextWidth(destText);
    doc.text(destText, pageW - 8 - destW, 35);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(148, 163, 184);
    const destLabelW = doc.getTextWidth('DESTINATION');
    doc.text('DESTINATION', pageW - 8 - destLabelW, 40);

    doc.setDrawColor(96, 165, 250);
    doc.setLineWidth(0.35);
    doc.setLineDashPattern([1, 1.2], 0);
    doc.line(37, 31, 63, 31);
    doc.setLineDashPattern([], 0);
    doc.setFillColor(96, 165, 250);
    doc.triangle(58, 29.3, 58, 32.7, 63.5, 31, 'F'); // simple plane-nose marker

    doc.setDrawColor(51, 65, 85);
    doc.line(8, 46, pageW - 8, 46);

    // ---- 4x2 info grid, mirrors the on-screen pass-grid ----
    const colW = (pageW - 16) / 4;
    const drawGridRow = (items, labelY, valueY) => {
        items.forEach((item, i) => {
            const x = 8 + i * colW;
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(6.3);
            doc.setTextColor(148, 163, 184);
            doc.text(item[0], x, labelY);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(9);
            doc.setTextColor(255, 255, 255);
            const lines = doc.splitTextToSize(String(item[1] ?? '—'), colW - 2);
            doc.text(lines, x, valueY);
        });
    };
    drawGridRow(
        [['PASSENGER', r.name], ['FLIGHT', r.flightNumber || '—'], ['SEAT', state.seat], ['GATE', b.gate]],
        54, 59
    );
    drawGridRow(
        [['BOARDING', b.boardingTime], ['DEPARTURE', b.departureTime], ['TERMINAL', b.terminal],
         ['DATE', r.departure ? fmtDateOnly(r.departure) : '—']],
        70, 75
    );

    // ---- perforated tear line ----
    const tearY = 85;
    doc.setDrawColor(71, 85, 105);
    doc.setLineWidth(0.3);
    doc.setLineDashPattern([1.5, 1.5], 0);
    doc.line(4, tearY, pageW - 4, tearY);
    doc.setLineDashPattern([], 0);
    doc.setFillColor(248, 250, 252); // matches --bg-light behind the page, simulates a punched notch
    doc.circle(0, tearY, 3, 'F');
    doc.circle(pageW, tearY, 3, 'F');

    // ---- QR + PNR ----
    const qrY = 95;
    doc.setFillColor(255, 255, 255);
    doc.roundedRect(8, qrY, 34, 34, 2, 2, 'F');
    if (qrDataUrl) {
        doc.addImage(qrDataUrl, 'PNG', 10, qrY + 2, 30, 30);
    } else {
        doc.setTextColor(15, 23, 42);
        doc.setFontSize(7);
        doc.setFont('helvetica', 'bold');
        doc.text('SCAN AT', 14, qrY + 16);
        doc.text('THE GATE', 13, qrY + 21);
    }

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(13);
    doc.setTextColor(255, 255, 255);
    doc.text(String(r.pnr || '—'), 46, qrY + 8);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.3);
    doc.setTextColor(148, 163, 184);
    const hintLines = doc.splitTextToSize('Scan this code at the gate. Please arrive by the boarding time shown.', pageW - 54);
    doc.text(hintLines, 46, qrY + 15);

    // ---- footer ----
    doc.setDrawColor(30, 41, 59);
    doc.line(8, 150, pageW - 8, 150);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(100, 116, 139);
    doc.text('Thank you for flying SmartFly.', 8, 156);
    doc.text('Boarding closes 20 min before departure.', 8, 161);

    doc.save(`SmartFly-BoardingPass-${r.pnr}.pdf`);
}

/* ---------------------------------------------------------------------- */
/* Renderer table + boot                                                  */
/* ---------------------------------------------------------------------- */

const RENDERERS = {
    'search': renderSearch,
    'flight-info': renderFlightInfo,
    'documents': renderDocuments,
    'baggage': renderBaggage,
    'dangerous-goods': renderDangerousGoods,
    'seat': renderSeat,
    'special-requests': renderSpecialRequests,
    'confirm': renderConfirm,
    'boarding-pass': renderBoardingPass
};

document.addEventListener('DOMContentLoaded', async () => {
    const err = await loadDatabase();
    if (err) {
        root().innerHTML = `
        <div class="card">
          <div class="outcome error">
            <i class="fa-solid fa-plug-circle-xmark big"></i>
            <h3>Couldn't load booking data</h3>
            <p>${esc(err)} Make sure bookings.json and passengers.json are served from the same folder as this page (or update BOOKINGS_URL / PASSENGERS_URL in checkin-validation.js).</p>
          </div>
        </div>`;
        return;
    }
    renderSearch();
});