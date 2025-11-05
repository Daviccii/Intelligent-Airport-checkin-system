// Admin Authentication
let adminToken = null;

async function handleAdminLogin(event) {
    event.preventDefault();
    const username = document.getElementById('adminUsername').value;
    const password = document.getElementById('adminPassword').value;

    try {
        const response = await fetch('/api/admin/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        if (response.ok) {
            const data = await response.json();
            adminToken = data.token;
            document.getElementById('adminLogin').style.display = 'none';
            document.getElementById('adminTools').style.display = 'block';
            document.getElementById('adminUsername-display').textContent = username;
            showAdminSection('flights');
            showToast('Login successful', 'success');
        } else {
            showToast('Invalid credentials', 'error');
        }
    } catch (error) {
        showToast('Login failed', 'error');
    }
}

function adminLogout() {
    adminToken = null;
    document.getElementById('adminLogin').style.display = 'block';
    document.getElementById('adminTools').style.display = 'none';
    document.getElementById('adminForm').reset();
    showToast('Logged out successfully', 'info');
}

// Section Management
function showAdminSection(section) {
    const sections = ['flights', 'passengers', 'bookings'];
    sections.forEach(s => {
        document.getElementById(`admin${s.charAt(0).toUpperCase() + s.slice(1)}`).style.display = 
            s === section ? 'block' : 'none';
    });
    if (section === 'flights') refreshFlights();
    else if (section === 'passengers') refreshPassengerList();
    else if (section === 'bookings') refreshBookings();
}

// Flights Management
async function refreshFlights() {
    try {
        const response = await fetch('/api/admin/flights', {
            headers: {
                'Authorization': `Bearer ${adminToken}`
            }
        });
        
        if (response.ok) {
            const flights = await response.json();
            const flightsList = document.getElementById('flightsList');
            flightsList.innerHTML = generateFlightsTable(flights);
            attachFlightEventListeners();
        }
    } catch (error) {
        showToast('Failed to load flights', 'error');
    }
}

function generateFlightsTable(flights) {
    return `
        <table>
            <thead>
                <tr>
                    <th>Flight No</th>
                    <th>From</th>
                    <th>To</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${flights.map(flight => `
                    <tr data-id="${flight.id}">
                        <td>${flight.flightNo}</td>
                        <td>${flight.origin}</td>
                        <td>${flight.destination}</td>
                        <td>${new Date(flight.date).toLocaleString()}</td>
                        <td>${flight.status}</td>
                        <td>
                            <button onclick="editFlight('${flight.id}')" class="btn small">Edit</button>
                            <button onclick="deleteFlight('${flight.id}')" class="btn danger small">Delete</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function editFlight(flightId) {
    try {
        const response = await fetch(`/api/admin/flights/${flightId}`, {
            headers: {
                'Authorization': `Bearer ${adminToken}`
            }
        });
        
        if (response.ok) {
            const flight = await response.json();
            showEditFlightModal(flight);
        }
    } catch (error) {
        showToast('Failed to load flight details', 'error');
    }
}

async function deleteFlight(flightId) {
    if (confirm('Are you sure you want to delete this flight?')) {
        try {
            const response = await fetch(`/api/admin/flights/${flightId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${adminToken}`
                }
            });
            
            if (response.ok) {
                showToast('Flight deleted successfully', 'success');
                refreshFlights();
            }
        } catch (error) {
            showToast('Failed to delete flight', 'error');
        }
    }
}

// Passengers Management
async function refreshPassengerList() {
    try {
        const response = await fetch('/api/admin/passengers', {
            headers: {
                'Authorization': `Bearer ${adminToken}`
            }
        });
        
        if (response.ok) {
            const passengers = await response.json();
            const passengersList = document.getElementById('passengersList');
            passengersList.innerHTML = generatePassengersTable(passengers);
            attachPassengerEventListeners();
        }
    } catch (error) {
        showToast('Failed to load passengers', 'error');
    }
}

function generatePassengersTable(passengers) {
    return `
        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Flight</th>
                    <th>Seat</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${passengers.map(passenger => `
                    <tr data-id="${passenger.id}">
                        <td>${passenger.name}</td>
                        <td>${passenger.flightNo}</td>
                        <td>${passenger.seat || 'Not assigned'}</td>
                        <td>${passenger.status}</td>
                        <td>
                            <button onclick="editPassenger('${passenger.id}')" class="btn small">Edit</button>
                            <button onclick="deletePassenger('${passenger.id}')" class="btn danger small">Delete</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Bookings Management
async function refreshBookings() {
    try {
        const response = await fetch('/api/admin/bookings', {
            headers: {
                'Authorization': `Bearer ${adminToken}`
            }
        });
        
        if (response.ok) {
            const bookings = await response.json();
            const bookingsList = document.getElementById('bookingsList');
            bookingsList.innerHTML = generateBookingsTable(bookings);
            attachBookingEventListeners();
        }
    } catch (error) {
        showToast('Failed to load bookings', 'error');
    }
}

function generateBookingsTable(bookings) {
    return `
        <table>
            <thead>
                <tr>
                    <th>Booking ID</th>
                    <th>Passenger</th>
                    <th>Flight</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${bookings.map(booking => `
                    <tr data-id="${booking.id}">
                        <td>${booking.bookingId}</td>
                        <td>${booking.passengerName}</td>
                        <td>${booking.flightNo}</td>
                        <td>${new Date(booking.date).toLocaleString()}</td>
                        <td>${booking.status}</td>
                        <td>
                            <button onclick="editBooking('${booking.id}')" class="btn small">Edit</button>
                            <button onclick="deleteBooking('${booking.id}')" class="btn danger small">Delete</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('adminForm').addEventListener('submit', handleAdminLogin);
});

// Helper Functions
function showToast(message, type = 'info') {
    // Implementation depends on your toast notification system
    console.log(`${type}: ${message}`);
}