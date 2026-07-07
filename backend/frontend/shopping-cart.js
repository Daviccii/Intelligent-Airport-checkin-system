// Shopping Cart JavaScript - SmartFly Airways

// Parse URL parameters
function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        from: params.get('from'),
        fromCity: params.get('fromCity'),
        to: params.get('to'),
        toCity: params.get('toCity'),
        departDate: params.get('departDate'),
        returnDate: params.get('returnDate'),
        tripType: params.get('tripType'),
        passengers: parseInt(params.get('passengers') || '1'),
        fare: params.get('fare'),
        price: params.get('price')
    };
}

// Get selected flight from sessionStorage
function getSelectedFlight() {
    const stored = sessionStorage.getItem('selectedFlight');
    return stored ? JSON.parse(stored) : null;
}

// Format date for display
function formatDate(dateStr) {
    const date = new Date(dateStr);
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${days[date.getDay()]}, ${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

// Format price for display
function formatPrice(price) {
    const numericPrice = parseFloat(price);
    return isNaN(numericPrice) ? 'Ksh 0' : `Ksh ${numericPrice.toLocaleString()}`;
}

// Calculate price breakdown
function calculatePriceBreakdown(basePrice, passengerCount, hasDiscount = false, discountPercent = 0) {
    const totalBaseFare = basePrice * passengerCount;
    const taxesAndFees = Math.round(totalBaseFare * 0.15); // 15% taxes
    let discount = 0;
    
    if (hasDiscount && discountPercent > 0) {
        discount = Math.round(totalBaseFare * (discountPercent / 100));
    }
    
    const total = totalBaseFare + taxesAndFees - discount;
    
    return {
        baseFare: totalBaseFare,
        taxesAndFees,
        discount,
        total
    };
}

// Generate realistic flight details
function generateFlightDetails(from, to, date, isReturn = false) {
    const category = (from === 'NBO' && (to === 'MBA' || to === 'KIS' || to === 'ELD')) ||
                     (to === 'NBO' && (from === 'MBA' || from === 'KIS' || from === 'ELD')) 
                     ? 'domestic' : 'international';
    
    // Generate realistic times
    const departHour = 6 + Math.floor(Math.random() * 14); // 6am - 8pm
    const departMin = Math.random() > 0.5 ? '00' : '30';
    const durationHours = category === 'domestic' ? 1 : (category === 'regional' ? 3 : 8);
    const durationMins = Math.random() > 0.5 ? 0 : 30;
    
    const departTime = `${departHour.toString().padStart(2, '0')}:${departMin}`;
    const arriveHour = (departHour + durationHours + (departMin === '30' && durationMins === 30 ? 1 : 0)) % 24;
    const arriveMins = (departMin === '30' && durationMins === 30) ? '00' : (durationMins === 30 ? '30' : departMin);
    const arriveTime = `${arriveHour.toString().padStart(2, '0')}:${arriveMins}`;
    
    // Select airline based on route
    let airline, airlineCode, flightNumber;
    if (category === 'domestic') {
        const airlines = [
            { name: 'Kenya Airways', code: 'KQ', logo: '✈️' },
            { name: 'JamboJet', code: 'JM', logo: '✈️' },
            { name: 'SmartFly', code: 'SF', logo: '✈️' }
        ];
        const selected = airlines[Math.floor(Math.random() * airlines.length)];
        airline = selected.name;
        airlineCode = selected.code;
        flightNumber = `${selected.code}${500 + Math.floor(Math.random() * 100)}`;
    } else {
        const airlines = [
            { name: 'Kenya Airways', code: 'KQ', logo: '✈️' },
            { name: 'Qatar Airways', code: 'QR', logo: '🛬' },
            { name: 'Emirates', code: 'EK', logo: '✈️' },
            { name: 'British Airways', code: 'BA', logo: '🛫' }
        ];
        const selected = airlines[Math.floor(Math.random() * airlines.length)];
        airline = selected.name;
        airlineCode = selected.code;
        flightNumber = `${selected.code}${100 + Math.floor(Math.random() * 900)}`;
    }
    
    return {
        departTime,
        arriveTime,
        duration: `${durationHours}h ${durationMins}m`,
        airline,
        airlineCode,
        airlineLogo: airline === 'Kenya Airways' ? '✈️' : '🛫',
        flightNumber,
        stops: category === 'domestic' ? 0 : (Math.random() > 0.5 ? 0 : 1),
        category
    };
}

// Initialize page
function initializePage() {
    const params = getUrlParams();
    const selectedFlight = getSelectedFlight();
    
    if (!params.from || !params.to || !params.price) {
        document.querySelector('.kq-flight-details').innerHTML = 
            '<div style="color: #c8102e; padding: 40px; text-align: center;">Flight details not found. <a href="/availability.html" style="color: #c8102e;">Go back to search</a></div>';
        return;
    }
    
    // Update trip summary
    document.getElementById('fromCode').textContent = params.from;
    document.getElementById('toCode').textContent = params.to;
    
    const departDate = formatDate(params.departDate);
    if (params.tripType === 'return' && params.returnDate) {
        const returnDate = formatDate(params.returnDate);
        document.getElementById('tripDates').textContent = `${departDate} - ${returnDate}`;
        document.getElementById('tripType').textContent = 'Return';
        document.getElementById('returnFlight').style.display = 'block';
    } else {
        document.getElementById('tripDates').textContent = departDate;
        document.getElementById('tripType').textContent = 'One-way';
    }
    
    document.getElementById('passengerCount').textContent = 
        params.passengers === 1 ? '1 Adult' : `${params.passengers} Adults`;
    
    // Generate and display outbound flight
    const outboundDetails = generateFlightDetails(params.from, params.to, params.departDate);
    document.getElementById('outboundDate').textContent = departDate;
    document.getElementById('outboundDepart').textContent = outboundDetails.departTime;
    document.getElementById('outboundFrom').textContent = params.from;
    document.getElementById('outboundDuration').textContent = outboundDetails.duration;
    document.getElementById('outboundStops').textContent = outboundDetails.stops === 0 ? 'Nonstop' : `${outboundDetails.stops} stop`;
    document.getElementById('outboundArrive').textContent = outboundDetails.arriveTime;
    document.getElementById('outboundTo').textContent = params.to;
    document.getElementById('outboundAirlineLogo').textContent = outboundDetails.airlineLogo;
    document.getElementById('outboundAirline').textContent = outboundDetails.airline;
    document.getElementById('outboundFlightNumber').textContent = outboundDetails.flightNumber;
    document.getElementById('outboundClass').textContent = params.fare ? params.fare.charAt(0).toUpperCase() + params.fare.slice(1) : 'Economy';
    
    // Generate and display return flight if applicable
    if (params.tripType === 'return' && params.returnDate) {
        const returnDetails = generateFlightDetails(params.to, params.from, params.returnDate, true);
        document.getElementById('returnDate').textContent = formatDate(params.returnDate);
        document.getElementById('returnDepart').textContent = returnDetails.departTime;
        document.getElementById('returnFrom').textContent = params.to;
        document.getElementById('returnDuration').textContent = returnDetails.duration;
        document.getElementById('returnStops').textContent = returnDetails.stops === 0 ? 'Nonstop' : `${returnDetails.stops} stop`;
        document.getElementById('returnArrive').textContent = returnDetails.arriveTime;
        document.getElementById('returnTo').textContent = params.from;
        document.getElementById('returnAirlineLogo').textContent = returnDetails.airlineLogo;
        document.getElementById('returnAirline').textContent = returnDetails.airline;
        document.getElementById('returnFlightNumber').textContent = returnDetails.flightNumber;
        document.getElementById('returnClass').textContent = params.fare ? params.fare.charAt(0).toUpperCase() + params.fare.slice(1) : 'Economy';
    }
    
    // Calculate and display prices
    const basePrice = parseFloat(params.price);
    const flightCount = params.tripType === 'return' ? 2 : 1;
    const totalBasePrice = basePrice * flightCount * params.passengers;
    
    // Check for offer discount
    let hasDiscount = false;
    let discountPercent = 0;
    if (selectedFlight && selectedFlight.offer && selectedFlight.offer.discount > 0) {
        hasDiscount = true;
        discountPercent = selectedFlight.offer.discount;
        document.getElementById('offerApplied').style.display = 'flex';
        document.getElementById('offerText').textContent = `${selectedFlight.offer.discount}% ${selectedFlight.offer.title}`;
    }
    
    const priceBreakdown = calculatePriceBreakdown(totalBasePrice, 1, hasDiscount, discountPercent);
    
    document.getElementById('baseFare').textContent = formatPrice(priceBreakdown.baseFare);
    document.getElementById('taxesFees').textContent = formatPrice(priceBreakdown.taxesAndFees);
    
    if (hasDiscount) {
        document.getElementById('discountRow').style.display = 'flex';
        document.getElementById('discountAmount').textContent = `-${formatPrice(priceBreakdown.discount)}`;
    }
    
    document.getElementById('totalPrice').textContent = formatPrice(priceBreakdown.total);
    
    // Store cart data for next steps
    const cartData = {
        params,
        outboundDetails,
        returnDetails: params.tripType === 'return' ? generateFlightDetails(params.to, params.from, params.returnDate, true) : null,
        priceBreakdown,
        hasDiscount,
        discountPercent
    };
    sessionStorage.setItem('cartData', JSON.stringify(cartData));
    
    console.log('🛒 Shopping Cart Initialized:', cartData);
}

// Proceed to traveler details
function proceedToTraveler() {
    const params = getUrlParams();
    const cartData = JSON.parse(sessionStorage.getItem('cartData'));
    
    if (!cartData) {
        console.error('Cart data not found');
        return;
    }
    
    // Redirect to traveler details page
    const travelerUrl = `/passenger-details.html?from=${params.from}&to=${params.to}&departDate=${params.departDate}&tripType=${params.tripType}&returnDate=${params.returnDate || ''}&fare=${params.fare}&price=${params.price}&passengers=${params.passengers}`;
    window.location.href = travelerUrl;
}

// Go back to availability
function goBack() {
    window.history.back();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initializePage);