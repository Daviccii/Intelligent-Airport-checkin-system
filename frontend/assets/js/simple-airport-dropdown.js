/**
 * Simple Airport Dropdown - Bulletproof implementation
 * Works directly with input elements without complex wrappers
 */
(function(window) {
    'use strict';
    
    let airportsData = [];
    let loadedPromise = null;
    let availableCodes = null; // Set of IATA codes from API flights
    let availableLoaded = null;
    
    // Load airports data
    function loadAirports() {
        if (loadedPromise) return loadedPromise;
        
        // Try API first, then fallback to static JSON
        loadedPromise = (async function(){
            try {
                const api = await fetch('/api/airports?limit=500');
                if (api.ok) {
                    const j = await api.json();
                    // Normalize shapes: API may return {airports:[{code,city,name,country}]}
                    const list = Array.isArray(j) ? j : (Array.isArray(j.airports) ? j.airports : []);
                    if (Array.isArray(list) && list.length) {
                        airportsData = list.map(a => ({
                            code: a.code || a.iata || a.IATA || '',
                            name: a.name || a.airport_name || a.Name || '',
                            city: a.city || a.City || '',
                            country: a.country || a.Country || '' ,
                            lat: a.lat || a.latitude || a.Latitude,
                            lon: a.lon || a.longitude || a.Longitude
                        })).filter(a => a.code);
                        if (airportsData.length) return airportsData;
                    }
                }
            } catch(e) {
                /* ignore and fallback */
            }
            try {
                const res = await fetch('/assets/data/airports.json');
                if (res.ok) {
                    const data = await res.json();
                    airportsData = data || [];
                } else {
                    airportsData = [];
                }
            } catch(err) {
                console.error('Failed to load airports:', err);
                airportsData = [];
            }
            return airportsData;
        })();
        
        return loadedPromise;
    }
    
    // Load available flight origin/destination codes from API
    function loadAvailableCodes(){
        if (availableLoaded) return availableLoaded;
        availableLoaded = (async function(){
            try{
                const res = await fetch('/api/flights');
                if (!res.ok) throw new Error('api failed');
                const data = await res.json();
                const flights = Array.isArray(data) ? data : (data.flights || []);
                const set = new Set();
                flights.forEach(f=>{ if (f && f.origin) set.add(String(f.origin).toUpperCase()); if (f && f.destination) set.add(String(f.destination).toUpperCase()); });
                availableCodes = set;
            }catch(e){ availableCodes = new Set(); }
            return availableCodes;
        })();
        return availableLoaded;
    }
    
    // Calculate distance between two coordinates
    function calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371; // Earth's radius in km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }
    
    // Find nearest airport to given coordinates
    function findNearestAirport(lat, lon) {
        if (!airportsData.length) return null;
        
        let nearest = null;
        let minDistance = Infinity;
        
        airportsData.forEach(airport => {
            if (airport.lat && airport.lon) {
                const distance = calculateDistance(lat, lon, airport.lat, airport.lon);
                if (distance < minDistance) {
                    minDistance = distance;
                    nearest = airport;
                }
            }
        });
        
        return nearest;
    }
    
    // Filter airports by search query and sort by proximity
    function filterAirports(query, limit = 50, userLat = null, userLon = null) {
        const q = (query||'').toLowerCase().trim();
        let pool = airportsData.slice();
        
        if (q) {
            pool = pool.filter(a => {
                const code = (a.code||'').toLowerCase();
                const name = (a.name||'').toLowerCase();
                const city = (a.city||'').toLowerCase();
                const country = (a.country||'').toLowerCase();
                return code.startsWith(q) || city.includes(q) || name.includes(q) || country.includes(q);
            });
        }
        
        // Sort by: 1) Nearest airport first, 2) Available flights, 3) Alphabetically
        pool.sort((a, b) => {
            // 1. Sort by distance from user if location available (Nairobi coordinates as default for Kenya)
            const defaultLat = userLat || -1.2857; // Nairobi latitude
            const defaultLon = userLon || 36.8172;  // Nairobi longitude
            
            const aHasLoc = a.lat && a.lon;
            const bHasLoc = b.lat && b.lon;
            
            if (aHasLoc && bHasLoc) {
                const distA = calculateDistance(defaultLat, defaultLon, a.lat, a.lon);
                const distB = calculateDistance(defaultLat, defaultLon, b.lat, b.lon);
                if (distA !== distB) return distA - distB; // Nearest first
            }
            
            // 2. Prioritize airports with available flights
            if (availableCodes && availableCodes.size) {
                const aa = availableCodes.has(String(a.code).toUpperCase()) ? 0 : 1;
                const bb = availableCodes.has(String(b.code).toUpperCase()) ? 0 : 1;
                if (aa !== bb) return aa - bb;
            }
            
            // 3. If querying, prioritize code matches
            if (q) {
                const ac = (a.code||'').toLowerCase();
                const bc = (b.code||'').toLowerCase();
                const ap = ac.startsWith(q) ? 0 : 1;
                const bp = bc.startsWith(q) ? 0 : 1;
                if (ap !== bp) return ap - bp;
            }
            
            // 4. Alphabetically by city
            return (a.city||'').localeCompare(b.city||'');
        });
        
        return pool.slice(0, limit);
    }
    
    // Attach dropdown to an input
    function attachDropdown(selector) {
        const input = typeof selector === 'string' 
            ? document.querySelector(selector) 
            : selector;
        
        if (!input) return;
        
        // Create dropdown element
        const dropdown = document.createElement('div');
        dropdown.className = 'simple-airport-dropdown';
        dropdown.style.cssText = `
            position: absolute;
            left: 0;
            right: 0;
            top: 100%;
            margin-top: 4px;
            background: white;
            border: 1px solid #e6e9ef;
            border-radius: 12px;
            box-shadow: 0 10px 32px rgba(9, 30, 66, 0.18);
            max-height: 400px;
            overflow-y: auto;
            z-index: 99999;
            display: none;
        `;
        
        // Anchor dropdown to the nearest positioned ancestor (prefer the label)
        let wrapper = input.parentElement;
        if (wrapper) {
            const cs = window.getComputedStyle(wrapper);
            if (cs.position === 'static') {
                try { wrapper.style.position = 'relative'; } catch(e) {}
            }
            wrapper.appendChild(dropdown);
        } else {
            // Fallback: create a wrapper if no parent
            wrapper = document.createElement('div');
            wrapper.style.position = 'relative';
            wrapper.style.display = 'inline-block';
            wrapper.style.width = '100%';
            if (input.parentNode) {
                input.parentNode.insertBefore(wrapper, input);
                wrapper.appendChild(input);
            } else {
                document.body.appendChild(wrapper);
                wrapper.appendChild(input);
            }
            wrapper.appendChild(dropdown);
        }
        
        let selectedIndex = -1;
        let currentResults = [];
        let nearestAirport = null;
        let userLocation = null;
        
        // Get user location (optional)
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                pos => {
                    userLocation = {
                        lat: pos.coords.latitude,
                        lon: pos.coords.longitude
                    };
                    nearestAirport = findNearestAirport(userLocation.lat, userLocation.lon);
                },
                () => {}, // Silently fail if denied
                { maximumAge: 600000, timeout: 5000 }
            );
        }
        
        // Render dropdown items
        function render(airports) {
            currentResults = airports;
            selectedIndex = -1;
            
            if (!airports.length) {
                const hasQuery = !!(input.value && input.value.trim());
                dropdown.innerHTML = hasQuery
                    ? '<div style="padding:16px;text-align:center;color:#999;">No matches</div>'
                    : '<div style="padding:16px;text-align:center;color:#999;">Start typing to search airports</div>';
                return;
            }
            
            dropdown.innerHTML = '';
            
            airports.forEach((airport, index) => {
                const item = document.createElement('div');
                item.className = 'dropdown-item';
                item.setAttribute('data-index', index);
                item.setAttribute('data-code', airport.code || '');
                
                const isNearest = nearestAirport && airport.code === nearestAirport.code;
                
                item.style.cssText = `
                    padding: 14px 16px;
                    cursor: pointer;
                    display: flex;
                    gap: 12px;
                    align-items: center;
                    border-bottom: 1px solid #f5f7fa;
                    transition: background 0.15s ease;
                `;
                
                item.innerHTML = `
                    <div style="font-weight:700;color:#667eea;font-size:15px;min-width:50px;text-align:center;">
                        ${airport.code || ''}
                    </div>
                    <div style="flex:1;min-width:0;">
                        <div style="color:#222;font-weight:500;font-size:14px;">
                            ${airport.city || ''}, ${airport.country || ''}
                        </div>
                        <div style="color:#666;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                            ${airport.name || ''}
                        </div>
                    </div>
                    ${isNearest ? '<div style="background:#667eea;color:white;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:600;white-space:nowrap;">📍 Nearest</div>' : ''}
                `;
                
                // Hover effect
                item.addEventListener('mouseenter', () => {
                    item.style.background = '#f8fbff';
                    selectedIndex = index;
                    updateSelection();
                });
                
                item.addEventListener('mouseleave', () => {
                    item.style.background = '';
                });
                
                // Click to select
                item.addEventListener('mousedown', (e) => {
                    e.preventDefault(); // Prevent input blur
                    selectAirport(airport);
                });
                
                dropdown.appendChild(item);
            });
        }
        
        // Update selection highlight
        function updateSelection() {
            const items = dropdown.querySelectorAll('.dropdown-item');
            items.forEach((item, index) => {
                if (index === selectedIndex) {
                    item.style.background = '#e8f2ff';
                    item.style.borderLeft = '4px solid #667eea';
                    item.style.paddingLeft = '12px';
                } else {
                    item.style.background = '';
                    item.style.borderLeft = '';
                    item.style.paddingLeft = '16px';
                }
            });
        }
        
        // Select airport and close dropdown
        function selectAirport(airport) {
            const displayValue = airport.city 
                ? `${airport.city} (${airport.code})` 
                : airport.code;
            
            input.value = displayValue;
            input.dataset.iata = airport.code;
            input.dataset.selected = 'true';
            input.dataset.city = airport.city || '';
            input.dataset.name = airport.name || '';
            
            // Trigger change events
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            
            closeDropdown();
            
            // Auto-advance to next field
            autoAdvanceToNextField(input);
        }
        
        // Auto-advance to the next input field
        function autoAdvanceToNextField(currentInput) {
            const inputId = currentInput.id;
            let nextField = null;
            
            // Define the flow: from -> to -> departDate -> returnDate
            if (inputId === 'from') {
                nextField = document.getElementById('to');
            } else if (inputId === 'to') {
                nextField = document.getElementById('departDate') || document.getElementById('depart');
            } else if (inputId === 'departDate' || inputId === 'depart') {
                nextField = document.getElementById('returnDate') || document.getElementById('return');
            }
            
            // Focus the next field after a short delay
            if (nextField) {
                setTimeout(() => {
                    nextField.focus();
                    // For date pickers, trigger click to open calendar
                    if (nextField.type === 'text' && nextField.classList.contains('date-picker')) {
                        nextField.click();
                    }
                }, 200);
            }
        }
        
        // Show dropdown
        function showDropdown() {
            dropdown.style.display = 'block';
        }
        
        // Hide dropdown
        function closeDropdown() {
            dropdown.style.display = 'none';
            selectedIndex = -1;
        }
        
        // Handle input focus
        input.addEventListener('focus', async () => {
            await Promise.all([loadAirports(), loadAvailableCodes()]);
            const query = input.value.trim();
            const results = filterAirports(query, 50, userLocation?.lat, userLocation?.lon);
            render(results);
            showDropdown();
            loadAvailableCodes().then(()=>{ render(filterAirports(input.value.trim(), 50, userLocation?.lat, userLocation?.lon)); });
        });
        
        // Handle input typing
        input.addEventListener('input', async () => {
            await Promise.all([loadAirports(), loadAvailableCodes()]);
            const query = input.value.trim();
            const results = filterAirports(query, 50, userLocation?.lat, userLocation?.lon);
            render(results);
            showDropdown();
            
            // Clear selection flag when user types
            if (query !== input.dataset.lastSelected) {
                delete input.dataset.selected;
            }
        });
        
        // Handle keyboard navigation
        input.addEventListener('keydown', (e) => {
            if (dropdown.style.display === 'none') return;
            
            const items = dropdown.querySelectorAll('.dropdown-item');
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIndex = Math.min(currentResults.length - 1, selectedIndex + 1);
                updateSelection();
                items[selectedIndex]?.scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIndex = Math.max(0, selectedIndex - 1);
                updateSelection();
                items[selectedIndex]?.scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'Enter') {
                e.preventDefault();
                if (selectedIndex >= 0 && currentResults[selectedIndex]) {
                    selectAirport(currentResults[selectedIndex]);
                }
            } else if (e.key === 'Escape') {
                closeDropdown();
                input.blur();
            }
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) {
                closeDropdown();
            }
        });
    }
    
    // Public API
    window.SimpleAirportDropdown = {
        attach: attachDropdown,
        loadAirports: loadAirports
    };
    
})(window);
