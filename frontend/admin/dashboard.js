(function() {
  // Utility functions
  const fmtNumber = (value) => value.toLocaleString('en-US');
  const fmtCurrency = (value) => `$${(value / 1000).toFixed(1)}K`;

  // Mock data source
  const state = {
    summary: {
      flights: { total: 342, delta: 18 },
      passengers: { total: 52840, delta: 1240 },
      revenue: { total: 8740000, deltaPct: 24 },
      checkins: { total: 156, live: true },
    },
    activities: [
      { type: 'Check-in', passenger: 'Amina Otieno', flight: 'KQ500', time: '1m ago', status: 'Success' },
      { type: 'Booking', passenger: 'James Karanja', flight: 'KQ502', time: '3m ago', status: 'Success' },
      { type: 'Payment', passenger: 'Emma Njoroge', flight: 'KQ504', time: '8m ago', status: 'Success' },
      { type: 'Check-in', passenger: 'David Singh', flight: 'KQ500', time: '12m ago', status: 'Pending' },
      { type: 'Booking', passenger: 'Lisa Mwangi', flight: 'KQ502', time: '18m ago', status: 'Success' },
      { type: 'Cancellation', passenger: 'Michael Njenga', flight: 'KQ504', time: '24m ago', status: 'Canceled' },
      { type: 'Check-in', passenger: 'Nina Patel', flight: 'KQ502', time: '31m ago', status: 'Pending' },
      { type: 'Booking', passenger: 'Carlos Wanjiru', flight: 'KQ500', time: '38m ago', status: 'Success' },
    ],
    charts: {
      bookings: {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        data: [280, 320, 295, 410, 450, 480, 520, 510, 485, 520, 580, 610],
      },
      passengers: {
        labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
        data: [8200, 9100, 8950, 10200, 11500, 12840],
      },
      flights: {
        labels: ['Boeing 737', 'Embraer E190', 'Boeing 787', 'Airbus A330', 'Dash 8'],
        data: [52, 43, 32, 21, 18],
      },
      loadFactor: {
        labels: ['NBO-JNB', 'NBO-ADD', 'NBO-KGL', 'NBO-CPT', 'NBO-LOS', 'NBO-MBA', 'NBO-EBB', 'NBO-DAR'],
        data: [93, 90, 88, 84, 82, 91, 89, 86],
      }
    }
  };

  // Hydrate summary cards
  function hydrateSummary() {
    document.getElementById('currentDate').textContent = new Date().toLocaleDateString('en-GB', {
      weekday: 'long',
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });

    document.getElementById('statFlights').textContent = fmtNumber(state.summary.flights.total);
    document.getElementById('statFlightsDelta').textContent = `+${state.summary.flights.delta} today`;

    document.getElementById('statPassengers').textContent = fmtNumber(state.summary.passengers.total);
    document.getElementById('statPassengersDelta').textContent = `+${fmtNumber(state.summary.passengers.delta)} today`;

    document.getElementById('statRevenue').textContent = fmtCurrency(state.summary.revenue.total);
    document.getElementById('statRevenueDelta').textContent = `+${state.summary.revenue.deltaPct}% vs last week`;

    document.getElementById('statCheckins').textContent = state.summary.checkins.total;
    document.getElementById('statCheckinsDelta').textContent = state.summary.checkins.live ? 'Live' : 'Offline';

    // Update timestamp
    document.getElementById('updateTime').textContent = 'just now';
  }

  // Render activities table
  function renderActivities() {
    const tbody = document.querySelector('#activitiesTable tbody');
    tbody.innerHTML = '';

    state.activities.forEach((item) => {
      const tr = document.createElement('tr');
      const iconMap = {
        'Booking': 'fa-ticket',
        'Check-in': 'fa-passport',
        'Payment': 'fa-credit-card',
        'Cancellation': 'fa-times-circle'
      };
      const icon = iconMap[item.type] || 'fa-circle';
      
      tr.innerHTML = `
        <td><i class="fas ${icon}" style="margin-right: 8px; color: var(--primary);"></i>${item.type}</td>
        <td>${item.passenger}</td>
        <td><strong>${item.flight}</strong></td>
        <td><small class="text-muted">${item.time}</small></td>
        <td class="text-end">${badgeForStatus(item.status)}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Status badge helper
  function badgeForStatus(status) {
    const normalized = status.toLowerCase();
    let cls = 'badge-status pending';
    if (normalized === 'success') cls = 'badge-status success';
    else if (normalized === 'canceled') cls = 'badge-status canceled';
    return `<span class="${cls}">${status}</span>`;
  }

  // Chart.js instances
  let charts = {};

  // Build charts
  function buildCharts() {
    // Bookings bar chart
    charts.bookings = new Chart(document.getElementById('chartBookings'), {
      type: 'bar',
      data: {
        labels: state.charts.bookings.labels,
        datasets: [{
          label: 'Monthly Bookings',
          data: state.charts.bookings.data,
          backgroundColor: 'rgba(0, 102, 204, 0.8)',
          borderColor: 'rgba(0, 102, 204, 1)',
          borderWidth: 0,
          borderRadius: 6,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          filler: { propagate: true }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(0, 0, 0, 0.05)' },
            ticks: { color: '#6b7280' }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#6b7280' }
          }
        }
      }
    });

    // Passengers line chart
    charts.passengers = new Chart(document.getElementById('chartPassengers'), {
      type: 'line',
      data: {
        labels: state.charts.passengers.labels,
        datasets: [{
          label: 'Passengers',
          data: state.charts.passengers.data,
          borderColor: 'rgba(5, 150, 105, 0.9)',
          backgroundColor: 'rgba(5, 150, 105, 0.1)',
          tension: 0.4,
          fill: true,
          pointRadius: 5,
          pointBackgroundColor: '#059669',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false },
          filler: { propagate: true }
        },
        scales: {
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(0, 0, 0, 0.05)' },
            ticks: { color: '#6b7280' }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#6b7280' }
          }
        }
      }
    });

    // Fleet doughnut chart
    charts.flights = new Chart(document.getElementById('chartFlights'), {
      type: 'doughnut',
      data: {
        labels: state.charts.flights.labels,
        datasets: [{
          label: 'Fleet Mix',
          data: state.charts.flights.data,
          backgroundColor: [
            '#0066cc',
            '#059669',
            '#d97706',
            '#0891b2',
            '#7c3aed'
          ],
          borderWidth: 2,
          borderColor: '#fff',
          hoverOffset: 8,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              padding: 16,
              usePointStyle: true,
              pointStyle: 'circle',
              font: { size: 12 }
            }
          }
        }
      }
    });

    // Load factor bar chart
    charts.loadFactor = new Chart(document.getElementById('chartLoadFactor'), {
      type: 'bar',
      data: {
        labels: state.charts.loadFactor.labels,
        datasets: [{
          label: 'Load Factor %',
          data: state.charts.loadFactor.data,
          backgroundColor: 'rgba(139, 92, 246, 0.8)',
          borderColor: 'rgba(139, 92, 246, 1)',
          borderWidth: 0,
          borderRadius: 6,
        }]
      },
      options: {
        indexAxis: 'x',
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            grid: { color: 'rgba(0, 0, 0, 0.05)' },
            ticks: { color: '#6b7280' }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#6b7280' }
          }
        }
      }
    });
  }

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    hydrateSummary();
    renderActivities();
    buildCharts();
  });

  // Optional: Re-render data every 10 seconds
  setInterval(() => {
    hydrateSummary();
    renderActivities();
  }, 10000);
})();
