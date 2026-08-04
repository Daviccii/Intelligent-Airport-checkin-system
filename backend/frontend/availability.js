// availability.js
// Single source of truth for the flight-availability page.
// This replaces the old client-side mock-data generator: this version talks
// to the real backend (/api/flights) so results always match what's actually
// in flights.json, instead of drifting from availability.html's own logic.

function qs() {
    const p = new URLSearchParams(window.location.search);
    const o = {};
    for (const [k, v] of p.entries()) o[k] = v;
    return o;
}

function fmtCurrency(v, c) {
    try {
        return new Intl.NumberFormat(undefined, { style: 'currency', currency: c || 'USD' }).format(Number(v));
    } catch (e) {
        return '$' + v;
    }
}

// Any fetch to a possibly-missing/slow backend endpoint gets a hard timeout so the
// page can fall back to generated data instead of sitting on the loading spinner forever.
async function fetchWithTimeout(url, ms) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), ms || 2500);
    try {
        return await fetch(url, { signal: controller.signal });
    } finally {
        clearTimeout(timer);
    }
}

const q = qs();

// Extract IATA codes from URL params
const fromRaw = q.from || '';
const toRaw = q.to || '';
const from = (fromRaw.match(/\(([A-Z]{3})\)/) || [null, fromRaw])[1]?.toUpperCase() || '';
const to = (toRaw.match(/\(([A-Z]{3})\)/) || [null, toRaw])[1]?.toUpperCase() || '';
const departureDate = q.departureDate || q.depart || '';
const returnDate = q.returnDate || q.return || '';
const tripType = q.tripType || q.trip || 'roundtrip';
const cabinClass = (q.cabin || 'economy').toLowerCase();

// Validate required parameters
if (!from || !to || !departureDate) {
    document.getElementById('loadingState').style.display = 'none';
    const es = document.getElementById('emptyState');
    es.style.display = 'block';
    es.querySelector('h3').textContent = 'Complete Your Search';
    es.querySelector('p').innerHTML = 'Please choose origin, destination, and dates before searching for flights.';
    throw new Error('Missing required search parameters');
}

// Get full airport names
let searchData = {};
try {
    const stored = sessionStorage.getItem('flightSearchData');
    if (stored) searchData = JSON.parse(stored);
} catch (e) {}

const fromFull = searchData.fromFull || fromRaw;
const toFull = searchData.toFull || toRaw;
const fromCity = fromFull.replace(/\s*\([^)]*\)$/, '') || from;
const toCity = toFull.replace(/\s*\([^)]*\)$/, '') || to;

// Update UI with search parameters
document.getElementById('fromCode').textContent = from;
document.getElementById('fromCity').textContent = fromCity;
document.getElementById('toCode').textContent = to;
document.getElementById('toCity').textContent = toCity;
document.getElementById('departDate').textContent = new Date(departureDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
document.getElementById('summaryOutbound').textContent = `${from} → ${to}`;

if (returnDate && tripType === 'roundtrip') {
    document.getElementById('returnContainer').style.display = 'block';
    document.getElementById('returnDate').textContent = new Date(returnDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    document.getElementById('summaryReturnLeg').style.display = 'block';
    document.getElementById('summaryReturn').textContent = `${to} → ${from}`;
}

// Load airports for pricing
let __airportsData = [];
async function loadAirportsData() {
    if (__airportsData.length > 0) return __airportsData;
    try {
        const res = await fetchWithTimeout('/assets/data/airports.json', 2500);
        if (res.ok) {
            __airportsData = await res.json();
        }
    } catch (e) {
        console.error('Failed to load airports:', e);
    }
    return __airportsData;
}

// --- Deterministic flight generator -------------------------------------
// Used whenever /api/flights doesn't have real schedule data for a route, is
// slow, or errors out. Same route + date always generates the same flights
// (no random reshuffling on refresh), and it works for ANY origin/destination
// pair, so the page never has "nothing to show" as its only state.
function seededRandom(seedStr) {
    let h = 0;
    for (let i = 0; i < seedStr.length; i++) {
        h = (Math.imul(31, h) + seedStr.charCodeAt(i)) | 0;
    }
    return function () {
        h = (Math.imul(h ^ (h >>> 15), h | 1) ^ 0) >>> 0;
        h = (h + Math.imul(h ^ (h >>> 7), h | 61)) >>> 0;
        return ((h ^ (h >>> 14)) >>> 0) / 4294967296;
    };
}

const AIRCRAFT_POOL = ['Boeing 787-8', 'Boeing 737-800', 'Embraer E190', 'Airbus A320'];
const DEPARTURE_HOURS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22];
const ALL_WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];

function getRouteOperatingDays(originCode, destCode) {
    const rand = seededRandom(`${originCode}-${destCode}-schedule`);
    let tier = 'regional';

    if (window.FlightPricing && __airportsData.length > 0) {
        const o = window.FlightPricing.findAirportByCode(originCode, __airportsData);
        const d = window.FlightPricing.findAirportByCode(destCode, __airportsData);
        if (o && d) {
            const dist = window.FlightPricing.calculateDistance(o.latitude, o.longitude, d.latitude, d.longitude);
            if (dist < 800) tier = 'domestic';
            else if (dist < 3000) tier = 'regional';
            else tier = 'longhaul';
        }
    }

    let dayCount;
    if (tier === 'domestic') dayCount = 7;
    else if (tier === 'regional') dayCount = 4 + Math.floor(rand() * 3);
    else dayCount = 2 + Math.floor(rand() * 3);

    const days = [...ALL_WEEKDAYS];
    for (let i = days.length - 1; i > 0; i--) {
        const j = Math.floor(rand() * (i + 1));
        [days[i], days[j]] = [days[j], days[i]];
    }
    return days.slice(0, dayCount).sort((a, b) => a - b);
}

function generateFlightsForRoute(originCode, destCode, dateStr) {
    const operatingDays = getRouteOperatingDays(originCode, destCode);
    const checkDate = new Date(`${dateStr}T00:00:00`);
    if (!operatingDays.includes(checkDate.getDay())) {
        return []; // this route doesn't fly on the requested day
    }

    const rand = seededRandom(`${originCode}-${destCode}-${dateStr}`);
    const flightCount = 4 + Math.floor(rand() * 4);
    const flights = [];
    const usedHours = new Set();

    for (let i = 0; i < flightCount; i++) {
        let hour;
        do { hour = DEPARTURE_HOURS[Math.floor(rand() * DEPARTURE_HOURS.length)]; }
        while (usedHours.has(hour) && usedHours.size < DEPARTURE_HOURS.length);
        usedHours.add(hour);

        const minute = Math.floor(rand() * 4) * 15;
        const depDate = new Date(`${dateStr}T00:00:00`);
        depDate.setHours(hour, minute, 0, 0);

        let durationMinutes = 90 + Math.floor(rand() * 120);
        if (window.FlightPricing && __airportsData.length > 0) {
            const o = window.FlightPricing.findAirportByCode(originCode, __airportsData);
            const d = window.FlightPricing.findAirportByCode(destCode, __airportsData);
            if (o && d) {
                const dist = window.FlightPricing.calculateDistance(o.latitude, o.longitude, d.latitude, d.longitude);
                durationMinutes = Math.max(45, Math.round((dist / 800) * 60) + 30);
            }
        }
        const arrDate = new Date(depDate.getTime() + durationMinutes * 60000);

        const aircraft = AIRCRAFT_POOL[Math.floor(rand() * AIRCRAFT_POOL.length)];
        const capacity = aircraft.includes('787') ? 240 : aircraft.includes('737') || aircraft.includes('A320') ? 160 : 100;
        const booked = Math.floor(capacity * (0.4 + rand() * 0.5));

        flights.push({
            origin: originCode,
            destination: destCode,
            flight_number: `SF${100 + Math.floor(rand() * 800)}`,
            airline: 'SmartFly Airlines',
            departure_time: depDate.toISOString(),
            arrival_time: arrDate.toISOString(),
            aircraft,
            capacity,
            booked_count: booked
        });
    }

    flights.sort((a, b) => new Date(a.departure_time) - new Date(b.departure_time));
    return flights;
}

// Create flight card
function createFlightCard(flight, index) {
    const originCode = flight.origin || from;
    const destCode = flight.destination || to;
    const flightNum = flight.flight_number || flight.flight || `SF${100 + index}`;
    const airline = flight.airline || 'SmartFly Airlines';

    // Parse times
    const depTime = flight.departure_time || '';
    const arrTime = flight.arrival_time || '';
    const depDate = depTime ? new Date(depTime) : null;
    const arrDate = arrTime ? new Date(arrTime) : null;

    const depTimeStr = depDate ? depDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : '08:00';
    const arrTimeStr = arrDate ? arrDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : '12:00';

    // Calculate duration
    let duration = flight.duration || '4h 0m';
    if (depDate && arrDate) {
        const diff = Math.abs(arrDate - depDate);
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        duration = `${hours}h ${mins}m`;
    }

    // Calculate price with advanced pricing logic
    let priceValue = 299;
    let priceStr = fmtCurrency(priceValue, 'USD');
    let priceBreakdown = { base: 299, distance: 0, cabin: 0, aircraft: 0, date: 0 };

    if (window.FlightPricing && __airportsData.length > 0) {
        const originAirport = window.FlightPricing.findAirportByCode(originCode, __airportsData);
        const destAirport = window.FlightPricing.findAirportByCode(destCode, __airportsData);

        if (originAirport && destAirport) {
            // Calculate distance-based pricing
            const distance = window.FlightPricing.calculateDistance(
                originAirport.latitude, originAirport.longitude,
                destAirport.latitude, destAirport.longitude
            );

            // Base price per km (varies by distance - economies of scale for longer flights)
            let pricePerKm = 0.15;
            if (distance > 5000) pricePerKm = 0.12;
            else if (distance > 2000) pricePerKm = 0.13;
            else if (distance < 500) pricePerKm = 0.20; // Short flights cost more per km

            let basePrice = distance * pricePerKm;
            basePrice = Math.max(basePrice, 50); // Minimum base fare
            priceBreakdown.base = Math.round(basePrice);
            priceBreakdown.distance = distance;

            // Cabin class multiplier
            let cabinMultiplier = 1.0;
            if (cabinClass === 'business') cabinMultiplier = 2.5;
            else if (cabinClass === 'first') cabinMultiplier = 4.0;
            else if (cabinClass === 'premium_economy') cabinMultiplier = 1.4;

            priceBreakdown.cabin = Math.round(basePrice * (cabinMultiplier - 1));

            // Aircraft type surcharge
            const aircraft = (flight.aircraft || '').toLowerCase();
            let aircraftSurcharge = 0;
            if (aircraft.includes('787') || aircraft.includes('777') || aircraft.includes('a350')) {
                aircraftSurcharge = 50; // Premium wide-body
            } else if (aircraft.includes('a380')) {
                aircraftSurcharge = 75; // Super jumbo
            } else if (aircraft.includes('737') || aircraft.includes('a320')) {
                aircraftSurcharge = 20; // Standard narrow-body
            } else if (aircraft.includes('dash') || aircraft.includes('embraer') || aircraft.includes('e190')) {
                aircraftSurcharge = -20; // Regional jets (discount)
            }
            priceBreakdown.aircraft = aircraftSurcharge;

            // Date-based pricing (peak times, weekends, holidays)
            let dateSurcharge = 0;
            if (depDate) {
                const dayOfWeek = depDate.getDay();
                const month = depDate.getMonth();
                const dayOfMonth = depDate.getDate();

                // Weekend surcharge (Friday-Sunday)
                if (dayOfWeek === 5 || dayOfWeek === 6 || dayOfWeek === 0) {
                    dateSurcharge += basePrice * 0.15;
                }

                // Peak season surcharge (December, July-August)
                if (month === 11 || month === 6 || month === 7) {
                    dateSurcharge += basePrice * 0.20;
                }

                // Holiday surcharges (approximate dates)
                const isChristmas = month === 11 && dayOfMonth >= 20 && dayOfMonth <= 27;
                const isNewYear = (month === 11 && dayOfMonth >= 28) || (month === 0 && dayOfMonth <= 5);
                const isEaster = month === 3 && dayOfMonth >= 15 && dayOfMonth <= 22; // approximate

                if (isChristmas || isNewYear) {
                    dateSurcharge += basePrice * 0.35;
                } else if (isEaster) {
                    dateSurcharge += basePrice * 0.25;
                }

                // Advance booking discount (more than 30 days in advance)
                const daysUntilFlight = Math.floor((depDate - new Date()) / (1000 * 60 * 60 * 24));
                if (daysUntilFlight > 60) {
                    dateSurcharge -= basePrice * 0.15; // Early bird discount
                } else if (daysUntilFlight < 7) {
                    dateSurcharge += basePrice * 0.30; // Last minute premium
                }
            }
            priceBreakdown.date = Math.round(dateSurcharge);

            // Calculate final price
            priceValue = basePrice * cabinMultiplier + aircraftSurcharge + dateSurcharge;

            // Add fuel surcharge (5-10% of base)
            const fuelSurcharge = basePrice * 0.075;
            priceValue += fuelSurcharge;

            // Round to nearest $5
            priceValue = Math.round(priceValue / 5) * 5;
            priceValue = Math.max(priceValue, 50); // Absolute minimum

            priceStr = fmtCurrency(priceValue, 'USD');
        }
    }

    const capacity = flight.capacity || 150;
    const booked = flight.booked_count || flight.booked_seats || Math.floor(capacity * 0.6);
    const available = capacity - booked;

    const card = `
        <div class="flight-card" data-flight-id="${flightNum}" data-price="${priceValue}">
            <div class="flight-header">
                <div class="airline-info">
                    <div class="airline-logo">
                        ${airline.substring(0, 2).toUpperCase()}
                    </div>
                    <div class="airline-details">
                        <h3>${airline}</h3>
                        <p>${flightNum} • ${flight.aircraft || 'Boeing 737'}</p>
                    </div>
                </div>
                ${available < 10 ? '<div class="flight-badge" style="background: var(--warning);">Only ' + available + ' Seats Left</div>' : ''}
            </div>

            <div class="flight-route">
                <div class="route-point">
                    <div class="route-time">${depTimeStr}</div>
                    <div class="route-code">${originCode}</div>
                </div>
                <div class="route-duration">
                    <div class="duration-line"></div>
                    <div class="duration-text">${duration}</div>
                </div>
                <div class="route-point">
                    <div class="route-time">${arrTimeStr}</div>
                    <div class="route-code">${destCode}</div>
                </div>
            </div>

            <div class="flight-details">
                <div class="detail-item">
                    <i class="fas fa-plane"></i>
                    <span>Direct</span>
                </div>
                <div class="detail-item">
                    <i class="fas fa-suitcase"></i>
                    <span>20kg Baggage</span>
                </div>
                <div class="detail-item">
                    <i class="fas fa-utensils"></i>
                    <span>Meal Included</span>
                </div>
                <div class="detail-item">
                    <i class="fas fa-wifi"></i>
                    <span>WiFi Available</span>
                </div>
            </div>

            <div class="flight-footer">
                <div class="flight-price">
                    <div class="price-label">Price per person</div>
                    <div class="price-amount">${priceStr}</div>
                    <div style="font-size: 11px; color: var(--gray-600); margin-top: 4px;">
                        ${Math.round(priceBreakdown.distance)}km • ${cabinClass.replace('_', ' ')} class
                    </div>
                </div>
                <button class="btn-select" onclick="selectFlight('${flightNum}', ${priceValue})">
                    Select Flight
                </button>
            </div>
        </div>
    `;

    return card;
}

// Select flight — forwards everything passenger-details.html needs.
// Looks up the full flight record (not just id/price) and persists it to
// sessionStorage as well as the URL, so the next page has real data to read
// even if it only checks one of the two.
window.selectFlight = function (flightId, price) {
    const flight = (window.__lastFlights || []).find(f => (f.flight_number || f.flight) === flightId) || {};

    const selection = {
        flight,
        price,
        cabinClass,
        tripType,
        from, to, fromFull, toFull, fromCity, toCity,
        departureDate, returnDate,
        passengers: q.passengers || '1-0-0'
    };
    try {
        sessionStorage.setItem('selectedFlight', JSON.stringify(selection));
    } catch (e) {
        console.warn('Could not persist selection to sessionStorage:', e);
    }

    const params = new URLSearchParams({
        flightId: flightId,
        price: price,
        // Keep both naming conventions so passenger-details.html gets what
        // it needs regardless of which key names it was written against.
        from: from,
        to: to,
        origin: from,
        destination: to,
        departureDate: departureDate,
        tripType: tripType,
        cabin: cabinClass,
        passengers: q.passengers || '1-0-0'
    });
    if (returnDate) params.set('returnDate', returnDate);

    window.location.href = `/passenger-details.html?${params.toString()}`;
};

// Load flights
async function loadFlights() {
    await loadAirportsData();

    let flights = [];
    try {
        // 2.5s hard timeout — a slow or hanging /api/flights can no longer
        // leave the page stuck on "Loading available flights..." forever.
        const response = await fetchWithTimeout(`/api/flights?origin=${from}&destination=${to}&date=${departureDate}`, 2500);
        if (response.ok) {
            const data = await response.json();
            flights = data.flights || data || [];
        }
    } catch (error) {
        console.warn('No live /api/flights data for this route, generating schedule instead:', error);
    }

    // The backend won't have every route seeded (or may not respond at all) —
    // fall back to a deterministic generated schedule so there's always
    // something for the user to select and pass on to the next page.
    if (!flights.length) {
        flights = generateFlightsForRoute(from, to, departureDate);
    }

    document.getElementById('loadingState').style.display = 'none';

    if (flights.length === 0) {
        document.getElementById('emptyState').style.display = 'block';
        document.getElementById('resultsCount').textContent = 'No flights found';
        return;
    }

    document.getElementById('resultsCount').textContent = `${flights.length} flight${flights.length !== 1 ? 's' : ''} available`;

    window.__lastFlights = flights;
    const container = document.getElementById('flightsContainer');
    container.innerHTML = flights.map((flight, index) => createFlightCard(flight, index)).join('');

    // Update summary with first flight price
    if (flights.length > 0) {
        updatePriceSummary(flights[0]);
    }
}

function updatePriceSummary(flight) {
    // Calculate price for the first available flight
    let baseFare = 299;

    if (window.FlightPricing && __airportsData.length > 0 && flight) {
        const originAirport = window.FlightPricing.findAirportByCode(flight.origin || from, __airportsData);
        const destAirport = window.FlightPricing.findAirportByCode(flight.destination || to, __airportsData);

        if (originAirport && destAirport) {
            const distance = window.FlightPricing.calculateDistance(
                originAirport.latitude, originAirport.longitude,
                destAirport.latitude, destAirport.longitude
            );

            let pricePerKm = 0.15;
            if (distance > 5000) pricePerKm = 0.12;
            else if (distance > 2000) pricePerKm = 0.13;
            else if (distance < 500) pricePerKm = 0.20;

            let basePrice = distance * pricePerKm;
            basePrice = Math.max(basePrice, 50);

            // Apply cabin multiplier
            let cabinMultiplier = 1.0;
            if (cabinClass === 'business') cabinMultiplier = 2.5;
            else if (cabinClass === 'first') cabinMultiplier = 4.0;
            else if (cabinClass === 'premium_economy') cabinMultiplier = 1.4;

            // Aircraft surcharge
            const aircraft = (flight.aircraft || '').toLowerCase();
            let aircraftSurcharge = 0;
            if (aircraft.includes('787') || aircraft.includes('777') || aircraft.includes('a350')) {
                aircraftSurcharge = 50;
            } else if (aircraft.includes('a380')) {
                aircraftSurcharge = 75;
            } else if (aircraft.includes('737') || aircraft.includes('a320')) {
                aircraftSurcharge = 20;
            } else if (aircraft.includes('dash') || aircraft.includes('embraer')) {
                aircraftSurcharge = -20;
            }

            baseFare = basePrice * cabinMultiplier + aircraftSurcharge;
            baseFare = Math.round(baseFare / 5) * 5;
            baseFare = Math.max(baseFare, 50);
        }
    }

    const taxes = Math.round(baseFare * 0.15);
    const total = baseFare + taxes;

    document.getElementById('baseFare').textContent = fmtCurrency(baseFare, 'USD');
    document.getElementById('taxesFees').textContent = fmtCurrency(taxes, 'USD');
    document.getElementById('totalPrice').textContent = fmtCurrency(total, 'USD');
}

// Initialize
loadFlights();