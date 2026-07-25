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
    required: (val) => {
        if (!val || val.trim() === '') return 'This field is required.';
        return true;
    }
};

function validateField(field) {
    const { input, group, validator } = field;
    const result = validator(input.value);
    const errorEl = group.querySelector('.invalid-feedback');

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
        'nationality': { validator: validators.required },
        'passport': { validator: validators.passport },
        'national-id': { validator: validators.nationalId },
        'email': { validator: validators.email },
        'phone': { validator: validators.kenyanPhone },
        'emergency-contact-name': { validator: validators.name }
    };

    // Initialize field elements and attach listeners
    for (const id in fieldsToValidate) {
        const field = fieldsToValidate[id];
        field.input = document.getElementById(id);
        field.group = document.getElementById(`group-${id}`);

        if (field.input && field.group) {
            // Add a placeholder for error messages if it doesn't exist
            if (!field.group.querySelector('.invalid-feedback')) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback';
                field.group.appendChild(errorDiv);
            }

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
    const bookingData = {
        pnr: "KQ-" + Math.floor(100000 + Math.random() * 900000),
        passengerName: `${sanitizeInput(document.getElementById('first-name').value.trim())} ${sanitizeInput(document.getElementById('last-name').value.trim())}`,
        email: sanitizeInput(document.getElementById('email').value.trim()),
        phone: sanitizeInput(document.getElementById('phone').value.trim()),
        paymentStatus: "Pending",
        bookingDate: new Date().toISOString()
    };
    localStorage.setItem('smartfly_booking', JSON.stringify(bookingData));
    // Redirect to the next step in the booking process
    window.location.href = 'payment.html';
}