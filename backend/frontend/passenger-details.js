// Passenger Details JavaScript - SmartFly Airways

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

// Get cart data from sessionStorage
function getCartData() {
    const stored = sessionStorage.getItem('cartData');
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

// Initialize page
function initializePage() {
    const params = getUrlParams();
    const cartData = getCartData();
    
    if (!params.from || !params.to || !params.price) {
        document.querySelector('.kq-traveler-form').innerHTML = 
            '<div style="color: #c8102e; padding: 40px; text-align: center;">Flight details not found. <a href="/availability.html" style="color: #c8102e;">Go back to search</a></div>';
        return;
    }
    
    // Update mini summary
    document.getElementById('miniFrom').textContent = params.from;
    document.getElementById('miniTo').textContent = params.to;
    
    const departDate = formatDate(params.departDate);
    if (params.tripType === 'return' && params.returnDate) {
        const returnDate = formatDate(params.returnDate);
        document.getElementById('miniDates').textContent = `${departDate} - ${returnDate}`;
    } else {
        document.getElementById('miniDates').textContent = departDate;
    }
    
    document.getElementById('miniPassengers').textContent = 
        params.passengers === 1 ? '1 Adult' : `${params.passengers} Adults`;
    
    // Update sidebar summary
    document.getElementById('summaryFrom').textContent = params.from;
    document.getElementById('summaryTo').textContent = params.to;
    
    if (params.tripType === 'return' && params.returnDate) {
        const returnDate = formatDate(params.returnDate);
        document.getElementById('summaryDates').textContent = `${departDate} - ${returnDate}`;
        document.getElementById('summaryTripType').textContent = 'Return';
    } else {
        document.getElementById('summaryDates').textContent = departDate;
        document.getElementById('summaryTripType').textContent = 'One-way';
    }
    
    document.getElementById('summaryPassengers').textContent = 
        params.passengers === 1 ? '1 Adult' : `${params.passengers} Adults`;
    document.getElementById('summaryClass').textContent = params.fare ? params.fare.charAt(0).toUpperCase() + params.fare.slice(1) : 'Economy';
    
    // Update total price
    if (cartData && cartData.priceBreakdown) {
        document.getElementById('summaryTotal').textContent = formatPrice(cartData.priceBreakdown.total);
    } else {
        const basePrice = parseFloat(params.price);
        const flightCount = params.tripType === 'return' ? 2 : 1;
        const total = basePrice * flightCount * params.passengers;
        document.getElementById('summaryTotal').textContent = formatPrice(total);
    }
    
    console.log('👤 Traveler Details Page Initialized:', params);
}

// Submit traveler details
function submitTravelerDetails(event) {
    event.preventDefault();
    
    const title = document.getElementById('title').value.trim();
    const firstName = document.getElementById('firstName').value.trim();
    const lastName = document.getElementById('lastName').value.trim();
    const dateOfBirth = document.getElementById('dateOfBirth').value;
    const gender = document.getElementById('gender').value;
    const nationality = document.getElementById('nationality').value;
    const email = document.getElementById('email').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const passportNumber = document.getElementById('passportNumber').value.trim();
    const passportExpiry = document.getElementById('passportExpiry').value;
    const issuingCountry = document.getElementById('issuingCountry').value;
    const ffProgram = document.getElementById('ffProgram').value;
    const ffNumber = document.getElementById('ffNumber').value.trim();
    
    // Validation
    if (!title || !firstName || !lastName || !dateOfBirth || !gender || !nationality || !email || !phone || !passportNumber || !passportExpiry || !issuingCountry) {
        alert('Please fill in all required fields');
        return;
    }
    
    if (!email.includes('@')) {
        alert('Please enter a valid email address');
        return;
    }
    
    // Store traveler details
    const travelerDetails = {
        title,
        firstName,
        lastName,
        dateOfBirth,
        gender,
        nationality,
        email,
        phone,
        passportNumber,
        passportExpiry,
        issuingCountry,
        ffProgram,
        ffNumber
    };
    
    console.log('👤 Traveler Details Submitted:', travelerDetails);
    sessionStorage.setItem('travelerDetails', JSON.stringify(travelerDetails));
    
    // Show loading state
    document.getElementById('travelerForm').style.display = 'none';
    document.getElementById('loadingState').style.display = 'block';
    
    // Simulate processing and redirect to payment
    setTimeout(() => {
        const params = getUrlParams();
        const fullName = `${title} ${firstName} ${lastName}`;
        const paymentUrl = `/payment.html?from=${params.from}&to=${params.to}&departDate=${params.departDate}&tripType=${params.tripType}&returnDate=${params.returnDate || ''}&fare=${params.fare}&price=${params.price}&passengers=${params.passengers}&name=${encodeURIComponent(fullName)}&email=${encodeURIComponent(email)}`;
        window.location.href = paymentUrl;
    }, 1500);
}

// Go back to shopping cart
function goBack() {
    window.location.href = '/shopping-cart.html';
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializePage();
    
    // Add form submit handler
    const form = document.getElementById('travelerForm');
    if (form) {
        form.addEventListener('submit', submitTravelerDetails);
    }
});