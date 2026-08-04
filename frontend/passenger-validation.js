function fmtKES(v) {
    try { return 'KES ' + Math.round(Number(v)).toLocaleString(); } catch (e) { return 'KES ' + v; }
}

// Recomputes the fare shown on the submit button. Cabin class was already chosen and
// priced on availability.html — incoming.price is the real, route-and-class-aware
// per-person fare for that choice, so this just applies passenger count and taxes.
// It must NOT re-multiply by a class factor: the cabin-class field on this page is a
// locked, read-only reflection of that earlier choice, not a second pricing input.
function updateFare() {
    const fareDisplay = document.getElementById('fare-display');
    if (!fareDisplay) return;

    const incoming = window.__incomingBooking || {};

    // No incoming flight context (e.g. someone landed here directly) — flat estimate
    const baseFarePerPerson = incoming.price > 0 ? incoming.price : 14850;

    const totalPassengers = incoming.totalPassengers || 1;
    const baseFare = baseFarePerPerson * totalPassengers;
    const taxes = Math.round(baseFare * 0.15);
    const total = Math.round(baseFare + taxes);

    fareDisplay.textContent = fmtKES(total);
    fareDisplay.dataset.total = total;
}

// Best-effort plausibility check, not true verification — client-side JS can never
// confirm a name or document is genuine, only that it's *shaped* like a real one.
// Flags strings with an unusually long run of consonants (a strong signal of
// keyboard-mashed input like "utghbikhuj") — occasional real names may be caught
// by this (e.g. some German/Polish surnames), it's a tradeoff, not a hard rule.
function hasExcessiveConsonantRun(str, maxRun) {
    const cleaned = str.replace(/[^a-zA-Z]/g, '').toLowerCase();
    let run = 0;
    for (const ch of cleaned) {
        if ('aeiou'.includes(ch)) {
            run = 0;
        } else {
            run++;
            if (run > maxRun) return true;
        }
    }
    return false;
}

// Reusable validation functions that return an error message string or `true` if valid.
const validators = {
    name: (val) => {
        const v = val.trim();
        if (v === '') return 'This field is required.';
        if (!/^[a-zA-Z\s'-]{2,50}$/.test(v)) return 'Enter a valid name (2-50 letters).';
        return true;
    },
    optionalName: (val) => {
        const v = val.trim();
        if (v !== '' && !/^[a-zA-Z\s'-]{1,50}$/.test(v)) return 'Enter a valid name (1-50 letters).';
        return true;
    },
    email: (val) => {
        const v = val.trim();
        if (v === '') return 'Email is required.';
        if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(v)) return 'Please enter a valid email address.';
        return true;
    },
    kenyanPhone: (val) => {
        const v = val.trim().replace(/\s+/g, '');
        if (v === '') return 'Phone number is required.';
        if (!/^(?:\+254|254|0)?(7\d{8})$/.test(v)) return 'Enter a valid Kenyan phone number (e.g., 0712345678).';
        return true;
    },
    internationalPhone: (val) => {
        const v = val.trim().replace(/\s+/g, '');
        if (v === '') return 'Contact phone is required.';
        if (!/^\+?[1-9]\d{9,14}$/.test(v)) return 'Enter a valid international phone number.';
        return true;
    },
    passport: (val) => {
        const v = val.trim();
        if (v === '') return 'Passport number is required.';
        if (!/^[A-Z0-9]{6,12}$/i.test(v)) return 'Passport must be 6-12 letters and numbers.';
        return true;
    },
    nationalId: (val) => {
        const v = val.trim();
        if (v !== '' && !/^\d{7,8}$/.test(v)) return 'National ID must be 7-8 digits.';
        return true; // Optional field
    },
    dob: (val) => {
        if (!val) return 'Date of birth is required.';
        const dob = new Date(val);
        const today = new Date();
        dob.setHours(0, 0, 0, 0);
        today.setHours(0, 0, 0, 0);
        if (dob >= today) return 'Date of birth cannot be in the future.';
        const eighteenYearsAgo = new Date(today.getFullYear() - 18, today.getMonth(), today.getDate());
        if (dob > eighteenYearsAgo) return 'Passenger must be at least 18 years old.';
        return true;
    },
    nationality: (val) => {
        const v = val.trim();
        if (v === '') return 'Nationality is required.';
        if (!/^[a-zA-Z\s'-]{2,50}$/.test(v)) return 'Enter a valid nationality (letters only, e.g. Kenyan).';
        return true;
    },
    address: (val) => {
        const v = val.trim();
        if (v === '') return 'Address is required.';
        if (v.length < 8) return 'Please enter your full address (at least 8 characters).';
        if (!/^[a-zA-Z0-9\s,.'#\/-]+$/.test(v)) return 'Address contains characters that aren\'t allowed.';
        // Check each word-like token individually (not the whole string, since real
        // addresses mix house numbers, abbreviations, and place names freely).
        const words = v.split(/[^a-zA-Z]+/).filter(w => w.length >= 4);
        if (words.length === 0) return 'Please enter a real address, not just numbers or symbols.';
        if (words.every(w => hasExcessiveConsonantRun(w, 3))) return 'Please enter a valid address.';
        return true;
    },
    required: (val) => {
        if (!val || val.trim() === '') return 'This field is required.';
        return true;
    }
};

function validateField(field) {
    const { input, group, validator } = field;
    const result = validator(input.value);
    const errorEl = group.querySelector('.error-feedback');

    if (result !== true) {
        group.classList.add('invalid');
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');
        if (errorEl) errorEl.textContent = result;
        return false;
    } else {
        group.classList.remove('invalid');
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
        if (errorEl) errorEl.textContent = '';
        return true;
    }
}

function checkFormValidity(fields) {
    const form = document.getElementById('passenger-form');
    const submitBtn = form.querySelector('button[type="submit"]');
    let isFormValid = true;

    for (const id in fields) {
        if (!validateField(fields[id])) {
            isFormValid = false;
        }
    }

    submitBtn.disabled = !isFormValid;
    return isFormValid;
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('passenger-form');
    if (!form) return;

    // Define all fields to be validated
    const fieldsToValidate = {
        'first-name': { validator: validators.name },
        'middle-name': { validator: validators.optionalName },
        'last-name': { validator: validators.name },
        'gender': { validator: validators.required },
        'dob': { validator: validators.dob },
        'nationality': { validator: validators.nationality },
        'passport': { validator: validators.passport },
        'national-id': { validator: validators.nationalId },
        'emergency-contact-name': { validator: validators.name },
        'emergency-contact-phone': { validator: validators.internationalPhone },
        'email': { validator: validators.email },
        'phone': { validator: validators.kenyanPhone },
        'address': { validator: validators.address }
    };

    // Initialize field elements and attach listeners
    for (const id in fieldsToValidate) {
        const field = fieldsToValidate[id];
        field.input = document.getElementById(id);
        field.group = document.getElementById(`group-${id}`);

        if (field.input && field.group) {
            // .error-feedback already exists in the HTML for every field and is
            // already wired to the .form-group.invalid CSS rule — no need to create one.

            field.input.addEventListener('input', () => {
                validateField(field);
                checkFormValidity(fieldsToValidate); // Check entire form to update button state
            });
        }
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        console.log('Submit button clicked. Checking form validity...');
        const isFormValid = checkFormValidity(fieldsToValidate);

        if (isFormValid) {
            console.log('✅ Form is valid. Saving details and proceeding to payment.');
            savePassengerDetails();
        } else {
            console.log('❌ Form is invalid. Submission blocked.');
            const firstInvalid = document.querySelector('.form-group.invalid');
            if (firstInvalid) {
                firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    });

    // Initial validation check to set button state
    checkFormValidity(fieldsToValidate);
});


function sanitizeInput(str) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return str.replace(/[&<>"']/g, (m) => map[m]);
}

function savePassengerDetails() {
    const incoming = window.__incomingBooking || {};
    const cabinSelect = document.getElementById('cabin-class');
    const fareDisplay = document.getElementById('fare-display');

    const totalPassengers = incoming.totalPassengers || 1;
    // fare-display's dataset.total is set by updateFare() whenever the passenger changes
    // route/cabin; if they never touched those dropdowns, derive it from what availability.html
    // already priced (per-person price × passenger count + 15% taxes).
    const perPersonPrice = incoming.price > 0 ? incoming.price : 3500; // sane KES fallback if landed here directly
    const totalFare = fareDisplay?.dataset.total
        ? Number(fareDisplay.dataset.total)
        : Math.round(perPersonPrice * totalPassengers * 1.15);

    // payment.html reads this exact shape from sessionStorage — it doesn't look at the
    // URL at all, so the object here has to match what it expects field-for-field.
    const bookingSession = {
        selectedFlight: {
            flightNumber: incoming.flight ? (incoming.flight.flight_number || incoming.flight.flight || 'N/A') : 'N/A',
            fareClass: cabinSelect ? cabinSelect.value : 'Economy Comfort',
            price: totalFare
        },
        passengers: [{
            firstName: sanitizeInput(document.getElementById('first-name').value.trim()),
            lastName: sanitizeInput(document.getElementById('last-name').value.trim()),
            email: sanitizeInput(document.getElementById('email').value.trim()),
            phone: sanitizeInput(document.getElementById('phone').value.trim()),
            passportNumber: sanitizeInput(document.getElementById('passport').value.trim())
        }],
        searchParams: {
            origin: incoming.from || '',
            destination: incoming.to || '',
            departure: incoming.departureDate || new Date().toISOString().split('T')[0]
        },
        selectedSeats: [] // seat selection isn't implemented yet — payment.html falls back to "AUTO"
    };

    sessionStorage.setItem('smartflyBookingSession', JSON.stringify(bookingSession));

    // payment.html reads purely from sessionStorage, not the URL
    window.location.href = 'payment.html';
}