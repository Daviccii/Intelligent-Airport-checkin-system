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
        
        const basePrice = 450 + Math.floor(Math.random() * 550); // $450-$1000
        const economyPrice = basePrice + (stops * 50);
        const businessPrice = Math.floor(economyPrice * (2.5 + Math.random() * 0.5));

        flights.push({
            airline: airline.name,
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
            seatsLeft: Math.floor(Math.random() * 5) + 3
        });
    }

    return flights;
}

// Generate date slider data
function generateDateSlider(departDate, tripType) {
    const dates = [];
    const centerDate = new Date(departDate);
    
    // Show 7 days: 3 before, selected, 3 after
    for (let i = -3; i <= 3; i++) {
        const date = new Date(centerDate);
        date.setDate(date.getDate() + i);
        
        const basePrice = 450 + Math.floor(Math.random() * 550);
        const priceVariation = i === 0 ? 0 : Math.floor(Math.random() * 100) - 50;
        
        dates.push({
            date: date.toISOString().split('T')[0],
            dayName: formatDateLong(date.toISOString().split('T')[0]).split(' ')[0],
            dayNum: date.getDate(),
            monthName: formatDateLong(date.toISOString().split('T')[0]).split(' ')[1],
            price: basePrice + priceVariation,
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
            <div class="date-card-price">Ksh ${dateData.price}</div>
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
                    <div class="fare-price">Ksh ${flight.economyPrice}</div>
                    <div class="fare-currency">KES</div>
                </div>
                <div class="fare-card business" onclick="selectFlight('business', ${flight.businessPrice})">
                    ${flight.seatsLeft <= 5 ? `<span class="seats-left-badge">${flight.seatsLeft} seats left</span>` : ''}
                    <div class="fare-class">Business</div>
                    <div class="fare-price">Ksh ${flight.businessPrice}</div>
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
    currentDateData = generateDateSlider(params.departDate, params.tripType);
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
