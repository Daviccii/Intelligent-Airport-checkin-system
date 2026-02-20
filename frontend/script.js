// Airport Dropdown Manager
class AirportDropdown {
    constructor() {
        this.airports = null;
        this.activeInput = null;
        this.debounceTimer = null;
        this.currentDropdown = null;
        this.highlightedIndex = -1;
        this.isPointerDownOnDropdown = false;
        this.modalEl = null;
        this.backdropEl = null;
        this.searchEl = null;
        this.listEl = null;
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
        if (!q) {
            const priorityCountries = ['Kenya', 'Uganda', 'Tanzania', 'Rwanda', 'Ethiopia', 'South Africa'];
            const priorityCities = ['Nairobi', 'Mombasa', 'Kisumu', 'Eldoret'];
            const priority = this.airports.filter(a =>
                priorityCountries.includes(a.country) || priorityCities.includes(a.city)
            );
            const rest = this.airports.filter(a => !priority.includes(a));
            return priority.concat(rest).slice(0, 30);
        }
        
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

    initModal() {
        if (this.modalEl) return;

        this.modalEl = document.getElementById('airportModal');
        this.backdropEl = document.getElementById('airportBackdrop');
        this.searchEl = document.getElementById('airportSearch');
        this.listEl = document.getElementById('airportList');

        if (!this.modalEl || !this.backdropEl || !this.searchEl || !this.listEl) {
            return;
        }

        this.backdropEl.addEventListener('click', () => this.closeModal());
        this.modalEl.addEventListener('click', (e) => e.stopPropagation());

        this.searchEl.addEventListener('input', async () => {
            await this.loadAirports();
            const filtered = this.filterAirports(this.searchEl.value);
            this.renderDropdown(filtered, this.currentDropdown);
        });

        this.searchEl.addEventListener('keydown', (e) => {
            const items = this.listEl.querySelectorAll('.airport-item');
            if (!items.length) return;

            switch (e.key) {
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
                        return;
                    }
                    break;
                case 'Escape':
                    e.preventDefault();
                    this.closeModal();
                    break;
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    async openModal(inputId) {
        this.initModal();

        const inputEl = document.getElementById(inputId);
        if (!inputEl || !this.modalEl || !this.backdropEl || !this.searchEl || !this.listEl) {
            return;
        }

        this.activeInput = inputEl;
        this.currentDropdown = inputId;

        await this.loadAirports();
        this.searchEl.value = '';
        const filtered = this.filterAirports('');
        this.renderDropdown(filtered, inputId);

        const rect = inputEl.getBoundingClientRect();
        const row = inputEl.closest('.kq-form-row');
        const rowRect = row ? row.getBoundingClientRect() : rect;

        const minWidth = 420;
        const maxWidth = 520;
        const width = Math.min(Math.max(rowRect.width, minWidth), maxWidth);

        let left = rect.left;
        if (left + width > window.innerWidth - 16) {
            left = window.innerWidth - width - 16;
        }
        if (left < 16) {
            left = 16;
        }

        this.modalEl.style.width = `${width}px`;
        this.modalEl.style.left = `${left}px`;
        this.modalEl.style.top = `${rect.bottom + 10}px`;
        this.modalEl.style.transform = 'none';

        this.modalEl.style.display = 'block';
        this.backdropEl.style.display = 'block';
        this.modalEl.setAttribute('aria-hidden', 'false');

        setTimeout(() => this.searchEl.focus(), 0);
    }

    closeModal() {
        if (!this.modalEl || !this.backdropEl) return;
        this.modalEl.style.display = 'none';
        this.backdropEl.style.display = 'none';
        this.modalEl.setAttribute('aria-hidden', 'true');
        this.highlightedIndex = -1;
    }

    positionDropdown(inputId) {
        const inputEl = document.getElementById(inputId);
        const dropdownEl = document.getElementById(`dropdown-${inputId}`);
        
        if (!inputEl || !dropdownEl) return;
        
        const rect = inputEl.getBoundingClientRect();
        dropdownEl.style.position = 'absolute';
        dropdownEl.style.top = (rect.bottom + window.scrollY + 8) + 'px';
        dropdownEl.style.left = (rect.left + window.scrollX) + 'px';
        const minWidth = 420;
        dropdownEl.style.width = Math.max(rect.width, minWidth) + 'px';
    }

    createDropdownElement(inputId) {
        // Check if dropdown already exists
        let dropdownEl = document.getElementById(`dropdown-${inputId}`);
        if (dropdownEl) return dropdownEl;
        
        // Create new dropdown at body level
        dropdownEl = document.createElement('div');
        dropdownEl.id = `dropdown-${inputId}`;
        dropdownEl.className = 'dropdown-menu autocomplete-dropdown';
        dropdownEl.role = 'listbox';
        dropdownEl.setAttribute('data-input', inputId);
        
        // Explicitly enable pointer events
        dropdownEl.style.pointerEvents = 'auto';
        dropdownEl.style.cursor = 'pointer';
        
        // Add click logger for debugging
        dropdownEl.addEventListener('click', (e) => {
            console.log('Dropdown clicked');
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
        if (!this.listEl) return;

        this.listEl.innerHTML = '';
        this.highlightedIndex = -1;

        if (!filteredAirports || filteredAirports.length === 0) {
            this.listEl.innerHTML = '<li class="no-results">No airports found</li>';
            return;
        }

        console.log(`📋 Rendering ${filteredAirports.length} airports for ${inputId}`);

        this.listEl.dataset.airports = JSON.stringify(filteredAirports);

        filteredAirports.forEach((airport, index) => {
            const item = document.createElement('li');
            item.className = 'airport-item';
            item.setAttribute('role', 'option');
            item.setAttribute('data-index', index);
            item.setAttribute('data-iata', airport.iata);
            item.setAttribute('data-airport-json', JSON.stringify(airport));

            item.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.selectAirport(airport, inputId);
            };

            item.onmousedown = (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.selectAirport(airport, inputId);
            };

            item.innerHTML = `
                <div class="airport-info">
                    <div class="airport-name">${airport.name}</div>
                    <div class="airport-meta">${airport.city}${airport.country ? ', ' + airport.country : ''}</div>
                </div>
                <div class="airport-code">${airport.iata}</div>
            `;

            this.listEl.appendChild(item);
        });

        this.currentDropdown = inputId;
    }

    highlightItem(index) {
        if (!this.listEl) return;

        const items = this.listEl.querySelectorAll('.airport-item');
        items.forEach(item => item.classList.remove('active'));

        if (index >= 0 && index < items.length) {
            items[index].classList.add('active');
            items[index].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            this.highlightedIndex = index;
        }
    }

    selectHighlightedAirport() {
        if (this.highlightedIndex < 0 || !this.listEl || !this.currentDropdown) return false;

        const items = this.listEl.querySelectorAll('.airport-item');
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
        
        if (this.listEl) {
            this.listEl.innerHTML = '';
        }

        this.closeModal();
        
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
            // After selecting "To", check if both are selected and reveal calendar
            console.log(`📅 Revealing calendar`);
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

    closeDropdown() {
        this.closeModal();
    }

    checkAndShowDateFields() {
        const fromInput = document.getElementById('fromInput');
        const toInput = document.getElementById('toInput');
        const departDateField = document.getElementById('departDateField');
        const returnDateField = document.getElementById('returnDateField');
        const datePickerWrapper = document.getElementById('datePickerWrapper');
        const tripType = document.getElementById('tripType');
        
        const fromSelected = fromInput && fromInput.dataset.selected === 'true';
        const toSelected = toInput && toInput.dataset.selected === 'true';
        
        // Only show dates when BOTH airports are selected
        if (fromSelected && toSelected) {
            if (departDateField) {
                departDateField.style.display = 'flex';
            }
            if (returnDateField) {
                const isReturnTrip = tripType && (tripType.value === 'return' || tripType.value === 'roundtrip');
                returnDateField.style.display = isReturnTrip ? 'flex' : 'none';
            }
            if (datePickerWrapper) {
                datePickerWrapper.style.display = 'block';
            }
        } else {
            // Hide dates if either airport is not selected
            if (departDateField) {
                departDateField.style.display = 'none';
            }
            if (returnDateField) {
                returnDateField.style.display = 'none';
            }
            if (datePickerWrapper) {
                datePickerWrapper.style.display = 'none';
            }
        }
    }

    attachAutocomplete(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.addEventListener('focus', async () => {
            if (input.dataset.selected === 'true') {
                input.value = '';
                input.dataset.selected = 'false';
                delete input.dataset.code;
            }
            await this.openModal(inputId);
        });

        input.addEventListener('click', async () => {
            await this.openModal(inputId);
        });

        input.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter' || e.key === 'ArrowDown') {
                e.preventDefault();
                await this.openModal(inputId);
            }
        });
    }
}

// Initialize
const airportDropdown = new AirportDropdown();

document.addEventListener('DOMContentLoaded', () => {
    // Header mega-menu: open only on click
    const megaParents = Array.from(document.querySelectorAll('.nav-menu .mega-parent'));
    megaParents.forEach(parent => {
        const link = parent.querySelector('a');
        if (!link) return;

        link.addEventListener('click', (event) => {
            const isOpen = parent.classList.contains('open');
            megaParents.forEach(p => p.classList.remove('open'));

            if (!isOpen) {
                event.preventDefault();
                parent.classList.add('open');
            }
        });
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.nav-menu')) {
            megaParents.forEach(p => p.classList.remove('open'));
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            megaParents.forEach(p => p.classList.remove('open'));
        }
    });

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
            
            if ((tripType.value === 'return' || tripType.value === 'roundtrip') && !returnDate.value) {
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
            
            if ((tripType.value === 'return' || tripType.value === 'roundtrip') && returnDate.value) {
                params.append('returnDate', returnDate.value);
            }
            
            console.log('🔍 Redirecting to availability page with params:', params.toString());
            
            // Redirect to availability page
            window.location.href = `/availability.html?${params.toString()}`;
        });
    }
    
    airportDropdown.initModal();
    
    // ========== CALENDAR FUNCTIONALITY ==========
    
    // Calendar state
    let currentMonthOffset = 0; // 0 = current month, 1 = next month
    let selectedDepartDate = null;
    let selectedReturnDate = null;
    
    // Get month data with prices
    function getCurrentMonthData(monthOffset) {
        const now = new Date();
        const targetDate = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1);
        const year = targetDate.getFullYear();
        const month = targetDate.getMonth();
        const monthName = targetDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        
        // Generate sample prices for the month
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const prices = {};
        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            prices[dateStr] = Math.floor(Math.random() * 200) + 100;
        }
        
        return { year, month, monthName, prices };
    }
    
    // Generate calendar with prices
    function generateCalendar(containerId, prices) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        const dates = Object.keys(prices).sort();
        if (dates.length === 0) return;
        
        // Find cheapest price
        const minPrice = Math.min(...Object.values(prices));

        const today = new Date();
        today.setHours(0,0,0,0);

        dates.forEach(dateStr => {
            const price = prices[dateStr];
            const dateObj = new Date(dateStr);
            dateObj.setHours(0,0,0,0);
            const day = dateObj.getDate();

            const dayCell = document.createElement('div');
            dayCell.className = 'calendar-day';
            dayCell.dataset.date = dateStr;

            if (price === minPrice) {
                dayCell.classList.add('cheapest');
            }

            // Disable past dates
            if (dateObj < today) {
                dayCell.classList.add('disabled');
                dayCell.title = 'Past dates cannot be selected';
            } else {
                // Add click handler for date selection
                dayCell.addEventListener('click', function() {
                    selectCalendarDate(dateStr);
                });
            }

            dayCell.innerHTML = `
                <div class="calendar-date">${day}</div>
                <div class="calendar-price">KES ${price.toLocaleString()}</div>
            `;

            container.appendChild(dayCell);
        });
    }
    
    // Handle calendar date selection
    function selectCalendarDate(dateStr) {
        const departInput = document.getElementById('departDate');
        const returnInput = document.getElementById('returnDate');
        const departLabel = document.getElementById('selectedDepartLabel');
        const returnLabel = document.getElementById('selectedReturnLabel');
        const tripTypeBtn = document.querySelector('#tripTypeDropdown .kq-dropdown-btn');
        const isOneWay = tripTypeBtn && tripTypeBtn.textContent.trim().includes('One Way');
        
        // Determine if selecting depart or return date
        if (!selectedDepartDate || (selectedDepartDate && selectedReturnDate)) {
            // First selection or reset - set depart date
            selectedDepartDate = dateStr;
            selectedReturnDate = null;
            departInput.value = dateStr;
            returnInput.value = '';
            
            // Update labels
            const dateObj = new Date(dateStr);
            departLabel.textContent = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            returnLabel.textContent = '';
            
            // Highlight selected depart date
            document.querySelectorAll('.calendar-day').forEach(cell => {
                cell.classList.remove('selected-depart', 'selected-return');
                if (cell.dataset.date === dateStr) {
                    cell.classList.add('selected-depart');
                }
            });
            
            // If one-way, we're done
            if (isOneWay) {
                selectedReturnDate = null;
            }
        } else if (selectedDepartDate && !selectedReturnDate) {
            // Second selection - set return date
            const departTime = new Date(selectedDepartDate).getTime();
            const returnTime = new Date(dateStr).getTime();
            
            if (returnTime < departTime) {
                // Return date before depart date - swap them
                selectedReturnDate = selectedDepartDate;
                selectedDepartDate = dateStr;
                departInput.value = dateStr;
                returnInput.value = selectedReturnDate;
                
                // Update labels
                const departObj = new Date(dateStr);
                const returnObj = new Date(selectedReturnDate);
                departLabel.textContent = departObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                returnLabel.textContent = returnObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            } else {
                selectedReturnDate = dateStr;
                returnInput.value = dateStr;
                
                // Update label
                const returnObj = new Date(dateStr);
                returnLabel.textContent = returnObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            }
            
            // Highlight both dates
            document.querySelectorAll('.calendar-day').forEach(cell => {
                cell.classList.remove('selected-depart', 'selected-return');
                if (cell.dataset.date === selectedDepartDate) {
                    cell.classList.add('selected-depart');
                }
                if (cell.dataset.date === selectedReturnDate) {
                    cell.classList.add('selected-return');
                }
            });
        }
    }
    
    // Update both calendars
    function updateCalendars() {
        const leftData = getCurrentMonthData(currentMonthOffset);
        const rightData = getCurrentMonthData(currentMonthOffset + 1);
        
        // Update month labels
        const monthLeftEl = document.getElementById('monthLeft');
        const monthRightEl = document.getElementById('monthRight');
        if (monthLeftEl) monthLeftEl.textContent = leftData.monthName;
        if (monthRightEl) monthRightEl.textContent = rightData.monthName;
        
        // Clear and regenerate calendars
        const calendarLeft = document.getElementById('calendarLeft');
        const calendarRight = document.getElementById('calendarRight');
        if (calendarLeft) calendarLeft.innerHTML = '';
        if (calendarRight) calendarRight.innerHTML = '';
        
        generateCalendar('calendarLeft', leftData.prices);
        generateCalendar('calendarRight', rightData.prices);
        
        // Restore selections
        if (selectedDepartDate || selectedReturnDate) {
            document.querySelectorAll('.calendar-day').forEach(cell => {
                if (cell.dataset.date === selectedDepartDate) {
                    cell.classList.add('selected-depart');
                }
                if (cell.dataset.date === selectedReturnDate) {
                    cell.classList.add('selected-return');
                }
            });
        }
    }
    
    // Initialize calendars
    updateCalendars();
    
    // Month navigation
    const prevBtn = document.getElementById('prevMonth');
    const nextBtn = document.getElementById('nextMonth');
    
    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
            if (currentMonthOffset > 0) {
                currentMonthOffset--;
                updateCalendars();
            }
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            currentMonthOffset++;
            updateCalendars();
        });
    }
    
    // Done button
    const doneBtn = document.querySelector('.kq-done-btn');
    if (doneBtn) {
        doneBtn.addEventListener('click', function() {
            const departInput = document.getElementById('departDate');
            const tripTypeBtn = document.querySelector('#tripTypeDropdown .kq-dropdown-btn');
            const isOneWay = tripTypeBtn && tripTypeBtn.textContent.trim().includes('One Way');
            
            // Validate: must have depart date
            if (!departInput.value) {
                alert('Please select a departure date');
                return;
            }
            
            // For return trips, must have return date
            const returnInput = document.getElementById('returnDate');
            if (!isOneWay && !returnInput.value) {
                alert('Please select a return date');
                return;
            }
            
            // Hide calendar
            const datePickerWrapper = document.getElementById('datePickerWrapper');
            if (datePickerWrapper) {
                datePickerWrapper.style.display = 'none';
            }
            
            // Trigger search
            const searchForm = document.getElementById('flightSearchForm');
            if (searchForm) {
                searchForm.dispatchEvent(new Event('submit'));
            }
        });
    }
});
