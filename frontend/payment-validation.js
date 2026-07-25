document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('payment-form');
    if (!form) return;

    // Luhn Algorithm for card number validation
    const luhnCheck = (val) => {
        let sum = 0;
        let shouldDouble = false;
        for (let i = val.length - 1; i >= 0; i--) {
            let digit = parseInt(val.charAt(i));
            if (shouldDouble) {
                if ((digit *= 2) > 9) digit -= 9;
            }
            sum += digit;
            shouldDouble = !shouldDouble;
        }
        return (sum % 10) === 0;
    };

    const paymentValidators = {
        'card-holder': (val) => {
            const v = val.trim();
            if (v === '') return 'Card holder name is required.';
            if (!/^[a-zA-Z\s\-'.]{2,100}$/.test(v)) return 'Please enter a valid name.';
            return true;
        },
        'card-number': (val) => {
            const v = val.replace(/[\s-]/g, '');
            if (v === '') return 'Card number is required.';
            if (!/^\d{13,19}$/.test(v)) return 'Card number must be 13-19 digits.';
            if (!luhnCheck(v)) return 'Invalid card number.';
            return true;
        },
        'card-expiry': (val) => {
            const v = val.trim();
            if (v === '') return 'Expiry date is required.';
            if (!/^(0[1-9]|1[0-2])\s?\/\s?\d{2}$/.test(v)) return 'Invalid format. Use MM/YY.';
            
            const [month, year] = v.split('/').map(s => parseInt(s.trim(), 10));
            const expiryDate = new Date(`20${year}`, month, 1); // Check against the first day of the next month
            const now = new Date();
            const currentDate = new Date(now.getFullYear(), now.getMonth(), 1);

            if (expiryDate <= currentDate) return 'Card has expired.';
            return true;
        },
        'card-cvv': (val) => {
            const v = val.trim();
            if (v === '') return 'CVV is required.';
            if (!/^\d{3,4}$/.test(v)) return 'CVV must be 3 or 4 digits.';
            return true;
        },
        'mpesa-phone': (val) => {
            const v = val.trim().replace(/\s+/g, '');
            if (v === '') return 'MPESA phone number is required.';
            if (!/^(?:\+254|254|0)?(7\d{8})$/.test(v)) return 'Enter a valid Kenyan phone number.';
            return true;
        }
    };

    const fieldsToValidate = {
        'card-holder': { validator: paymentValidators['card-holder'], paymentMethod: 'card' },
        'card-number': { validator: paymentValidators['card-number'], paymentMethod: 'card' },
        'card-expiry': { validator: paymentValidators['card-expiry'], paymentMethod: 'card' },
        'card-cvv': { validator: paymentValidators['card-cvv'], paymentMethod: 'card' },
        'mpesa-phone': { validator: paymentValidators['mpesa-phone'], paymentMethod: 'mpesa' }
    };

    function validateField(field) {
        const { input, group, validator } = field;
        const result = validator(input.value);
        const errorEl = group.querySelector('.invalid-feedback');

        if (result !== true) {
            group.classList.add('invalid');
            if (errorEl) errorEl.textContent = result;
            return false;
        } else {
            group.classList.remove('invalid');
            if (errorEl) errorEl.textContent = '';
            return true;
        }
    }

    function checkPaymentFormValidity() {
        const submitBtn = form.querySelector('button[type="submit"]');
        const selectedMethod = form.querySelector('input[name="paymentMethod"]:checked')?.value;
        let isFormValid = true;

        if (!selectedMethod) {
            isFormValid = false;
        } else {
            for (const id in fieldsToValidate) {
                const field = fieldsToValidate[id];
                // Only validate fields for the selected payment method
                if (field.paymentMethod === selectedMethod) {
                    if (!validateField(field)) {
                        isFormValid = false;
                    }
                } else {
                    // Clear errors from other payment method fields
                    field.group.classList.remove('invalid');
                    const errorEl = field.group.querySelector('.invalid-feedback');
                    if (errorEl) errorEl.textContent = '';
                }
            }
        }

        submitBtn.disabled = !isFormValid;
        console.log('Payment form validity:', { isValid: isFormValid, method: selectedMethod });
        return isFormValid;
    }

    // Initialize fields and attach listeners
    for (const id in fieldsToValidate) {
        const field = fieldsToValidate[id];
        field.input = document.getElementById(id);
        field.group = field.input.closest('.form-group');

        if (field.input && field.group) {
            if (!field.group.querySelector('.invalid-feedback')) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback';
                field.group.appendChild(errorDiv);
            }
            field.input.addEventListener('input', checkPaymentFormValidity);
        }
    }

    // Listen for changes in payment method selection
    form.querySelectorAll('input[name="paymentMethod"]').forEach(radio => {
        radio.addEventListener('change', checkPaymentFormValidity);
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        if (checkPaymentFormValidity()) {
            console.log('✅ Payment form is valid. Processing payment...');
            // Add payment processing logic here
            alert('Payment processing simulation...');
            window.location.href = 'booking-confirm.html';
        } else {
            console.log('❌ Payment form is invalid. Submission blocked.');
            const firstInvalid = form.querySelector('.form-group.invalid input');
            if (firstInvalid) {
                firstInvalid.focus();
            }
        }
    });

    // Initial check
    checkPaymentFormValidity();
});