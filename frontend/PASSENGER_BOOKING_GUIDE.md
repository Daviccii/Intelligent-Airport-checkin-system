# SmartFly Passenger Booking System - Complete Guide

## Overview
The SmartFly Passenger Booking System provides a complete end-to-end booking experience for passengers. Users can browse all travel services (flights, hotels, cars, vacation packages), select and book items, enter passenger details, make payments, and receive instant ticket confirmation.

## System Architecture

### 1. **Passenger Portal** (`passenger-portal.html`)
**Purpose:** Landing page and service discovery hub

**Features:**
- Hero section with primary CTA
- Service grid showcasing:
  - Flight Bookings
  - Hotel Reservations
  - Car Rentals
  - Vacation Packages
  - Check-in Services
  - Flexible Payments
- Feature highlights (Security, Support, Best Prices, etc.)
- Navigation to booking pages

**Access Path:**
```
http://127.0.0.1:5000/passenger-portal.html
```

---

### 2. **Smart Booking System** (`passenger-booking.html`)
**Purpose:** Comprehensive all-in-one booking interface with complete passenger booking workflow

#### Header Section
- SmartFly branding
- Currency toggle (USD ↔ KSH at 130:1 rate)
- User profile display
- Real-time pricing updates

#### Tab Navigation
Users can switch between 4 main service categories:
1. **✈️ Flights** - Flight selection and booking
2. **🏨 Hotels** - Hotel reservations
3. **🚗 Car Rentals** - Vehicle rentals
4. **🏖️ Vacation Packages** - All-inclusive travel packages

#### Offers Grid
- Displays available services in card format
- Shows:
  - Service icon
  - Discount badge
  - Meta information (duration, seats, rating, etc.)
  - Original and current pricing
  - "Book Now" button

---

## Booking Workflow

### **Step 1: Service Selection**
```
Passenger views offers grid → Clicks "Book Flight" button
```

**Modal Opens:** Flight Selection Dialog

**Actions:**
- Select from available flights
- View flight details:
  - Departure/arrival times
  - Duration
  - Number of available seats
  - Price per person
  - Airline information

### **Step 2: Seat Selection**
```
Flight selected → Seat map displays
```

**Seat Map Features:**
- 6x6 grid layout (36 seats)
- Visual indicators:
  - **Available seats:** White with border
  - **Booked seats:** Gray, non-clickable
  - **Selected seat:** Blue highlight
- Legend showing seat status
- Seat numbering system (A1-F6)

### **Step 3: Passenger Details**
```
Seat selected → Passenger form displays
```

**Required Information:**
- Full Name
- Email Address
- Phone Number
- Passport/ID Number
- Date of Birth
- Nationality

**Auto-Updated Summary:**
- Flight details
- Selected seat number
- Passenger name
- Base price
- Taxes & fees (15% of base price)
- Total amount

### **Step 4: Payment**
```
Passenger details entered → Continue to payment → Payment modal opens
```

**Payment Form:**
- Cardholder Name
- Card Number (16 digits)
- Expiry Date (MM/YY)
- CVV (3 digits)

**Summary Display:**
- Flight information
- Seat number
- Passenger name
- Total amount

### **Step 5: Confirmation & Ticket**
```
Payment processed → Ticket modal displays
```

**Ticket Information Generated:**
- **Ticket Number:** Auto-generated (e.g., SFA1B2C3D)
- **Booking Reference:** Auto-generated (e.g., BKXYZ123)
- **Flight Details:**
  - Airline name
  - Flight code
  - Departure and arrival times
  - Route (FROM → TO)
  - Date
  - Seat assignment
- **Passenger Information:**
  - Full name
  - Passport/ID
  - Email
  - Phone
- **Check-in Instructions:**
  - Arrive 2 hours before departure
  - Keep ticket number safe
  - Confirmation email sent
  - E-ticket available for download

**Actions:**
- Download ticket as PDF
- Close and return to booking

---

## Service Offerings

### **Flights**
```json
{
  "airline": "Kenya Airways | Ethiopian Airlines | RwandAir",
  "route": "NBO → JNB | NBO → ADD | NBO → KGL",
  "departure": "08:45 - 14:15",
  "duration": "1h 30m - 2h 30m",
  "priceUSD": "$250 - $320",
  "capacity": "150 - 200 seats",
  "available": "35 - 80 seats"
}
```

### **Hotels**
```json
{
  "name": "Serena Hotel Nairobi | Villa Rosa Kempinski | Hilton Nairobi",
  "location": "Nairobi",
  "priceUSD": "$200 - $320 per night",
  "discount": "26% - 29%",
  "rating": "4.6 - 4.9 stars"
}
```

### **Car Rentals**
```json
{
  "vehicle": "Toyota Corolla | Honda Accord | Toyota RAV4",
  "category": "Economy | Sedan | SUV",
  "priceUSD": "$35 - $75 per day",
  "discount": "18% - 20%",
  "seats": "5 seats"
}
```

### **Vacation Packages**
```json
{
  "name": "Maldives Paradise | Swiss Alps Adventure | Egyptian Wonder",
  "destination": "Maldives | Switzerland | Egypt",
  "duration": "5 - 7 days",
  "priceUSD": "$999 - $1,899",
  "discount": "14% - 17%",
  "highlights": ["All-inclusive meals", "Guided tours", "Accommodations"]
}
```

---

## Currency System

### Exchange Rate
- **Base Currency:** USD
- **Local Currency:** KSH (Kenyan Shilling)
- **Rate:** 1 USD = 130 KSH

### Implementation
```javascript
function getPrice(priceUSD) {
  return currentCurrency === 'USD' ? 
    priceUSD : 
    Math.round(priceUSD * exchangeRate);
}

function getCurrencySymbol() {
  return currentCurrency === 'USD' ? '$' : 'KSH ';
}
```

### Usage
- Click currency toggle (USD/KSH) in header
- All prices update instantly
- Taxes calculated based on selected currency
- Ticket shows pricing in selected currency

---

## User Experience Features

### **Form Validation**
✅ All fields required before proceeding
✅ Payment card validation
✅ Email format validation
✅ Phone number format support
✅ Clear error messages

### **Real-time Updates**
✅ Order summary updates as user fills form
✅ Price calculation includes taxes
✅ Available seats count displayed
✅ Discount percentages calculated

### **Visual Feedback**
✅ Hover animations on cards
✅ Modal animations (slide-up)
✅ Button state changes
✅ Selected seat highlighting
✅ Success messages

### **Responsive Design**
✅ Mobile-optimized layout
✅ Flexible grid system
✅ Touch-friendly buttons
✅ Readable on all screen sizes

---

## Booking Flow Diagram

```
┌─────────────────────┐
│  Passenger Portal   │ (passenger-portal.html)
│   Landing Page      │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Smart Booking Page  │ (passenger-booking.html)
│  - Tab Navigation   │
│  - Offers Grid      │
└──────────┬──────────┘
           │
           ↓
    ┌──────────────┐
    │ Click "Book" │
    └──────┬───────┘
           │
           ↓
┌─────────────────────┐
│ Flight Selection    │
│ Modal Opens         │
│ - Select Flight     │
│ - [Next Step]       │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Seat Selection      │
│ - Choose Seat       │
│ - View Summary      │
│ - [Next Step]       │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Passenger Details   │
│ - Enter Info        │
│ - [Proceed Payment] │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Payment Information │
│ - Card Details      │
│ - [Confirm & Pay]   │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Ticket Confirmation │
│ ✓ Booking Confirmed │
│ - Ticket Number     │
│ - Flight Details    │
│ - Passenger Info    │
│ - [Download/Done]   │
└─────────────────────┘
```

---

## Technical Implementation

### **Technologies Used**
- HTML5
- CSS3 (Flexbox, Grid, Animations)
- Vanilla JavaScript (ES6+)
- No external dependencies required

### **Key JavaScript Functions**

**Currency Management:**
```javascript
setCurrency(currency)      // Toggle USD/KSH
getPrice(priceUSD)        // Convert prices
getCurrencySymbol()       // Get currency display
```

**Tab Navigation:**
```javascript
switchTab(tabName)        // Switch between Flights/Hotels/Cars/Packages
renderOffers()            // Render service grid
```

**Flight Booking:**
```javascript
bookFlight(flightId)      // Initiate flight booking
selectFlight(flightId)    // Select specific flight
renderFlightsList()       // Display available flights
renderSeatMap()           // Display seat grid
selectSeat(seatNum)       // Select seat
```

**Modal Management:**
```javascript
openModal(modalId)        // Open modal dialog
closeModal(modalId)       // Close modal dialog
```

**Booking Steps:**
```javascript
nextStep()                // Advance to next booking step
previousStep()            // Go back to previous step
updateOrderSummary()      // Update price summary
updatePaymentSummary()    // Update payment display
processPayment()          // Process payment and generate ticket
downloadTicket()          // Download e-ticket
```

### **Data Structures**

**Flight Object:**
```javascript
{
  id: 'FL001',
  airline: 'Kenya Airways',
  from: 'NBO',
  to: 'JNB',
  departure: '10:30',
  arrival: '13:00',
  date: '2025-12-20',
  duration: '2h 30m',
  priceUSD: 320,
  originalPriceUSD: 450,
  capacity: 180,
  booked: 145,
  stops: 'Direct'
}
```

**Booking Data Object:**
```javascript
{
  flight: {/* flight object */},
  seat: 15,
  passenger: {
    name: 'John Doe',
    email: 'john@example.com',
    phone: '+1 (555) 000-0000',
    passport: 'ABC123456',
    dob: '1990-01-15',
    nationality: 'Kenya'
  }
}
```

---

## Integration with Backend API

### **Suggested API Endpoints**

**Get Available Flights:**
```
GET /api/flights?from=NBO&to=JNB&date=2025-12-20
Response: Array of flight objects
```

**Get Seat Availability:**
```
GET /api/flights/{flightId}/seats
Response: Array of seat objects with availability status
```

**Create Booking:**
```
POST /api/bookings
Body: bookingData (flight, seat, passenger info)
Response: Booking confirmation with ticket number
```

**Process Payment:**
```
POST /api/payments
Body: {bookingId, cardDetails, amount}
Response: Payment confirmation or error
```

---

## Security Considerations

### **Current Implementation (Development)**
- Form validation on client-side
- Basic card input masks
- Modal-based form containment

### **Recommended for Production**
- SSL/TLS encryption
- PCI-DSS compliance for payment
- Server-side validation of all inputs
- Secure payment gateway integration (Stripe, PayPal)
- Rate limiting on booking endpoints
- CSRF token validation
- Proper error handling (don't expose sensitive info)

---

## Future Enhancements

1. **Real-time Seat Synchronization**
   - WebSocket for live seat updates
   - Prevent double-booking

2. **Multi-Passenger Booking**
   - Add/remove passengers
   - Different details per passenger
   - Group discount calculation

3. **Payment Methods**
   - Mobile money (M-Pesa, AirtelMoney)
   - Bank transfers
   - Cryptocurrency
   - Installment plans

4. **Booking Management**
   - Modify bookings
   - Cancel with refund
   - View booking history
   - Reschedule flights

5. **Advanced Features**
   - Baggage selection and pricing
   - Meal preferences
   - Seat upgrades
   - Travel insurance options

6. **Notifications**
   - Email confirmation
   - SMS updates
   - Flight status alerts
   - Reminder emails

---

## File Structure

```
frontend/
├── passenger-portal.html          # Landing/menu page
├── passenger-booking.html         # Main booking system
├── flights-booking.html           # Legacy flights page
├── hotels-booking.html            # Hotels booking page
├── car-rentals-booking.html       # Car rentals page
├── vacation-packages.html         # Vacation packages page
└── ...
```

---

## How to Access

### **User Access**
1. **Portal:** `http://127.0.0.1:5000/passenger-portal.html`
2. **Smart Booking:** `http://127.0.0.1:5000/passenger-booking.html`

### **Navigation**
- From portal, click "Smart Booking" button
- Or directly visit booking URL
- All services accessible via tabs

---

## Support

For issues or questions:
- Contact support team
- Email: support@smartfly.com
- Phone: +1 (555) 123-4567
- Live chat available 24/7

---

**Last Updated:** December 18, 2025
**Version:** 1.0 - Initial Release
