// Airport Dropdown Manager
class AirportDropdown {
    constructor() {
        this.airports = null;
        this.activeInput = null;
        this.debounceTimer = null;
        this.currentDropdown = null;
        this.highlightedIndex = -1;
    }

    async loadAirports() {
        if (this.airports) return this.airports;
        
        const fallbackAirports = [
            { name: 'Jomo Kenyatta Intl', city: 'Nairobi', country: 'Kenya', iata: 'NBO' },
            { name: 'Moi Intl', city: 'Mombasa', country: 'Kenya', iata: 'MBA' },
            { name: 'Kisumu Intl', city: 'Kisumu', country: 'Kenya', iata: 'KIS' },
            { name: 'Eldoret Intl', city: 'Eldoret', country: 'Kenya', iata: 'EDL' },
            { name: 'Wilson', city: 'Nairobi', country: 'Kenya', iata: 'WIL' },
            { name: 'Heathrow', city: 'London', country: 'United Kingdom', iata: 'LHR' },
            { name: 'Gatwick', city: 'London', country: 'United Kingdom', iata: 'LGW' },
            { name: 'John F. Kennedy', city: 'New York', country: 'USA', iata: 'JFK' },
            { name: 'Dubai Intl', city: 'Dubai', country: 'UAE', iata: 'DXB' },
            { name: 'Doha Hamad', city: 'Doha', country: 'Qatar', iata: 'DOH' },
            { name: 'O.R. Tambo', city: 'Johannesburg', country: 'South Africa', iata: 'JNB' },
            { name: 'Kilimanjaro', city: 'Arusha', country: 'Tanzania', iata: 'JRO' },
            { name: 'Cape Town', city: 'Cape Town', country: 'South Africa', iata: 'CPT' },
            { name: 'Entebbe', city: 'Kampala', country: 'Uganda', iata: 'EBB' }
        ];
        
        try {
            const response = await fetch('/assets/data/airports.json');
            if (!response.ok) throw new Error('Failed to load airports');
            const data = await response.json();
            
            this.airports = (Array.isArray(data) ? data : [])
                .map(airport => ({
                    name: airport.name || airport.airport || '',
                    city: airport.city || '',
                    country: airport.country || '',
                    iata: (airport.iata || airport.code || '').toUpperCase()
                }))
                .filter(airport => airport.iata && (airport.name || airport.city));
                
            if (this.airports.length === 0) {
                console.warn('⚠️ Airport list empty from API, using fallback');
                this.airports = fallbackAirports;
            }
            return this.airports;
        } catch (error) {
            console.error('Error loading airports:', error);
            this.airports = fallbackAirports;
            return this.airports;
        }
    }

    filterAirports(query) {
        if (!this.airports || this.airports.length === 0) return [];
        
        const q = (query || '').toLowerCase().trim();
        if (!q) return this.airports.slice(0, 20);
        
        // Prioritize IATA codes, then cities, then names
        const byCode = this.airports.filter(a => 
            (a.iata || '').toLowerCase().startsWith(q)
        );
        
        const byCity = this.airports.filter(a => 
            (a.city || '').toLowerCase().includes(q) && !byCode.includes(a)
        );
        
        const byName = this.airports.filter(a => 
            (a.name || '').toLowerCase().includes(q) && !byCode.includes(a) && !byCity.includes(a)
        );
        
        return byCode.concat(byCity).concat(byName).slice(0, 50);
    }

    positionDropdown(inputId) {
        const inputEl = document.getElementById(inputId);
        const dropdownEl = document.getElementById(`dropdown-${inputId}`);
        
        if (!inputEl || !dropdownEl) return;
        
        const rect = inputEl.getBoundingClientRect();
        dropdownEl.style.position = 'absolute';
        dropdownEl.style.top = (rect.bottom + window.scrollY + 8) + 'px';
        dropdownEl.style.left = (rect.left + window.scrollX) + 'px';
        dropdownEl.style.width = rect.width + 'px';
    }

    createDropdownElement(inputId) {
        // Check if dropdown already exists
        let dropdownEl = document.getElementById(`dropdown-${inputId}`);
        if (dropdownEl) return dropdownEl;
        
        // Create new dropdown at body level
        dropdownEl = document.createElement('div');
        dropdownEl.id = `dropdown-${inputId}`;
        dropdownEl.className = 'dropdown-menu';
        dropdownEl.role = 'listbox';
        dropdownEl.setAttribute('data-input', inputId);
        
        // Explicitly enable pointer events
        dropdownEl.style.pointerEvents = 'auto';
        dropdownEl.style.cursor = 'pointer';
        
        // Add click logger for debugging
        dropdownEl.addEventListener('click', (e) => {
            console.log('🖱️ Dropdown clicked!', {
                target: e.target,
                inputId: inputId,
                classList: e.target.classList.toString()
            });
        });
        
        document.body.appendChild(dropdownEl);
        console.log(`✅ Dropdown created for ${inputId} and appended to body`);
        return dropdownEl;
    }

    renderDropdown(filteredAirports, inputId) {
        const dropdownEl = this.createDropdownElement(inputId);
        dropdownEl.innerHTML = '';
        this.highlightedIndex = -1;
        
        if (!filteredAirports || filteredAirports.length === 0) {
            dropdownEl.classList.remove('visible');
            return;
        }
        
        console.log(`📋 Rendering ${filteredAirports.length} airports for ${inputId}`);
        
        // Store the airports data in the dropdown element for event delegation
        dropdownEl.dataset.airports = JSON.stringify(filteredAirports);
        dropdownEl.dataset.inputId = inputId;
        
        filteredAirports.forEach((airport, index) => {
            const item = document.createElement('div');
            item.className = 'dropdown-item';
            item.setAttribute('role', 'option');
            item.setAttribute('data-index', index);
            item.setAttribute('data-iata', airport.iata);
            item.setAttribute('data-airport-json', JSON.stringify(airport));
            
            // Add inline click handler as backup
            item.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log(`✈️ CLICKED: ${airport.iata} for ${inputId}`);
                this.selectAirport(airport, inputId);
            };
            
            item.innerHTML = `
                <div class="airport-info">
                    <div class="airport-name">${airport.name}</div>
                    <div class="airport-meta">${airport.city}${airport.country ? ', ' + airport.country : ''}</div>
                </div>
                <div class="airport-code">${airport.iata}</div>
            `;
            
            dropdownEl.appendChild(item);
        });
        
        this.positionDropdown(inputId);
        dropdownEl.classList.add('visible');
        this.currentDropdown = inputId;
        console.log(`✅ Dropdown visible at body level`);
    }

    highlightItem(index) {
        const dropdownEl2 = document.getElementById(`dropdown-${this.currentDropdown}`);
        if (!dropdownEl2) return;
        
        const items = dropdownEl2.querySelectorAll('.dropdown-item');
        items.forEach(item => item.classList.remove('active'));
        
        if (index >= 0 && index < items.length) {
            items[index].classList.add('active');
            items[index].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            this.highlightedIndex = index;
        }
    }

    selectHighlightedAirport() {
        if (this.highlightedIndex < 0) return false;
        
        const dropdownEl3 = document.getElementById(`dropdown-${this.currentDropdown}`);
        if (!dropdownEl3) return false;
        
        const items = dropdownEl3.querySelectorAll('.dropdown-item');
        const item = items[this.highlightedIndex];
        
        if (item) {
            const airportJson = item.getAttribute('data-airport-json');
            if (airportJson) {
                const airport = JSON.parse(airportJson);
                this.selectAirport(airport, this.currentDropdown);
                return true;
            }
        }
        return false;
    }

    selectAirport(airport, inputId) {
        console.log(`🎯 selectAirport called: ${airport.iata} for ${inputId}`);
        
        const inputEl = document.getElementById(inputId);
        if (!inputEl) {
            console.error(`❌ Input not found: ${inputId}`);
            return;
        }
        
        // Set the value and store in data-code attribute
        inputEl.value = `${airport.city} (${airport.iata})`;
        inputEl.dataset.selected = 'true';
        inputEl.dataset.code = airport.iata;
        inputEl.dataset.city = airport.city;
        inputEl.dataset.name = airport.name;
        
        console.log(`✅ Value set: ${inputEl.value}`);
        
        // Close dropdown
        this.closeDropdown(inputId);
        
        // Handle flow: From → To → Dates
        if (inputId === 'fromInput') {
            const toInput = document.getElementById('toInput');
            if (toInput) {
                toInput.disabled = false;
                console.log(`➡️ Focusing "To" field`);
                setTimeout(() => {
                    toInput.focus();
                    toInput.select();
                }, 150);
            }
        } else if (inputId === 'toInput') {
            // After selecting "To", check if both are selected and reveal dates
            console.log(`📅 Revealing date fields`);
            setTimeout(() => {
                this.checkAndShowDateFields();
                // Focus on departure date after dates are revealed
                const departDate = document.getElementById('departDate');
                if (departDate) {
                    setTimeout(() => departDate.focus(), 300);
                }
            }, 150);
        }
    }

    closeDropdown(inputId) {
        const dropdownEl4 = document.getElementById(`dropdown-${inputId}`);
        if (dropdownEl4) {
            dropdownEl4.classList.remove('visible');
            // Remove from DOM after transition
            setTimeout(() => {
                if (dropdownEl4 && dropdownEl4.parentNode) {
                    dropdownEl4.remove();
                }
            }, 300);
        }
        this.highlightedIndex = -1;
    }

    checkAndShowDateFields() {
        const fromInput = document.getElementById('fromInput');
        const toInput = document.getElementById('toInput');
        const datesRow = document.getElementById('datesRow');
        const returnDateGroup = document.getElementById('returnDateGroup');
        const tripType = document.getElementById('tripType');
        
        const fromSelected = fromInput && fromInput.dataset.selected === 'true';
        const toSelected = toInput && toInput.dataset.selected === 'true';
        
        // Only show dates when BOTH airports are selected
        if (fromSelected && toSelected) {
            // Smooth reveal with CSS transition
            datesRow.style.display = 'grid';
            setTimeout(() => {
                datesRow.classList.add('visible');
            }, 10);
            
            // Show/hide return date based on trip type
            if (tripType && tripType.value === 'oneway') {
                returnDateGroup.style.display = 'none';
            } else {
                returnDateGroup.style.display = 'block';
            }
        } else {
            // Hide dates if either airport is not selected
            datesRow.classList.remove('visible');
            setTimeout(() => {
                if (!fromSelected || !toSelected) {
                    datesRow.style.display = 'none';
                }
            }, 300);
        }
    }

    attachAutocomplete(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.addEventListener('focus', async () => {
            this.activeInput = input;
            this.currentDropdown = inputId;
            
            // Clear previous selection when focusing
            if (input.dataset.selected === 'true') {
                input.value = '';
                input.dataset.selected = 'false';
                delete input.dataset.code;
            }
            
            await this.loadAirports();
            const filtered = this.filterAirports(input.value);
            this.renderDropdown(filtered, inputId);
        });
        
        input.addEventListener('input', async () => {
            this.activeInput = input;
            this.currentDropdown = inputId;
            input.dataset.selected = 'false';
            
            await this.loadAirports();
            
            clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                const filtered = this.filterAirports(input.value);
                this.renderDropdown(filtered, inputId);
            }, 150);
        });
        
        input.addEventListener('blur', () => {
            setTimeout(() => {
                this.closeDropdown(inputId);
            }, 200);
        });
        
        input.addEventListener('keydown', (e) => {
            const dropdownEl5 = document.getElementById(`dropdown-${inputId}`);
            if (!dropdownEl5 || !dropdownEl5.classList.contains('visible')) {
                return;
            }
            
            const items = dropdownEl5.querySelectorAll('.dropdown-item');
            
            switch(e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    this.highlightedIndex = Math.min(this.highlightedIndex + 1, items.length - 1);
                    this.highlightItem(this.highlightedIndex);
                    break;
                    
                case 'ArrowUp':
                    e.preventDefault();
                    this.highlightedIndex = Math.max(this.highlightedIndex - 1, 0);
                    this.highlightItem(this.highlightedIndex);
                    break;
                    
                case 'Enter':
                    e.preventDefault();
                    if (this.selectHighlightedAirport()) {
                        // Successfully selected
                    } else if (items.length > 0) {
                        // Select first item if none highlighted
                        const firstItem = items[0];
                        const airportJson = firstItem.getAttribute('data-airport-json');
                        if (airportJson) {
                            const airport = JSON.parse(airportJson);
                            this.selectAirport(airport, inputId);
                        }
                    }
                    break;
                    
                case 'Escape':
                    e.preventDefault();
                    this.closeDropdown(inputId);
                    input.blur();
                    break;
            }
        });
    }
}

// Initialize
const airportDropdown = new AirportDropdown();

document.addEventListener('DOMContentLoaded', () => {
    // Attach airport autocomplete
    airportDropdown.attachAutocomplete('fromInput');
    airportDropdown.attachAutocomplete('toInput');
    
    // Swap button
    const swapBtn = document.getElementById('swapBtn');
    if (swapBtn) {
        swapBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const fromInput = document.getElementById('fromInput');
            const toInput = document.getElementById('toInput');
            
            if (fromInput.value && toInput.value) {
                // Swap values
                [fromInput.value, toInput.value] = [toInput.value, fromInput.value];
                [fromInput.dataset.selected, toInput.dataset.selected] = [toInput.dataset.selected, fromInput.dataset.selected];
                [fromInput.dataset.city, toInput.dataset.city] = [toInput.dataset.city, fromInput.dataset.city];
                [fromInput.dataset.name, toInput.dataset.name] = [toInput.dataset.name, fromInput.dataset.name];
            }
        });
    }
    
    // Trip type change
    const tripType = document.getElementById('tripType');
    if (tripType) {
        tripType.addEventListener('change', () => {
            airportDropdown.checkAndShowDateFields();
        });
    }
    
    // Search form
    const searchForm = document.getElementById('flightSearchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const fromInput = document.getElementById('fromInput');
            const toInput = document.getElementById('toInput');
            const departDate = document.getElementById('departDate');
            const returnDate = document.getElementById('returnDate');
            const tripType = document.getElementById('tripType');
            
            if (!fromInput.dataset.code || !toInput.dataset.code) {
                alert('Please select both departure and arrival airports');
                return;
            }
            
            if (!departDate.value) {
                alert('Please select a departure date');
                return;
            }
            
            if (tripType.value === 'return' && !returnDate.value) {
                alert('Please select a return date for round trip');
                return;
            }
            
            // Build query parameters
            const params = new URLSearchParams({
                from: fromInput.dataset.code,
                fromCity: fromInput.dataset.city,
                to: toInput.dataset.code,
                toCity: toInput.dataset.city,
                departDate: departDate.value,
                tripType: tripType.value
            });
            
            if (tripType.value === 'return' && returnDate.value) {
                params.append('returnDate', returnDate.value);
            }
            
            console.log('🔍 Redirecting to availability page with params:', params.toString());
            
            // Redirect to availability page
            window.location.href = `/availability.html?${params.toString()}`;
        });
    }
    
    // Close dropdowns when clicking outside and handle dropdown item clicks
    document.addEventListener('click', (e) => {
        console.log('🖱️ Click detected:', e.target.className);
        
        const isInput = e.target.closest('.input-wrapper');
        const isDropdown = e.target.closest('.dropdown-menu');
        const isDropdownItem = e.target.closest('.dropdown-item');
        
        // Handle dropdown item clicks with event delegation
        if (isDropdownItem && isDropdown) {
            console.log('✅ Dropdown item click detected via delegation');
            e.preventDefault();
            e.stopPropagation();
            
            const inputId = isDropdown.getAttribute('data-input');
            const airportJson = isDropdownItem.getAttribute('data-airport-json');
            
            console.log(`Input ID: ${inputId}, Has JSON: ${!!airportJson}`);
            
            if (airportJson && inputId) {
                try {
                    const airport = JSON.parse(airportJson);
                    console.log(`Parsed airport: ${airport.iata}`);
                    airportDropdown.selectAirport(airport, inputId);
                } catch (error) {
                    console.error('Error parsing airport JSON:', error);
                }
            }
            return;
        }
        
        // Close dropdowns when clicking outside
        if (!isInput && !isDropdown) {
            document.querySelectorAll('.dropdown-menu.visible').forEach(dropdown => {
                const inputId = dropdown.getAttribute('data-input');
                airportDropdown.closeDropdown(inputId);
            });
        }
    });
    
    // Handle mouseenter for hover highlighting
    document.addEventListener('mouseenter', (e) => {
        const dropdownItem = e.target.closest('.dropdown-item');
        if (dropdownItem) {
            const dropdown = dropdownItem.closest('.dropdown-menu');
            if (dropdown) {
                const index = parseInt(dropdownItem.getAttribute('data-index'));
                airportDropdown.highlightedIndex = index;
                dropdown.querySelectorAll('.dropdown-item').forEach(item => {
                    item.classList.remove('active');
                });
                dropdownItem.classList.add('active');
            }
        }
    }, true);
});
