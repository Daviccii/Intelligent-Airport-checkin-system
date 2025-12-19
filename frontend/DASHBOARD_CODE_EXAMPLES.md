# Dashboard Interactive Features - Code Examples

## HTML Structure

### Summary Card Structure
```html
<div class="summary-card card h-100 shadow-sm border-0 clickable-card" data-card="flights">
  <div class="card-body">
    <div class="d-flex align-items-start justify-content-between">
      <div class="flex-grow-1">
        <div class="text-muted small text-uppercase tracking-wide">Total Flights</div>
        <div class="display-5 fw-bold mt-2" id="statFlights">—</div>
        <div class="badge bg-success bg-opacity-25 text-success mt-2" id="statFlightsDelta">+0 today</div>
      </div>
      <div class="summary-icon flights">
        <i class="fas fa-plane-departure"></i>
      </div>
    </div>
  </div>
  <div class="card-hover-indicator"></div>
</div>
```

**Key Elements:**
- `clickable-card` class: Makes card interactive
- `data-card` attribute: Identifies card type
- `card-hover-indicator` div: Bottom border animation

### Activity Table with Search
```html
<div class="card-header bg-white border-bottom">
  <div class="d-flex justify-content-between align-items-center gap-2 flex-wrap">
    <div>
      <h5 class="mb-1 fw-semibold">Recent Activities</h5>
      <p class="text-muted mb-0 small">Latest bookings and check-ins across the system</p>
    </div>
    <div class="d-flex gap-2">
      <input type="text" class="form-control form-control-sm" 
             id="activitySearch" placeholder="Search activities..." 
             style="max-width: 200px;">
      <button class="btn btn-sm btn-outline-secondary" id="activityViewAll">
        View all →
      </button>
    </div>
  </div>
</div>
```

---

## CSS Styling

### Card Hover Animation
```css
.clickable-card {
  position: relative;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 12px !important;
}

.clickable-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 32px rgba(13, 110, 253, 0.18) !important;
}

.card-hover-indicator {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--primary-light));
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.clickable-card:hover .card-hover-indicator {
  transform: scaleX(1);
}
```

**Effect Breakdown:**
- `translateY(-8px)`: Lifts card up on hover
- `box-shadow`: Creates depth with glowing effect
- `scaleX`: Bottom indicator animates from left to right
- `cubic-bezier`: Smooth, natural animation curve

### Icon Gradient Backgrounds
```css
.summary-icon.flights {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
}

.summary-icon.pax {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  box-shadow: 0 8px 24px rgba(245, 87, 108, 0.3);
}

.summary-icon.revenue {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  box-shadow: 0 8px 24px rgba(79, 172, 254, 0.3);
}

.summary-icon.checkins {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  box-shadow: 0 8px 24px rgba(67, 233, 123, 0.3);
}

.clickable-card:hover .summary-icon {
  transform: scale(1.08) rotate(2deg);
}
```

### Activity Table Row Styling
```css
.activities-table tbody tr {
  position: relative;
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  transition: all 0.2s ease;
}

.activities-table tbody tr:hover {
  background-color: rgba(13, 110, 253, 0.04);
  transform: translateX(4px);
}

.activities-table tbody tr::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--primary), var(--primary-light));
  transform: scaleY(0);
  transform-origin: center;
  transition: transform 0.3s ease;
}

.activities-table tbody tr:hover::before {
  transform: scaleY(1);
}
```

**Effect Breakdown:**
- `.hover`: Light blue background on row
- `translateX(4px)`: Row slides right slightly
- `::before`: Left gradient border animates in height
- `scaleY`: Border animates from top/bottom to full height

### Activity Badge Styling
```css
.activity-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.activity-badge.booking {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.activity-badge.checkin {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #fff;
}

.activity-badge.payment {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
}

.activity-badge.system {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  color: #fff;
}
```

### Pulse Animation
```css
@keyframes pulse-update {
  0% {
    box-shadow: 0 0 0 0 rgba(13, 110, 253, 0.4);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(13, 110, 253, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(13, 110, 253, 0);
  }
}

.updating {
  animation: pulse-update 1.5s infinite;
}
```

---

## JavaScript Implementation

### Card Click Handler
```javascript
// Attach click listeners to all summary cards
document.querySelectorAll('.clickable-card').forEach(card => {
  card.addEventListener('click', function() {
    const cardType = this.getAttribute('data-card');
    showCardDetails(cardType);
  });
});

// Show card details modal
function showCardDetails(cardType) {
  const modalElement = document.getElementById('cardDetailsModal');
  const modal = new bootstrap.Modal(modalElement);
  const title = document.getElementById('cardDetailsTitle');
  const content = document.getElementById('cardDetailsContent');
  
  let detailsHTML = '';
  
  switch(cardType) {
    case 'flights':
      title.textContent = '✈️ Flight Management';
      detailsHTML = `
        <div class="row g-3">
          <div class="col-md-6">
            <div class="activity-detail-item">
              <div class="activity-detail-label">Total Flights</div>
              <div class="activity-detail-value" id="detailFlightsTotal">0</div>
            </div>
          </div>
          <div class="col-md-6">
            <div class="activity-detail-item">
              <div class="activity-detail-label">Active Today</div>
              <div class="activity-detail-value" id="detailFlightsDelta">0</div>
            </div>
          </div>
          <div class="col-12">
            <a href="flights.html" class="btn btn-primary w-100">
              <i class="fas fa-arrow-right me-2"></i>Manage Flights
            </a>
          </div>
        </div>
      `;
      document.getElementById('detailFlightsTotal').textContent = state.summary.flights.total;
      document.getElementById('detailFlightsDelta').textContent = state.summary.flights.delta;
      break;
    // ... more cases for other cards
  }
  
  content.innerHTML = detailsHTML;
  modal.show();
}
```

### Activity Row Click Handler
```javascript
function attachActivityRowListeners() {
  document.querySelectorAll('.activities-table tbody tr').forEach(row => {
    row.addEventListener('click', function() {
      const activityData = {
        type: this.cells[0].textContent.trim(),
        passenger: this.cells[1].textContent.trim(),
        flight: this.cells[2].textContent.trim(),
        time: this.cells[3].textContent.trim(),
        status: this.cells[4].textContent.trim()
      };
      showActivityDetails(activityData);
    });
  });
}

function showActivityDetails(activity) {
  const modalElement = document.getElementById('activityModal');
  const modal = new bootstrap.Modal(modalElement);
  const content = document.getElementById('activityDetailContent');
  
  const statusClass = activity.status.includes('completed') ? 'status-completed' : 
                     activity.status.includes('pending') ? 'status-pending' :
                     activity.status.includes('active') ? 'status-active' : 'status-failed';
  
  const detailsHTML = `
    <div class="row g-3">
      <div class="col-md-6">
        <div class="activity-detail-item">
          <div class="activity-detail-label">Activity Type</div>
          <div class="activity-detail-value">
            <span class="badge activity-badge ${activity.type.toLowerCase()}">
              ${activity.type}
            </span>
          </div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="activity-detail-item">
          <div class="activity-detail-label">Status</div>
          <div class="activity-detail-value">
            <span class="badge ${statusClass}">${activity.status}</span>
          </div>
        </div>
      </div>
      <!-- ... more detail rows ... -->
    </div>
  `;
  
  content.innerHTML = detailsHTML;
  modal.show();
}
```

### Activity Search Functionality
```javascript
// Real-time activity search
document.getElementById('activitySearch').addEventListener('input', function(e) {
  const searchTerm = e.target.value.toLowerCase();
  const tableBody = document.querySelector('.activities-table tbody');
  
  Array.from(tableBody.querySelectorAll('tr')).forEach(row => {
    const text = row.textContent.toLowerCase();
    row.style.display = text.includes(searchTerm) ? '' : 'none';
  });
});

// View all activities button
document.getElementById('activityViewAll').addEventListener('click', function() {
  const tableBody = document.querySelector('.activities-table tbody');
  Array.from(tableBody.querySelectorAll('tr')).forEach(row => {
    row.style.display = '';
  });
});
```

### Auto-Refresh Mechanism
```javascript
let refreshInterval = null;

function startAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(async () => {
    // Fetch fresh data
    await fetchDashboardData();
    updateUI();
    attachActivityRowListeners();
    
    // Add pulse animation to updated stats
    document.querySelectorAll('.summary-card').forEach(card => {
      card.classList.add('updating');
      setTimeout(() => card.classList.remove('updating'), 1500);
    });
  }, 30000); // Refresh every 30 seconds
}

function stopAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
}

// Start on page load
window.addEventListener('load', () => {
  attachActivityRowListeners();
  startAutoRefresh();
});

// Stop on page unload
window.addEventListener('beforeunload', stopAutoRefresh);
```

### Keyboard Shortcuts
```javascript
// Ctrl+R to manually refresh
document.addEventListener('keydown', function(e) {
  if (e.ctrlKey && e.key === 'r') {
    e.preventDefault();
    fetchDashboardData()
      .then(updateUI)
      .then(attachActivityRowListeners);
  }
});
```

---

## Data Flow Example

### When user clicks a summary card:
```
User clicks card
  ↓
Event listener triggered
  ↓
Extract data-card attribute ("flights")
  ↓
Call showCardDetails("flights")
  ↓
Create modal HTML with flights data
  ↓
Get flights count from state.summary.flights.total
  ↓
Get flights delta from state.summary.flights.delta
  ↓
Set modal title and content
  ↓
Show modal with bootstrap.Modal.show()
  ↓
User sees detailed information
  ↓
User clicks "Manage Flights" button
  ↓
Navigate to flights.html
```

### When user searches activities:
```
User types in search box
  ↓
Input event triggered
  ↓
Extract search term (lowercase)
  ↓
Get all activity table rows
  ↓
For each row:
   - Get row text content
   - Convert to lowercase
   - Check if includes search term
   - Set display to '' (visible) or 'none' (hidden)
  ↓
Table updates in real-time
```

---

## State Management

### Global State Object
```javascript
const state = {
  summary: {
    flights: { total: 0, delta: 0 },
    passengers: { total: 0, delta: 0 },
    revenue: { total: 0, deltaPct: 0 },
    checkins: { total: 0, live: false }
  },
  activities: [],
  charts: {
    bookings: { data: [] },
    traffic: { data: [] },
    shares: { labels: [], data: [] },
    payments: { data: [] }
  },
  systemStatus: {
    uptime: 99.9,
    database: 98.5,
    apiRequests: 0,
    activeSessions: 0,
    userSessions: 0
  }
};
```

### State Updates on Refresh
```javascript
// When data is fetched:
state.summary.flights.total = flights.length;
state.summary.flights.delta = Math.floor(flights.length * 0.15);

// When UI is updated:
document.getElementById('statFlights').textContent = state.summary.flights.total;
document.getElementById('statFlightsDelta').textContent = `+${state.summary.flights.delta} today`;
```

---

## Performance Tips

### Efficient Event Delegation
```javascript
// ❌ Bad: Attaches listener to every row
document.querySelectorAll('.activities-table tbody tr').forEach(row => {
  row.addEventListener('click', handler); // Lots of listeners!
});

// ✅ Good: Single listener on parent
document.querySelector('.activities-table tbody').addEventListener('click', (e) => {
  const row = e.target.closest('tr');
  if (row) handleRowClick(row);
});
```

### Debounced Search
```javascript
// Prevents excessive reflows
let searchTimeout;
document.getElementById('activitySearch').addEventListener('input', function(e) {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    // Perform search
  }, 300);
});
```

### CSS Transforms for Animations
```css
/* ❌ Bad: Causes layout recalculation */
.item:hover { left: 10px; }

/* ✅ Good: Uses GPU acceleration */
.item:hover { transform: translateX(10px); }
```

---

## Summary

The dashboard interactivity is built on:
1. **CSS Animations** - Smooth visual feedback with `transform` and gradients
2. **JavaScript Events** - Click handlers for cards and rows
3. **Bootstrap Modals** - For displaying detailed information
4. **Real-time Updates** - Auto-refresh every 30 seconds
5. **Search Filtering** - Dynamic activity filtering

All working together to create a professional, responsive, and engaging admin dashboard experience.

---

**Documentation Version:** 1.0
**Last Updated:** December 18, 2025
