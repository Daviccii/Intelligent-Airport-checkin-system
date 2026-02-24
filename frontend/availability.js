// Define domestic and international airports
const DOMESTIC_AIRPORTS = ['NBO', 'MBA', 'KIS', 'EDL', 'WIL']; // Kenya only
const INTERNATIONAL_AIRPORTS = ['LHR', 'CDG', 'DXB', 'JFK', 'SIN', 'JNB', 'CPT', 'EBB', 'CMN', 'BLR'];

// Route pricing aligned with homepage calendar (KES)
const ROUTE_PRICING = {
    // Domestic routes (Kenya)
    'NBO-MBA': { distance: 500, basePrice: 7500 },
    'MBA-NBO': { distance: 500, basePrice: 7500 },
    'NBO-KIS': { distance: 350, basePrice: 6200 },
    'KIS-NBO': { distance: 350, basePrice: 6200 },
    'NBO-ELD': { distance: 300, basePrice: 5800 },
    'ELD-NBO': { distance: 300, basePrice: 5800 },
    'MBA-KIS': { distance: 700, basePrice: 9800 },
    'KIS-MBA': { distance: 700, basePrice: 9800 },

    // Regional routes (East Africa)
    'NBO-EBB': { distance: 700, basePrice: 18500 },
    'EBB-NBO': { distance: 700, basePrice: 18500 },
    'NBO-DAR': { distance: 400, basePrice: 15500 },
    'DAR-NBO': { distance: 400, basePrice: 15500 },

    // Long-haul international routes
    'NBO-LHR': { distance: 7200, basePrice: 78000 },
    'LHR-NBO': { distance: 7200, basePrice: 78000 },
    'NBO-CDG': { distance: 7500, basePrice: 82000 },
    'CDG-NBO': { distance: 7500, basePrice: 82000 },
    'NBO-DXB': { distance: 4200, basePrice: 52000 },
    'DXB-NBO': { distance: 4200, basePrice: 52000 },
    'NBO-JFK': { distance: 8900, basePrice: 98000 },
    'JFK-NBO': { distance: 8900, basePrice: 98000 },
    'NBO-SIN': { distance: 9000, basePrice: 102000 },
    'SIN-NBO': { distance: 9000, basePrice: 102000 }
};

function getRoutePricing(from, to) {
    const routeKey = `${from}-${to}`;
    return ROUTE_PRICING[routeKey] || { distance: 5000, basePrice: 45000 };
}

function getDeterministicVariation(date, basePrice) {
    const seed = (date.getFullYear() * 10000) + ((date.getMonth() + 1) * 100) + date.getDate();
    const normalized = Math.abs(Math.sin(seed) * 10000) % 1;
    return (normalized * 0.1 - 0.05) * basePrice; // +/-5%
}

function getCalendarPriceForDate(date, from, to) {
    const routeInfo = getRoutePricing(from, to);
    const basePrice = routeInfo.basePrice;
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    const weekendSurge = isWeekend ? (basePrice * 0.15) : 0;
    const dayVariation = getDeterministicVariation(date, basePrice);
    const finalPrice = Math.max(basePrice * 0.9, basePrice + weekendSurge + dayVariation);
    return Math.round(finalPrice);
}

// Domestic aircraft (suitable for short-haul)
const DOMESTIC_AIRCRAFT = [
    { name: 'Boeing 737-700', type: 'Narrow-body', capacity: 120 },
    { name: 'Embraer E190', type: 'Regional Jet', capacity: 100 },
    { name: 'Airbus A320', type: 'Narrow-body', capacity: 130 },
    { name: 'Boeing 737-800', type: 'Narrow-body', capacity: 125 }
];

// International aircraft (suitable for long-haul)
const INTERNATIONAL_AIRCRAFT = [
    { name: 'Boeing 787-8', type: 'Wide-body', capacity: 242 },
    { name: 'Airbus A350-900', type: 'Wide-body', capacity: 300 },
    { name: 'Boeing 777-300ER', type: 'Wide-body', capacity: 350 },
    { name: 'Airbus A380', type: 'Wide-body', capacity: 555 }
];

// Determine if route is domestic or international
function isRouteDomestic(origin, destination) {
    return DOMESTIC_AIRPORTS.includes(origin) && DOMESTIC_AIRPORTS.includes(destination);
}

// Generate terminal assignments
function assignTerminal(origin, destination, isDomestic) {
    if (origin === 'NBO') {
        return isDomestic ? 'Terminal 1' : 'Terminal 3'; // Nairobi domestic vs international
    }
    return isDomestic ? 'Terminal 1' : 'Terminal 2'; // Default assignments
}

// Parse URL parameters
function getSearchParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        from: params.get('from'),
        fromCity: params.get('fromCity'),
        to: params.get('to'),
        toCity: params.get('toCity'),
        departDate: params.get('departDate'),
        returnDate: params.get('returnDate'),
        tripType: params.get('tripType'),
        passengers: parseInt(params.get('passengers') || '1')
    };
}

// Format date strings
function formatDate(dateStr) {
    const date = new Date(dateStr);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[date.getMonth()]} ${date.getDate()}`;
}

function formatDateLong(dateStr) {
    const date = new Date(dateStr);
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${days[date.getDay()]} ${months[date.getMonth()]} ${date.getDate()}`;
}

// Generate mock flight data
function generateFlights(from, to, date) {
    const airlines = [
        { name: 'Kenya Airways', code: 'KQ', logo: '✈️' },
        { name: 'British Airways', code: 'BA', logo: '🛫' },
        { name: 'Emirates', code: 'EK', logo: '✈️' },
        { name: 'Qatar Airways', code: 'QR', logo: '🛬' },
        { name: 'Ethiopian Airlines', code: 'ET', logo: '✈️' }
    ];

    const isDomestic = isRouteDomestic(from, to);
    const aircraftPool = isDomestic ? DOMESTIC_AIRCRAFT : INTERNATIONAL_AIRCRAFT;
    const numFlights = isDomestic ? 6 + Math.floor(Math.random() * 4) : 8 + Math.floor(Math.random() * 5); // Fewer domestic flights

    const flights = [];

    for (let i = 0; i < numFlights; i++) {
        const airline = airlines[Math.floor(Math.random() * airlines.length)];
        const aircraft = aircraftPool[Math.floor(Math.random() * aircraftPool.length)];
        
        // Domestic: 1-2 hours, International: 8-15 hours
        let durationHours, durationMins;
        if (isDomestic) {
            durationHours = 1 + Math.floor(Math.random() * 2); // 1-2 hours
            durationMins = Math.random() > 0.5 ? 0 : 30;
        } else {
            durationHours = 8 + Math.floor(Math.random() * 7); // 8-14 hours
            durationMins = Math.random() > 0.5 ? 0 : 30;
        }
        
        const departHour = isDomestic ? (6 + Math.floor(Math.random() * 16)) : (6 + Math.floor(Math.random() * 18)); // 6am-10pm domestic, 6am-11pm intl
        const departMin = Math.random() > 0.5 ? '00' : '30';
        
        const departTime = `${departHour.toString().padStart(2, '0')}:${departMin}`;
        const arriveHour = (departHour + durationHours + (departMin === '30' && durationMins === 30 ? 1 : 0)) % 24;
        const arriveMins = (departMin === '30' && durationMins === 30) ? '00' : (durationMins === 30 ? '30' : departMin);
        const arriveTime = `${arriveHour.toString().padStart(2, '0')}:${arriveMins}`;

        // Domestic: mostly nonstop; International: can have stops
        const stops = isDomestic ? (Math.random() > 0.8 ? 0 : 1) : (Math.random() > 0.6 ? 0 : (Math.random() > 0.5 ? 1 : 2));
        const stopText = stops === 0 ? 'Nonstop' : `${stops} stop${stops > 1 ? 's' : ''}`;
        
        const basePrice = getCalendarPriceForDate(new Date(date), from, to);
        const stopSurcharge = isDomestic ? 800 : 3500;
        const economyPrice = basePrice + (stops * stopSurcharge);
        const businessPrice = Math.floor(economyPrice * (isDomestic ? 1.8 : (2.5 + Math.random() * 0.5)));

        const terminal = assignTerminal(from, to, isDomestic);

        flights.push({
            airline: airline.name,
            airlineCode: airline.code,
            airlineLogo: airline.logo,
            aircraft: aircraft.name,
            aircraftType: aircraft.type,
            departTime,
            arriveTime,
            duration: `${durationHours}h ${durationMins}m`,
            durationMinutes: durationHours * 60 + durationMins,
            stops,
            stopText,
            terminal,
            economyPrice,
            businessPrice,
            seatsLeft: Math.floor(Math.random() * 5) + 3,
            isDomestic: isDomestic
        });
    }

    return flights;
}

// Generate date slider data
function generateDateSlider(departDate, tripType, from, to) {
    const dates = [];
    const centerDate = new Date(departDate);
    
    // Show 7 days: 3 before, selected, 3 after
    for (let i = -3; i <= 3; i++) {
        const date = new Date(centerDate);
        date.setDate(date.getDate() + i);
        
        const price = getCalendarPriceForDate(date, from, to);
        
        dates.push({
            date: date.toISOString().split('T')[0],
            dayName: formatDateLong(date.toISOString().split('T')[0]).split(' ')[0],
            dayNum: date.getDate(),
            monthName: formatDateLong(date.toISOString().split('T')[0]).split(' ')[1],
            price,
            selected: i === 0
        });
    }
    
    return dates;
}

// Render summary bar
function renderSummary(params) {
    const { from, fromCity, to, toCity, departDate, returnDate, tripType, passengers } = params;
    
    document.getElementById('fromCode').textContent = from;
    document.getElementById('fromCity').textContent = fromCity;
    document.getElementById('toCode').textContent = to;
    document.getElementById('toCity').textContent = toCity;
    
    const dateText = returnDate && tripType === 'return' 
        ? `${formatDate(departDate)} - ${formatDate(returnDate)}`
        : formatDate(departDate);
    document.getElementById('travelDates').textContent = dateText;
    
    const passengerText = passengers === 1 ? '1 Adult' : `${passengers} Adults`;
    document.getElementById('passengerCount').textContent = passengerText;
}

// Render date slider
function renderDateSlider(dates, onDateSelect) {
    const slider = document.getElementById('dateSlider');
    slider.innerHTML = '';
    
    dates.forEach(dateData => {
        const card = document.createElement('div');
        card.className = `date-card ${dateData.selected ? 'selected' : ''}`;
        card.innerHTML = `
            <div class="date-card-day">${dateData.dayName}</div>
            <div class="date-card-date">${dateData.monthName} ${dateData.dayNum}</div>
            <div class="date-card-price">Ksh ${dateData.price.toLocaleString()}</div>
        `;
        card.addEventListener('click', () => onDateSelect(dateData.date));
        slider.appendChild(card);
    });
}

// Render flight cards
function renderFlights(flights) {
    const container = document.getElementById('flightResults');
    container.innerHTML = '';
    
    if (flights.length === 0) {
        container.innerHTML = '<p style="text-align: center; padding: 48px; color: #757575;">No flights found for this route.</p>';
        return;
    }
    
    flights.forEach(flight => {
        const card = document.createElement('div');
        card.className = `flight-card ${flight.isDomestic ? 'domestic' : 'international'}`;
        const routeType = flight.isDomestic ? 'DOMESTIC' : 'INTERNATIONAL';
        const routeBadgeColor = flight.isDomestic ? '#4CAF50' : '#2196F3';
        
        card.innerHTML = `
            <div class="flight-route-badge" style="background: ${routeBadgeColor}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; display: inline-block; margin-bottom: 8px;">
                ${routeType}
            </div>
            <div class="flight-times">
                <div class="time-row">
                    <div class="time-info">
                        <div class="time">${flight.departTime}</div>
                        <div class="airport">${document.getElementById('fromCode').textContent} - ${flight.terminal}</div>
                    </div>
                </div>
                <div class="stop-info">
                    <span class="stop-badge ${flight.stops === 0 ? 'nonstop' : ''}">${flight.stopText}</span>
                    <span class="aircraft-info">${flight.aircraft}</span>
                </div>
            </div>
            
            <div class="flight-details">
                <div class="duration">${flight.duration}</div>
                <div class="airline-info">
                    <div class="airline-logo">${flight.airlineLogo}</div>
                    <div class="airline-name">${flight.airline}</div>
                </div>
                <button class="view-details-btn">View Details</button>
            </div>
            
            <div class="flight-times">
                <div class="time-row">
                    <div class="time-info">
                        <div class="time">${flight.arriveTime}</div>
                        <div class="airport">${document.getElementById('toCode').textContent}</div>
                    </div>
                </div>
            </div>
            
            <div class="flight-fares" style="grid-column: 1 / -1;">
                <div class="fare-card" onclick="selectFlight('economy', ${flight.economyPrice})">
                    <div class="fare-class">Economy</div>
                    <div class="fare-price">Ksh ${flight.economyPrice.toLocaleString()}</div>
                    <div class="fare-currency">KES</div>
                </div>
                <div class="fare-card business" onclick="selectFlight('business', ${flight.businessPrice})">
                    ${flight.seatsLeft <= 5 ? `<span class="seats-left-badge">${flight.seatsLeft} seats left</span>` : ''}
                    <div class="fare-class">Business</div>
                    <div class="fare-price">Ksh ${flight.businessPrice.toLocaleString()}</div>
                    <div class="fare-currency">KES</div>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
    
    // Update results count
    document.getElementById('resultsCount').textContent = `${flights.length} flights found`;
}

// Sort flights
function sortFlights(flights, sortBy) {
    const sorted = [...flights];
    
    switch(sortBy) {
        case 'cheapest':
            sorted.sort((a, b) => a.economyPrice - b.economyPrice);
            break;
        case 'fastest':
            sorted.sort((a, b) => a.durationMinutes - b.durationMinutes);
            break;
        case 'earliest':
            sorted.sort((a, b) => a.departTime.localeCompare(b.departTime));
            break;
        case 'latest':
            sorted.sort((a, b) => b.departTime.localeCompare(a.departTime));
            break;
        case 'recommended':
        default:
            // Score: lower is better (cheaper + fewer stops + reasonable time)
            sorted.sort((a, b) => {
                const scoreA = (a.economyPrice / 10) + (a.stops * 50) + (a.durationMinutes / 10);
                const scoreB = (b.economyPrice / 10) + (b.stops * 50) + (b.durationMinutes / 10);
                return scoreA - scoreB;
            });
    }
    
    return sorted;
}

// Handle flight selection
window.selectFlight = function(fareClass, price) {
    const params = getSearchParams();
    
    // Store selected flight data in sessionStorage
    const selectedFlight = {
        from: params.from,
        fromCity: params.fromCity,
        to: params.to,
        toCity: params.toCity,
        departDate: params.departDate,
        returnDate: params.returnDate,
        tripType: params.tripType,
        fareClass: fareClass,
        price: price,
        passengers: params.passengers
    };
    
    console.log('🎫 Flight selected:', selectedFlight);
    sessionStorage.setItem('selectedFlight', JSON.stringify(selectedFlight));
    
    // Redirect to passenger details page
    window.location.href = `/passenger-details.html?from=${params.from}&to=${params.to}&date=${params.departDate}&fare=${fareClass}&price=${price}`;
};

// Initialize page
let currentFlights = [];
let currentDateData = [];
let selectedDate = '';

document.addEventListener('DOMContentLoaded', () => {
    const params = getSearchParams();
    
    // Render summary
    renderSummary(params);
    
    // Generate and render date slider
    selectedDate = params.departDate;
    currentDateData = generateDateSlider(params.departDate, params.tripType, params.from, params.to);
    renderDateSlider(currentDateData, (date) => {
        selectedDate = date;
        // Update date cards
        currentDateData.forEach(d => d.selected = d.date === date);
        renderDateSlider(currentDateData, (date) => {
            selectedDate = date;
            currentDateData.forEach(d => d.selected = d.date === date);
            renderDateSlider(currentDateData, arguments.callee);
            // Regenerate flights for new date
            currentFlights = generateFlights(params.from, params.to, date);
            const sortBy = document.getElementById('sortSelect').value;
            renderFlights(sortFlights(currentFlights, sortBy));
        });
        // Regenerate flights for new date
        currentFlights = generateFlights(params.from, params.to, date);
        const sortBy = document.getElementById('sortSelect').value;
        renderFlights(sortFlights(currentFlights, sortBy));
    });
    
    // Generate initial flights
    currentFlights = generateFlights(params.from, params.to, params.departDate);
    renderFlights(sortFlights(currentFlights, 'recommended'));
    
    // Sort dropdown handler
    document.getElementById('sortSelect').addEventListener('change', (e) => {
        renderFlights(sortFlights(currentFlights, e.target.value));
    });
    
    // Date navigation buttons
    document.getElementById('prevDate').addEventListener('click', () => {
        const slider = document.getElementById('dateSlider');
        slider.scrollBy({ left: -300, behavior: 'smooth' });
    });
    
    document.getElementById('nextDate').addEventListener('click', () => {
        const slider = document.getElementById('dateSlider');
        slider.scrollBy({ left: 300, behavior: 'smooth' });
    });
});
