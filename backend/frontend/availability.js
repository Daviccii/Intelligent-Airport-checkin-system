// Parse URL parameters
function getSearchParams() {
    const params = new URLSearchParams(window.location.search);
    // Security Check: Ensure essential parameters exist
    if (!params.has('origin') || !params.has('destination') || !params.has('departure')) {
        alert('Invalid search criteria. Redirecting to homepage.');
        window.location.href = 'index.html';
        return null; // Stop execution
    }
    return {
        origin: params.get('origin'),
        destination: params.get('destination'),
        departure: params.get('departure'),
        returnDate: params.get('returnDate'),
        passengers: params.get('passengers') || '1-0-0',
        cabin: params.get('cabin') || 'economy'
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

// Generate mock flight data
function generateFlights(from, to, date) {
    const airlines = [
        { name: 'Kenya Airways', code: 'KQ', logo: '✈️' },
        { name: 'British Airways', code: 'BA', logo: '🛫' },
        { name: 'Emirates', code: 'EK', logo: '✈️' },
        { name: 'Qatar Airways', code: 'QR', logo: '🛬' },
        { name: 'Ethiopian Airlines', code: 'ET', logo: '✈️' }
    ];

    const flights = [];
    const numFlights = 8 + Math.floor(Math.random() * 5); // 8-12 flights

    for (let i = 0; i < numFlights; i++) {
        const airline = airlines[Math.floor(Math.random() * airlines.length)];
        const departHour = 6 + Math.floor(Math.random() * 18); // 6am - 11pm
        const departMin = Math.random() > 0.5 ? '00' : '30';
        const durationHours = 8 + Math.floor(Math.random() * 6); // 8-13 hours
        const durationMins = Math.random() > 0.5 ? 0 : 30;
        
        const departTime = `${departHour.toString().padStart(2, '0')}:${departMin}`;
        const arriveHour = (departHour + durationHours + (departMin === '30' && durationMins === 30 ? 1 : 0)) % 24;
        const arriveMins = (departMin === '30' && durationMins === 30) ? '00' : (durationMins === 30 ? '30' : departMin);
        const arriveTime = `${arriveHour.toString().padStart(2, '0')}:${arriveMins}`;

        const stops = Math.random() > 0.6 ? 0 : (Math.random() > 0.5 ? 1 : 2);
        const stopText = stops === 0 ? 'Nonstop' : `${stops} stop${stops > 1 ? 's' : ''}`;
        
        const basePrice = getCalendarPriceForDate(new Date(date), from, to);
        const seatsLeft = Math.floor(Math.random() * 25) + 3; // 3-27 seats left
        const isSoldOut = Math.random() < 0.05; // 5% chance of being sold out

        const stopSurcharge = 3500;
        const economyPrice = basePrice + (stops * stopSurcharge);
        const businessPrice = Math.floor(economyPrice * (2.5 + Math.random() * 0.5));

        flights.push({
            airlineName: airline.name,
            airlineCode: airline.code,
            airlineLogo: airline.logo,
            departTime,
            arriveTime,
            duration: `${durationHours}h ${durationMins}m`,
            durationMinutes: durationHours * 60 + durationMins,
            stops,
            stopText,
            terminal: `Terminal ${Math.floor(Math.random() * 3) + 1}`,
            economyPrice,
            businessPrice,
            seatsLeft: isSoldOut ? 0 : seatsLeft,
            flightNumber: `${airline.code}${Math.floor(100 + Math.random() * 900)}`
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
    if (!params) return;
    const { origin, destination, departure, returnDate, passengers } = params;
    
    document.getElementById('fromCode').textContent = origin;
    // You might want to add a lookup for city names based on code
    document.getElementById('toCode').textContent = destination;
    
    const dateText = returnDate
        ? `${formatDate(departure)} - ${formatDate(returnDate)}`
        : formatDate(departure);
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
function renderFlights(flights, cabinClass) {
    const container = document.getElementById('flightResults');
    container.innerHTML = '';
    
    const isBusiness = cabinClass.toLowerCase().includes('business');
    if (flights.length === 0) {
        container.innerHTML = '<p style="text-align: center; padding: 48px; color: #757575;">No flights found for this route.</p>';
        return;
    }
    
    flights.forEach(flight => {
        const card = document.createElement('div');
        const farePrice = isBusiness ? flight.businessPrice : flight.economyPrice;
        const fareClassDisplay = isBusiness ? 'Business' : 'Economy';
        const isSoldOut = flight.seatsLeft === 0;

        card.className = 'flight-card';
        card.innerHTML = `
            <div class="flight-times">
                <div class="time-row">
                    <div class="time-info">
                        <div class="time">${flight.departTime}</div>
                        <div class="airport">${document.getElementById('fromCode').textContent} - ${flight.terminal}</div>
                    </div>
                </div>
                <div class="stop-info">
                    <span class="stop-badge ${flight.stops === 0 ? 'nonstop' : ''}">${flight.stopText}</span>
                    <span class="terminal-info">${flight.terminal}</span>
                </div>
            </div>
            
            <div class="flight-details">
                <div class="duration">${flight.duration}</div>
                <div class="airline-info">
                    <div class="airline-logo">${flight.airlineLogo}</div>
                    <div class="airline-name">${flight.airlineName}</div>
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
            
            <div class="flight-fares" style="grid-column: 1 / -1;">` +
                (isSoldOut ?
                    `<div class="fare-card sold-out"><div class="fare-class">Sold Out</div></div>` :
                    `<div class="fare-card ${isBusiness ? 'business' : ''}" onclick='selectFlight(${JSON.stringify(flight)}, "${fareClassDisplay}", ${farePrice})'>
                        ${flight.seatsLeft <= 10 ? `<span class="seats-left-badge">${flight.seatsLeft} seats left</span>` : ''}
                        <div class="fare-class">${fareClassDisplay}</div>
                        <div class="fare-price">Ksh ${farePrice.toLocaleString()}</div>
                        <div class="fare-currency">KES</div>
                    </div>`) +
            `</div>`;
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
window.selectFlight = function(flight, fareClass, price) {
    const params = getSearchParams();
    
    // Create the booking session object
    const bookingSession = {
        searchParams: params,
        selectedFlight: {
            ...flight, // The full flight object
            fareClass: fareClass,
            price: price
        },
        passengers: [],
        selectedSeats: [],
        payment: { status: 'pending' },
        booking: { status: 'pending' }
    };
    
    console.log('🎫 Flight selected, creating booking session:', bookingSession);
    sessionStorage.setItem('smartflyBookingSession', JSON.stringify(bookingSession));
    
    // Redirect to passenger details page
    window.location.href = 'passenger-details.html';
};

// Initialize page
let currentFlights = [];
let currentDateData = [];
let selectedDate = '';

document.addEventListener('DOMContentLoaded', () => {
    const params = getSearchParams();
    if (!params) return; // Stop if security check failed
    
    // Render summary
    renderSummary(params);
    
    // Generate and render date slider
    selectedDate = params.departure;
    currentDateData = generateDateSlider(params.departure, params.tripType, params.origin, params.destination);
    renderDateSlider(currentDateData, (date) => {
        selectedDate = date;
        // Update date cards
        currentDateData.forEach(d => d.selected = d.date === date);
        renderDateSlider(currentDateData, (date) => {
            selectedDate = date;
            currentDateData.forEach(d => d.selected = d.date === date);
            renderDateSlider(currentDateData, arguments.callee);
            // Regenerate flights for new date
            currentFlights = generateFlights(params.origin, params.destination, date);
            const sortBy = document.getElementById('sortSelect').value;
            renderFlights(sortFlights(currentFlights, sortBy), params.cabin);
        });
        // Regenerate flights for new date
        currentFlights = generateFlights(params.origin, params.destination, date);
        const sortBy = document.getElementById('sortSelect').value;
        renderFlights(sortFlights(currentFlights, sortBy), params.cabin);
    });
    
    // Generate initial flights
    currentFlights = generateFlights(params.origin, params.destination, params.departure);
    renderFlights(sortFlights(currentFlights, 'recommended'), params.cabin);
    
    // Sort dropdown handler
    document.getElementById('sortSelect').addEventListener('change', (e) => {
        renderFlights(sortFlights(currentFlights, e.target.value), params.cabin);
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
