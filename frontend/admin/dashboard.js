(function() {
  // Utility functions
  const fmtNumber = (value) => value.toLocaleString('en-US');
  const fmtCurrency = (value) => `$${(value / 1000).toFixed(1)}K`; // Example formatting

  // Hydrate summary cards
  function hydrateSummary(summary) {
    if (!summary) {
      console.warn('hydrateSummary called with no data.');
      return;
    }

    document.getElementById('currentDate').textContent = new Date().toLocaleDateString('en-GB', {
      weekday: 'long',
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });

    document.getElementById('statFlights').textContent = fmtNumber(summary.flights.total);
    document.getElementById('statFlightsDelta').textContent = `+${summary.flights.delta} today`;

    document.getElementById('statPassengers').textContent = fmtNumber(summary.passengers.total);
    document.getElementById('statPassengersDelta').textContent = `+${fmtNumber(summary.passengers.delta)} today`;

    document.getElementById('statRevenue').textContent = fmtCurrency(summary.revenue.total);
    document.getElementById('statRevenueDelta').textContent = `+${summary.revenue.deltaPct}% vs last week`;

    document.getElementById('statCheckins').textContent = summary.checkins.total;
    document.getElementById('statCheckinsDelta').textContent = summary.checkins.live ? 'Live' : 'Offline';

    // Update timestamp
    document.getElementById('updateTime').textContent = 'just now';
  }

  // Render activities table
  function renderActivities(activities) {
    if (!activities) {
      console.warn('renderActivities called with no data.');
      return;
    }

    const tbody = document.querySelector('#activitiesTable tbody');
    tbody.innerHTML = '';

    activities.forEach((item) => {
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

  // Function to update charts with new data
  function updateCharts(chartData) {
    if (!chartData || !Object.keys(charts).length) return;

    charts.bookings.data.labels = chartData.bookings.labels;
    charts.bookings.data.datasets[0].data = chartData.bookings.data;
    charts.bookings.update();

    charts.passengers.data.labels = chartData.passengers.labels;
    charts.passengers.data.datasets[0].data = chartData.passengers.data;
    charts.passengers.update();

    charts.flights.data.labels = chartData.flights.labels;
    charts.flights.data.datasets[0].data = chartData.flights.data;
    charts.flights.update();

    charts.loadFactor.data.labels = chartData.loadFactor.labels;
    charts.loadFactor.data.datasets[0].data = chartData.loadFactor.data;
    charts.loadFactor.update();
  }

  // Build charts
  function buildCharts(initialData = {}) {
    // Bookings bar chart
    charts.bookings = new Chart(document.getElementById('chartBookings'), {
      type: 'bar',
      data: {
        labels: initialData.bookings?.labels || [],
        datasets: [{
          label: 'Monthly Bookings',
          data: initialData.bookings?.data || [],
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
        labels: initialData.passengers?.labels || [],
        datasets: [{
          label: 'Passengers',
          data: initialData.passengers?.data || [],
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
        labels: initialData.flights?.labels || [],
        datasets: [{
          label: 'Fleet Mix',
          data: initialData.flights?.data || [],
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
        labels: initialData.loadFactor?.labels || [],
        datasets: [{
          label: 'Load Factor %',
          data: initialData.loadFactor?.data || [],
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
    // Build charts with empty data initially
    buildCharts(); 

    // --- WebSocket Implementation ---
    // Note: Ensure the Socket.IO client library is included in dashboard.html
    // e.g., <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    
    const socket = io();
    const connectionStatusEl = document.getElementById('connectionStatus');

    socket.on('connect', () => {
      console.log('✅ WebSocket connected. Requesting initial data...');
      if (connectionStatusEl) {
        connectionStatusEl.textContent = 'Live';
        connectionStatusEl.className = 'status-dot live';
      }
      socket.emit('request_initial_data');
    });

    socket.on('dashboard_update', (data) => {
      console.log('📊 Received dashboard update via WebSocket:', data);
      if (data.summary) hydrateSummary(data.summary);
      if (data.activities) renderActivities(data.activities);
      if (data.charts) updateCharts(data.charts);
    });

    socket.on('disconnect', () => {
      console.warn('❌ WebSocket disconnected.');
      if (connectionStatusEl) {
        connectionStatusEl.textContent = 'Offline';
        connectionStatusEl.className = 'status-dot offline';
      }
    });
  });
})();
