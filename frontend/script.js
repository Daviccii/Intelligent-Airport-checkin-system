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
    console.log('DOM Content Loaded - Initializing dropdowns...');
    
    // ========== BOOKING WIDGET DROPDOWN FUNCTIONALITY ==========
    
    // Initialize all dropdowns in the booking widget
    function initBookingWidgetDropdowns() {
        console.log('Setting up dropdowns...');
        
        // Trip type dropdown
        const tripTypeDropdown = document.getElementById('tripTypeDropdown');
        console.log('Trip type dropdown found:', !!tripTypeDropdown);
        if (tripTypeDropdown) {
            const dropdownBtn = tripTypeDropdown.querySelector('.dropdown-btn-compact');
            const dropdownMenu = tripTypeDropdown.querySelector('.dropdown-menu-compact');
            const hiddenInput = document.getElementById('tripType');
            const valueDisplay = dropdownBtn.querySelector('.dropdown-value');
            
            console.log('Trip type elements:', { dropdownBtn: !!dropdownBtn, dropdownMenu: !!dropdownMenu, hiddenInput: !!hiddenInput });
            
            if (dropdownBtn && dropdownMenu) {
                dropdownBtn.addEventListener('click', (e) => {
                    console.log('Trip type dropdown clicked');
                    e.stopPropagation();
                    closeAllDropdowns(tripTypeDropdown);
                    dropdownBtn.classList.toggle('active');
                    dropdownMenu.classList.toggle('show');
                    console.log('Dropdown classes:', dropdownBtn.classList.toString(), dropdownMenu.classList.toString());
                });
                
                // Handle option selection
                const options = dropdownMenu.querySelectorAll('li');
                options.forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const value = option.dataset.value;
                        const display = option.textContent;
                        
                        valueDisplay.textContent = display;
                        if (hiddenInput) hiddenInput.value = value;
                        
                        dropdownBtn.classList.remove('active');
                        dropdownMenu.classList.remove('show');
                        
                        // Handle return date visibility based on trip type
                        updateReturnDateVisibility(value);
                    });
                });
            }
        }
        
        // From airport dropdown - click handler only (options loaded dynamically)
        const fromDropdown = document.getElementById('fromDropdown');
        if (fromDropdown) {
            const dropdownBtn = fromDropdown.querySelector('.dropdown-btn-compact');
            const dropdownMenu = fromDropdown.querySelector('.dropdown-menu-compact');
            
            if (dropdownBtn && dropdownMenu) {
                dropdownBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeAllDropdowns(fromDropdown);
                    dropdownBtn.classList.toggle('active');
                    dropdownMenu.classList.toggle('show');
                });
            }
        }
        
        // To airport dropdown - click handler only (options loaded dynamically)
        const toDropdown = document.getElementById('toDropdown');
        if (toDropdown) {
            const dropdownBtn = toDropdown.querySelector('.dropdown-btn-compact');
            const dropdownMenu = toDropdown.querySelector('.dropdown-menu-compact');
            
            if (dropdownBtn && dropdownMenu) {
                dropdownBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeAllDropdowns(toDropdown);
                    dropdownBtn.classList.toggle('active');
                    dropdownMenu.classList.toggle('show');
                });
            }
        }
        
        // Departure date dropdown
        const departDateDropdown = document.getElementById('departDateDropdown');
        if (departDateDropdown) {
            const dropdownBtn = departDateDropdown.querySelector('.dropdown-btn-compact');
            const calendarPopup = departDateDropdown.querySelector('.calendar-popup');
            const hiddenInput = document.getElementById('departDate');
            const valueDisplay = document.getElementById('departDateValue');
            
            if (dropdownBtn && calendarPopup) {
                dropdownBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeAllDropdowns(departDateDropdown);
                    dropdownBtn.classList.toggle('active');
                    calendarPopup.classList.toggle('show');
                    
                    // Initialize calendar if not already done
                    if (calendarPopup.classList.contains('show')) {
                        initDepartureCalendar();
                    }
                });
            }
        }
        
        // Return date dropdown
        const returnDateDropdown = document.getElementById('returnDateDropdown');
        if (returnDateDropdown) {
            const dropdownBtn = returnDateDropdown.querySelector('.dropdown-btn-compact');
            const calendarPopup = returnDateDropdown.querySelector('.calendar-popup');
            const hiddenInput = document.getElementById('returnDate');
            const valueDisplay = document.getElementById('returnDateValue');
            
            if (dropdownBtn && calendarPopup) {
                dropdownBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeAllDropdowns(returnDateDropdown);
                    dropdownBtn.classList.toggle('active');
                    calendarPopup.classList.toggle('show');
                    
                    // Initialize calendar if not already done
                    if (calendarPopup.classList.contains('show')) {
                        initReturnCalendar();
                    }
                });
            }
        }
        
        // Passengers dropdown
        const passengersDropdown = document.getElementById('passengersDropdown');
        if (passengersDropdown) {
            const dropdownBtn = passengersDropdown.querySelector('.dropdown-btn-compact');
            const passengersPopup = passengersDropdown.querySelector('.passengers-popup');
            const hiddenInput = document.getElementById('passengers');
            const valueDisplay = document.getElementById('passengersValue');
            
            if (dropdownBtn && passengersPopup) {
                dropdownBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeAllDropdowns(passengersDropdown);
                    dropdownBtn.classList.toggle('active');
                    passengersPopup.classList.toggle('show');
                });
                
                // Handle passenger counter buttons
                const counterBtns = passengersPopup.querySelectorAll('.counter-btn');
                counterBtns.forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const type = btn.dataset.type;
                        const isPlus = btn.classList.contains('plus');
                        const countEl = document.getElementById(`${type}Count`);
                        let count = parseInt(countEl.textContent);
                        
                        // Calculate current total before change
                        const adults = parseInt(document.getElementById('adultCount').textContent);
                        const children = parseInt(document.getElementById('childCount').textContent);
                        const infants = parseInt(document.getElementById('infantCount').textContent);
                        const currentTotal = adults + children + infants;
                        
                        if (isPlus) {
                            // Check maximum passengers (9 total)
                            if (currentTotal >= 9) {
                                showPassengerValidation('Maximum 9 passengers allowed per booking', 'error');
                                return;
                            }
                            count++;
                        } else if (count > 0) {
                            // Check if this would make total zero
                            if (currentTotal - 1 <= 0) {
                                showPassengerValidation('At least 1 passenger is required', 'error');
                                return;
                            }
                            count--;
                        }
                        
                        // Clear validation message if valid
                        hidePassengerValidation();
                        
                        // Update count display
                        countEl.textContent = count;
                        
                        // Update dropdown value display
                        updatePassengersDisplay();
                        
                        // Update hidden input
                        if (hiddenInput) {
                            const adults = document.getElementById('adultCount').textContent;
                            const children = document.getElementById('childCount').textContent;
                            const infants = document.getElementById('infantCount').textContent;
                            hiddenInput.value = `${adults}-${children}-${infants}`;
                        }
                    });
                });
            }
        }
        
        // Class dropdown
        const classDropdown = document.getElementById('classDropdown');
        if (classDropdown) {
            const dropdownBtn = classDropdown.querySelector('.dropdown-btn-compact');
            const dropdownMenu = classDropdown.querySelector('.dropdown-menu-compact');
            const hiddenInput = document.getElementById('cabinClass');
            const valueDisplay = dropdownBtn.querySelector('.dropdown-value');
            
            if (dropdownBtn && dropdownMenu) {
                dropdownBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    closeAllDropdowns(classDropdown);
                    dropdownBtn.classList.toggle('active');
                    dropdownMenu.classList.toggle('show');
                });
                
                // Handle option selection
                const options = dropdownMenu.querySelectorAll('li');
                options.forEach(option => {
                    option.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const value = option.dataset.value;
                        const display = option.textContent;
                        
                        valueDisplay.textContent = display;
                        if (hiddenInput) hiddenInput.value = value;
                        
                        dropdownBtn.classList.remove('active');
                        dropdownMenu.classList.remove('show');
                    });
                });
            }
        }
    }
    
    // Close all dropdowns except the one specified
    function closeAllDropdowns(exceptDropdown) {
        const allDropdowns = document.querySelectorAll('.dropdown-compact');
        allDropdowns.forEach(dropdown => {
            if (dropdown !== exceptDropdown) {
                const btn = dropdown.querySelector('.dropdown-btn-compact');
                const menu = dropdown.querySelector('.dropdown-menu-compact, .calendar-popup, .passengers-popup');
                
                if (btn) btn.classList.remove('active');
                if (menu) menu.classList.remove('show');
            }
        });
    }
    
    // Show passenger validation message
    function showPassengerValidation(message, type = 'error') {
        const validationMsg = document.getElementById('passengerValidationMessage');
        if (validationMsg) {
            validationMsg.textContent = message;
            validationMsg.style.display = 'block';
            if (type === 'error') {
                validationMsg.style.background = '#fee';
                validationMsg.style.color = '#c33';
                validationMsg.style.border = '1px solid #fcc';
            } else {
                validationMsg.style.background = '#efe';
                validationMsg.style.color = '#3c3';
                validationMsg.style.border = '1px solid #cfc';
            }
        }
    }
    
    // Hide passenger validation message
    function hidePassengerValidation() {
        const validationMsg = document.getElementById('passengerValidationMessage');
        if (validationMsg) {
            validationMsg.style.display = 'none';
        }
    }
    
    // Update passengers display text
    function updatePassengersDisplay() {
        const adults = document.getElementById('adultCount').textContent;
        const children = document.getElementById('childCount').textContent;
        const infants = document.getElementById('infantCount').textContent;
        const valueDisplay = document.getElementById('passengersValue');
        
        let display = '';
        const totalPassengers = parseInt(adults) + parseInt(children) + parseInt(infants);
        
        // Validation: Ensure at least 1 passenger
        if (totalPassengers <= 0) {
            valueDisplay.textContent = 'Select passengers';
            valueDisplay.style.color = '#e74c3c';
            showPassengerValidation('At least 1 passenger is required', 'error');
            return;
        }
        
        // Validation: Ensure maximum 9 passengers
        if (totalPassengers > 9) {
            valueDisplay.textContent = 'Too many passengers';
            valueDisplay.style.color = '#e74c3c';
            showPassengerValidation('Maximum 9 passengers allowed per booking', 'error');
            return;
        }
        
        valueDisplay.style.color = '#1f2937';
        hidePassengerValidation();
        
        if (totalPassengers === 1) {
            display = '1 Adult';
        } else {
            const parts = [];
            if (parseInt(adults) > 0) parts.push(`${adults} Adult${parseInt(adults) > 1 ? 's' : ''}`);
            if (parseInt(children) > 0) parts.push(`${children} Child${parseInt(children) > 1 ? 'ren' : ''}`);
            if (parseInt(infants) > 0) parts.push(`${infants} Infant${parseInt(infants) > 1 ? 's' : ''}`);
            display = parts.join(', ');
        }
        
        if (valueDisplay) valueDisplay.textContent = display;
    }
    
    // Update return date visibility based on trip type
    function updateReturnDateVisibility(tripType) {
        const returnDateField = document.getElementById('returnDateField');
        if (returnDateField) {
            if (tripType === 'oneway') {
                returnDateField.style.display = 'none';
            } else {
                returnDateField.style.display = 'flex';
            }
        }
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.dropdown-compact')) {
            closeAllDropdowns(null);
        }
    });
    
    // Validate booking form before submission
    function validateBookingForm(form) {
        const origin = document.getElementById('origin')?.value;
        const destination = document.getElementById('destination')?.value;
        const departDate = document.getElementById('departDate')?.value;
        const passengers = document.getElementById('passengers')?.value;
        const tripType = document.getElementById('tripType')?.value;
        
        let errors = [];
        
        // Validate origin
        if (!origin || origin === '') {
            errors.push('Please select departure airport');
        }
        
        // Validate destination
        if (!destination || destination === '') {
            errors.push('Please select destination airport');
        }
        
        // Validate route (origin != destination)
        if (origin && destination && origin === destination) {
            errors.push('Departure and destination airports cannot be the same');
        }
        
        // Validate departure date
        if (!departDate || departDate === '') {
            errors.push('Please select departure date');
        }
        
        // Validate return date for round-trip
        if (tripType === 'roundtrip') {
            const returnDate = document.getElementById('returnDate')?.value;
            if (!returnDate || returnDate === '') {
                errors.push('Please select return date');
            }
        }
        
        // Validate passengers
        if (!passengers || passengers === '') {
            errors.push('Please select number of passengers');
        } else {
            const [adults, children, infants] = passengers.split('-').map(Number);
            const total = adults + children + infants;
            
            if (total <= 0) {
                errors.push('At least 1 passenger is required');
            }
            
            if (total > 9) {
                errors.push('Maximum 9 passengers allowed per booking');
            }
            
            // Validate that adults accompany children/infants
            if ((children > 0 || infants > 0) && adults === 0) {
                errors.push('At least 1 adult must accompany children or infants');
            }
        }
        
        return errors;
    }
    
    // Add form submission validation
    const bookingForm = document.querySelector('.booking-form-compact');
    if (bookingForm) {
        bookingForm.addEventListener('submit', (e) => {
            const errors = validateBookingForm(bookingForm);
            
            if (errors.length > 0) {
                e.preventDefault();
                alert('Please fix the following errors:\n\n' + errors.join('\n'));
                return false;
            }
            
            // If validation passes, allow form submission
            return true;
        });
    }
    
    // Initialize booking widget dropdowns
    console.log('Initializing booking widget dropdowns...');
    initBookingWidgetDropdowns();
    
    // Load airports and populate dropdowns
    loadAirportsData();
    
    // Function to load airports from JSON and populate dropdowns
    async function loadAirportsData() {
        try {
            const response = await fetch('/assets/data/airports.json');
            if (!response.ok) throw new Error('Failed to load airports');
            const airports = await response.json();
            
            console.log('Loaded airports:', airports.length);
            
            // Populate from and to dropdowns
            populateAirportDropdown('fromDropdown', 'fromAirport', airports);
            populateAirportDropdown('toDropdown', 'toAirport', airports);
            
        } catch (error) {
            console.error('Error loading airports:', error);
            // Fallback to hardcoded airports
            const fallbackAirports = [
                { code: 'NBO', name: 'Jomo Kenyatta International Airport', city: 'Nairobi', country: 'Kenya' },
                { code: 'MBA', name: 'Moi International Airport', city: 'Mombasa', country: 'Kenya' },
                { code: 'LHR', name: 'Heathrow Airport', city: 'London', country: 'United Kingdom' },
                { code: 'JFK', name: 'John F. Kennedy International Airport', city: 'New York', country: 'USA' },
                { code: 'DXB', name: 'Dubai International', city: 'Dubai', country: 'UAE' },
                { code: 'JNB', name: 'O.R. Tambo International Airport', city: 'Johannesburg', country: 'South Africa' },
                { code: 'CDG', name: 'Charles de Gaulle Airport', city: 'Paris', country: 'France' },
                { code: 'AMS', name: 'Amsterdam Schiphol', city: 'Amsterdam', country: 'Netherlands' }
            ];
            
            populateAirportDropdown('fromDropdown', 'fromAirport', fallbackAirports);
            populateAirportDropdown('toDropdown', 'toAirport', fallbackAirports);
        }
    }
    
    function populateAirportDropdown(dropdownId, hiddenInputId, airports) {
        const dropdown = document.getElementById(dropdownId);
        if (!dropdown) return;
        
        const menu = dropdown.querySelector('.dropdown-menu-compact');
        if (!menu) return;
        
        // Clear existing options
        menu.innerHTML = '';
        
        // Group airports by city
        const airportsByCity = {};
        airports.forEach(airport => {
            if (!airportsByCity[airport.city]) {
                airportsByCity[airport.city] = [];
            }
            airportsByCity[airport.city].push(airport);
        });
        
        // Sort cities alphabetically
        const sortedCities = Object.keys(airportsByCity).sort();
        
        // Prioritize Kenyan cities first
        const kenyanCities = sortedCities.filter(city => {
            const airport = airportsByCity[city][0];
            return airport.country === 'Kenya';
        });
        const otherCities = sortedCities.filter(city => {
            const airport = airportsByCity[city][0];
            return airport.country !== 'Kenya';
        });
        const prioritizedCities = [...kenyanCities, ...otherCities];
        
        // Create dropdown items
        prioritizedCities.forEach(city => {
            const cityAirports = airportsByCity[city];
            
            if (cityAirports.length === 1) {
                // Single airport in city
                const airport = cityAirports[0];
                const li = document.createElement('li');
                li.dataset.value = airport.code;
                li.dataset.display = `${city} (${airport.code})`;
                li.innerHTML = `
                    <div class="airport-name">${airport.name}</div>
                    <div class="airport-location">
                        <span class="airport-code">${airport.code}</span>
                        <span>${city}, ${airport.country}</span>
                    </div>
                `;
                li.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const valueDisplay = dropdown.querySelector('.dropdown-value');
                    const hiddenInput = document.getElementById(hiddenInputId);
                    const dropdownBtn = dropdown.querySelector('.dropdown-btn-compact');
                    
                    valueDisplay.textContent = `${city} (${airport.code})`;
                    hiddenInput.value = airport.code;
                    
                    dropdownBtn.classList.remove('active');
                    menu.classList.remove('show');
                });
                menu.appendChild(li);
            } else {
                // Multiple airports in city - create city header and sub-items
                const cityHeader = document.createElement('li');
                cityHeader.className = 'city-header';
                cityHeader.innerHTML = `<strong>${city}</strong>`;
                cityHeader.style.background = '#f8f9fa';
                cityHeader.style.fontWeight = '600';
                cityHeader.style.color = '#1e3a8a';
                cityHeader.style.padding = '8px 16px';
                cityHeader.style.cursor = 'default';
                menu.appendChild(cityHeader);
                
                cityAirports.forEach(airport => {
                    const li = document.createElement('li');
                    li.dataset.value = airport.code;
                    li.dataset.display = `${city} (${airport.code})`;
                    li.innerHTML = `
                        <div class="airport-name">${airport.name}</div>
                        <div class="airport-location">
                            <span class="airport-code">${airport.code}</span>
                            <span>${airport.country}</span>
                        </div>
                    `;
                    li.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const valueDisplay = dropdown.querySelector('.dropdown-value');
                        const hiddenInput = document.getElementById(hiddenInputId);
                        const dropdownBtn = dropdown.querySelector('.dropdown-btn-compact');
                        
                        valueDisplay.textContent = `${city} (${airport.code})`;
                        hiddenInput.value = airport.code;
                        
                        dropdownBtn.classList.remove('active');
                        menu.classList.remove('show');
                    });
                    menu.appendChild(li);
                });
            }
        });
    }
    
    // Swap button functionality
    const swapBtn = document.getElementById('swapBtn');
    if (swapBtn) {
        console.log('Setting up swap button...');
        swapBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const fromDropdown = document.getElementById('fromDropdown');
            const toDropdown = document.getElementById('toDropdown');
            const fromAirport = document.getElementById('fromAirport');
            const toAirport = document.getElementById('toAirport');
            
            if (fromDropdown && toDropdown && fromAirport && toAirport) {
                // Swap the values
                const fromValue = fromDropdown.querySelector('.dropdown-value').textContent;
                const toValue = toDropdown.querySelector('.dropdown-value').textContent;
                const fromCode = fromAirport.value;
                const toCode = toAirport.value;
                
                fromDropdown.querySelector('.dropdown-value').textContent = toValue;
                toDropdown.querySelector('.dropdown-value').textContent = fromValue;
                fromAirport.value = toCode;
                toAirport.value = fromCode;
                console.log('Swapped airports:', fromValue, '<->', toValue);
            }
        });
    }
    
    // Header mega-menu: open only on click
    const navItems = Array.from(document.querySelectorAll('.nav-menu .nav-item'));
    navItems.forEach(item => {
        const link = item.querySelector('a');
        if (!link) return;

        link.addEventListener('click', (event) => {
            const isOpen = item.classList.contains('open');
            navItems.forEach(p => p.classList.remove('open'));

            if (!isOpen) {
                event.preventDefault();
                item.classList.add('open');
            }
        });
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('.nav-menu')) {
            navItems.forEach(p => p.classList.remove('open'));
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            navItems.forEach(p => p.classList.remove('open'));
        }
    });

    // Attach airport autocomplete (for different inputs if they exist)
    const fromInput = document.getElementById('fromInput');
    const toInput = document.getElementById('toInput');
    if (fromInput) airportDropdown.attachAutocomplete('fromInput');
    if (toInput) airportDropdown.attachAutocomplete('toInput');
    
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
            
            if (!fromInput || !toInput) {
                // Use the dropdown values instead
                const fromAirport = document.getElementById('fromAirport');
                const toAirport = document.getElementById('toAirport');
                
                if (!fromAirport || !fromAirport.value || !toAirport || !toAirport.value) {
                    alert('Please select both departure and arrival airports');
                    return;
                }
                
                if (!departDate || !departDate.value) {
                    alert('Please select a departure date');
                    return;
                }
                
                if ((tripType && (tripType.value === 'return' || tripType.value === 'roundtrip')) && (!returnDate || !returnDate.value)) {
                    alert('Please select a return date for round trip');
                    return;
                }
                
                // Build query parameters
                const params = new URLSearchParams({
                    from: fromAirport.value,
                    to: toAirport.value,
                    departDate: departDate ? departDate.value : '',
                    tripType: tripType ? tripType.value : 'return'
                });
                
                if (returnDate && returnDate.value) {
                    params.append('returnDate', returnDate.value);
                }
                
                console.log('🔍 Redirecting to availability page with params:', params.toString());
                
                // Redirect to availability page
                window.location.href = `/availability.html?${params.toString()}`;
                return;
            }
            
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
    console.log('Dropdown initialization complete');
});

// Calendar state
let currentMonthOffset = 0;
let selectedDepartDate = null;
let selectedReturnDate = null;

// Get month data with prices
function getCurrentMonthData(monthOffset) {
    const now = new Date();
    const targetDate = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1);
    const year = targetDate.getFullYear();
    const month = targetDate.getMonth();
    const monthName = targetDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    
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

        if (dateObj < today) {
            dayCell.classList.add('disabled');
            dayCell.title = 'Past dates cannot be selected';
        } else {
            dayCell.addEventListener('click', function() {
                selectCalendarDate(dateStr, containerId);
            });
        }

        dayCell.innerHTML = `
            <div class="day-number">${day}</div>
            <div class="day-price">KES ${price.toLocaleString()}</div>
        `;

        container.appendChild(dayCell);
    });
}

// Handle calendar date selection
function selectCalendarDate(dateStr, containerId) {
    const isDeparture = containerId === 'departCalendarGrid';
    const dateInput = isDeparture ? document.getElementById('departDate') : document.getElementById('returnDate');
    const valueDisplay = isDeparture ? document.getElementById('departDateValue') : document.getElementById('returnDateValue');
    const calendarPopup = isDeparture ? document.getElementById('departCalendar') : document.getElementById('returnCalendar');
    const dropdownBtn = isDeparture ? document.getElementById('departDateDropdown').querySelector('.dropdown-btn-compact') : document.getElementById('returnDateDropdown').querySelector('.dropdown-btn-compact');
    
    if (dateInput) {
        dateInput.value = dateStr;
    }
    
    if (valueDisplay) {
        const dateObj = new Date(dateStr);
        const formattedDate = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        valueDisplay.textContent = formattedDate;
    }
    
    if (calendarPopup) {
        calendarPopup.classList.remove('show');
    }
    
    if (dropdownBtn) {
        dropdownBtn.classList.remove('active');
    }
    
    if (isDeparture) {
        const tripType = document.getElementById('tripType');
        if (tripType && tripType.value !== 'oneway') {
            const returnDateField = document.getElementById('returnDateField');
            if (returnDateField && returnDateField.style.display !== 'none') {
                setTimeout(() => {
                    const returnDropdownBtn = document.getElementById('returnDateDropdown').querySelector('.dropdown-btn-compact');
                    if (returnDropdownBtn) returnDropdownBtn.click();
                }, 200);
            }
        }
    }
}

// Calendar initialization functions
function initDepartureCalendar() {
    const calendarGrid = document.getElementById('departCalendarGrid');
    if (!calendarGrid) return;
    
    calendarGrid.innerHTML = '';
    const monthData = getCurrentMonthData(0);
    
    const monthLabel = document.getElementById('departMonthLabel');
    if (monthLabel) monthLabel.textContent = monthData.monthName;
    
    generateCalendar('departCalendarGrid', monthData.prices);
    setupCalendarNavigation('departCalendarGrid', 'departMonthLabel', 0);
}

function initReturnCalendar() {
    const calendarGrid = document.getElementById('returnCalendarGrid');
    if (!calendarGrid) return;
    
    calendarGrid.innerHTML = '';
    const monthData = getCurrentMonthData(1);
    
    const monthLabel = document.getElementById('returnMonthLabel');
    if (monthLabel) monthLabel.textContent = monthData.monthName;
    
    generateCalendar('returnCalendarGrid', monthData.prices);
    setupCalendarNavigation('returnCalendarGrid', 'returnMonthLabel', 1);
}

function setupCalendarNavigation(gridId, labelId, initialOffset) {
    const container = document.getElementById(gridId);
    if (!container) return;
    
    let monthOffset = initialOffset;
    const popup = container.closest('.calendar-popup');
    if (!popup) return;
    
    const navButtons = popup.querySelectorAll('.cal-nav');
    
    navButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            const action = btn.dataset.action;
            if (action === 'prev' && monthOffset > 0) {
                monthOffset--;
            } else if (action === 'next') {
                monthOffset++;
            }
            
            const monthData = getCurrentMonthData(monthOffset);
            const monthLabel = document.getElementById(labelId);
            if (monthLabel) monthLabel.textContent = monthData.monthName;
            
            container.innerHTML = '';
            generateCalendar(gridId, monthData.prices);
        });
    });
}
