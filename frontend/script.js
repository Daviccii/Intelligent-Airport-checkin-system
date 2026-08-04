document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM Content Loaded - Initializing dropdowns...');

    // ========== BOOKING WIDGET DROPDOWN FUNCTIONALITY ==========
    
    // Initialize all dropdowns in the booking widget
    function initBookingWidgetDropdowns() {
        console.log('Setting up dropdowns...');
        
        // Trip type dropdown
        const tripTypeDropdown = document.getElementById('tripTypeDropdown'); // This is the custom dropdown wrapper
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
                        checkBookingFormValidity(); // Re-validate form on trip type change
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
            const dropdownBtn = departDateDropdown.querySelector('.dropdown-btn-compact'); // This is the button that triggers the calendar
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
                        initDepartureCalendar(); // Re-initialize to ensure correct dates are disabled
                    }
                });
            }
        }
        
        // Return date dropdown
        const returnDateDropdown = document.getElementById('returnDateDropdown');
        if (returnDateDropdown) { // This is the button that triggers the calendar
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
                        initReturnCalendar(); // Re-initialize to ensure correct dates are disabled
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
                        const passengerType = btn.dataset.passengerType; // adult, child, infant
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
                                showPassengerValidation('Maximum 9 passengers allowed per booking.', 'error');
                                return;
                            }
                            count++;
                        } else if (count > 0) {
                            // Check if this would make total zero
                            if (currentTotal - 1 <= 0 && passengerType === 'adult') { // Only prevent if removing last adult
                                showPassengerValidation('At least 1 adult is required.', 'error');
                                return;
                            }
                            count--;
                            // If removing an adult, and there are children/infants, ensure at least one adult remains
                            if (passengerType === 'adult' && count === 0 && (children > 0 || infants > 0)) {
                                showPassengerValidation('An adult must accompany children/infants.', 'error');
                                // Revert count change
                                count = 1;
                                countEl.textContent = count;
                                return;
                            }
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
            showPassengerValidation('At least 1 passenger is required.', 'error');
            return;
        }
        
        // Validation: Ensure maximum 9 passengers
        if (totalPassengers > 9) {
            valueDisplay.textContent = 'Too many passengers';
            valueDisplay.style.color = '#e74c3c';
            showPassengerValidation('Maximum 9 passengers allowed per booking.', 'error');
            return;
        }
        // Validation: Ensure at least one adult if children/infants are present
        if ((parseInt(children) > 0 || parseInt(infants) > 0) && parseInt(adults) === 0) {
            valueDisplay.textContent = 'Adult required';
            valueDisplay.style.color = '#e74c3c';
            showPassengerValidation('An adult must accompany children/infants.', 'error');
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
            returnDateField.classList.remove('visible'); // Start with removing visible class
            if (tripType === 'oneway') {
                returnDateField.style.display = 'none';
            } else {
                returnDateField.style.display = 'flex';
                setTimeout(() => returnDateField.classList.add('visible'), 10); // Add visible after display change
            }
        }
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.dropdown-compact')) {
            closeAllDropdowns(null);
        }
    });
    
const flightSearchForm = document.getElementById('flightSearchForm');
if (flightSearchForm) {
    flightSearchForm.addEventListener('submit', (e) => {
        e.preventDefault(); // We navigate manually below instead of letting the browser GET-submit to itself
        
        const submitBtn = flightSearchForm.querySelector('button[type="submit"]');
        if (submitBtn.disabled) {
            console.log('❌ Form submission blocked due to validation errors.');
            const firstError = flightSearchForm.querySelector('.kq-form-group.invalid input');
            if (firstError) firstError.focus();
            return;
        }
        
        const fromCode = document.getElementById('fromAirport')?.value || '';
        const toCode = document.getElementById('toAirport')?.value || '';
        const fromDisplay = document.querySelector('#fromDropdown .dropdown-value')?.textContent.trim() || fromCode;
        const toDisplay = document.querySelector('#toDropdown .dropdown-value')?.textContent.trim() || toCode;
        const departDate = document.getElementById('departDate')?.value || '';
        const returnDate = document.getElementById('returnDate')?.value || '';
        const tripType = document.getElementById('tripType')?.value || 'return';
        const cabinClass = document.getElementById('cabinClass')?.value || 'economy';
        const passengers = document.getElementById('passengers')?.value || '1-0-0';
        
        // Make sure the essentials are actually filled in before sending people to the results page
        const missing = [];
        if (!fromCode) missing.push('departure airport');
        if (!toCode) missing.push('destination airport');
        if (!departDate) missing.push('departure date');
        if (tripType === 'return' && !returnDate) missing.push('return date');
        if (missing.length) {
            let msg = document.getElementById('searchValidationMessage');
            if (!msg) {
                msg = document.createElement('div');
                msg.id = 'searchValidationMessage';
                msg.style.cssText = 'color:#c33;font-size:13px;margin-top:8px;text-align:center;';
                submitBtn.insertAdjacentElement('afterend', msg);
            }
            msg.textContent = `Please select ${missing.join(', ')} before searching.`;
            msg.style.display = 'block';
            return;
        }
        
        // availability.html expects: from, to, departureDate, returnDate, tripType ('roundtrip'|'oneway'), cabin
        const params = new URLSearchParams({
            from: fromDisplay,          // e.g. "Eldoret (EDL)" — availability.html pulls the 3-letter code out of this
            to: toDisplay,
            departureDate: departDate,
            tripType: tripType === 'return' ? 'roundtrip' : tripType,
            cabin: cabinClass,
            passengers: passengers
        });
        if (returnDate) params.set('returnDate', returnDate);
        
        window.location.href = `/availability.html?${params.toString()}`;
    });
}
    
    // Initialize booking widget dropdowns (this will set up passenger counters, trip type, cabin class)
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
                    if (isSameAsOppositeAirport(hiddenInputId, airport.code)) {
                        showAirportValidation(hiddenInputId, city, airport.code);
                        return;
                    }
                    hideAirportValidation();
                    
                    const valueDisplay = dropdown.querySelector('.dropdown-value');
                    const hiddenInput = document.getElementById(hiddenInputId);
                    const dropdownBtn = dropdown.querySelector('.dropdown-btn-compact');
                    
                    valueDisplay.textContent = `${city} (${airport.code})`;
                    hiddenInput.value = airport.code;
                    
                    dropdownBtn.classList.remove('active');
                    menu.classList.remove('show');
                    
                    updateAirportOptionAvailability();
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
                        if (isSameAsOppositeAirport(hiddenInputId, airport.code)) {
                            showAirportValidation(hiddenInputId, city, airport.code);
                            return;
                        }
                        hideAirportValidation();
                        
                        const valueDisplay = dropdown.querySelector('.dropdown-value');
                        const hiddenInput = document.getElementById(hiddenInputId);
                        const dropdownBtn = dropdown.querySelector('.dropdown-btn-compact');
                        
                        valueDisplay.textContent = `${city} (${airport.code})`;
                        hiddenInput.value = airport.code;
                        
                        dropdownBtn.classList.remove('active');
                        menu.classList.remove('show');
                        
                        updateAirportOptionAvailability();
                    });
                    menu.appendChild(li);
                });
            }
        });
        
        // Reflect current selections (e.g. after a re-populate) in this freshly-built menu
        updateAirportOptionAvailability();
    }
    
    // Returns true if `code` is already selected in the *other* airport dropdown
    function isSameAsOppositeAirport(hiddenInputId, code) {
        const oppositeInputId = hiddenInputId === 'fromAirport' ? 'toAirport' : 'fromAirport';
        const oppositeInput = document.getElementById(oppositeInputId);
        return !!(oppositeInput && oppositeInput.value && oppositeInput.value === code);
    }
    
    // Grey out / disable whichever option in each dropdown matches the other dropdown's current selection
    function updateAirportOptionAvailability() {
        const fromAirport = document.getElementById('fromAirport');
        const toAirport = document.getElementById('toAirport');
        const fromMenu = document.querySelector('#fromDropdown .dropdown-menu-compact');
        const toMenu = document.querySelector('#toDropdown .dropdown-menu-compact');
        if (!fromAirport || !toAirport || !fromMenu || !toMenu) return;
        
        fromMenu.querySelectorAll('li[data-value]').forEach(li => {
            const isTaken = !!(toAirport.value && li.dataset.value === toAirport.value);
            li.classList.toggle('option-disabled', isTaken);
            li.style.opacity = isTaken ? '0.4' : '';
            li.style.pointerEvents = isTaken ? 'none' : '';
            li.title = isTaken ? 'Already selected as your destination' : '';
        });
        
        toMenu.querySelectorAll('li[data-value]').forEach(li => {
            const isTaken = !!(fromAirport.value && li.dataset.value === fromAirport.value);
            li.classList.toggle('option-disabled', isTaken);
            li.style.opacity = isTaken ? '0.4' : '';
            li.style.pointerEvents = isTaken ? 'none' : '';
            li.title = isTaken ? 'Already selected as your departure' : '';
        });

        // Reveal the Departure/Return date fields once both airports are set
        // (defined in index.html; guarded here so script.js never breaks if
        // that hook isn't present on some other page reusing this file).
        if (typeof syncDateFieldsVisibility === 'function') {
            syncDateFieldsVisibility();
        }
    }
    
    // Show an inline message near the From/To fields when someone tries to pick a duplicate
    function showAirportValidation(hiddenInputId, city, code) {
        const otherLabel = hiddenInputId === 'fromAirport' ? 'destination' : 'departure';
        let msg = document.getElementById('airportValidationMessage');
        if (!msg) {
            const row = document.getElementById('fromDropdown')?.closest('.form-row-compact');
            if (!row || !row.parentNode) return;
            msg = document.createElement('div');
            msg.id = 'airportValidationMessage';
            msg.style.cssText = 'color:#c33;font-size:13px;margin-top:8px;';
            row.parentNode.insertBefore(msg, row.nextSibling);
        }
        msg.textContent = `${city} (${code}) is already your ${otherLabel} — please choose a different airport.`;
        msg.style.display = 'block';
    }
    
    function hideAirportValidation() {
        const msg = document.getElementById('airportValidationMessage');
        if (msg) msg.style.display = 'none';
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
                
                updateAirportOptionAvailability();
                hideAirportValidation();
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

    console.log('Dropdown initialization complete');
});

// Calendar state
let currentMonthOffset = 0;
let selectedDepartDate = null;
let selectedReturnDate = null; // Not directly used, but kept for consistency

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
function generateCalendar(containerId, prices, currentMonthOffset) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const dates = Object.keys(prices).sort();
    if (dates.length === 0) return;
    
    const minPrice = Math.min(...Object.values(prices));
    const today = new Date();
    const departDateInput = document.getElementById('departDate');
    today.setHours(0,0,0,0);

    const isReturnCalendar = containerId === 'returnCalendarGrid';
    const departDateVal = document.getElementById('departDate')?.value;

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

        // Requirement 4: Prevent users from selecting invalid dates.
        // Departure cannot be before today. // Return cannot be before departure.
        let isBeforeDeparture = false;
        if (isReturnCalendar && departDateInput && departDateInput.value) {
            const dDate = new Date(departDateInput.value);
            dDate.setHours(0,0,0,0);
            isBeforeDeparture = dateObj < dDate;
        }
        if (dateObj < today || isBeforeDeparture || (currentMonthOffset < 0 && !isReturnCalendar)) { // Also disable past months for departure
            dayCell.classList.add('disabled');
            dayCell.title = isBeforeDeparture 
                ? 'Return date cannot be before departure date' 
                : 'Past dates cannot be selected';
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
    const departInput = document.getElementById('departDate');
    const returnInput = document.getElementById('returnDate');

    // Requirement 4: Prevent selecting a return date prior to departure date
    if (!isDeparture && departInput && departInput.value) {
        const dDate = new Date(departInput.value);
        const rDate = new Date(dateStr);
        dDate.setHours(0,0,0,0);
        rDate.setHours(0,0,0,0);
        if (rDate < dDate) {
            return; // Do not select, the UI already disables it.
        }
    }

    const dateInput = isDeparture ? departInput : returnInput;
    const valueDisplay = isDeparture ? document.getElementById('departDateValue') : document.getElementById('returnDateValue');
    const calendarPopup = isDeparture ? document.getElementById('departCalendar') : document.getElementById('returnCalendar');
    const dropdownBtn = isDeparture ? document.getElementById('departDateDropdown')?.querySelector('.dropdown-btn-compact') : document.getElementById('returnDateDropdown')?.querySelector('.dropdown-btn-compact');
    
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
            initReturnCalendar(); // Requirement 4: Update the return date minimum automatically
            const returnDateField = document.getElementById('returnDateField');
            if (returnDateField && returnDateField.style.display !== 'none') {
                setTimeout(() => {
                    const returnDropdownBtn = document.getElementById('returnDateDropdown')?.querySelector('.dropdown-btn-compact');
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
    
    generateCalendar('departCalendarGrid', monthData.prices, 0);
    setupCalendarNavigation('departCalendarGrid', 'departMonthLabel', 0);
}

function initReturnCalendar() {
    const calendarGrid = document.getElementById('returnCalendarGrid');
    if (!calendarGrid) return;
    
    calendarGrid.innerHTML = '';
    const monthData = getCurrentMonthData(1);
    
    const monthLabel = document.getElementById('returnMonthLabel');
    if (monthLabel) monthLabel.textContent = monthData.monthName;
    
    generateCalendar('returnCalendarGrid', monthData.prices, 1);
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
        // The calendar re-initializes (and calls setupCalendarNavigation again)
        // every time the popup is opened, but these buttons are never removed
        // from the DOM. Without this, each reopen stacks another listener on
        // top of the old ones, so a single click fires multiple times and the
        // displayed month jumps out of sync with the label. Cloning the node
        // strips any previously-bound listeners before we attach a fresh one.
        const freshBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(freshBtn, btn);
        
        freshBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            const action = freshBtn.dataset.action;
            if (action === 'prev' && monthOffset > 0) {
                monthOffset--;
            } else if (action === 'next') {
                monthOffset++;
            }
            
            const monthData = getCurrentMonthData(monthOffset);
            const monthLabel = document.getElementById(labelId);
            if (monthLabel) monthLabel.textContent = monthData.monthName;
            
            container.innerHTML = '';
            generateCalendar(gridId, monthData.prices, monthOffset);
        });
    });
}