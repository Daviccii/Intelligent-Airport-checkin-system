# 🔗 Admin Dashboard - System Integration Flow Visualization

## Real-Time Data Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER INTERACTIONS                                   │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┬──────────────────┐
        │                     │                     │                  │
        ▼                     ▼                     ▼                  ▼
    ┌────────────┐       ┌──────────┐        ┌──────────┐      ┌──────────┐
    │  Passenger │       │Passenger │        │  Admin   │      │ Payment  │
    │   Books    │       │  Checks  │        │  Adds    │      │ System   │
    │  Ticket    │       │   In     │        │ Flight   │      │ Processes│
    └─────┬──────┘       └────┬─────┘        └────┬─────┘      └────┬─────┘
          │ POST             │ POST              │ POST             │ POST
          ▼                  ▼                  ▼                  ▼
    /api/bookings      /api/checkin       /api/flights      /api/baggage/pay
          │                  │                  │                  │
          └──────────────────┴──────────────────┴──────────────────┘
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │          FLASK BACKEND (app.py)                           │
        │                                                            │
        │  • Validates requests                                     │
        │  • Saves to JSON files                                    │
        │  • Returns JSON responses                                 │
        └────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬────────────────┐
        │                    │                    │                │
        ▼                    ▼                    ▼                ▼
    bookings.json       passengers.json     flights.json       events.json
    (Payment records)  (Check-in data)     (Flight info)     (Event logs)
        │                    │                    │                │
        └────────────────────┼────────────────────┴────────────────┘
                             │
                      GET requests ↓
                             │
        ┌────────────────────┼────────────────────┬────────────────┐
        │                    │                    │                │
    /api/flights        /api/bookings        /api/passengers      │
        │                    │                    │                │
        └────────────────────┴────────────────────┴────────────────┘
                             │
                        Every 10 seconds
                             │
                             ▼
        ┌────────────────────────────────────────────────────────────┐
        │       ADMIN DASHBOARD (Real-Time Monitoring)              │
        │                                                            │
        │  • fetchDashboardData() runs                             │
        │  • Fetches all 3 API endpoints                           │
        │  • Calculates all metrics                                │
        │  • Updates DOM elements                                  │
        │  • Refreshes charts                                      │
        └────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┬────────────────┐
        │                    │                    │                │
        ▼                    ▼                    ▼                ▼
    Summary Cards      Activities Table      Charts            System Status
    • Flights          • Recent bookings     • Monthly bookings  • Uptime
    • Passengers       • Check-ins           • Passenger traffic • API requests
    • Revenue          • Payments            • Top flights       • Sessions
    • Check-ins        • Cancellations       • Revenue trend     • Performance
        │                    │                    │                │
        └────────────────────┴────────────────────┴────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   ADMIN SEES    │
                    │                 │
                    │ Real-time data! │
                    │ All system      │
                    │ activity        │
                    │ visible         │
                    └─────────────────┘
```

## Time Sequence Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  TIMELINE: How Data Flows From User Action to Admin Dashboard               │
└──────────────────────────────────────────────────────────────────────────────┘

t=0s
│
├─ User Action: PASSENGER BOOKS A FLIGHT
│  ├─ User clicks "Book Flight" button
│  ├─ Frontend validates form
│  └─ Frontend POSTs to /api/bookings
│
├─ Backend Processes:
│  ├─ Flask receives POST request
│  ├─ Validates booking data
│  ├─ Saves to bookings.json
│  └─ Returns success response
│
└─ DASHBOARD STATE: Still shows old data (no refresh yet)

t=0-10s
│
├─ User browsing dashboard
├─ Dashboard shows 1,233 passengers
├─ Dashboard shows $457,920 revenue
└─ Nothing changes yet...

t=10s
│
├─ AUTO-REFRESH TRIGGERED! ⏰
│  ├─ setInterval() fires
│  └─ fetchDashboardData() called
│
├─ FETCH PHASE:
│  ├─ fetch('/api/flights')     ─→ Receives flight array
│  ├─ fetch('/api/bookings')    ─→ Receives [new booking + others]
│  └─ fetch('/api/passengers')  ─→ Receives passenger array
│
├─ CALCULATE PHASE:
│  ├─ Count flights: 45
│  ├─ Count passengers: 1,234 ← INCREASED BY 1!
│  ├─ Sum revenue: $458,370 ← INCREASED!
│  └─ Calculate metrics (occupancy, growth, etc.)
│
├─ RENDER PHASE:
│  ├─ hydrateSummary()    → Update card numbers
│  ├─ renderActivities()  → Add new event to table
│  ├─ Update charts        → Refresh data visualization
│  └─ Update status        → Refresh system metrics
│
└─ DASHBOARD NOW SHOWS: ✨
   ├─ Total Passengers: 1,234 (was 1,233)
   ├─ Total Revenue: $458,370 (was $457,920)
   ├─ New activity in table: "Booking | [Passenger] | [Flight]"
   └─ Charts updated with latest data

t=10s THROUGH t=20s
│
├─ Admin sees the updates! 🎉
├─ New activity displayed in Recent Activities table
├─ Summary cards show updated numbers
├─ Charts reflect new data point
└─ Dashboard continues monitoring...

t=20s
│
├─ AUTO-REFRESH TRIGGERED AGAIN! ⏰
│  └─ (Same process repeats)
│
└─ Dashboard stays perfectly current

═══════════════════════════════════════════════════════════════════════════════

This cycle repeats every 10 seconds, keeping the dashboard always fresh!
```

## Data Flow for Each Event Type

### 1️⃣ NEW BOOKING EVENT

```
PASSENGER BOOKS FLIGHT:
   │
   └─ POST /api/bookings
        │
        ├─ Validate data
        ├─ Save to bookings.json:
        │   {
        │     "id": "BOOK_NEW",
        │     "name": "Jane Doe",
        │     "amount": 450,
        │     "status": "completed",
        │     "created_at": "2025-12-17T10:15:00Z"
        │   }
        └─ Return success
           │
           ▼ (After 10s, dashboard auto-refreshes)
           │
           ├─ fetch(/api/bookings) ─→ [includes new booking]
           ├─ Count total: 1,234 (was 1,233)
           ├─ Sum amount: $458,370 (was $457,920)
           │
           └─ DASHBOARD UPDATES:
              ├─ Card shows: "1,234 passengers"
              ├─ Card shows: "$458,370 revenue"
              ├─ Activity shows: "Booking | Jane Doe | ... | just now"
              └─ Charts include new data point
```

### 2️⃣ PASSENGER CHECK-IN EVENT

```
PASSENGER CHECKS IN:
   │
   └─ POST /api/checkin
        │
        ├─ Validate passport & flight
        ├─ Update passengers.json:
        │   {
        │     "name": "John Smith",
        │     "passport": "GB123456",
        │     "flight": "AA100",
        │     "seat": "12A",
        │     "checked_in": true ← SET TO TRUE
        │   }
        └─ Return seat assignment
           │
           ▼ (After 10s, dashboard auto-refreshes)
           │
           ├─ fetch(/api/passengers) ─→ [includes updated record]
           ├─ Count checked_in: true ─→ 246 (was 245)
           ├─ Calculate occupancy: (246/750) × 100 = 32.8%
           │
           └─ DASHBOARD UPDATES:
              ├─ Card shows: "246 checked in"
              ├─ Status shows: "✓ Live"
              ├─ Quick stat shows: "32.8% occupancy"
              └─ Activity shows: "Check-in | John Smith | AA100 | ✓ Success"
```

### 3️⃣ NEW FLIGHT ADDED EVENT

```
ADMIN ADDS FLIGHT:
   │
   └─ POST /api/flights
        │
        ├─ Validate flight data
        ├─ Save to flights.json:
        │   {
        │     "flight": "BA206",
        │     "airline": "British Airways",
        │     "departure_time": "2025-12-17T14:30:00Z",
        │     "capacity": 242
        │   }
        └─ Return success
           │
           ▼ (After 10s, dashboard auto-refreshes)
           │
           ├─ fetch(/api/flights) ─→ [includes new flight]
           ├─ Count total: 46 flights (was 45)
           │
           └─ DASHBOARD UPDATES:
              ├─ Card shows: "46 flights | +1 today"
              └─ Capacity calculations updated
```

### 4️⃣ PAYMENT PROCESSED EVENT

```
PAYMENT SYSTEM PROCESSES PAYMENT:
   │
   └─ POST /api/baggage/pay
        │
        ├─ Process payment
        ├─ Update booking in bookings.json:
        │   {
        │     "id": "BOOK001",
        │     "amount": 450,
        │     "payment_status": "completed" ← UPDATED
        │   }
        └─ Return payment confirmation
           │
           ▼ (After 10s, dashboard auto-refreshes)
           │
           ├─ fetch(/api/bookings) ─→ [includes updated booking]
           ├─ Sum amount: includes this payment
           ├─ Count confirmed: increased
           │
           └─ DASHBOARD UPDATES:
              ├─ Revenue card updated
              ├─ Activity shows: "Payment | [Passenger] | ... | ✓ Success"
              └─ Growth rate recalculated
```

## Component Interaction Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        BROWSER (Admin Dashboard)                          │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ dashboard.html (Layout)                                           │ │
│ │ ┌──────────────────────────────────────────────────────────────┐ │ │
│ │ │ <div class="dashboard-header">...</div>                    │ │ │
│ │ │ <div class="quick-stats-bar">...</div>                    │ │ │
│ │ │ <div class="summary-cards">...</div>                      │ │ │
│ │ │ <div class="activities-table">...</div>                   │ │ │
│ │ │ <div class="system-status">...</div>                      │ │ │
│ │ │ <canvas id="chartBookings"></canvas>                      │ │ │
│ │ │ <canvas id="chartTraffic"></canvas>                       │ │ │
│ │ │ <canvas id="chartShares"></canvas>                        │ │ │
│ │ │ <canvas id="chartRevenue"></canvas>                       │ │ │
│ │ └──────────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                   ▲                                      │
│                                   │ updates                              │
│                                   │                                      │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ dashboard.js (Logic)                                              │ │
│ │                                                                    │ │
│ │ ┌─────────────────────────────────────────────────────────────┐  │ │
│ │ │ const state = {                                            │  │ │
│ │ │   summary: { flights, passengers, revenue, checkins }     │  │ │
│ │ │   activities: [],                                          │  │ │
│ │ │   charts: { bookings, traffic, shares, payments }         │  │ │
│ │ │ }                                                           │  │ │
│ │ └─────────────────────────────────────────────────────────────┘  │ │
│ │                                                                    │ │
│ │ ┌────────────────────────┐      ┌──────────────────────────────┐ │ │
│ │ │ fetchDashboardData()   │      │ hydrateSummary()           │ │ │
│ │ │                        │      │                            │ │ │
│ │ │ • GET /api/flights     │      │ • Update card numbers      │ │ │
│ │ │ • GET /api/bookings    │  →  │ • Update timestamps       │ │ │
│ │ │ • GET /api/passengers  │      │ • Format currencies       │ │ │
│ │ │                        │      │ • Set metric values       │ │ │
│ │ │ • Calculate metrics    │      │                            │ │ │
│ │ │ • Update state         │      └──────────────────────────────┘ │ │
│ │ │                        │                                       │ │
│ │ │ Every 10 seconds ⏰   │      renderActivities()             │ │ │
│ │ └────────────────────────┘      buildCharts()                 │ │ │
│ │                                                                    │ │
│ │ ┌─────────────────────────────────────────────────────────────┐  │ │
│ │ │ DOMContentLoaded:                                          │  │ │
│ │ │   1. fetchDashboardData()                                  │  │ │
│ │ │   2. hydrateSummary()                                      │  │ │
│ │ │   3. renderActivities()                                    │  │ │
│ │ │   4. buildCharts()                                         │  │ │
│ │ │   5. setInterval(10000) ← Auto-refresh every 10 seconds   │  │ │
│ │ └─────────────────────────────────────────────────────────────┘  │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                                   │                                      │
│                         HTTP GET requests                                │
│                                   │                                      │
└───────────────────────────────────┼──────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
              /api/flights    /api/bookings   /api/passengers
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
            ┌──────────────────┐          ┌─────────────────┐
            │ Flask Backend    │          │  JSON Files     │
            │ (app.py)         │          │                 │
            │                  │◄────────►│ • flights.json  │
            │ • Validate       │          │ • bookings.json │
            │ • Process        │          │ • passengers.json
            │ • Save to files  │          │ • events.json   │
            │ • Return JSON    │          │                 │
            └──────────────────┘          └─────────────────┘
```

## State Management Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  STATE OBJECT STRUCTURE (dashboard.js)                                 │
└─────────────────────────────────────────────────────────────────────────┘

const state = {
  summary: {
    flights: { total: 45, delta: 3 },
    passengers: { total: 1234, delta: 45 },
    revenue: { total: 458370, deltaPct: 18 },
    checkins: { total: 246, live: true }
  },
  activities: [
    { type: "Check-in", passenger: "John", flight: "AA100", ... },
    { type: "Booking", passenger: "Jane", flight: "BA206", ... },
    ...
  ],
  charts: {
    bookings: { data: [280, 320, 295, ...] },
    traffic: { data: [336, 384, 354, ...] },
    shares: { 
      labels: ["AA100", "BA205", "UA380"],
      data: [245, 210, 189]
    },
    payments: { data: [42000, 48000, 44250, ...] }
  },
  systemStatus: {
    apiRequests: 3702,
    activeSessions: 180,
    userSessions: 990
  }
}

↓ Every 10 seconds, this flow occurs:

┌──────────────────────┐
│ Fetch all APIs       │
│ (3 parallel calls)   │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ Parse JSON responses │
│ into arrays          │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ Calculate metrics    │
│ (counts, sums, %)    │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ Update state object  │
│ (new values)         │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ Render to DOM        │
│ (hydrate functions)  │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ Update charts        │
│ (Chart.js .update()) │
└──────────────────────┘
         │
         ▼
   Dashboard reflects
   latest system data!
```

---

## Summary

The admin dashboard is fully integrated with your airport check-in system through:

1. **Real-time API Integration**
   - Fetches `/api/flights`, `/api/bookings`, `/api/passengers` every 10 seconds
   - Processes JSON responses into actionable metrics

2. **Automatic Data Processing**
   - Calculates occupancy, revenue, growth rates
   - Aggregates activities from all sources
   - Prepares chart data

3. **Instant Visual Updates**
   - Updates card numbers
   - Refreshes activity table
   - Rebuilds charts
   - All without page reload

4. **Continuous Monitoring**
   - Every 10 seconds, fresh data fetched
   - Dashboard always shows current system state
   - Admin never misses an update

**Result**: Complete real-time visibility of your entire airport operations! 🎉
